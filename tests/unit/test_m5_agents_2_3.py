"""
Tests automatiques des Agents 2 (niveaux) et 3 (satisfaction) du M5.

Jusqu'ici ces agents n'étaient couverts que par des scripts manuels
(scripts/test_agent2.py, test_agent3.py) qui appellent Groq pour de vrai,
n'ont aucune assertion et écrivent dans le VRAI store HITL. La suite pytest
restait verte alors que pandas n'était même pas installé.

Ici : faux LLM (aucun appel réseau), store HITL dans un dossier temporaire,
et les valeurs des scripts recalculées à la main :
  Agent 2 : avant 60/40/20/100 → 55.0 ; après 100/100/60/100 → 90.0
  Agent 3 : notes 4.33 / 4.83 / 4.17 / 3.83 / 4.33, recommandation 5/6 = 83 %

Exécution :
    python -m pytest tests/unit/test_m5_agents_2_3.py -q
"""

import asyncio
import json

import pytest

from app.services.formations.level_analyzer_service import LevelAnalyzerService
from app.services.formations.satisfaction_analyzer_service import (
    SatisfactionAnalyzerService,
)
from app.services.hitl import hitl_helper


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    """Aucune review de test dans le vrai store data/hitl_reviews.json."""
    chemin = tmp_path / "hitl_reviews.json"
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", chemin)
    return chemin


class FauxLLM:
    """Faux LLMProvider (interface app.services.llm.LLMProvider.generate)."""

    def __init__(self, contenu=None, finish="stop", erreur=None):
        self.contenu = contenu
        self.finish = finish
        self.erreur = erreur
        self.appels = 0

    async def generate(self, system_prompt, user_prompt, temperature=0.4,
                       max_tokens=4000, json_mode=True, reasoning_effort=None,
                       timeout=None):
        self.appels += 1
        if self.erreur:
            raise self.erreur
        contenu = self.contenu if isinstance(self.contenu, str) else json.dumps(self.contenu)
        return {"content": contenu, "finish_reason": self.finish,
                "usage": {}, "model": "faux", "provider": "faux"}


# ============================================================
# Données des scripts (mêmes valeurs que scripts/test_agent2.py et test_agent3.py)
# ============================================================

SESSION = {"id": 1, "titre": "Introduction à l'IA", "domaine": "IA"}
CORRIGE = {"av_01": "A", "av_02": "B", "av_03": "C", "av_04": "B", "av_05": "B"}
PARTICIPANTS = [
    {"nom": "Jean Dupont",
     "reponses_avant": {"av_01": "A", "av_02": "B", "av_03": "A", "av_04": "B", "av_05": "A"},
     "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"}},
    {"nom": "Marie Rasoa",
     "reponses_avant": {"av_01": "A", "av_02": "A", "av_03": "A", "av_04": "B", "av_05": "A"},
     "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"}},
    {"nom": "Paul Andry",
     "reponses_avant": {"av_01": "A", "av_02": "A", "av_03": "A", "av_04": "A", "av_05": "A"},
     "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "A", "ap_04": "B", "ap_05": "A"}},
    {"nom": "Sophie R.",
     "reponses_avant": {"av_01": "A", "av_02": "B", "av_03": "C", "av_04": "B", "av_05": "B"},
     "reponses_apres": {"ap_01": "A", "ap_02": "B", "ap_03": "C", "ap_04": "B", "ap_05": "B"}},
]


def reponse_enquete(globale, formateur, contenu, supports, orga, reco, **texte):
    return {"note_globale": globale, "note_formateur": formateur,
            "note_contenu": contenu, "note_supports": supports,
            "note_organisation": orga, "recommandation": reco,
            "points_forts": "", "points_faibles": "", "suggestions": "", **texte}


REPONSES = [
    reponse_enquete(5, 5, 4, 4, 5, "Oui", points_forts="Formateur excellent"),
    reponse_enquete(4, 5, 4, 3, 4, "Oui", points_faibles="Supports PDF denses"),
    reponse_enquete(5, 5, 5, 4, 5, "Oui"),
    reponse_enquete(3, 4, 3, 3, 3, "Peut-être", points_faibles="Trop rapide"),
    reponse_enquete(4, 5, 4, 4, 4, "Oui"),
    reponse_enquete(5, 5, 5, 5, 5, "Oui"),
]


@pytest.fixture
def niveaux():
    service = LevelAnalyzerService()
    service.llm = None                     # jamais de vrai appel Groq
    return service


@pytest.fixture
def satisfaction():
    service = SatisfactionAnalyzerService()
    service.llm = None
    return service


# ============================================================
# AGENT 2 — calculs déterministes (pandas)
# ============================================================

def test_agent2_statistiques_du_scenario_de_reference(niveaux):
    stats = niveaux._compute_statistics(PARTICIPANTS, CORRIGE)

    assert stats["statistiques"] == {
        "score_moyen_avant": 55.0, "score_moyen_apres": 90.0,
        "progression_absolue": 35.0, "progression_relative": "63.6%",
        "nb_participants": 4,
    }
    assert stats["cas_remarquables"]["meilleure_progression"] == {
        "nom": "Marie Rasoa", "avant": 40.0, "apres": 100.0, "gain": 60.0}
    assert [p["nom"] for p in stats["cas_remarquables"]["progressions_faibles"]] == ["Sophie R."]


def test_agent2_distribution_avant_et_apres(niveaux):
    stats = niveaux._compute_statistics(PARTICIPANTS, CORRIGE)

    avant, apres = stats["distribution_avant"], stats["distribution_apres"]
    assert (avant["debutants"]["nb"], avant["intermediaires"]["nb"], avant["avances"]["nb"]) == (1, 2, 1)
    assert (apres["debutants"]["nb"], apres["intermediaires"]["nb"], apres["avances"]["nb"]) == (0, 1, 3)
    assert apres["avances"]["pourcentage"] == "75%"


@pytest.mark.parametrize("score, attendu", [
    (39.9, "debutants"), (40.0, "intermediaires"),
    (69.9, "intermediaires"), (70.0, "avances"),
])
def test_agent2_seuils_de_niveau(niveaux, score, attendu):
    distribution = niveaux._distribution([score])

    assert distribution[attendu]["nb"] == 1


def test_agent2_score_normalise_ap_en_av_et_ignore_la_casse(niveaux):
    corrige = {"av_01": "A", "av_02": "B"}

    assert niveaux._score({"ap_01": "a", "ap_02": " b "}, corrige) == 100.0
    assert niveaux._score({"av_01": "A"}, corrige) == 50.0          # réponse manquante
    assert niveaux._score({"av_01": "A"}, {}) == 0.0                # corrigé vide


def test_agent2_sans_participant_statistiques_vides(niveaux):
    stats = niveaux._compute_statistics([], CORRIGE)

    assert stats["statistiques"]["nb_participants"] == 0
    assert stats["cas_remarquables"]["meilleure_progression"] is None


# ============================================================
# AGENT 2 — analyse complète, LLM, repli, HITL
# ============================================================

def test_agent2_sans_llm_utilise_le_gabarit_python(niveaux):
    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["statistiques"]["score_moyen_apres"] == 90.0
    assert resultat["recommandations"]


def test_agent2_le_llm_redige_mais_ne_change_pas_les_chiffres(niveaux):
    niveaux.llm = FauxLLM({
        "resume": "Bonne progression.",
        "interpretation": "Le groupe a progressé.",
        "recommandations": [f"reco {i}" for i in range(8)],
        "statistiques": {"score_moyen_apres": 12.0},            # tentative de réécriture
    })

    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    assert resultat["metadata"]["source"] == "llm"
    assert resultat["resume"] == "Bonne progression."
    assert len(resultat["recommandations"]) == 5                # plafonné à 5
    assert resultat["statistiques"]["score_moyen_apres"] == 90.0  # calcul Python intact


def test_agent2_accepte_les_cles_alternatives_du_llm(niveaux):
    niveaux.llm = FauxLLM({"summary": "S", "analysis": "A",
                              "recommendations": {"a": "r1", "b": "r2"}})

    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    assert resultat["recommandations"] == ["r1", "r2"]
    assert resultat["resume"] == "S" and resultat["interpretation"] == "A"


@pytest.mark.parametrize("faux", [
    FauxLLM(erreur=RuntimeError("quota")),
    FauxLLM("pas du json"),
    FauxLLM({"recommandations": ["x"]}, finish="length"),       # réponse tronquée
])
def test_agent2_llm_en_echec_bascule_sur_le_gabarit(niveaux, faux):
    niveaux.llm = faux

    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["success"] is True and resultat["recommandations"]


def test_agent2_llm_sans_recommandation_complete_avec_le_gabarit(niveaux):
    niveaux.llm = FauxLLM({"resume": "Résumé LLM", "recommandations": []})

    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    assert resultat["resume"] == "Résumé LLM"                   # conservé
    assert resultat["recommandations"]                          # complété


def test_agent2_cree_une_review_hitl_dans_le_store_temporaire(niveaux, store_hitl_temporaire):
    resultat = run(niveaux.analyze(SESSION, PARTICIPANTS, CORRIGE))

    review = hitl_helper.get_review(resultat["_review_id"])
    assert resultat["_review_id"].startswith("HITL-A2L-")
    assert resultat["_review_status"] == "pending_review"
    assert review["agent_id"] == "agent_2_levels" and review["criticity"] == "medium"
    assert store_hitl_temporaire.exists()                       # le vrai store n'est pas touché


# ---- Défauts CONNUS du gabarit de repli (agent stabilisé : documentés, non corrigés) ----

@pytest.mark.xfail(strict=True, reason=(
    "Gabarit Agent 2 : écrit '+{progression}' sans gérer le négatif "
    "→ 'progression moyenne de +-10.0 points'"))
def test_agent2_gabarit_progression_negative_bien_formatee(niveaux):
    participants = [{"nom": "A",
                     "reponses_avant": {"av_01": "A", "av_02": "B"},
                     "reponses_apres": {"ap_01": "X", "ap_02": "B"}}]
    stats = niveaux._compute_statistics(participants, {"av_01": "A", "av_02": "B"})

    assert "+-" not in niveaux._generate_with_template(stats)["resume"]


@pytest.mark.xfail(strict=True, reason=(
    "Gabarit Agent 2 : `len(pourcentage) > 0` est toujours vrai → recommande un "
    "'module avancé' même quand 0 % des participants sont avancés"))
def test_agent2_gabarit_pas_de_module_avance_sans_participant_avance(niveaux):
    participants = [{"nom": "A",
                     "reponses_avant": {"av_01": "X"}, "reponses_apres": {"ap_01": "X"}}]
    stats = niveaux._compute_statistics(participants, {"av_01": "A"})

    recos = niveaux._generate_with_template(stats)["recommandations"]
    assert not any("module avancé" in r for r in recos)


# ============================================================
# AGENT 3 — calculs déterministes (pandas)
# ============================================================

def test_agent3_statistiques_du_scenario_de_reference(satisfaction):
    s = satisfaction._compute_statistics(REPONSES)["statistiques"]

    assert s["notes"] == {"note_globale": 4.33, "note_formateur": 4.83,
                          "note_contenu": 4.17, "note_supports": 3.83,
                          "note_organisation": 4.33}
    assert (s["taux_recommandation"], s["nb_recommandent"],
            s["nb_neutres"], s["nb_deconseillent"], s["nb_reponses"]) == ("83%", 5, 1, 0, 6)


@pytest.mark.parametrize("valeur, oui, peut, non", [
    ("Oui", 1, 0, 0), (" OUI ", 1, 0, 0),
    ("Peut-être", 0, 1, 0), ("peut etre", 0, 1, 0),
    ("Non", 0, 0, 1), ("", 0, 0, 0), ("Bof", 0, 0, 0),
])
def test_agent3_lecture_des_recommandations(satisfaction, valeur, oui, peut, non):
    s = satisfaction._compute_statistics([reponse_enquete(4, 4, 4, 4, 4, valeur)])["statistiques"]

    assert (s["nb_recommandent"], s["nb_neutres"], s["nb_deconseillent"]) == (oui, peut, non)


def test_agent3_taux_a_zero_si_personne_ne_repond_a_la_question(satisfaction):
    s = satisfaction._compute_statistics([reponse_enquete(4, 4, 4, 4, 4, "")])["statistiques"]

    assert s["taux_recommandation"] == "0%"


def test_agent3_notes_absentes_ou_vides_ne_faussent_pas_la_moyenne(satisfaction):
    reponses = [{"note_globale": 4}, {"note_globale": None}, {"note_globale": 2}]

    notes = satisfaction._compute_statistics(reponses)["statistiques"]["notes"]

    assert notes["note_globale"] == 3.0                         # None ignoré
    assert notes["note_formateur"] == 0.0                       # colonne absente


def test_agent3_sans_reponse_pas_d_appel_llm(satisfaction):
    faux = FauxLLM({"points_forts": ["x"], "recommandations": ["y"]})
    satisfaction.llm = faux

    resultat = run(satisfaction.analyze(SESSION, []))

    assert faux.appels == 0
    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["statistiques"]["nb_reponses"] == 0


# ============================================================
# AGENT 3 — analyse complète, LLM, repli, HITL
# ============================================================

def test_agent3_sans_llm_utilise_le_gabarit_python(satisfaction):
    resultat = run(satisfaction.analyze(SESSION, REPONSES))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["statistiques"]["taux_recommandation"] == "83%"
    assert resultat["points_forts"] and resultat["recommandations"]


def test_agent3_le_llm_redige_mais_ne_change_pas_les_chiffres(satisfaction):
    satisfaction.llm = FauxLLM({
        "resume": "Très bien reçu.",
        "points_forts": ["a", "b", "c", "d", "e"],
        "axes_amelioration": ["x", "y", "z", "w"],
        "themes_recurrents": [
            {"theme": "Formateur", "frequence": "élevée", "sentiment": "positif"},
            {"theme": "Sans détails"},
            {"pas_un_theme": True},
            "texte",
        ],
        "recommandations": [f"r{i}" for i in range(9)],
        "interpretation": "OK",
        "statistiques": {"notes": {"note_globale": 1.0}},        # tentative de réécriture
    })

    resultat = run(satisfaction.analyze(SESSION, REPONSES))

    assert resultat["metadata"]["source"] == "llm"
    assert resultat["statistiques"]["notes"]["note_globale"] == 4.33   # calcul Python intact
    assert len(resultat["points_forts"]) == 3
    assert len(resultat["axes_amelioration"]) == 3
    assert len(resultat["recommandations"]) == 5
    assert resultat["themes_recurrents"] == [
        {"theme": "Formateur", "frequence": "élevée", "sentiment": "positif"},
        {"theme": "Sans détails", "frequence": "moyenne", "sentiment": "neutre"},
    ]


@pytest.mark.parametrize("faux", [
    FauxLLM(erreur=RuntimeError("quota")),
    FauxLLM("{pas du json"),
    FauxLLM({"points_forts": ["x"]}, finish="length"),
])
def test_agent3_llm_en_echec_bascule_sur_le_gabarit(satisfaction, faux):
    satisfaction.llm = faux

    resultat = run(satisfaction.analyze(SESSION, REPONSES))

    assert resultat["metadata"]["source"] == "fallback_template"
    assert resultat["success"] is True and resultat["points_forts"]


def test_agent3_llm_incomplet_est_complete_par_le_gabarit(satisfaction):
    satisfaction.llm = FauxLLM({"resume": "Résumé LLM", "points_forts": [],
                                   "recommandations": []})

    resultat = run(satisfaction.analyze(SESSION, REPONSES))

    assert resultat["metadata"]["source"] == "llm"
    assert resultat["resume"] == "Résumé LLM"
    assert resultat["points_forts"] and resultat["recommandations"]


def test_agent3_le_prompt_transmet_les_notes_calculees_et_les_feedbacks(satisfaction):
    faux = FauxLLM({"points_forts": ["x"], "recommandations": ["y"]})
    satisfaction.llm = faux
    envoye = {}
    origine = faux.generate

    async def espion(**kwargs):
        envoye.update(kwargs)
        return await origine(**kwargs)

    faux.generate = espion

    run(satisfaction.analyze(SESSION, REPONSES))

    prompt = envoye["user_prompt"]
    assert "4.33" in prompt                                     # note calculée par Python
    assert "Formateur excellent" in prompt and "Supports PDF denses" in prompt
    assert envoye["json_mode"] is True


def test_agent3_gabarit_signale_les_supports_faibles(satisfaction):
    stats = satisfaction._compute_statistics(REPONSES)

    axes = satisfaction._generate_with_template(stats)["axes_amelioration"]
    assert any("supports" in a.lower() for a in axes)           # note_supports 3.83 < 4


def test_agent3_cree_une_review_hitl_dans_le_store_temporaire(satisfaction, store_hitl_temporaire):
    resultat = run(satisfaction.analyze(SESSION, REPONSES))

    review = hitl_helper.get_review(resultat["_review_id"])
    assert resultat["_review_id"].startswith("HITL-A3S-")
    assert review["agent_id"] == "agent_3_satisfaction" and review["criticity"] == "medium"
    assert store_hitl_temporaire.exists()
