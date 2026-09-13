# scripts/generate_template_tdr.py
# ============================================================
# GÉNÉRATEUR DE TEMPLATE TDR — FORMA-IA / M2
# ============================================================
# Version : V3.0 — Syntaxe docxtpl SIMPLE (sans p/tr)
# ============================================================
# 
# ⚠️ ZAVA-DEHIBE : 
#   1. Alefaso ity script ity
#   2. Aza sokafy amin'ny Word ilay .docx
#   3. Test mivantana amin'ny API
#
# Raha sokafy amin'ny Word ianao dia mety hanapaka ny tags ny Word
# (izany no nahatonga ny "Encountered unknown tag 'endfor'")
# ============================================================

from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


NAVY = RGBColor(0x1B, 0x2A, 0x4A)
GOLD = RGBColor(0xB8, 0x91, 0x2F)
GRAY = RGBColor(0x5B, 0x64, 0x72)

OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "app" / "templates" / "tdr" / "template_tdr_formation.docx"
)


# ============================================================
# HELPERS
# ============================================================

def add_title(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = "Calibri"
        run.font.color.rgb = NAVY if level == 1 else GOLD
        run.font.size = Pt(15 if level == 1 else 12)
    return h


def add_text(doc, text, bold=False, color=None, size=11):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    return p


def add_simple_loop(doc, item_var, items_var, content):
    """
    Boucle SIMPLE (recommandée) :
    
    {% for item in items %}
    {{ content }}
    {% endfor %}
    
    Chaque tag dans un paragraphe propre.
    """
    # Paragraphe d'ouverture
    p1 = doc.add_paragraph()
    r1 = p1.add_run()
    r1.text = "{% for " + item_var + " in " + items_var + " %}"
    
    # Paragraphe de contenu
    p2 = doc.add_paragraph()
    r2 = p2.add_run()
    r2.text = content
    
    # Paragraphe de fermeture
    p3 = doc.add_paragraph()
    r3 = p3.add_run()
    r3.text = "{% endfor %}"


def add_rich_loop(doc, item_var, items_var, content_builder):
    """
    Boucle riche (avec plusieurs paragraphes dans le corps).
    content_builder est une fonction qui prend (doc, item_var) 
    et ajoute les paragraphes.
    """
    p1 = doc.add_paragraph()
    r1 = p1.add_run()
    r1.text = "{% for " + item_var + " in " + items_var + " %}"
    
    # Corps de la boucle
    content_builder(doc, item_var)
    
    p3 = doc.add_paragraph()
    r3 = p3.add_run()
    r3.text = "{% endfor %}"


def add_table_with_loop(doc, headers, items_var, item_var, columns):
    """
    Tableau avec boucle.
    
    ⚠️ IMPORTANT : 
    Le tag {% for %} doit être dans la MÊME LIGNE que la première valeur.
    Le tag {% endfor %} dans la MÊME LIGNE que la dernière valeur.
    """
    table = doc.add_table(rows=2, cols=len(headers))
    table.style = "Light Grid Accent 1"
    
    # Ligne d'en-tête
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    
    # Ligne-modèle avec boucle
    row = table.rows[1].cells
    
    # Première cellule : {% for ... %} + première valeur
    row[0].text = "{% for " + item_var + " in " + items_var + " %}" + "{{ " + item_var + "." + columns[0] + " }}"
    
    # Cellules intermédiaires : juste les valeurs
    for i in range(1, len(columns) - 1):
        row[i].text = "{{ " + item_var + "." + columns[i] + " }}"
    
    # Dernière cellule : dernière valeur + {% endfor %}
    last = len(columns) - 1
    row[last].text = "{{ " + item_var + "." + columns[last] + " }}" + "{% endfor %}"
    
    return table


# ============================================================
# BUILD
# ============================================================

def build_template():
    doc = Document()
    
    # Marges
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
    
    # ============================================================
    # PAGE DE GARDE
    # ============================================================
    add_text(doc, "ALTIORA SOLUTIONS", bold=True, color=NAVY, size=16)
    add_text(doc, "Startup Tech — Antananarivo, Madagascar", color=GRAY, size=10)
    doc.add_paragraph()
    
    add_title(doc, "TERMES DE RÉFÉRENCE", level=1)
    add_text(doc, "Formation professionnelle", color=GOLD, size=12)
    doc.add_paragraph()
    
    add_text(doc, "{{ titre_formation }}", bold=True, size=14)
    add_text(doc, "Réf. {{ reference_tdr }}", color=GRAY, size=10)
    doc.add_paragraph()
    
    # Tableau récapitulatif (sans boucle)
    table = doc.add_table(rows=6, cols=2)
    table.style = "Light List Accent 1"
    recap = [
        ("Client", "{{ client_nom }}"),
        ("Public visé", "{{ public_cible }}"),
        ("Durée totale", "{{ duree_totale }}"),
        ("Lieu de la formation", "{{ lieu }}"),
        ("Date d'émission", "{{ date_emission }}"),
        ("Coordonnées ALTIORA", "{{ altiora_coordonnees }}"),
    ]
    for i, (label, value) in enumerate(recap):
        table.rows[i].cells[0].text = label
        table.rows[i].cells[1].text = value
    
    doc.add_page_break()
    
    # ============================================================
    # SOMMAIRE
    # ============================================================
    add_title(doc, "Sommaire", level=1)
    add_text(doc, "(Ctrl+A puis F9 dans Word pour mettre à jour)",
             color=GRAY, size=9)
    doc.add_page_break()
    
    # ============================================================
    # SECTION 1
    # ============================================================
    add_title(doc, "1. Contexte et présentation du client", level=1)
    add_title(doc, "1.1 Contexte de la demande", level=2)
    add_text(doc, "{{ contexte }}")
    
    add_title(doc, "1.2 Présentation du client", level=2)
    add_text(doc, "{{ client_description }}")
    
    # ============================================================
    # SECTION 2
    # ============================================================
    add_title(doc, "2. Objectifs de la formation", level=1)
    add_title(doc, "2.1 Objectif général", level=2)
    add_text(doc, "{{ objectif_general }}")
    
    add_title(doc, "2.2 Objectifs spécifiques", level=2)
    add_simple_loop(doc, "obj", "objectifs_specifiques", "• {{ obj }}")
    
    # ============================================================
    # SECTION 3
    # ============================================================
    add_title(doc, "3. Public cible et prérequis", level=1)
    add_title(doc, "3.1 Public visé", level=2)
    add_text(doc, "{{ public_cible }}")
    add_text(doc, "Effectif prévu : {{ effectif_prevu }} participant(s).")
    
    add_title(doc, "3.2 Prérequis", level=2)
    add_simple_loop(doc, "prereq", "prerequis", "• {{ prereq }}")
    
    # ============================================================
    # SECTION 4 — PROGRAMME
    # ============================================================
    add_title(doc, "4. Programme de la formation", level=1)
    add_text(doc, "Durée totale : {{ duree_totale }}")
    
    # Boucle riche sur les modules
    def build_module_content(doc, module_var):
        p = doc.add_paragraph()
        r = p.add_run()
        r.text = "Module {{ loop.index }} — {{ " + module_var + ".module }} ({{ " + module_var + ".duree }})"
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = GOLD
        
        p2 = doc.add_paragraph()
        r2 = p2.add_run()
        r2.text = "{{ " + module_var + ".contenu }}"
        r2.font.size = Pt(11)
    
    add_rich_loop(doc, "module", "modules", build_module_content)
    
    doc.add_page_break()
    
    # ============================================================
    # SECTION 5
    # ============================================================
    add_title(doc, "5. Intervenant, modalités pédagogiques et évaluation", level=1)
    
    add_title(doc, "5.1 Intervenant(s)", level=2)
    add_text(doc, "{{ formateur_nom }}")
    add_text(doc, "{{ formateur_profil }}", color=GRAY, size=10)
    
    add_title(doc, "5.2 Modalités pédagogiques et évaluation", level=2)
    add_text(doc, "{{ modalites_pedagogiques }}")
    
    add_text(doc, "Moyens et supports :", bold=True, size=10)
    add_simple_loop(doc, "moyen", "moyens_pedagogiques", "• {{ moyen }}")
    
    add_text(doc, "Modalités d'évaluation :", bold=True, size=10)
    add_text(doc, "{{ modalites_evaluation }}")
    
    add_text(doc, "Livrables remis au client :", bold=True, size=10)
    add_simple_loop(doc, "livrable", "livrables", "• {{ livrable }}")
    
    # ============================================================
    # SECTION 6
    # ============================================================
    add_title(doc, "6. Planning et logistique", level=1)
    add_text(doc, "Dates prévues : {{ dates_prevues }}")
    add_text(doc, "Lieu : {{ lieu }}")
    
    add_table_with_loop(
        doc,
        headers=["Date", "Horaire", "Thème abordé"],
        items_var="planning_sessions",
        item_var="seance",
        columns=["date", "horaire", "theme"],
    )
    
    # ============================================================
    # SECTION 7 — BUDGET
    # ============================================================
    add_title(doc, "7. Budget prévisionnel", level=1)
    
    add_table_with_loop(
        doc,
        headers=["Désignation", "Quantité", "Prix unitaire (Ar)", "Total (Ar)"],
        items_var="budget_lignes",
        item_var="ligne",
        columns=["designation", "quantite", "prix_unitaire", "total"],
    )
    
    doc.add_paragraph()
    add_text(doc, "TOTAL GÉNÉRAL : {{ budget_total }}", bold=True, color=NAVY)
    add_text(doc, "Ce budget est indicatif et sera confirmé par devis formel avant signature.",
             color=GRAY, size=10)
    add_text(doc, "Conditions de paiement :", bold=True, size=10)
    add_text(doc, "{{ conditions_paiement }}")
    
    doc.add_page_break()
    
    # ============================================================
    # SECTION 8
    # ============================================================
    add_title(doc, "8. Conditions générales et validation", level=1)
    
    add_title(doc, "8.1 Conditions particulières", level=2)
    add_text(doc, "{{ conditions_particulieres }}")
    
    add_title(doc, "8.2 Validité de l'offre", level=2)
    add_text(doc, "La présente proposition est valable jusqu'au {{ date_validite_offre }}.")
    
    add_title(doc, "8.3 Signatures", level=2)
    
    table = doc.add_table(rows=2, cols=2)
    table.style = "Light Grid Accent 1"
    table.rows[0].cells[0].text = "Pour ALTIORA SOLUTIONS"
    table.rows[0].cells[1].text = "Pour le client"
    table.rows[1].cells[0].text = "{{ responsable_altiora }}\n\nDate et signature :"
    table.rows[1].cells[1].text = "{{ client_signataire }}\n\nDate et signature :"
    
    # ============================================================
    # SAUVEGARDE
    # ============================================================
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_PATH))
    
    size = OUTPUT_PATH.stat().st_size
    print(f"✅ Template généré : {OUTPUT_PATH}")
    print(f"   Taille : {size} bytes")
    print()
    print("⚠️  NE PAS ouvrir ce fichier dans Word !")
    print("    Ouvrir Word peut casser les tags Jinja2.")
    print("    Pour vérifier : test avec l'API directement.")


if __name__ == "__main__":
    build_template()