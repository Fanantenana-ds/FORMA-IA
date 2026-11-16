import io

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from xml.sax.saxutils import escape
from app.services.document_design import apply_docx_branding, draw_pdf_branding

from app.models.document import Document, FormatExport, TypeDocument


class DocumentExportService:
    def exporter(self, document: Document, format: FormatExport) -> tuple[bytes, str, str]:
        """Retourne contenu binaire, nom de fichier, media_type"""
        if format == FormatExport.DOCX:
            return self._exporter_word(document)

        if format == FormatExport.PDF:
            return self._exporter_pdf(document)

        raise ValueError(f"Format d'export non supporté : {format}")


    def _titre_document(self, document: Document) -> str:
        titres = {
            TypeDocument.TDR: "Termes de Références",
            TypeDocument.OFFRE: "Offre Technique et Financière",
            TypeDocument.ATTESTATION: "Attestation de Formation",
        }
        return titres.get(document.type, "Document")


    def _ligne_contenu(self, document: Document) -> list[str]:
        if document.type == TypeDocument.TDR:
            return [
                f"Client : {document.client or '-'}",
                f"Objectifs : {document.objectifs or '-'}",
                f"Budget : {document.montant or '-'}",
            ]

        if document.type == TypeDocument.ATTESTATION:
            return [f"Numéro d'attestation : {document.numero_unique or '-'}"]
        return [document.contenu or ""]


    def _exporter_word(self, document: Document) -> tuple[bytes, str, str]:
        doc = DocxDocument()
        doc.add_heading(self._titre_document(document), level=0)

        for ligne in self._ligne_contenu(document):
            if ": " in ligne:
                label, value = ligne.split(": ", 1)
                p = doc.add_paragraph()
                p.add_run(label + " : ").bold = True
                p.add_run(value)
            else:
                doc.add_paragraph(ligne)

        apply_docx_branding(doc, self._titre_document(document))

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        nom_fichier = f"{document.type.value.lower()}_{document.id}.docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        return buffer.read(), nom_fichier, media_type


    def _exporter_pdf(self, document: Document) -> tuple[bytes, str, str]:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2.6*cm, bottomMargin=1.8*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("BrandTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                                     fontSize=22, leading=27, textColor=colors.HexColor("#11162A"),
                                     spaceAfter=18)
        body_style = ParagraphStyle("BrandBody", parent=styles["BodyText"], fontSize=10,
                                    leading=15, textColor=colors.HexColor("#202938"), spaceAfter=10)
        story = [Paragraph(escape(self._titre_document(document)), title_style)]
        for ligne in self._ligne_contenu(document):
            if ": " in ligne:
                label, value = ligne.split(": ", 1)
                line = f"<b>{escape(label)} :</b> {escape(value)}"
            else:
                line = escape(ligne).replace("\n", "<br/>")
            story.append(Paragraph(line, body_style))
        doc.build(story, onFirstPage=lambda canvas, layout: draw_pdf_branding(canvas, layout, self._titre_document(document)),
                  onLaterPages=lambda canvas, layout: draw_pdf_branding(canvas, layout, self._titre_document(document)))
        buffer.seek(0)

        nom_fichier = f"{document.type.value.lower()}_{document.id}.pdf"

        return buffer.read(), nom_fichier, "application/pdf"


    @staticmethod
    def _decouper_ligne(texte: str, largeur_max: int) -> list[str]:
        mots = texte.split(" ")
        lignes, ligne_courante = [], ""
        for mot in mots:
            if len(ligne_courante) + len(mot) + 1 <= largeur_max:
                ligne_courante = f"{ligne_courante} {mot}".strip()

            else:
                lignes.append(ligne_courante)
                ligne_courante = mot

        if ligne_courante:
            lignes.append(ligne_courante)

        return lignes or [""]
