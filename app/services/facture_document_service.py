"""Generate a professional, downloadable PDF for one invoice."""
from __future__ import annotations

import io
import os
from datetime import date
from xml.sax.saxutils import escape

from app.models.facture import Facture


def _configured(name: str, default: str = "À renseigner") -> str:
    return os.getenv(name, "").strip() or default


def _money(value: float) -> str:
    return f"{value:,.2f}".replace(",", "\u202f").replace(".", ",") + " Ar"


def _date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def generate_invoice_pdf(facture: Facture) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from app.services.document_design import NAVY, TEAL, MUTED, draw_pdf_branding

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm,
        topMargin=2.45 * cm, bottomMargin=1.8 * cm,
        title=f"Facture {facture.numero}", author="ALTIORA PREST",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("InvoiceTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=23,
                           leading=27, textColor=colors.HexColor(f"#{NAVY}"), alignment=TA_LEFT, spaceAfter=4)
    small = ParagraphStyle("InvoiceSmall", parent=styles["BodyText"], fontSize=8.5, leading=12,
                           textColor=colors.HexColor(f"#{MUTED}"))
    body = ParagraphStyle("InvoiceBody", parent=styles["BodyText"], fontSize=9, leading=13,
                          textColor=colors.HexColor("#202938"))
    right = ParagraphStyle("InvoiceRight", parent=small, alignment=TA_RIGHT)
    section_heading = ParagraphStyle("InvoiceSection", parent=styles["Heading3"], fontName="Helvetica-Bold",
                                     fontSize=9, leading=12, textColor=colors.HexColor(f"#{NAVY}"), spaceAfter=5)

    safe = lambda value: escape(str(value or "—")).replace("\n", "<br/>")
    seller = [
        f"<b>{safe(_configured('INVOICE_ISSUER_NAME', 'ALTIORA PREST'))}</b>",
        safe(_configured("INVOICE_ISSUER_ADDRESS")),
        f"SIRET : {safe(_configured('INVOICE_ISSUER_SIRET'))}",
        f"RCS : {safe(_configured('INVOICE_ISSUER_RCS'))}",
        f"TVA intracommunautaire : {safe(_configured('INVOICE_ISSUER_VAT'))}",
        f"{safe(_configured('INVOICE_ISSUER_EMAIL'))} · {safe(_configured('INVOICE_ISSUER_PHONE'))}",
    ]
    client = [
        f"<b>{safe(facture.client)}</b>",
        safe(facture.client_adresse),
        f"SIRET : {safe(facture.client_siret)}",
        f"RCS : {safe(facture.client_rcs)}",
        f"TVA intracommunautaire : {safe(facture.client_tva)}",
    ]
    invoice_meta = [
        [Paragraph("N° FACTURE", small), Paragraph("DATE D’ÉMISSION", small)],
        [Paragraph(f"<b>{safe(facture.numero)}</b>", body), Paragraph(f"<b>{_date(facture.date_emission.date() if facture.date_emission else None)}</b>", body)],
        [Paragraph("ÉCHÉANCE", small), Paragraph("STATUT", small)],
        [Paragraph(f"<b>{_date(facture.date_echeance)}</b>", body), Paragraph(f"<b>{safe(facture.statut.value)}</b>", body)],
    ]
    meta_table = Table(invoice_meta, colWidths=[4.2 * cm, 4.2 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F4F8")),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D9E2E8")),
        ("INNERGRID", (0, 0), (-1, -1), .35, colors.HexColor("#D9E2E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    parties = Table([
        [Paragraph("ÉMETTEUR", section_heading), Paragraph("FACTURÉ À", section_heading)],
        [Paragraph("<br/>".join(seller), body), Paragraph("<br/>".join(client), body)],
    ], colWidths=[8.8 * cm, 8.8 * cm])
    parties.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#D9E2E8")),
        ("LINEBEFORE", (1, 0), (1, -1), .6, colors.HexColor("#D9E2E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    description = facture.session.titre if facture.session else "Prestation de formation professionnelle"
    line_rows = [
        [Paragraph("DÉSIGNATION", small), Paragraph("QTÉ", right), Paragraph("PRIX HT", right), Paragraph("TVA", right), Paragraph("TOTAL TTC", right)],
        [Paragraph(safe(description), body), Paragraph("1", right), Paragraph(_money(facture.montant), right),
         Paragraph(f"{facture.tva_taux:g} %", right), Paragraph(_money(facture.montant_ttc), right)],
    ]
    lines = Table(line_rows, colWidths=[7.7 * cm, 1 * cm, 2.8 * cm, 1.7 * cm, 3.7 * cm], repeatRows=1)
    lines.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{NAVY}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D9E2E8")),
        ("INNERGRID", (0, 0), (-1, -1), .35, colors.HexColor("#D9E2E8")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#FBFCFD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))

    paid = round(sum(payment.montant for payment in facture.paiements), 2)
    remaining = max(0, round(facture.montant_ttc - paid, 2))
    vat = round(facture.montant_ttc - facture.montant, 2)
    totals = Table([
        [Paragraph("Total hors taxes", body), Paragraph(_money(facture.montant), right)],
        [Paragraph(f"TVA ({facture.tva_taux:g} %)", body), Paragraph(_money(vat), right)],
        [Paragraph("TOTAL TTC À RÉGLER", ParagraphStyle("TotalLabel", parent=body, fontName="Helvetica-Bold", textColor=colors.white)),
         Paragraph(f"<b>{_money(facture.montant_ttc)}</b>", ParagraphStyle("TotalValue", parent=right, fontName="Helvetica-Bold", textColor=colors.white))],
        [Paragraph("Paiements reçus", body), Paragraph(_money(paid), right)],
        [Paragraph("SOLDE RESTANT DÛ", ParagraphStyle("BalanceLabel", parent=body, fontName="Helvetica-Bold", textColor=colors.HexColor(f"#{NAVY}"))),
         Paragraph(f"<b>{_money(remaining)}</b>", ParagraphStyle("BalanceValue", parent=right, fontName="Helvetica-Bold", textColor=colors.HexColor(f"#{NAVY}")))],
    ], colWidths=[9.3 * cm, 3.7 * cm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor(f"#{TEAL}")),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#E8F4F0")),
        ("LINEABOVE", (0, 0), (-1, 0), .6, colors.HexColor("#D9E2E8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    terms = [
        f"<b>Date d’échéance :</b> {_date(facture.date_echeance)}",
        f"<b>Pénalités de retard :</b> {safe(_configured('INVOICE_LATE_PENALTY_RATE'))}",
        f"<b>Indemnité forfaitaire pour frais de recouvrement :</b> {safe(_configured('INVOICE_RECOVERY_FEE'))}",
    ]
    payment_section = []
    if facture.paiements:
        payment_rows = [[Paragraph("PAIEMENTS ENREGISTRÉS", small), Paragraph("DATE", right), Paragraph("MODE", right), Paragraph("MONTANT", right)]]
        payment_rows.extend([
            [Paragraph("Règlement", small), Paragraph(_date(payment.date), right), Paragraph(safe(payment.mode or "—"), right), Paragraph(_money(payment.montant), right)]
            for payment in facture.paiements
        ])
        payment_table = Table(payment_rows, colWidths=[7.6 * cm, 3 * cm, 3 * cm, 3.8 * cm], repeatRows=1)
        payment_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F4F8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(f"#{NAVY}")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#D9E2E8")),
            ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#D9E2E8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        payment_section = [Spacer(1, .35 * cm), payment_table]
    story = [
        Table([[Paragraph("FACTURE", title), meta_table]], colWidths=[9 * cm, 8.6 * cm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])),
        Spacer(1, .45 * cm), parties, Spacer(1, .55 * cm),
        Paragraph("DÉTAIL DE LA PRESTATION", section_heading), lines, Spacer(1, .35 * cm),
        Table([[Spacer(1, 1), totals]], colWidths=[4.6 * cm, 13 * cm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])),
        *payment_section,
        Spacer(1, .5 * cm), Paragraph("CONDITIONS DE RÈGLEMENT", section_heading),
        Paragraph("<br/>".join(terms), small), Spacer(1, .3 * cm),
        Paragraph("Merci pour votre confiance. Veuillez mentionner le numéro de facture lors de votre règlement.", small),
    ]
    doc.build(story, onFirstPage=lambda canvas, layout: draw_pdf_branding(canvas, layout, "Facture professionnelle"),
              onLaterPages=lambda canvas, layout: draw_pdf_branding(canvas, layout, "Facture professionnelle"))
    return output.getvalue()
