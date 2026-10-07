# app/services/rh/cv_extractor_service.py
# ============================================================
# SERVICE D'EXTRACTION DE TEXTE — CV (tous formats)
# ============================================================
# Logique par format :
#
#   PDF  → pymupdf4llm + pdfplumber en parallèle
#           → garder le plus long
#           → si < 200 chars : Tesseract OCR (PDF scanné)
#           → si encore < 200 chars : Groq Vision (dernier recours)
#
#   JPG/PNG/image → Tesseract OCR
#                 → si < 200 chars : Groq Vision
#
#   DOCX → python-docx (direct)
#   TXT  → lecture directe
#
# Après extraction : validation LLM ("texte lisible ?")
# → si NON : erreur claire à l'utilisateur
# ============================================================

import asyncio
import base64
import io
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"

SEUIL_TEXTE_MIN = 200
# Vision désactivée — aucun modèle vision disponible sur ce compte Groq
# Activer si un modèle vision est ajouté : ex. gemini-1.5-flash via Google AI
GROQ_VISION_MODEL = ""
EXTENSIONS_IMAGE = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class MethodeExtraction(str, Enum):
    PYMUPDF4LLM = "pymupdf4llm"
    PDFPLUMBER  = "pdfplumber"
    TESSERACT   = "tesseract_ocr"
    GROQ_VISION = "groq_vision"
    DOCX        = "python_docx"
    TEXTE_BRUT  = "texte_brut"
    ECHEC       = "echec"


# =============================================================================
# MÉTHODES INDIVIDUELLES (synchrones — exécutées dans un thread)
# =============================================================================

def _pymupdf4llm(contenu: bytes) -> str:
    """pymupdf4llm : PDF Canva / multi-colonnes → Markdown structuré."""
    try:
        import pymupdf4llm
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contenu)
            tmp_path = tmp.name
        try:
            return pymupdf4llm.to_markdown(tmp_path).strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except ImportError:
        vlog("⚠️ pymupdf4llm non installé", "warning")
        return ""
    except Exception as exc:
        vlog(f"⚠️ pymupdf4llm : {exc}", "warning")
        return ""


def _pdfplumber(contenu: bytes) -> str:
    """pdfplumber : PDF texte sélectionnable classique."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(contenu)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n".join(pages).strip()
    except ImportError:
        vlog("⚠️ pdfplumber non installé", "warning")
        return ""
    except Exception as exc:
        vlog(f"⚠️ pdfplumber : {exc}", "warning")
        return ""


def _tesseract(contenu: bytes, est_pdf: bool = False) -> str:
    """Tesseract OCR : PDF scanné ou image directe."""
    try:
        import pytesseract
        from PIL import Image

        if est_pdf:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(contenu, dpi=200)
        else:
            images = [Image.open(io.BytesIO(contenu))]

        pages = [pytesseract.image_to_string(img, lang="fra+eng") for img in images]
        return "\n".join(pages).strip()
    except ImportError:
        vlog("⚠️ pytesseract/pdf2image non installé", "warning")
        return ""
    except Exception as exc:
        vlog(f"⚠️ Tesseract : {exc}", "warning")
        return ""


def _docx(contenu: bytes) -> str:
    """python-docx : fichier Word .docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(contenu))
        lignes = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(lignes).strip()
    except Exception as exc:
        vlog(f"⚠️ python-docx : {exc}", "warning")
        return ""


def _texte_brut(contenu: bytes) -> str:
    """Lecture directe d'un fichier .txt."""
    for encodage in ("utf-8", "latin-1", "cp1252"):
        try:
            return contenu.decode(encodage).strip()
        except UnicodeDecodeError:
            continue
    return ""


async def _groq_vision(contenu: bytes, est_pdf: bool = False) -> str:
    """Vision LLM : dernier recours pour CV ultra-graphiques (désactivé si GROQ_VISION_MODEL vide)."""
    if not GROQ_VISION_MODEL:
        vlog("⚠️ Vision LLM non configuré — étape ignorée", "warning")
        return ""
    try:
        from PIL import Image

        if est_pdf:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(contenu, dpi=150, first_page=1, last_page=2)
        else:
            images = [Image.open(io.BytesIO(contenu))]

        if not images:
            return ""

        buf = io.BytesIO()
        images[0].save(buf, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
        )
        response = await client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extrais tout le texte visible dans ce CV. "
                            "Conserve la structure : nom, contact, expériences, "
                            "formations, compétences. "
                            "Réponds uniquement avec le texte extrait, sans commentaire."
                        ),
                    },
                ],
            }],
            max_tokens=2000,
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()

    except ImportError:
        vlog("⚠️ pdf2image/PIL non installé — Groq Vision ignorée", "warning")
        return ""
    except Exception as exc:
        vlog(f"⚠️ Groq Vision : {exc}", "warning")
        return ""


# =============================================================================
# VALIDATION LLM — texte lisible ?
# =============================================================================

async def _valider_lisibilite(texte: str) -> bool:
    """Demande au LLM si le texte extrait est un CV exploitable."""
    try:
        from app.services.llm import get_llm_provider

        provider = get_llm_provider()
        prompt = (
            "Voici un texte extrait d'un fichier soumis comme CV :\n\n"
            f"{texte[:1500]}\n\n"
            "Ce texte contient-il des informations exploitables d'un CV "
            "(nom, expérience, compétences, contact) ? "
            "Réponds uniquement par OUI ou NON."
        )
        reponse = await provider.generate(
            system_prompt="Tu es un assistant RH.",
            user_prompt=prompt,
            temperature=0.0,
            max_tokens=10,
        )
        return "OUI" in reponse.upper()
    except Exception as exc:
        vlog(f"⚠️ Validation lisibilité échouée : {exc} — on suppose OUI", "warning")
        return True  # en cas d'erreur, on laisse passer plutôt que de bloquer


# =============================================================================
# EXTRACTEUR PRINCIPAL
# =============================================================================

async def extraire_texte_cv(
    contenu: bytes,
    nom_fichier: str,
) -> Tuple[str, MethodeExtraction, bool]:
    """
    Extrait le texte d'un CV selon son format, en cascade.

    Retourne :
        texte          : texte extrait (str)
        methode        : MethodeExtraction utilisée
        lisible        : True si validé exploitable par le LLM
    """
    extension = Path(nom_fichier).suffix.lower()
    vlog(f"📄 Extraction CV '{nom_fichier}' (ext={extension}, {len(contenu)} bytes)")

    texte = ""
    methode = MethodeExtraction.ECHEC

    # ── TXT ──────────────────────────────────────────────────────────────────
    if extension == ".txt":
        texte = _texte_brut(contenu)
        methode = MethodeExtraction.TEXTE_BRUT if texte else MethodeExtraction.ECHEC

    # ── DOCX ─────────────────────────────────────────────────────────────────
    elif extension in (".docx", ".doc"):
        texte = _docx(contenu)
        methode = MethodeExtraction.DOCX if texte else MethodeExtraction.ECHEC

    # ── IMAGE ─────────────────────────────────────────────────────────────────
    elif extension in EXTENSIONS_IMAGE:
        vlog("🖼️ Image → Tesseract OCR")
        texte = await asyncio.to_thread(_tesseract, contenu, False)

        if len(texte) < SEUIL_TEXTE_MIN:
            vlog("⚠️ Tesseract insuffisant → Groq Vision")
            texte = await _groq_vision(contenu, est_pdf=False)
            methode = MethodeExtraction.GROQ_VISION if len(texte) >= SEUIL_TEXTE_MIN else MethodeExtraction.ECHEC
        else:
            methode = MethodeExtraction.TESSERACT

    # ── PDF ───────────────────────────────────────────────────────────────────
    elif extension == ".pdf":

        # Étape 1 : pymupdf4llm + pdfplumber en parallèle
        vlog("🔍 PDF → pymupdf4llm + pdfplumber en parallèle")
        t1, t2 = await asyncio.gather(
            asyncio.to_thread(_pymupdf4llm, contenu),
            asyncio.to_thread(_pdfplumber, contenu),
        )
        vlog(f"   pymupdf4llm={len(t1)} chars | pdfplumber={len(t2)} chars")

        # Garder le plus long
        if len(t1) >= len(t2):
            texte, methode = t1, MethodeExtraction.PYMUPDF4LLM
        else:
            texte, methode = t2, MethodeExtraction.PDFPLUMBER

        # Étape 2 : PDF scanné → Tesseract
        if len(texte) < SEUIL_TEXTE_MIN:
            vlog("⚠️ PDF semble scanné → Tesseract OCR")
            texte = await asyncio.to_thread(_tesseract, contenu, True)
            methode = MethodeExtraction.TESSERACT

        # Étape 3 : Groq Vision (dernier recours)
        if len(texte) < SEUIL_TEXTE_MIN:
            vlog("⚠️ Tesseract insuffisant → Groq Vision")
            texte = await _groq_vision(contenu, est_pdf=True)
            methode = MethodeExtraction.GROQ_VISION if len(texte) >= SEUIL_TEXTE_MIN else MethodeExtraction.ECHEC

    else:
        vlog(f"⚠️ Format non supporté : {extension}", "warning")
        return f"[Format non supporté : {extension}]", MethodeExtraction.ECHEC, False

    if methode == MethodeExtraction.ECHEC or not texte:
        vlog("❌ Toutes les méthodes ont échoué", "error")
        return "[Extraction échouée — CV illisible]", MethodeExtraction.ECHEC, False

    vlog(f"✅ Extraction via {methode} ({len(texte)} chars) — validation LLM...")

    # Validation finale : le texte est-il exploitable ?
    try:
        lisible = await _valider_lisibilite(texte)
    except Exception as exc:
        vlog(f"⚠️ Validation lisibilité échouée : {exc} — on suppose OUI", "warning")
        lisible = True

    if not lisible:
        vlog("❌ LLM : texte non exploitable", "warning")

    return texte, methode, lisible
