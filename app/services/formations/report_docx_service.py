"""Production d'un rapport de formation Word aux couleurs ALTIORA PREST."""

from io import BytesIO
from pathlib import Path
from typing import Any


NAVY = "0B1F4D"
DARK_NAVY = "06132F"
GOLD = "C9A84C"
PALE_GOLD = "FBF6E8"
LIGHT = "F3F5F9"
TEXT = "243047"
MUTED = "64748B"
LOGO_PATH = Path(__file__).resolve().parents[2] / "templates" / "logo_altiora_prest.png"


def _shade(cell, fill: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def _set_cell_margins(cell, top=90, start=110, bottom=90, end=110) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    properties = cell._tc.get_or_add_tcPr()
    margins = OxmlElement("w:tcMar")
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        margins.append(node)
    properties.append(margins)


def _set_repeat_table_header(row) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    row._tr.get_or_add_trPr().append(repeat)


def _set_cell_text(cell, value: Any, *, color=TEXT, bold=False, size=9) -> None:
    from docx.shared import Pt, RGBColor

    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(str(value if value not in (None, "") else "—"))
    run.bold = bold
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    _set_cell_margins(cell)


def _styled_table(document, headers: list[str], rows: list[list[Any]], widths: list[int] | None = None):
    from docx.shared import Inches

    table = document.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.style = "Table Grid"
    _set_repeat_table_header(table.rows[0])
    for index, label in enumerate(headers):
        cell = table.rows[0].cells[index]
        _shade(cell, NAVY)
        _set_cell_text(cell, label, color="FFFFFF", bold=True, size=8)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for column, value in enumerate(values):
            if row_index % 2 == 1:
                _shade(cells[column], LIGHT)
            _set_cell_text(cells[column], value, size=8)
    if widths:
        for row in table.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Inches(width)
    document.add_paragraph().paragraph_format.space_after = 0
    return table


def _section(document, title: str) -> None:
    from docx.shared import Pt, RGBColor

    paragraph = document.add_paragraph()
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(title.upper())
    run.bold = True
    run.font.name = "Aptos Display"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor.from_string(NAVY)
    ppr = paragraph._p.get_or_add_pPr()
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), GOLD)
    border.append(bottom)
    ppr.append(border)


def _paragraph(document, text: Any, *, italic=False):
    from docx.shared import Pt, RGBColor

    if not text:
        return
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.12
    run = paragraph.add_run(str(text))
    run.italic = italic
    run.font.name = "Aptos"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor.from_string(TEXT)


def _bullet_list(document, values: Any) -> None:
    from docx.shared import Pt, RGBColor

    if isinstance(values, str):
        values = [line.strip() for line in values.splitlines() if line.strip()]
    for value in values or []:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(str(value))
        run.font.name = "Aptos"
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor.from_string(TEXT)


def _key_values(document, rows: list[tuple[str, Any]]) -> None:
    _styled_table(document, ["INFORMATION", "DÉTAIL"], [[key, value or "Non renseigné"] for key, value in rows], [2.0, 4.55])


def generate_report_docx(report_data: dict[str, Any]) -> bytes:
    """Construit le DOCX final à partir de la version validée par HITL."""
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.3)

    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(9.5)
    styles["Normal"].font.color.rgb = RGBColor.from_string(TEXT)
    for heading in ("Heading 1", "Heading 2"):
        styles[heading].font.name = "Aptos Display"
        styles[heading].font.color.rgb = RGBColor.from_string(NAVY)

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if LOGO_PATH.is_file():
        header.add_run().add_picture(str(LOGO_PATH), width=Inches(1.05))
    header.paragraph_format.space_after = Pt(2)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("ALTIORA PREST  ·  Rapport de formation  ·  Document confidentiel")
    footer_run.font.name = "Aptos"
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor.from_string(MUTED)

    title = report_data.get("titre_rapport", "Rapport de formation")
    presentation = report_data.get("presentation") or {}
    stats = report_data.get("statistiques_participants") or {}
    metadata = report_data.get("metadata") or {}

    brand = document.add_paragraph()
    brand.alignment = WD_ALIGN_PARAGRAPH.CENTER
    brand.paragraph_format.space_before = Pt(42)
    if LOGO_PATH.is_file():
        brand.add_run().add_picture(str(LOGO_PATH), width=Inches(1.6))

    kicker = document.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kicker.paragraph_format.space_before = Pt(20)
    run = kicker.add_run("RAPPORT FINAL DE FORMATION")
    run.bold = True
    run.font.name = "Aptos Display"
    run.font.size = Pt(21)
    run.font.color.rgb = RGBColor.from_string(NAVY)

    course_title = document.add_paragraph()
    course_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    course_title.paragraph_format.space_before = Pt(8)
    run = course_title.add_run(str(presentation.get("titre_formation") or title))
    run.bold = True
    run.font.name = "Aptos Display"
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor.from_string(GOLD)

    _key_values(document, [
        ("Client / organisation", report_data.get("client") or "Non renseigné"),
        ("Période", presentation.get("dates")),
        ("Lieu", presentation.get("lieu")),
        ("Formateur", presentation.get("formateur")),
        ("Durée", presentation.get("duree")),
        ("Participants", presentation.get("nombre_participants", stats.get("total_inscrits", "—"))),
    ])
    emission = document.add_paragraph()
    emission.alignment = WD_ALIGN_PARAGRAPH.CENTER
    emission.paragraph_format.space_before = Pt(10)
    emission_run = emission.add_run(f"Émis à {report_data.get('lieu_emission', 'Antananarivo')} · {report_data.get('date_emission', '')}")
    emission_run.font.size = Pt(8)
    emission_run.font.color.rgb = RGBColor.from_string(MUTED)

    document.add_page_break()

    _section(document, "Résumé exécutif")
    _paragraph(document, report_data.get("resume_executif"))

    _section(document, "Contexte et objectifs")
    _key_values(document, [
        ("Client", report_data.get("client")),
        ("Public cible", presentation.get("public_cible")),
        ("Domaine", report_data.get("domaine")),
    ])
    _bullet_list(document, report_data.get("objectifs"))
    if not report_data.get("objectifs"):
        _paragraph(document, "Les objectifs détaillés n’ont pas été renseignés dans le dossier de session.", italic=True)

    _section(document, "Déroulement pédagogique")
    schedule = report_data.get("deroulement") or []
    if schedule:
        _styled_table(document, ["DATE", "HORAIRES", "DURÉE", "THÈME / SÉQUENCE"], [
            [item.get("date", "—"), item.get("horaires", "—"), item.get("duree", "—"), item.get("theme", "—")]
            for item in schedule
        ], [1.0, 1.1, 0.8, 3.65])
    else:
        _paragraph(document, "Aucune séance détaillée n’est disponible pour ce rapport.", italic=True)
    if report_data.get("methodes_pedagogiques"):
        _paragraph(document, "Méthodes : " + ", ".join(report_data["methodes_pedagogiques"]))
    if report_data.get("outils"):
        _paragraph(document, "Outils et supports : " + ", ".join(report_data["outils"]))

    _section(document, "Participation et assiduité")
    _key_values(document, [
        ("Inscrits", stats.get("total_inscrits")),
        ("Présents au moins une séance", stats.get("total_presents")),
        ("Taux de présence moyen", stats.get("taux_presence_moyen")),
        ("Pointages manquants", stats.get("pointages_manquants", 0)),
    ])
    participants = report_data.get("participants") or []
    if participants:
        _styled_table(document, ["PARTICIPANT", "FONCTION", "ORGANISATION", "PRÉSENCE"], [
            [item.get("nom"), item.get("fonction") or "—", item.get("entreprise") or "—", item.get("taux_presence_affiche", "—")]
            for item in participants
        ], [2.0, 1.55, 1.8, 1.2])

    _section(document, "Évaluation des acquis")
    levels = report_data.get("analyse_niveaux") or {}
    _paragraph(document, (levels.get("commentaire") or "Les résultats ci-dessous sont présentés uniquement lorsque des scores initiaux et finaux sont enregistrés."), italic=True)
    score_rows = []
    if levels.get("avant", {}).get("score_moyen") is not None:
        score_rows.append(("Score moyen initial", f"{levels['avant']['score_moyen']} / 100"))
    if levels.get("apres", {}).get("score_moyen") is not None:
        score_rows.append(("Score moyen final", f"{levels['apres']['score_moyen']} / 100"))
    if score_rows:
        _key_values(document, score_rows)
    individual = report_data.get("resultats_individuels") or []
    if individual:
        _styled_table(document, ["PARTICIPANT", "SCORE INITIAL", "SCORE FINAL", "ÉVOLUTION"], [
            [item.get("nom"), item.get("score_avant_affiche", "—"), item.get("score_apres_affiche", "—"), item.get("progression_affiche", "—")]
            for item in individual
        ], [2.5, 1.2, 1.2, 1.65])
    if report_data.get("observations_formateur"):
        _paragraph(document, "Observation du formateur : " + str(report_data["observations_formateur"]))

    _section(document, "Satisfaction des participants")
    satisfaction = report_data.get("satisfaction") or {}
    satisfaction_rows = [
        [label, satisfaction.get(key, "Non mesuré")]
        for label, key in (("Note globale", "note_globale"), ("Formateur", "note_formateur"), ("Contenu", "note_contenu"), ("Supports", "note_supports"), ("Organisation", "note_organisation"), ("Recommandation", "taux_recommandation"))
    ]
    _styled_table(document, ["INDICATEUR", "RÉSULTAT"], satisfaction_rows, [3.6, 2.95])
    _paragraph(document, f"Nombre de questionnaires exploités : {satisfaction.get('nb_reponses', 0)}.", italic=True)
    for label, key in (("Points forts", "points_forts"), ("Axes d’amélioration", "axes_amelioration")):
        items = satisfaction.get(key) or []
        if items:
            _paragraph(document, label + " :")
            _bullet_list(document, items)

    _section(document, "Recommandations")
    _bullet_list(document, report_data.get("recommandations_formateur") or report_data.get("recommandations"))
    _section(document, "Conclusion")
    _paragraph(document, report_data.get("conclusion"))

    document.add_paragraph()
    signature = document.add_table(rows=1, cols=1)
    signature_cell = signature.cell(0, 0)
    signature_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _shade(signature_cell, PALE_GOLD)
    _set_cell_text(signature_cell, "Pour ALTIORA PREST\nLa Direction\n\n\nSignature et cachet", color=NAVY, bold=True, size=9)

    document.core_properties.title = str(title)
    document.core_properties.subject = "Rapport final de formation ALTIORA PREST"
    document.core_properties.author = "ALTIORA PREST"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
