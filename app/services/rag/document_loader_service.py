# app/services/rag/document_loader_service.py
# ============================================================
# SERVICE — Extraction de texte (PDF, DOCX, PPTX, XLSX, TXT)
# ============================================================
# Retourne des SEGMENTS numérotés (page/diapositive/feuille) plutôt qu'un
# texte plat, pour que chaque chunk puisse garder sa page ou son numéro de
# diapositive (mission C3, Étape C). Limite connue et assumée : DOCX n'a
# pas de pagination native (le texte reflow) — traité comme un segment
# unique (numero=1) ; XLSX : un segment par feuille (numero = ordre 1-based).
# ============================================================

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import filetype
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    """Un segment de texte numéroté (page PDF, diapositive PPTX, feuille XLSX)."""
    numero: int
    texte: str


# ============================================================
# DÉTECTION DU TYPE
# ============================================================

_MIME_TO_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
}

FORMATS_INDEXABLES = ("pdf", "docx", "pptx", "xlsx")
FORMATS_IMAGE = ("jpg", "jpeg", "png")


def detect_file_type(file_path: str) -> str:
    """
    Détecte le type réel du fichier (par signature binaire).

    Returns: "pdf", "docx", "pptx", "xlsx", "txt", "jpg", "png" ou "unknown"
    """
    path = Path(file_path)

    try:
        kind = filetype.guess(file_path)
        if kind and kind.mime in _MIME_TO_TYPE:
            return _MIME_TO_TYPE[kind.mime]
        if kind and kind.mime == "image/jpeg":
            return "jpg"
        if kind and kind.mime == "image/png":
            return "png"
    except Exception as exc:
        logger.warning(f"⚠️ filetype.guess échoué : {exc}")

    ext = path.suffix.lstrip(".").lower()
    if ext in ("pdf", "docx", "pptx", "xlsx", "txt", "md"):
        return "txt" if ext == "md" else ext
    if ext in ("jpg", "jpeg", "png"):
        return ext

    return "unknown"


# ============================================================
# EXTRACTION — Point d'entrée (segments numérotés)
# ============================================================

def extract_segments(file_path: str, file_type: Optional[str] = None) -> List[Segment]:
    """Extrait le contenu d'un fichier sous forme de segments numérotés."""
    if file_type is None:
        file_type = detect_file_type(file_path)

    extracteurs = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "pptx": _extract_pptx,
        "xlsx": _extract_xlsx,
        "txt": _extract_txt,
    }

    extracteur = extracteurs.get(file_type)
    if not extracteur:
        raise ValueError(f"Type de fichier non supporté pour l'extraction : {file_type}")

    logger.info(f"📄 Extraction {file_type} : {Path(file_path).name}")
    return extracteur(file_path)


def extract_text(file_path: str, file_type: Optional[str] = None) -> str:
    """Texte plat (concatène tous les segments) — pratique pour un aperçu
    ou un résumé global, mais perd la numérotation par page/diapositive."""
    segments = extract_segments(file_path, file_type)
    return "\n\n".join(s.texte for s in segments)


# ============================================================
# EXTRACTEURS SPÉCIFIQUES
# ============================================================

def compter_pages_pdf(path: str) -> int:
    """Nombre total de pages d'un PDF (y compris les pages sans texte
    extractible) — utilisé pour pdf_necessite_ocr()."""
    return len(PdfReader(path).pages)


def _extract_pdf(path: str) -> List[Segment]:
    reader = PdfReader(path)
    segments = []
    for numero, page in enumerate(reader.pages, start=1):
        texte = (page.extract_text() or "").strip()
        if texte:
            segments.append(Segment(numero=numero, texte=texte))
    return segments


def _extract_docx(path: str) -> List[Segment]:
    """DOCX : pas de pagination native -> segment unique (numero=1)."""
    doc = Document(path)
    parts = []

    for para in doc.paragraphs:
        texte = para.text.strip()
        if not texte:
            continue
        if para.style.name.startswith("Heading"):
            niveau = para.style.name.replace("Heading ", "")
            parts.append(f"\n{'#' * int(niveau) if niveau.isdigit() else '#'} {texte}\n")
        else:
            parts.append(texte)

    for table in doc.tables:
        parts.append("\n--- Tableau ---")
        for row in table.rows:
            cellules = [cell.text.strip() for cell in row.cells]
            parts.append(" | ".join(cellules))

    texte_complet = "\n".join(parts).strip()
    return [Segment(numero=1, texte=texte_complet)] if texte_complet else []


def _extract_pptx(path: str) -> List[Segment]:
    """PPTX : un segment PAR DIAPOSITIVE (numero = numéro de diapositive),
    pour que le regroupement 3-5 diapositives/chunk (chunking_service) sache
    où couper."""
    prs = Presentation(path)
    segments = []

    for numero, slide in enumerate(prs.slides, start=1):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texte = shape.text_frame.text.strip()
                if texte:
                    parts.append(texte)
        texte_slide = "\n".join(parts).strip()
        if texte_slide:
            segments.append(Segment(numero=numero, texte=texte_slide))

    return segments


def _extract_xlsx(path: str) -> List[Segment]:
    """XLSX : un segment par feuille (numero = ordre 1-based, pas de
    notion de page dans un tableur)."""
    wb = load_workbook(path, data_only=True)
    segments = []

    for numero, sheet_name in enumerate(wb.sheetnames, start=1):
        ws = wb[sheet_name]
        parts = [f"Feuille : {sheet_name}"]

        for row in ws.iter_rows(values_only=True):
            cellules = [str(c) for c in row if c is not None]
            if cellules:
                parts.append(" | ".join(cellules))

        texte_feuille = "\n".join(parts).strip()
        if len(parts) > 1:  # au moins une ligne de données
            segments.append(Segment(numero=numero, texte=texte_feuille))

    return segments


def _extract_txt(path: str) -> List[Segment]:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=encoding) as f:
                texte = f.read()
            return [Segment(numero=1, texte=texte)] if texte.strip() else []
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Impossible de décoder le fichier : {path}")


# ============================================================
# CLASSIFICATION — PDF sans texte, images seules (mission C3 §3)
# ============================================================

CARACTERES_MIN_PAR_PAGE_MOYENNE = 50


def pdf_necessite_ocr(segments: List[Segment], nb_pages_total: int) -> bool:
    """True si le PDF a moins de 50 caractères/page en moyenne (probablement
    scanné, sans couche texte) -> statut 'ocr_necessaire', pas une erreur."""
    if nb_pages_total == 0:
        return True
    total_caracteres = sum(len(s.texte) for s in segments)
    return (total_caracteres / nb_pages_total) < CARACTERES_MIN_PAR_PAGE_MOYENNE
