"""Reusable ALTIORA PREST styling for generated Word and PDF documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx.document import Document as DocxDocumentType
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Cm, Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

NAVY = "11162A"
TEAL = "1B8F6E"
PALE_TEAL = "E8F4F0"
PALE_BLUE = "F1F4F8"
INK = "202938"
MUTED = "667085"
GOLD = "B89445"
WHITE = "FFFFFF"
LOGO_PATH = Path(__file__).resolve().parents[1] / "templates" / "logo_altiora_prest.png"


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def _set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_paragraph_bottom_border(paragraph, color: str = TEAL, size: str = "8") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "6")
    bottom.set(qn("w:color"), color)
    borders.append(bottom)


def _add_page_number(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    value = OxmlElement("w:t")
    value.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instruction, separate, value, end):
        run._r.append(node)


def apply_docx_branding(
    doc: DocxDocumentType,
    document_type: str,
    *,
    format_tables: bool = False,
) -> DocxDocumentType:
    """Apply consistent page setup, typography, logo header, and page footer."""
    for section in doc.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.15)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(2.15)
        section.right_margin = Cm(2.15)
        section.header_distance = Cm(0.75)
        section.footer_distance = Cm(0.75)

        header = section.header
        p = header.paragraphs[0]
        p.clear()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.tab_stops.add_tab_stop(Inches(6.15), WD_TAB_ALIGNMENT.RIGHT)
        if LOGO_PATH.is_file():
            p.add_run().add_picture(str(LOGO_PATH), height=Cm(0.8))
            p.add_run("\t")
        company = p.add_run("ALTIORA PREST")
        company.bold = True
        company.font.name = "Arial"
        company.font.size = Pt(9)
        company.font.color.rgb = RGBColor.from_string(NAVY)
        label = p.add_run(f"\t{document_type.upper()}")
        label.font.name = "Arial"
        label.font.size = Pt(8)
        label.font.color.rgb = RGBColor.from_string(TEAL)
        _set_paragraph_bottom_border(p)

        footer = section.footer
        p = footer.paragraphs[0]
        p.clear()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.tab_stops.add_tab_stop(Inches(6.15), WD_TAB_ALIGNMENT.RIGHT)
        left = p.add_run("ALTIORA PREST  ·  Antananarivo, Madagascar")
        left.font.name = "Arial"
        left.font.size = Pt(8)
        left.font.color.rgb = RGBColor.from_string(MUTED)
        p.add_run("\tPage ")
        _add_page_number(p)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12

    title = styles["Title"]
    title.font.name = "Arial"
    title.font.size = Pt(25)
    title.font.bold = True
    title.font.color.rgb = RGBColor.from_string("000000")
    title.paragraph_format.space_before = Pt(14)
    title.paragraph_format.space_after = Pt(8)
    title.paragraph_format.keep_with_next = True

    for name, size, color in (("Heading 1", 15, NAVY), ("Heading 2", 12, TEAL), ("Heading 3", 10.5, NAVY)):
        style = styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(13 if name == "Heading 1" else 9)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.keep_with_next = True

    for paragraph in doc.paragraphs:
        if paragraph.style and paragraph.style.name.startswith("Heading"):
            paragraph.paragraph_format.keep_with_next = True

    if format_tables:
        for table in doc.tables:
            style_docx_table(table)

    doc.core_properties.author = "ALTIORA PREST"
    return doc


def style_docx_table(table, *, header_row: bool = True, key_value: bool = False) -> None:
    """Format a data table with readable labels, spacing, and restrained bands."""
    table.autofit = True
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row.cells):
            _set_cell_margins(cell)
            if header_row and row_index == 0:
                _set_cell_shading(cell, NAVY)
            elif key_value and col_index == 0:
                _set_cell_shading(cell, PALE_TEAL)
            elif row_index % 2 == 0:
                _set_cell_shading(cell, PALE_BLUE)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(1)
                paragraph.paragraph_format.line_spacing = 1.0
                for run in paragraph.runs:
                    run.font.name = "Arial"
                    run.font.size = Pt(9)
                    if header_row and row_index == 0:
                        run.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
                    elif key_value and col_index == 0:
                        run.bold = True
                        run.font.color.rgb = RGBColor.from_string(NAVY)


def add_metadata_table(doc: DocxDocumentType, rows: list[tuple[str, Any]]) -> None:
    table = doc.add_table(rows=0, cols=2)
    table.autofit = True
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = str(label)
        cells[1].text = str(value if value not in (None, "") else "—")
    style_docx_table(table, header_row=False, key_value=True)


def draw_pdf_branding(canvas, document, document_type: str) -> None:
    """ReportLab page callback for a compact corporate header and page footer."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm

    page_width, page_height = document.pagesize
    canvas.saveState()
    if LOGO_PATH.is_file():
        canvas.drawImage(
            str(LOGO_PATH), 1.7 * cm, page_height - 1.65 * cm,
            width=2.6 * cm, height=0.9 * cm,
            preserveAspectRatio=True, anchor="sw", mask="auto",
        )
    canvas.setFillColor(colors.HexColor(f"#{NAVY}"))
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawRightString(page_width - 1.7 * cm, page_height - 1.15 * cm, "ALTIORA PREST")
    canvas.setFillColor(colors.HexColor(f"#{TEAL}"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(page_width - 1.7 * cm, page_height - 1.55 * cm, document_type.upper())
    canvas.setStrokeColor(colors.HexColor(f"#{TEAL}"))
    canvas.setLineWidth(0.8)
    canvas.line(1.7 * cm, page_height - 1.95 * cm, page_width - 1.7 * cm, page_height - 1.95 * cm)
    canvas.setStrokeColor(colors.HexColor("#D9E2E8"))
    canvas.setLineWidth(0.45)
    canvas.line(1.7 * cm, 1.35 * cm, page_width - 1.7 * cm, 1.35 * cm)
    canvas.setFillColor(colors.HexColor(f"#{MUTED}"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(1.7 * cm, 0.95 * cm, "ALTIORA PREST  ·  Antananarivo, Madagascar")
    canvas.drawRightString(page_width - 1.7 * cm, 0.95 * cm, f"Page {document.page}")
    canvas.restoreState()


def brand_html_document(title: str, subtitle: str = "") -> str:
    """Shared print styling for browser-generated Word-compatible HTML/PDF."""
    safe_title = str(title)
    safe_subtitle = str(subtitle)
    return f"""<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><title>{safe_title}</title>
<style>
@page {{ size: A4; margin: 22mm 20mm 20mm; @bottom-left {{ content: 'ALTIORA PREST · Antananarivo, Madagascar'; color: #667085; font: 8pt Arial; }} @bottom-right {{ content: 'Page ' counter(page); color: #667085; font: 8pt Arial; }} }}
* {{ box-sizing: border-box; }} body {{ margin: 0; color: #{INK}; font: 10.5pt/1.55 Arial, sans-serif; }}
.brand {{ display:flex; align-items:center; justify-content:space-between; border-bottom: 2px solid #{TEAL}; padding-bottom: 10px; margin-bottom: 26px; color: #{NAVY}; font-size: 9pt; font-weight:700; }}
.brand img {{ max-height: 36px; max-width: 150px; }} .brand-label {{ color: #{TEAL}; font-size:8pt; text-transform:uppercase; letter-spacing:.08em; }}
h1 {{ color:#000; font-size:24pt; line-height:1.2; margin: 0 0 7px; }} .subtitle {{ color: #{MUTED}; font-size:11pt; margin:0 0 20px; }}
h2 {{ color: #{NAVY}; font-size:14pt; margin:22px 0 8px; page-break-after:avoid; }} h3 {{ color: #{TEAL}; font-size:11pt; margin:15px 0 6px; page-break-after:avoid; }}
p {{ margin:0 0 9px; }} table {{ width:100%; border-collapse:collapse; margin:10px 0 16px; font-size:9pt; }} th {{ background:#{NAVY}; color:#fff; text-align:left; padding:8px 9px; }} td {{ border-bottom:1px solid #dfe5eb; padding:7px 9px; vertical-align:top; }}
tr:nth-child(even) td {{ background:#f4f7f9; }} .meta {{ background:#f2f8f6; border-left:3px solid #{TEAL}; padding:12px 14px; margin:14px 0 20px; }} .meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 22px; }} .meta-label {{ color:#{MUTED}; font-size:8pt; text-transform:uppercase; letter-spacing:.04em; }}
.signature {{ margin-top:38px; display:grid; grid-template-columns:1fr 1fr; gap:30px; }} .signature div {{ border-top:1px solid #98a2b3; padding-top:8px; min-height:56px; }} .small {{ color:#{MUTED}; font-size:8pt; }}
</style></head><body><header class=\"brand\"><span>ALTIORA PREST</span><span class=\"brand-label\">{safe_subtitle}</span></header><main><h1>{safe_title}</h1>"""

