# app/services/tdr/tdr_document_generator.py
# ============================================================
# GÉNÉRATEUR WORD + PDF — Remplit le template ALTIORA
# ============================================================
# Version : V4.0 — Word + PDF (LibreOffice / Word / reportlab)
# ============================================================
# 
# Stratégie de conversion PDF :
#   1. LibreOffice (soffice) — prioritaire, cross-platform
#   2. docx2pdf (Microsoft Word) — fallback Windows
#   3. reportlab — fallback final (toujours disponible)
#
# Le PDF est TOUJOURS généré, quel que soit l'environnement.
# ============================================================

import logging
import os
import re
import shutil
import subprocess
import unicodedata
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)

# ============================================================
# CHEMINS
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = BASE_DIR / "templates" / "tdr" / "template_tdr_formation.docx"
EXPORTS_DIR = BASE_DIR / "exports" / "tdr"

# ============================================================
# CONFIG ALTIORA
# ============================================================
ALTIORA_COORDONNEES = os.getenv(
    "ALTIORA_COORDONNEES",
    "ALTIORA SOLUTIONS — Lot II M 85 Antananarivo — "
    "contact@altiora.mg — +261 34 00 000 00"
)
ALTIORA_RESPONSABLE = os.getenv(
    "ALTIORA_RESPONSABLE",
    "M. RANAIVOSOA Sandamampianina"
)


# ============================================================
# UTILITAIRES — DÉTECTION DES OUTILS DISPONIBLES
# ============================================================

def _libreoffice_available() -> bool:
    """Vérifie si LibreOffice est installé."""
    return (
        shutil.which("soffice") is not None
        or shutil.which("soffice.exe") is not None
    )


def _word_available() -> bool:
    """Vérifie si Microsoft Word est installé."""
    return (
        shutil.which("winword") is not None
        or shutil.which("winword.exe") is not None
        or shutil.which("WINWORD.EXE") is not None
    )


# ============================================================
# UTILITAIRE — SANITIZE FILENAME (accents préservés)
# ============================================================

def _sanitize_filename(name: str, max_len: int = 40) -> str:
    """
    Nettoie un nom pour usage dans un nom de fichier.
    
    ✅ Garde les accents (é, è, à, ô, sns.)
    ✅ Remplace seulement les caractères INTERDITS par Windows
    """
    if not name:
        return "Client"

    # Normaliser en NFC (garde les accents composés)
    name = unicodedata.normalize("NFC", str(name))

    # Remplacer les caractères interdits par Windows
    name = re.sub(r'[\\/:*?"<>|]', "_", name)

    # Remplacer les espaces par underscore
    name = name.replace(" ", "_")

    # Supprimer les caractères de contrôle
    name = "".join(c for c in name if c.isprintable())

    # Nettoyer les underscores multiples
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    return name[:max_len] or "Client"


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class TDRDocumentGenerator:
    """Génère les documents Word + PDF à partir du template ALTIORA."""

    def __init__(self):
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # Détecter les outils disponibles
        self.has_libreoffice = _libreoffice_available()
        self.has_word = _word_available()

        if self.has_libreoffice:
            logger.info("✅ LibreOffice détecté — conversion PDF optimale")
        elif self.has_word:
            logger.info("✅ Microsoft Word détecté — conversion PDF via docx2pdf")
        else:
            logger.warning(
                "⚠️ Ni LibreOffice ni Word détecté — "
                "fallback reportlab sera utilisé pour le PDF"
            )

        if not TEMPLATE_PATH.exists():
            logger.warning(
                "⚠️ Template introuvable : %s — la génération Word échouera",
                TEMPLATE_PATH
            )

    # ============================================================
    # MÉTHODE PRINCIPALE
    # ============================================================

    def generate(
        self,
        tdr_content: Dict[str, Any],
        client: str = "Client",
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Génère le TDR en Word et PDF.
        Retourne (docx_filename, pdf_filename).
        
        ✅ Word : TOUJOURS généré si template existe
        ✅ PDF : TOUJOURS généré (LibreOffice / Word / reportlab)
        """
        # 1. Vérifier que le template existe
        if not TEMPLATE_PATH.exists():
            logger.error("❌ Template introuvable : %s", TEMPLATE_PATH)
            return None, None

        # 2. Préparer le contexte
        try:
            context = self._build_context(tdr_content, client)
        except Exception as exc:
            logger.exception("❌ Erreur build_context : %s", exc)
            return None, None

        # 3. Nom de fichier sécurisé (accents préservés)
        safe_client = _sanitize_filename(client, max_len=40)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"TDR_{safe_client}_{timestamp}"

        docx_filename = f"{base_filename}.docx"
        pdf_filename = f"{base_filename}.pdf"

        docx_path = EXPORTS_DIR / docx_filename
        pdf_path = EXPORTS_DIR / pdf_filename

        # ============================================================
        # 4. GÉNÉRATION WORD
        # ============================================================
        try:
            doc = DocxTemplate(str(TEMPLATE_PATH))
            doc.render(context)
            doc.save(str(docx_path))
            logger.info("✅ Word généré : %s", docx_filename)
        except Exception as exc:
            logger.exception("❌ Erreur génération Word : %s", exc)
            return None, None

        # ============================================================
        # 5. GÉNÉRATION PDF (avec fallback en cascade)
        # ============================================================
        pdf_success = False

        # ---------- Tentative 1 : LibreOffice ----------
        if self.has_libreoffice and not pdf_success:
            try:
                logger.info("🔄 Conversion PDF via LibreOffice...")
                self._convert_via_libreoffice(docx_path, pdf_path)
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    logger.info("✅ PDF généré (LibreOffice) : %s", pdf_filename)
                    pdf_success = True
            except Exception as exc:
                logger.warning("⚠️ LibreOffice échoué : %s", exc)

        # ---------- Tentative 2 : docx2pdf (Word) ----------
        if self.has_word and not pdf_success:
            try:
                logger.info("🔄 Conversion PDF via docx2pdf (Microsoft Word)...")
                self._convert_via_docx2pdf(docx_path, pdf_path)
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    logger.info("✅ PDF généré (docx2pdf) : %s", pdf_filename)
                    pdf_success = True
            except Exception as exc:
                logger.warning("⚠️ docx2pdf échoué : %s", exc)

        # ---------- Tentative 3 : reportlab (fallback) ----------
        if not pdf_success:
            try:
                logger.info("🔄 Fallback : génération PDF via reportlab...")
                self._generate_pdf_reportlab(tdr_content, client, pdf_path)
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    logger.info("✅ PDF généré (reportlab) : %s", pdf_filename)
                    pdf_success = True
            except Exception as exc:
                logger.error("❌ reportlab échoué : %s", exc)

        # ---------- Résultat final ----------
        if not pdf_success:
            logger.error("❌ Impossible de générer le PDF")
            pdf_filename = None

        return docx_filename, pdf_filename

    # ============================================================
    # CONVERSION — LibreOffice
    # ============================================================

    def _convert_via_libreoffice(
        self, docx_path: Path, pdf_path: Path
    ) -> None:
        """Convertit .docx → .pdf via LibreOffice (headless)."""
        for cmd in ["soffice", "soffice.exe"]:
            if shutil.which(cmd) is None:
                continue
            try:
                result = subprocess.run(
                    [
                        cmd, "--headless",
                        "--convert-to", "pdf",
                        "--outdir", str(pdf_path.parent),
                        str(docx_path),
                    ],
                    check=True,
                    timeout=120,
                    capture_output=True,
                )
                if pdf_path.exists():
                    return
            except Exception:
                continue
        raise RuntimeError("LibreOffice n'a pas pu convertir le fichier")

    # ============================================================
    # CONVERSION — docx2pdf (Word)
    # ============================================================

    def _convert_via_docx2pdf(
        self, docx_path: Path, pdf_path: Path
    ) -> None:
        """Convertit .docx → .pdf via docx2pdf (Microsoft Word)."""
        from docx2pdf import convert
        convert(str(docx_path), str(pdf_path))

    # ============================================================
    # CONSTRUCTION DU CONTEXTE
    # ============================================================

    def _build_context(
        self,
        tdr_content: Dict[str, Any],
        client: str,
    ) -> Dict[str, Any]:
        """Construit le contexte pour le template."""

        today = datetime.now()
        reference = f"TDR-FORM-{today.year}-{uuid.uuid4().hex[:4].upper()}"

        public_cible = tdr_content.get("public_cible", "")
        effectif = self._extract_effectif(public_cible)

        # Modules
        programme = (
            tdr_content.get("modules", [])
            or tdr_content.get("programme", [])
        )
        modules = []
        for m in programme:
            modules.append({
                "module": m.get("module", "") or m.get("titre", ""),
                "duree": m.get("duree", ""),
                "contenu": m.get("contenu", ""),
            })

        # Budget
        budget_details = tdr_content.get("budget_details", [])
        budget_lignes = []
        for b in budget_details:
            montant = b.get("montant", 0)
            try:
                montant_str = f"{int(montant):,}".replace(",", " ")
            except (ValueError, TypeError):
                montant_str = str(montant)
            budget_lignes.append({
                "designation": b.get("poste", ""),
                "quantite": b.get("quantite", 1),
                "prix_unitaire": montant_str,
                "total": montant_str,
            })

        budget_total = tdr_content.get("budget_total", 0)
        try:
            budget_total_str = f"{int(budget_total):,} Ar".replace(",", " ")
        except (ValueError, TypeError):
            budget_total_str = str(budget_total)

        date_validite = (today + timedelta(days=30)).strftime("%d/%m/%Y")

        context = {
            # Page de garde
            "titre_formation": tdr_content.get("titre", "Formation professionnelle"),
            "reference_tdr": reference,
            "client_nom": client,
            "client_description": tdr_content.get("client_description", client),
            "date_emission": today.strftime("%d/%m/%Y"),
            "altiora_coordonnees": ALTIORA_COORDONNEES,

            # Section 1
            "contexte": tdr_content.get("contexte", ""),

            # Section 2
            "objectif_general": tdr_content.get("objectif_general", ""),
            "objectifs_specifiques": tdr_content.get("objectifs_specifiques", []),

            # Section 3
            "public_cible": public_cible,
            "effectif_prevu": effectif,
            "prerequis": tdr_content.get("prerequis", []),

            # Section 4
            "duree_totale": tdr_content.get("duree_totale", ""),
            "modules": modules,

            # Section 5
            "formateur_nom": tdr_content.get("formateur_nom", ALTIORA_RESPONSABLE),
            "formateur_profil": tdr_content.get("formateur_profil", ""),
            "modalites_pedagogiques": tdr_content.get("methodologie", ""),
            "moyens_pedagogiques": tdr_content.get("moyens_materiels", []),
            "modalites_evaluation": tdr_content.get("evaluation", ""),
            "livrables": tdr_content.get("livrables", []),

            # Section 6
            "dates_prevues": tdr_content.get("calendrier", ""),
            "lieu": tdr_content.get("lieu", ""),
            "planning_sessions": tdr_content.get("planning_sessions", []),

            # Section 7
            "budget_lignes": budget_lignes,
            "budget_total": budget_total_str,
            "conditions_paiement": tdr_content.get("conditions", ""),

            # Section 8
            "conditions_particulieres": tdr_content.get("conditions_particulieres", ""),
            "date_validite_offre": date_validite,
            "responsable_altiora": ALTIORA_RESPONSABLE,
            "client_signataire": "[À COMPLÉTER]",
        }

        return context

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _extract_effectif(public_text: str) -> int:
        if not public_text:
            return 0
        match = re.search(r"(\d+)", str(public_text))
        return int(match.group(1)) if match else 0

    # ============================================================
    # FALLBACK PDF (reportlab)
    # ============================================================

    def _generate_pdf_reportlab(
        self,
        tdr_content: Dict[str, Any],
        client: str,
        pdf_path: Path,
    ) -> None:
        """Fallback : génère le PDF avec reportlab."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak,
        )

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
        )

        styles = getSampleStyleSheet()

        # Styles personnalisés
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Heading1"],
            fontSize=20,
            textColor=colors.HexColor("#1B2A4A"),
            spaceAfter=20,
            alignment=1,  # Center
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#B8912F"),
            spaceAfter=10,
            alignment=1,
        )
        h1 = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1B2A4A"),
            spaceAfter=12,
            spaceBefore=18,
        )
        h2 = ParagraphStyle(
            "H2",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.HexColor("#B8912F"),
            spaceAfter=8,
            spaceBefore=12,
        )
        body = ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontSize=11,
            leading=16,
            spaceAfter=6,
        )

        story = []

        # ---------- Page de garde ----------
        story.append(Paragraph("ALTIORA SOLUTIONS", title_style))
        story.append(Paragraph(
            "Startup Tech — Antananarivo, Madagascar", subtitle_style
        ))
        story.append(Spacer(1, 2 * cm))

        story.append(Paragraph(
            tdr_content.get("titre", "TERMES DE RÉFÉRENCE"), title_style
        ))
        story.append(Paragraph("Formation professionnelle", subtitle_style))
        story.append(Spacer(1, 1 * cm))

        story.append(Paragraph(f"<b>Client :</b> {client}", body))
        story.append(Paragraph(
            f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y')}", body
        ))
        story.append(Paragraph(
            f"<b>Durée :</b> {tdr_content.get('duree_totale', 'Non précisée')}",
            body
        ))
        story.append(Paragraph(
            f"<b>Lieu :</b> {tdr_content.get('lieu', 'Non précisé')}", body
        ))
        story.append(PageBreak())

        # ---------- Sections ----------
        sections = [
            ("1. Contexte et présentation du client", [
                ("1.1 Contexte de la demande", tdr_content.get("contexte", "")),
                ("1.2 Présentation du client",
                 tdr_content.get("client_description", "")),
            ]),
            ("2. Objectifs de la formation", [
                ("2.1 Objectif général", tdr_content.get("objectif_general", "")),
                ("2.2 Objectifs spécifiques",
                 self._format_list(tdr_content.get("objectifs_specifiques", []))),
            ]),
            ("3. Public cible et prérequis", [
                ("3.1 Public visé", tdr_content.get("public_cible", "")),
                ("3.2 Prérequis",
                 self._format_list(tdr_content.get("prerequis", []))),
            ]),
            ("4. Programme de la formation", [
                ("Programme", self._format_programme(
                    tdr_content.get("modules", [])
                )),
            ]),
            ("5. Intervenant, modalités pédagogiques et évaluation", [
                ("Intervenant", tdr_content.get("formateur_nom", "")),
                ("Profil", tdr_content.get("formateur_profil", "")),
                ("Modalités pédagogiques", tdr_content.get("methodologie", "")),
                ("Moyens et supports", self._format_list(
                    tdr_content.get("moyens_materiels", [])
                )),
                ("Évaluation", tdr_content.get("evaluation", "")),
                ("Livrables", self._format_list(
                    tdr_content.get("livrables", [])
                )),
            ]),
            ("6. Planning et logistique", [
                ("Dates prévues", tdr_content.get("calendrier", "")),
                ("Lieu", tdr_content.get("lieu", "")),
            ]),
            ("7. Budget prévisionnel", [
                ("Détails", self._format_budget(tdr_content)),
                ("Conditions de paiement", tdr_content.get("conditions", "")),
            ]),
            ("8. Conditions générales et validation", [
                ("Conditions particulières",
                 tdr_content.get("conditions_particulieres", "")),
            ]),
        ]

        for section_title, subsections in sections:
            story.append(Paragraph(section_title, h1))
            for sub_title, content in subsections:
                if sub_title:
                    story.append(Paragraph(sub_title, h2))
                story.append(Paragraph(str(content) or "Non précisé", body))
            story.append(Spacer(1, 0.5 * cm))

        doc.build(story)

    # ============================================================
    # FORMAT HELPERS
    # ============================================================

    @staticmethod
    def _format_list(items) -> str:
        if not items:
            return "Non précisé"
        return "<br/>".join(f"• {item}" for item in items)

    @staticmethod
    def _format_programme(programme) -> str:
        if not programme:
            return "Non précisé"
        lines = []
        for m in programme:
            lines.append(
                f"• <b>{m.get('module', '')}</b> ({m.get('duree', '')}) : "
                f"{m.get('contenu', '')}"
            )
        return "<br/>".join(lines)

    @staticmethod
    def _format_budget(tdr_content) -> str:
        details = tdr_content.get("budget_details", [])
        if not details:
            return f"Budget total : {tdr_content.get('budget_total', 0)} Ar"
        lines = [
            f"• {d.get('poste', '')} : {d.get('montant', 0)} Ar"
            for d in details
        ]
        lines.append(
            f"<b>Total : {tdr_content.get('budget_total', 0)} Ar</b>"
        )
        return "<br/>".join(lines)