"""
ReportPdfService
================
Génère le PDF du rapport final de formation ALTIORA.
Mise en forme navy/or premium, logo officiel, sections structurées.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).resolve().parents[2] / "templates" / "logo_altiora_prest.png"

# ── Couleurs ALTIORA ──────────────────────────────────────────
NAVY       = "#0B1F4D"
DARK_NAVY  = "#001736"
GOLD       = "#C9A84C"
GOLD_LIGHT = "#E8C97A"
WHITE      = "#FFFFFF"
LIGHT_BG   = "#F4F6FA"
SLATE      = "#64748B"
TEXT       = "#1E293B"
EMERALD    = "#10B981"
RED_SOFT   = "#EF4444"


def _hex(h: str):
    from reportlab.lib import colors
    return colors.HexColor(h)


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    registered = pdfmetrics.getRegisteredFontNames()
    for name, filename in (
        ("AltioraRegular", "georgia.ttf"),
        ("AltioraBold",    "georgiab.ttf"),
        ("AltioraItalic",  "georgiai.ttf"),
    ):
        fp = Path(r"C:\Windows\Fonts") / filename
        if fp.is_file() and name not in registered:
            try:
                pdfmetrics.registerFont(TTFont(name, str(fp)))
            except Exception:
                pass
    if "AltioraRegular" in pdfmetrics.getRegisteredFontNames():
        return "AltioraRegular", "AltioraBold", "AltioraItalic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


def _wrap_text(text: str, font: str, size: float, max_width: float, pdf) -> list[str]:
    """Découpe le texte en lignes qui rentrent dans max_width."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if stringWidth(test, font, size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def generate_report_pdf(report_data: dict[str, Any]) -> bytes:
    """
    Génère le PDF du rapport final à partir des données JSON approuvées.
    Retourne les bytes du PDF.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader

    buf = BytesIO()
    W, H = A4  # 595 × 842 pts

    pdf = rl_canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(report_data.get("titre_rapport", "Rapport de formation ALTIORA"))

    font_reg, font_bold, font_italic = _register_fonts()

    logo = ImageReader(str(LOGO_PATH)) if LOGO_PATH.is_file() else None

    margin_l = 20 * mm
    margin_r = 20 * mm
    content_w = W - margin_l - margin_r

    # ─── État de pagination ───────────────────────────────────
    page_num = [0]
    y = [0.0]  # curseur vertical courant

    def new_page():
        if page_num[0] > 0:
            _draw_footer(pdf, font_reg, font_italic, page_num[0], W, H, margin_l)
            pdf.showPage()
        page_num[0] += 1
        y[0] = H - 15 * mm  # on dessine le header ensuite

    def ensure_space(needed: float):
        if y[0] < (15 * mm + needed):
            new_page()
            _draw_running_header(pdf, font_bold, font_italic, W, H, margin_l, logo,
                                  report_data.get("titre_rapport", "Rapport de formation"))
            y[0] = H - 42 * mm

    # ══════════════════════════════════════════════════════════
    # PAGE 1 — COUVERTURE
    # ══════════════════════════════════════════════════════════
    page_num[0] = 1

    # Fond navy haut (40% de la page)
    cover_h = H * 0.42
    pdf.setFillColor(_hex(DARK_NAVY))
    pdf.rect(0, H - cover_h, W, cover_h, fill=1, stroke=0)

    # Bande or fine sous le fond navy
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(0, H - cover_h - 3, W, 3, fill=1, stroke=0)

    # Logo en haut à gauche
    if logo:
        pdf.drawImage(logo, margin_l, H - cover_h + 12 * mm,
                      width=38 * mm, height=20 * mm,
                      preserveAspectRatio=True, anchor="nw", mask="auto")

    # Numéro de référence en haut à droite
    ref = report_data.get("metadata", {}).get("session_id", "")
    if ref:
        pdf.setFont(font_reg, 7)
        pdf.setFillColor(_hex(GOLD_LIGHT))
        pdf.drawRightString(W - margin_r, H - 10 * mm, f"Réf. session : {ref}")

    # Titre du rapport
    titre = report_data.get("titre_rapport", "RAPPORT DE FORMATION")
    pdf.setFillColor(_hex(WHITE))
    pdf.setFont(font_bold, 20)
    titre_lines = _wrap_text(titre, font_bold, 20, content_w, pdf)
    ty = H - cover_h * 0.38
    for line in titre_lines:
        pdf.drawCentredString(W / 2, ty, line)
        ty -= 24

    # Ligne or décorative centrée
    bar_w = 60 * mm
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(W / 2 - bar_w / 2, ty - 4, bar_w, 2, fill=1, stroke=0)
    ty -= 14

    # Sous-titre / session
    pres = report_data.get("presentation", {})
    sous = pres.get("titre_formation", "")
    if sous:
        pdf.setFont(font_italic, 10)
        pdf.setFillColor(_hex(GOLD_LIGHT))
        for line in _wrap_text(sous, font_italic, 10, content_w * 0.8, pdf):
            pdf.drawCentredString(W / 2, ty, line)
            ty -= 13

    # Zone blanche inférieure — infos clés
    info_top = H - cover_h - 3
    info_bottom = info_top - 65 * mm
    pdf.setFillColor(_hex(LIGHT_BG))
    pdf.rect(margin_l, info_bottom, content_w, 65 * mm, fill=1, stroke=0)

    # Bordure gauche or
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(margin_l, info_bottom, 3, 65 * mm, fill=1, stroke=0)

    # Champs informatifs
    fields = [
        ("Période", f"{pres.get('dates', '—')}"),
        ("Lieu", f"{pres.get('lieu', '—')}"),
        ("Formateur", f"{pres.get('formateur', '—')}"),
        ("Public cible", f"{pres.get('public_cible', '—')}"),
        ("Durée", f"{pres.get('duree', '—')}"),
        ("Participants", f"{pres.get('nombre_participants', '—')}"),
    ]
    col_w = content_w / 2
    fx = margin_l + 8 * mm
    fy = info_bottom + 57 * mm
    for i, (label, value) in enumerate(fields):
        cx = fx + (i % 2) * col_w
        cy = fy - (i // 2) * 42
        pdf.setFont(font_bold, 7.5)
        pdf.setFillColor(_hex(SLATE))
        pdf.drawString(cx, cy, label.upper())
        pdf.setFont(font_reg, 9)
        pdf.setFillColor(_hex(TEXT))
        for line_index, line in enumerate(_wrap_text(str(value), font_reg, 9, col_w - 8 * mm, pdf)[:2]):
            pdf.drawString(cx, cy - 10 - line_index * 10, line)

    # Date d'émission en bas
    pdf.setFont(font_italic, 8)
    pdf.setFillColor(_hex(SLATE))
    date_em = report_data.get("date_emission", "")
    lieu_em = report_data.get("lieu_emission", "")
    if date_em or lieu_em:
        pdf.drawCentredString(W / 2, info_bottom - 8 * mm,
                              f"Émis le {date_em} à {lieu_em}")

    _draw_footer(pdf, font_reg, font_italic, 1, W, H, margin_l)

    # ══════════════════════════════════════════════════════════
    # PAGE 2+ — CONTENU
    # ══════════════════════════════════════════════════════════
    pdf.showPage()
    page_num[0] = 2
    _draw_running_header(pdf, font_bold, font_italic, W, H, margin_l, logo,
                          report_data.get("titre_rapport", "Rapport de formation"))
    y[0] = H - 42 * mm

    # ── 1. Résumé exécutif ────────────────────────────────────
    resume = report_data.get("resume_executif", "")
    if resume:
        y[0] = _section_title(pdf, "Résumé exécutif", y[0], font_bold, margin_l, W)
        y[0] -= 2
        y[0] = _paragraph(pdf, resume, y[0], font_reg, font_italic,
                          margin_l, content_w, 9.5, _hex(TEXT))
        y[0] -= 6

    objectifs = report_data.get("objectifs") or []
    if objectifs:
        ensure_space(35)
        y[0] = _section_title(pdf, "Objectifs pédagogiques", y[0], font_bold, margin_l, W)
        y[0] = _draw_list(pdf, objectifs, y[0], font_reg, margin_l, content_w, ensure_space, y)
        y[0] -= 5

    methods = report_data.get("methodes_pedagogiques") or []
    tools = report_data.get("outils") or []
    if methods or tools:
        ensure_space(45)
        y[0] = _section_title(pdf, "Démarche et moyens pédagogiques", y[0], font_bold, margin_l, W)
        for label, values in (("Méthodes", methods), ("Outils et supports", tools)):
            if values:
                y[0] = _paragraph(pdf, f"{label} : {', '.join(map(str, values))}", y[0], font_reg, font_italic, margin_l, content_w, 9)
        y[0] -= 5

    schedule = report_data.get("deroulement") or []
    if schedule:
        ensure_space(45)
        y[0] = _section_title(pdf, "Déroulement de la formation", y[0], font_bold, margin_l, W)
        y[0] = _draw_table(pdf, ["Date", "Horaires", "Durée", "Thème / séquence"], [
            [item.get("date", "—"), item.get("horaires", "—"), item.get("duree", "—"), item.get("theme") or "Thème non renseigné"]
            for item in schedule
        ], y[0], font_reg, font_bold, margin_l, content_w, ensure_space, y, [0.16, 0.20, 0.13, 0.51])
        y[0] -= 5

    # ── 2. Statistiques participants ──────────────────────────
    stats = report_data.get("statistiques_participants", {})
    if stats:
        ensure_space(50)
        y[0] = _section_title(pdf, "Statistiques des participants", y[0], font_bold, margin_l, W)
        kpis = [
            ("Inscrits", str(stats.get("total_inscrits", "—"))),
            ("Présents", str(stats.get("total_presents", "—"))),
            ("Taux présence", str(stats.get("taux_presence_moyen", "—"))),
        ]
        y[0] = _kpi_row(pdf, kpis, y[0], margin_l, content_w, font_bold, font_reg)
        commentaire = stats.get("commentaire", "")
        if commentaire:
            y[0] = _paragraph(pdf, commentaire, y[0], font_reg, font_italic,
                              margin_l, content_w, 9)
        entreprises = stats.get("entreprises", [])
        if entreprises:
            y[0] -= 3
            pdf.setFont(font_bold, 8)
            pdf.setFillColor(_hex(SLATE))
            pdf.drawString(margin_l, y[0], "Entreprises / organisations :")
            y[0] -= 11
            pdf.setFont(font_reg, 8.5)
            pdf.setFillColor(_hex(TEXT))
            pdf.drawString(margin_l + 4 * mm, y[0], "  ·  ".join(entreprises[:8]))
            y[0] -= 8
        y[0] -= 6

    roster = report_data.get("participants") or []
    if roster:
        ensure_space(45)
        y[0] = _section_title(pdf, "Liste des participants et assiduité", y[0], font_bold, margin_l, W)
        y[0] = _draw_table(pdf, ["Participant", "Fonction", "Organisation", "Présence"], [
            [item.get("nom", "—"), item.get("fonction") or "—", item.get("entreprise") or "—", item.get("taux_presence_affiche", "—")]
            for item in roster
        ], y[0], font_reg, font_bold, margin_l, content_w, ensure_space, y, [0.30, 0.22, 0.30, 0.18])
        y[0] -= 5

    # ── 3. Analyse des niveaux ────────────────────────────────
    niveaux = report_data.get("analyse_niveaux", {})
    if niveaux:
        ensure_space(55)
        y[0] = _section_title(pdf, "Analyse des niveaux", y[0], font_bold, margin_l, W)
        avant = niveaux.get("avant", {})
        apres = niveaux.get("apres", {})
        progression = niveaux.get("progression_globale", "")
        commentaire = niveaux.get("commentaire", "")

        if avant.get("score_moyen") is not None or apres.get("score_moyen") is not None:
            y[0] = _kpi_row(pdf, [
                ("Score moyen avant", f"{avant.get('score_moyen', '—')} / 100"),
                ("Score moyen après", f"{apres.get('score_moyen', '—')} / 100"),
                ("Participants avec scores complets", str(report_data.get("nb_scores_complets", "—"))),
            ], y[0], margin_l, content_w, font_bold, font_reg)
        else:
            # Compatibilité avec les anciens rapports contenant les répartitions par niveau.
            col = content_w / 4
            headers = ["", "Avant", "Après", "Progression"]
            for i, h in enumerate(headers):
                px = margin_l + i * col
                pdf.setFillColor(_hex(NAVY) if i == 0 else _hex(LIGHT_BG))
                pdf.rect(px, y[0] - 10, col, 12, fill=1, stroke=0)
                pdf.setFont(font_bold, 7.5)
                pdf.setFillColor(_hex(WHITE) if i == 0 else _hex(SLATE))
                pdf.drawCentredString(px + col / 2, y[0] - 7, h)
            y[0] -= 10
            for key, label in (("debutants", "Débutants"), ("intermediaires", "Intermédiaires"), ("avances", "Avancés")):
                av = avant.get(key, "—")
                ap = apres.get(key, "—")
                is_odd = label == "Intermédiaires"
                for i, val in enumerate(["", av, ap, ""]):
                    px = margin_l + i * col
                    pdf.setFillColor(_hex("#EEF2FF") if is_odd else _hex(WHITE))
                    pdf.rect(px, y[0] - 10, col, 11, fill=1, stroke=0)
                    pdf.setFont(font_bold if i == 0 else font_reg, 8)
                    pdf.setFillColor(_hex(TEXT))
                    txt = label if i == 0 else (val if i < 3 else "")
                    pdf.drawCentredString(px + col / 2, y[0] - 7, txt)
                y[0] -= 11

        if progression:
            pdf.setFont(font_bold, 9)
            pdf.setFillColor(_hex(GOLD))
            pdf.drawString(margin_l, y[0] - 10, f"Progression globale : {progression}")
            y[0] -= 23

        if commentaire:
            y[0] = _paragraph(pdf, commentaire, y[0] - 2, font_reg, font_italic,
                              margin_l, content_w, 9)
        y[0] -= 6

    individual = report_data.get("resultats_individuels") or []
    if individual:
        ensure_space(45)
        y[0] = _section_title(pdf, "Résultats individuels des acquis", y[0], font_bold, margin_l, W)
        y[0] = _draw_table(pdf, ["Participant", "Avant", "Après", "Évolution"], [
            [item.get("nom", "—"), item.get("score_avant_affiche", "—"), item.get("score_apres_affiche", "—"), item.get("progression_affiche", "—")]
            for item in individual
        ], y[0], font_reg, font_bold, margin_l, content_w, ensure_space, y, [0.40, 0.18, 0.18, 0.24])
        y[0] -= 5

    observations = report_data.get("observations_formateur")
    if observations:
        ensure_space(45)
        y[0] = _section_title(pdf, "Observations du formateur", y[0], font_bold, margin_l, W)
        y[0] = _paragraph(pdf, str(observations), y[0], font_reg, font_italic, margin_l, content_w, 9)
        y[0] -= 5

    # ── 4. Satisfaction ───────────────────────────────────────
    satisfaction = report_data.get("satisfaction", {})
    if satisfaction:
        ensure_space(240)
        y[0] = _section_title(pdf, "Résultats de satisfaction", y[0], font_bold, margin_l, W)
        notes = [
            ("Globale", satisfaction.get("note_globale", "—")),
            ("Formateur", satisfaction.get("note_formateur", "—")),
            ("Contenu", satisfaction.get("note_contenu", "—")),
            ("Supports", satisfaction.get("note_supports", "—")),
            ("Organisation", satisfaction.get("note_organisation", "—")),
        ]
        y[0] = _kpi_row(pdf, notes[:3], y[0], margin_l, content_w, font_bold, font_reg)
        y[0] = _kpi_row(pdf, notes[3:], y[0], margin_l + content_w / 3, content_w * 2 / 3, font_bold, font_reg)

        taux_reco = satisfaction.get("taux_recommandation", "")
        if taux_reco:
            pdf.setFont(font_italic, 8.5)
            pdf.setFillColor(_hex(SLATE))
            pdf.drawString(margin_l, y[0], f"Taux de recommandation : {taux_reco}")
            y[0] -= 12
        response_count = satisfaction.get("nb_reponses")
        if response_count is not None:
            pdf.setFont(font_italic, 8)
            pdf.setFillColor(_hex(SLATE))
            pdf.drawString(margin_l, y[0], f"Questionnaires exploités : {response_count}")
            y[0] -= 12

        points_forts = satisfaction.get("points_forts", [])
        axes = satisfaction.get("axes_amelioration", [])
        if points_forts or axes:
            col_w2 = content_w / 2 - 3 * mm
            # Points forts
            if points_forts:
                y[0] -= 2
                pdf.setFillColor(_hex("#ECFDF5"))
                pdf.rect(margin_l, y[0] - len(points_forts) * 12 - 16, col_w2, len(points_forts) * 12 + 16, fill=1, stroke=0)
                pdf.setFont(font_bold, 8)
                pdf.setFillColor(_hex(EMERALD))
                pdf.drawString(margin_l + 3 * mm, y[0] - 10, "Points forts")
                cy = y[0] - 22
                for point in points_forts[:4]:
                    pdf.setFont(font_reg, 8)
                    pdf.setFillColor(_hex(TEXT))
                    for line in _wrap_text(f"• {point}", font_reg, 8, col_w2 - 6 * mm, pdf):
                        pdf.drawString(margin_l + 4 * mm, cy, line)
                        cy -= 11
            # Axes d'amélioration
            if axes:
                ax = margin_l + col_w2 + 6 * mm
                ay = y[0]
                pdf.setFillColor(_hex("#FFF7ED"))
                pdf.rect(ax, ay - len(axes) * 12 - 16, col_w2, len(axes) * 12 + 16, fill=1, stroke=0)
                pdf.setFont(font_bold, 8)
                pdf.setFillColor(_hex(GOLD))
                pdf.drawString(ax + 3 * mm, ay - 10, "Axes d'amélioration")
                cy2 = ay - 22
                for axe in axes[:4]:
                    pdf.setFont(font_reg, 8)
                    pdf.setFillColor(_hex(TEXT))
                    for line in _wrap_text(f"— {axe}", font_reg, 8, col_w2 - 6 * mm, pdf):
                        pdf.drawString(ax + 4 * mm, cy2, line)
                        cy2 -= 11
            drop = max(len(points_forts), len(axes)) * 12 + 22
            y[0] -= drop + 6

        y[0] -= 4

    # ── 5. Recommandations ────────────────────────────────────
    recos = report_data.get("recommandations_formateur") or report_data.get("recommandations", [])
    if recos:
        ensure_space(len(recos) * 20 + 20)
        y[0] = _section_title(pdf, "Recommandations", y[0], font_bold, margin_l, W)
        for i, reco in enumerate(recos, 1):
            ensure_space(22)
            # Badge numéroté
            pdf.setFillColor(_hex(NAVY))
            pdf.circle(margin_l + 5, y[0] - 5, 5, fill=1, stroke=0)
            pdf.setFont(font_bold, 7)
            pdf.setFillColor(_hex(WHITE))
            pdf.drawCentredString(margin_l + 5, y[0] - 7.5, str(i))
            # Texte
            pdf.setFont(font_reg, 9)
            pdf.setFillColor(_hex(TEXT))
            reco_lines = _wrap_text(str(reco), font_reg, 9, content_w - 12 * mm, pdf)
            for j, line in enumerate(reco_lines):
                pdf.drawString(margin_l + 12 * mm, y[0] - 5 - j * 12, line)
            y[0] -= len(reco_lines) * 12 + 6
        y[0] -= 4

    # ── 6. Conclusion ─────────────────────────────────────────
    conclusion = report_data.get("conclusion", "")
    if conclusion:
        ensure_space(50)
        y[0] = _section_title(pdf, "Conclusion", y[0], font_bold, margin_l, W)
        y[0] = _paragraph(pdf, conclusion, y[0], font_reg, font_italic,
                          margin_l, content_w, 9.5, _hex(TEXT))
        y[0] -= 6

    # ── 7. Bloc signature ─────────────────────────────────────
    ensure_space(110)
    y[0] -= 10
    sig_x = W - margin_r - 55 * mm
    pdf.setFillColor(_hex(LIGHT_BG))
    pdf.rect(sig_x, y[0] - 35 * mm, 55 * mm, 35 * mm, fill=1, stroke=0)
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(sig_x, y[0] - 35 * mm, 55 * mm, 2, fill=1, stroke=0)
    pdf.setFont(font_bold, 8)
    pdf.setFillColor(_hex(NAVY))
    pdf.drawCentredString(sig_x + 27.5 * mm, y[0] - 10, "ALTIORA PREST")
    pdf.setFont(font_reg, 7.5)
    pdf.setFillColor(_hex(SLATE))
    pdf.drawCentredString(sig_x + 27.5 * mm, y[0] - 20, "Validation de la Direction")

    # Footer dernière page
    _draw_footer(pdf, font_reg, font_italic, page_num[0], W, H, margin_l)

    pdf.save()
    return buf.getvalue()


# ─── Helpers de mise en page ──────────────────────────────────

def _section_title(pdf, text: str, y: float, font_bold: str, ml: float, W: float) -> float:
    from reportlab.lib.units import mm
    # Fond navy + texte blanc
    pdf.setFillColor(_hex(NAVY))
    pdf.rect(ml - 2, y - 11, W - ml * 2 + 4, 14, fill=1, stroke=0)
    # Accent or gauche
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(ml - 2, y - 11, 3, 14, fill=1, stroke=0)
    pdf.setFont(font_bold, 9.5)
    pdf.setFillColor(_hex(WHITE))
    pdf.drawString(ml + 5, y - 7, text.upper())
    return y - 20


def _paragraph(pdf, text: str, y: float, font_reg: str, font_italic: str,
               ml: float, cw: float, size: float = 9.5, color=None) -> float:
    if color is None:
        color = _hex(TEXT)
    pdf.setFont(font_reg, size)
    pdf.setFillColor(color)
    for line in _wrap_text(text, font_reg, size, cw, pdf):
        pdf.drawString(ml, y, line)
        y -= size * 1.45
    return y


def _kpi_row(pdf, kpis: list, y: float, ml: float, cw: float,
             font_bold: str, font_reg: str) -> float:
    n = len(kpis)
    if n == 0:
        return y
    col = cw / n
    for i, (label, value) in enumerate(kpis):
        px = ml + i * col
        pdf.setFillColor(_hex(LIGHT_BG))
        pdf.rect(px, y - 36, col - 3, 38, fill=1, stroke=0)
        pdf.setFillColor(_hex(GOLD))
        pdf.rect(px, y - 36, col - 3, 2, fill=1, stroke=0)
        pdf.setFont(font_bold, 14)
        pdf.setFillColor(_hex(NAVY))
        pdf.drawCentredString(px + (col - 3) / 2, y - 14, str(value))
        pdf.setFont(font_reg, 7)
        pdf.setFillColor(_hex(SLATE))
        pdf.drawCentredString(px + (col - 3) / 2, y - 29, str(label))
    return y - 44


def _draw_list(pdf, values, y, font_reg, ml, cw, ensure_space, state):
    for value in values:
        lines = _wrap_text(f"• {value}", font_reg, 9, cw, pdf)
        ensure_space(len(lines) * 13 + 3)
        y = state[0]
        for line in lines:
            pdf.setFont(font_reg, 9)
            pdf.setFillColor(_hex(TEXT))
            pdf.drawString(ml + 2, y, line)
            y -= 13
            state[0] = y
        y -= 2
        state[0] = y
    return y


def _draw_table(pdf, headers, rows, y, font_reg, font_bold, ml, cw, ensure_space, state, ratios):
    from reportlab.lib.units import mm

    widths = [cw * ratio for ratio in ratios]

    def draw_header(y_pos):
        pdf.setFillColor(_hex(NAVY))
        pdf.rect(ml, y_pos - 17, cw, 18, fill=1, stroke=0)
        x = ml
        for label, width in zip(headers, widths):
            pdf.setFont(font_bold, 7)
            pdf.setFillColor(_hex(WHITE))
            pdf.drawString(x + 4, y_pos - 11, label[:28])
            x += width
        return y_pos - 20

    y = draw_header(y)
    state[0] = y
    for row_index, row in enumerate(rows):
        wrapped = [_wrap_text(str(value or "—"), font_reg, 7.2, max(16, width - 8), pdf) for value, width in zip(row, widths)]
        row_height = max(14, max(map(len, wrapped)) * 9 + 5)
        if y - row_height < 18 * mm:
            ensure_space(row_height + 20)
            y = state[0]
            y = draw_header(y)
        if row_index % 2 == 0:
            pdf.setFillColor(_hex(LIGHT_BG))
            pdf.rect(ml, y - row_height + 3, cw, row_height, fill=1, stroke=0)
        x = ml
        for lines, width in zip(wrapped, widths):
            pdf.setFont(font_reg, 7.2)
            pdf.setFillColor(_hex(TEXT))
            for line_index, line in enumerate(lines):
                pdf.drawString(x + 4, y - 8 - line_index * 9, line)
            x += width
        y -= row_height
        state[0] = y
    return y - 4


def _draw_running_header(pdf, font_bold: str, font_italic: str,
                          W: float, H: float, ml: float, logo, titre: str):
    from reportlab.lib.units import mm
    pdf.setFillColor(_hex(NAVY))
    pdf.rect(0, H - 12 * mm, W, 12 * mm, fill=1, stroke=0)
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(0, H - 12 * mm - 1.5, W, 1.5, fill=1, stroke=0)
    if logo:
        pdf.drawImage(logo, ml, H - 11 * mm, width=22 * mm, height=8 * mm,
                      preserveAspectRatio=True, anchor="nw", mask="auto")
    pdf.setFont(font_bold, 8)
    pdf.setFillColor(_hex(WHITE))
    short = titre[:70] + ("…" if len(titre) > 70 else "")
    pdf.drawCentredString(W / 2, H - 8 * mm, short)


def _draw_footer(pdf, font_reg: str, font_italic: str,
                 page_num: int, W: float, H: float, ml: float):
    from reportlab.lib.units import mm
    pdf.setFillColor(_hex(LIGHT_BG))
    pdf.rect(0, 0, W, 10 * mm, fill=1, stroke=0)
    pdf.setFillColor(_hex(GOLD))
    pdf.rect(0, 10 * mm, W, 1, fill=1, stroke=0)
    pdf.setFont(font_reg, 7)
    pdf.setFillColor(_hex(SLATE))
    pdf.drawString(ml, 6, "ALTIORA PREST — Document confidentiel")
    pdf.drawRightString(W - ml, 6, f"Page {page_num}")
