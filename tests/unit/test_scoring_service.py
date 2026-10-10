# tests/unit/test_scoring_service.py
# ============================================================
# Étape C (mission "Préparation soutenance") — reproductibilité du scoring
# ============================================================
# AVANT cette correction, ScoringService.score() utilisait
# datetime.now() EN DUR pour évaluer l'échéance ("dans 10 jours" ?
# "expirée" ?) -- rejouer le MÊME corpus annoté à des dates différentes
# (ex. le jour de l'annotation vs. le jour du benchmark officiel, des
# semaines plus tard) donnait un score différent pour la même opportunité,
# rendant le benchmark M1 non reproductible (le CDC exige une mesure
# fiable, pas un chiffre qui varie selon la date d'exécution).
#
# Aucun réseau, aucune donnée inventée : opportunités synthétiques
# minimales pour isoler le comportement de _score_deadline / score().
# ============================================================

from datetime import datetime

from app.services.veille import scoring_service as scoring_module
from app.services.veille.scoring_service import ScoringService

OPPORTUNITE = {
    "title": "Formation en intelligence artificielle",
    "summary": "Le Ministère recherche un formateur en IA pour 30 agents.",
    "url": "https://asako.mg/offre",
    "budget": "10 000 000 Ar",
    "deadline": "2026-10-01",
    "organizer": "Ministère de l'Économie",
    "domain": "ia",
}


def test_date_reference_par_defaut_utilise_maintenant_comportement_inchange():
    """Sans date_reference : comportement API inchangé (retro-compatible)."""
    service = ScoringService()
    resultat = service.score(dict(OPPORTUNITE))
    assert isinstance(resultat["score"], int)


def test_meme_corpus_meme_score_quelle_que_soit_la_date_reelle_du_jour(monkeypatch):
    """LE bug corrigé : passer explicitement date_reference rend le score
    indépendant de la vraie horloge système."""
    service = ScoringService()
    reference = datetime(2026, 9, 20)

    resultat_1 = service.score(dict(OPPORTUNITE), date_reference=reference)

    class HorlogeSysteme(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2027, 3, 1)  # "aujourd'hui" très différent

    monkeypatch.setattr(scoring_module, "datetime", HorlogeSysteme)
    resultat_2 = service.score(dict(OPPORTUNITE), date_reference=reference)

    assert resultat_1 == resultat_2


def test_date_reference_influe_reellement_sur_le_score_echeance():
    """Preuve que date_reference est bien PRISE EN COMPTE (pas ignorée) :
    la même échéance, évaluée à deux dates de référence différentes,
    donne des points d'échéance différents."""
    service = ScoringService()

    proche = service.score(dict(OPPORTUNITE), date_reference=datetime(2026, 9, 28))  # 3 jours avant
    lointain = service.score(dict(OPPORTUNITE), date_reference=datetime(2026, 7, 1))  # 3 mois avant
    expiree = service.score(dict(OPPORTUNITE), date_reference=datetime(2026, 10, 15))  # après l'échéance

    assert "Échéance (+10)" in proche["details"]       # < 7 jours
    assert "Échéance (+1)" in lointain["details"]       # > 60 jours
    assert "Échéance expirée (-10)" in expiree["details"]
