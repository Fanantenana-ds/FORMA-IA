# ============================================================
# GÉNÉRATEUR PDF — TDR (AVEC FORMATAGE PROFESSIONNEL)
# ============================================================

import os
from datetime import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
import logging

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Générateur de documents PDF professionnels pour les TDR"""

    # Couleurs ALTIORA
    COLOR_PRIMARY = colors.HexColor('#003366')
    COLOR_SECONDARY = colors.HexColor('#0066CC')
    COLOR_ACCENT = colors.HexColor('#FFA500')
    COLOR_LIGHT = colors.HexColor('#E6F0FA')

    def __init__(self, output_dir: str = "exports/tdr"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"📁 Stockage PDF: {self.output_dir}")

    def generate(self, tdr_data: Dict[str, Any], brief: Dict[str, Any]) -> str:
        """
        Génère un document PDF professionnel à partir des données du TDR

        Args:
            tdr_data: Données du TDR généré par Groq
            brief: Brief client original

        Returns:
            str: Chemin vers le fichier généré
        """
        try:
            filename = f"TDR_{brief.get('client', 'client').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(self.output_dir, filename)

            # Créer le document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72,
                title=f"TDR - {brief.get('client', 'Client')}",
                author="ALTIORA SOLUTIONS"
            )

            # Styles
            styles = getSampleStyleSheet()

            # Style titre principal
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=20,
                alignment=TA_CENTER,
                spaceAfter=30,
                textColor=self.COLOR_PRIMARY,
                fontName='Helvetica-Bold'
            )

            # Style sous-titre
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=14,
                alignment=TA_CENTER,
                spaceAfter=20,
                textColor=self.COLOR_SECONDARY,
                fontName='Helvetica-Oblique'
            )

            # Style titre de section
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                alignment=TA_LEFT,
                spaceAfter=12,
                textColor=self.COLOR_SECONDARY,
                fontName='Helvetica-Bold'
            )

            # Style corps de texte
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                alignment=TA_LEFT,
                spaceAfter=6,
                fontName='Helvetica'
            )

            # Style liste à puces
            bullet_style = ParagraphStyle(
                'CustomBullet',
                parent=styles['BodyText'],
                fontSize=11,
                alignment=TA_LEFT,
                spaceAfter=4,
                leftIndent=20,
                fontName='Helvetica'
            )

            # Style pour les modules
            module_style = ParagraphStyle(
                'CustomModule',
                parent=styles['BodyText'],
                fontSize=11,
                alignment=TA_LEFT,
                spaceAfter=6,
                textColor=self.COLOR_PRIMARY,
                fontName='Helvetica-Bold'
            )

            # Contenu
            story = []

            # 1. Titre
            title = tdr_data.get("tdr", {}).get("titre", "Termes de Référence")
            story.append(Paragraph(title, title_style))

            # 2. Sous-titre
            story.append(Paragraph("Termes de Référence", subtitle_style))
            story.append(Spacer(1, 0.2 * inch))

            # 3. Ligne de séparation
            story.append(Paragraph("_" * 80, body_style))
            story.append(Spacer(1, 0.2 * inch))

            # 4. Informations de base (Tableau)
            info_data = [
                ["Client", brief.get('client', 'Non précisé')],
                ["Date", datetime.now().strftime('%d/%m/%Y')],
                ["Durée", brief.get('duree', 'Non précisé')],
                ["Format", brief.get('format', 'Non précisé')],
                ["Budget", brief.get('budget', 'Non précisé')]
            ]

            table = Table(info_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), self.COLOR_LIGHT),
                ('TEXTCOLOR', (0, 0), (0, -1), self.COLOR_PRIMARY),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(table)
            story.append(Spacer(1, 0.3 * inch))

            # 5. Sections
            sections = tdr_data.get("tdr", {}).get("sections", {})
            section_titles = {
                "contexte": "1. Contexte et justification",
                "objectifs": "2. Objectifs de la formation",
                "public": "3. Public cible et prérequis",
                "contenu": "4. Contenu et programme détaillé",
                "methodologie": "5. Méthodologie pédagogique",
                "evaluation": "6. Évaluation et suivi",
                "budget": "7. Budget et planning",
                "annexes": "8. Annexes"
            }

            for key, title_text in section_titles.items():
                content = sections.get(key, "À préciser par le client")
                story.append(Paragraph(title_text, heading_style))

                # Traiter le contenu
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                        # Liste à puces
                        clean_line = line.lstrip('-•* ').strip()
                        story.append(Paragraph(f"• {clean_line}", bullet_style))
                    elif line.startswith('Module') or line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                        # Titre de module
                        story.append(Paragraph(line, module_style))
                    elif line.startswith('Annexe'):
                        # Titre d'annexe
                        annexe_style = ParagraphStyle(
                            'CustomAnnexe',
                            parent=body_style,
                            textColor=self.COLOR_ACCENT,
                            fontName='Helvetica-Bold'
                        )
                        story.append(Paragraph(line, annexe_style))
                    else:
                        # Paragraphe normal
                        story.append(Paragraph(line, body_style))

                story.append(Spacer(1, 0.1 * inch))

            # 6. Pied de page
            footer_text = f"ALTIORA SOLUTIONS — Document confidentiel — {datetime.now().year}"
            footer_style = ParagraphStyle(
                'CustomFooter',
                parent=body_style,
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.grey
            )
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(footer_text, footer_style))

            # Générer le PDF
            doc.build(story)

            logger.info(f"✅ PDF généré: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Erreur génération PDF: {e}")
            raise