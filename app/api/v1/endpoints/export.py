# app/api/v1/endpoints/export.py
# ============================================================
# ROUTES BACKEND — Exports comptables
# ============================================================
# Bloc K (2026-09-28) :
#   GET /exports/comptable   Export CSV / Excel / PDF des factures
#
# Format de chaque ligne :
#   Numéro · Client · Date émission · Date échéance · Montant HT · TVA %
#   · Montant TTC · Statut · Montant encaissé · Reste dû · Nb paiements
#
# Rôles autorisés : DIRECTION, COMPTABLE
# ============================================================

import csv
import io
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.facture import Facture, StatutFacture
from app.models.user import User

router = APIRouter(prefix="/exports", tags=["Exports"])


# ── colonnes CSV/Excel ──────────────────────────────────────
_COLONNES = [
    "Numéro",
    "Client",
    "Date émission",
    "Date échéance",
    "Montant HT (Ar)",
    "TVA (%)",
    "Montant TTC (Ar)",
    "Statut",
    "Encaissé (Ar)",
    "Reste dû (Ar)",
    "Nb paiements",
]


def _lignes(factures: list[Facture]):
    """Générateur : retourne une liste de valeurs par facture."""
    for f in factures:
        encaisse = round(sum(p.montant for p in f.paiements), 2)
        reste = round(f.montant_ttc - encaisse, 2)
        yield [
            f.numero,
            f.client,
            f.date_emission.strftime("%Y-%m-%d") if f.date_emission else "",
            f.date_echeance.strftime("%Y-%m-%d") if f.date_echeance else "",
            round(f.montant, 2),
            round(f.tva_taux, 2),
            round(f.montant_ttc, 2),
            f.statut.value,
            encaisse,
            reste,
            len(f.paiements),
        ]


def _export_csv(factures: list[Facture]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(_COLONNES)
    for ligne in _lignes(factures):
        w.writerow(ligne)
    return buf.getvalue().encode("utf-8-sig")  # BOM pour Excel FR


def _export_excel(factures: list[Facture]) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Factures"

    # En-tête
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="AAAAAA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, col_name in enumerate(_COLONNES, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # Données
    statut_couleurs = {
        "EMISE":             "FFF2CC",
        "PARTIELLEMENT_PAYEE": "DDEBF7",
        "PAYEE":             "E2EFDA",
        "EN_RETARD":         "FCE4D6",
    }

    for row_idx, ligne in enumerate(_lignes(factures), 2):
        statut_val = ligne[7]  # colonne Statut
        fill_color = statut_couleurs.get(statut_val, "FFFFFF")
        row_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
        for col_idx, val in enumerate(ligne, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.fill = row_fill
            cell.border = border
            if isinstance(val, float):
                cell.number_format = "#,##0.00"

    # Largeurs auto
    for col_idx in range(1, len(_COLONNES) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 18

    # Figer la ligne d'en-tête
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _export_pdf(factures: list[Facture], date_export: str) -> bytes:
    """Export PDF simple via reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Export comptable — Factures ALTIORA PREST", styles["Title"]))
    elements.append(Paragraph(f"Généré le {date_export} — {len(factures)} facture(s)", styles["Normal"]))
    elements.append(Spacer(1, 0.4*cm))

    # Colonnes réduites pour PDF (format paysage)
    cols_pdf = ["Numéro", "Client", "Émission", "Échéance", "HT (Ar)", "TTC (Ar)", "Statut", "Encaissé", "Reste"]
    data = [cols_pdf]
    for f in factures:
        encaisse = round(sum(p.montant for p in f.paiements), 2)
        reste = round(f.montant_ttc - encaisse, 2)
        data.append([
            f.numero,
            f.client[:20],
            f.date_emission.strftime("%d/%m/%Y") if f.date_emission else "",
            f.date_echeance.strftime("%d/%m/%Y") if f.date_echeance else "",
            f"{f.montant:,.0f}",
            f"{f.montant_ttc:,.0f}",
            f.statut.value,
            f"{encaisse:,.0f}",
            f"{reste:,.0f}",
        ])

    col_widths = [3.5*cm, 4.5*cm, 2.5*cm, 2.5*cm, 3*cm, 3*cm, 3.5*cm, 3*cm, 3*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#AAAAAA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
    return buf.getvalue()


# ── route ───────────────────────────────────────────────────

@router.get(
    "/comptable",
    summary="Export comptable des factures (CSV / Excel / PDF)",
    description=(
        "Exporte toutes les factures (ou filtrées) dans le format demandé.\n\n"
        "**Formats :**\n"
        "- `csv` — Séparateur `;`, encodage UTF-8 BOM (compatible Excel FR)\n"
        "- `excel` — Classeur `.xlsx` avec mise en forme (couleurs par statut, en-tête figée)\n"
        "- `pdf` — Document PDF paysage A4 (via reportlab)\n\n"
        "**Filtres optionnels :**\n"
        "- `statut` : `EMISE` | `PARTIELLEMENT_PAYEE` | `PAYEE` | `EN_RETARD`\n"
        "- `client` : recherche partielle\n"
        "- `annee` : filtre sur l'année d'émission\n\n"
        "**Rôles autorisés :** DIRECTION, COMPTABLE."
    ),
)
def export_comptable(
    format: str = Query(default="csv", pattern="^(csv|excel|pdf)$",
                        description="Format de l'export : csv | excel | pdf"),
    statut: Optional[StatutFacture] = Query(default=None),
    client: Optional[str] = Query(default=None, description="Recherche partielle sur le nom du client"),
    annee: Optional[int] = Query(default=None, ge=2020, le=2100, description="Filtrer par année d'émission"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("DIRECTION", "COMPTABLE")),
):
    q = db.query(Facture)
    if statut:
        q = q.filter(Facture.statut == statut)
    if client:
        q = q.filter(Facture.client.ilike(f"%{client}%"))
    if annee:
        from sqlalchemy import extract
        q = q.filter(extract("year", Facture.date_emission) == annee)

    factures = q.order_by(Facture.date_emission.desc()).all()
    date_export = datetime.now().strftime("%Y-%m-%d_%H-%M")

    if format == "csv":
        contenu = _export_csv(factures)
        return Response(
            content=contenu,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=export_comptable_{date_export}.csv"},
        )
    elif format == "excel":
        contenu = _export_excel(factures)
        return Response(
            content=contenu,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=export_comptable_{date_export}.xlsx"},
        )
    else:  # pdf
        contenu = _export_pdf(factures, date_export)
        return Response(
            content=contenu,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=export_comptable_{date_export}.pdf"},
        )
