from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT


def create_template():
    out_dir = Path(__file__).resolve().parents[1] / "app" / "templates" / "attestations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "template_attestation.docx"

    doc = Document()

    # ── Mise en page A4 paysage ──
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for m in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, m, Cm(2))

    # ── En-tête ALTIORA ──
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("ALTIORA SOLUTIONS")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    h2 = doc.add_paragraph()
    h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = h2.add_run("Antananarivo, Madagascar")
    r2.italic = True
    r2.font.size = Pt(11)

    doc.add_paragraph()  # espace

    # ── Titre ──
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = t.add_run("{{ titre_attestation }}")
    tr.bold = True
    tr.font.size = Pt(26)
    tr.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)

    doc.add_paragraph()

    # ── Introduction ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{{ introduction }}").font.size = Pt(14)

    doc.add_paragraph()

    # ── Corps ──
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.add_run("{{ corps }}").font.size = Pt(12)

    doc.add_paragraph()

    # ── Détails formation ──
    details_lines = [
        ("Formation",   "{{ details.formation }}"),
        ("Dates",       "{{ details.dates }}"),
        ("Lieu",        "{{ details.lieu }}"),
        ("Durée",       "{{ details.duree }}"),
        ("Formateur",   "{{ details.formateur }}"),
        ("Domaine",     "{{ details.domaine }}"),
        ("Niveau",      "{{ details.niveau }}"),
    ]
    for label, value in details_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rl = p.add_run(f"{label} : ")
        rl.bold = True
        rl.font.size = Pt(11)
        p.add_run(value).font.size = Pt(11)

    doc.add_paragraph()

    # ── Compétences ──
    ct = doc.add_paragraph()
    ct.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ctr = ct.add_run("Compétences acquises :")
    ctr.bold = True
    ctr.font.size = Pt(12)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{% for c in competences %}• {{ c }}{% if not loop.last %}    {% endif %}{% endfor %}").font.size = Pt(11)

    doc.add_paragraph()

    # ── Clôture ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("{{ cloture }}").font.size = Pt(11)
    p.runs[0].italic = True

    doc.add_paragraph()

    # ── Signature ──
    sig = doc.add_paragraph()
    sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    sig.add_run("Fait à {{ lieu_emission }}, le {{ date_emission }}").font.size = Pt(11)

    sig2 = doc.add_paragraph()
    sig2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = sig2.add_run("Le Directeur\nALTIORA Solutions")
    r.bold = True
    r.font.size = Pt(11)

    # ── Numéro unique ──
    num = doc.add_paragraph()
    num.alignment = WD_ALIGN_PARAGRAPH.LEFT
    nr = num.add_run("N° {{ numero_unique }}")
    nr.italic = True
    nr.font.size = Pt(9)
    nr.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.save(out_file)
    print(f"✅ Template créé : {out_file}")


if __name__ == "__main__":
    create_template()