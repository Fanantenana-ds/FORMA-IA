"""
Tests de l'analyse IA d'une opportunité (scoring M1 branché sur la route
POST /opportunites/{id}/analyse) — service seul, sans base de données.

Aucun appel réseau : le LLM est remplacé par un faux, la sync Backend est
piégée pour prouver qu'elle n'est jamais appelée (elle recréerait
l'opportunité en doublon).

Exécution :
    python -m pytest tests/unit/test_analyse_ia.py -q
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models.opportunite import Domaine
from app.services.backend_sync import base_sync
from app.services.veille import opportunity_analysis_service as module
from app.services.veille.opportunity_analysis_service import OpportuniteAnalyseIAService

TEXTE_IA = (
    "Le Ministère de l'Économie à Antananarivo recherche un prestataire pour une "
    "formation IA et prompt engineering de 30 agents.\n"
    "Dossier complet disponible auprès du secrétariat de la direction générale."
)


@pytest.fixture(autouse=True)
def pas_de_backend(monkeypatch):
    """Garde-fou : l'analyse ne doit JAMAIS appeler le Backend."""
    async def interdit(*args, **kwargs):
        raise AssertionError("L'analyse ne doit pas appeler le Backend")

    monkeypatch.setattr(base_sync, "backend_request", interdit)


class FauxLLM:
    def __init__(self, reponse=None, erreur=None, delai=0.0):
        self.reponse = reponse
        self.erreur = erreur
        self.delai = delai
        self.appels = 0

    async def analyze(self, query, results):
        self.appels += 1
        if self.delai:
            await asyncio.sleep(self.delai)
        if self.erreur:
            raise self.erreur
        return self.reponse


def activer_llm(monkeypatch, faux):
    monkeypatch.setenv("ANALYSE_USE_LLM", "true")
    monkeypatch.setattr(module, "_creer_llm_service", lambda: faux)


@pytest.fixture
def service():
    return OpportuniteAnalyseIAService()


# ============================================================
# Score : échelle et cohérence
# ============================================================

def test_le_score_est_entre_0_et_1_et_divise_le_score_m1_par_100(service):
    resultat = service.analyser(contenu=TEXTE_IA)

    assert 0.0 <= resultat["score_pertinence"] <= 1.0
    assert resultat["score_pertinence"] == pytest.approx(resultat["score"] / 100)
    assert resultat["niveau"] and resultat["recommandation"]


def test_un_contenu_ia_pertinent_score_plus_qu_un_contenu_bureautique(service):
    ia = service.analyser(
        contenu=TEXTE_IA,
        budget=60_000_000.0,
        echeance=datetime.now(timezone.utc) + timedelta(days=10),
    )
    bureautique = service.analyser(contenu="Formation Excel et Word pour le personnel")

    assert ia["score_pertinence"] > 0.5
    assert ia["domaine"] == Domaine.IA
    assert bureautique["score_pertinence"] < 0.2
    assert bureautique["domaine"] == Domaine.BUREAUTIQUE


def test_le_budget_float_n_est_pas_gonfle_par_le_scoring(service):
    """
    "5000000.0" serait lu 50 000 000 par le scoring M1 (×10) : 5 M doit
    rapporter 5 points (tranche 5-20 M), pas 15.
    """
    resultat = service.analyser(contenu="Formation IA", budget=5_000_000.0)

    assert "Budget (+5)" in resultat["raisons"]
    assert "Budget (+15)" not in resultat["raisons"]


def test_une_echeance_expiree_penalise_le_score(service):
    en_cours = service.analyser(
        contenu=TEXTE_IA, echeance=datetime.now(timezone.utc) + timedelta(days=10)
    )
    expiree = service.analyser(
        contenu=TEXTE_IA, echeance=datetime.now(timezone.utc) - timedelta(days=10)
    )

    assert expiree["score"] < en_cours["score"]


# ============================================================
# Champs renseignés : jamais écrasés
# ============================================================

def test_le_domaine_saisi_prime_sur_la_classification(service):
    resultat = service.analyser(contenu=TEXTE_IA, domaine=Domaine.DATA)

    assert resultat["domaine"] == Domaine.DATA


def test_l_objet_saisi_est_conserve(service):
    resultat = service.analyser(contenu=TEXTE_IA, objet="Mon objet")

    assert resultat["objet"] == "Mon objet"


def test_sans_objet_le_titre_vient_de_la_premiere_ligne_du_contenu(service):
    resultat = service.analyser(contenu="\n\n  Formation IA pour la DSI  \nsuite du texte")

    assert resultat["objet"] == "Formation IA pour la DSI"


def test_l_objet_est_tronque_a_la_taille_de_la_colonne(service):
    resultat = service.analyser(contenu="x" * 1000)

    assert len(resultat["objet"]) == 255


def test_budget_et_echeance_saisis_sont_renvoyes_tels_quels(service):
    echeance = datetime(2026, 12, 1, tzinfo=timezone.utc)
    resultat = service.analyser(contenu=TEXTE_IA, budget=1234.5, echeance=echeance)

    assert resultat["budget"] == 1234.5
    assert resultat["echeance"] == echeance


def test_sans_budget_ni_echeance_les_valeurs_restent_vides(service):
    resultat = service.analyser(contenu=TEXTE_IA)

    assert resultat["budget"] is None
    assert resultat["echeance"] is None


# ============================================================
# Extraction LLM
# ============================================================

def test_llm_coupe_par_defaut_dans_les_tests_aucun_appel(monkeypatch, service):
    monkeypatch.setattr(
        module, "_creer_llm_service",
        lambda: (_ for _ in ()).throw(AssertionError("LLM appelé alors qu'il est coupé")),
    )

    resultat = service.analyser(contenu=TEXTE_IA)

    assert resultat["llm_utilise"] is False


def test_le_llm_complete_objet_budget_et_echeance_manquants(monkeypatch, service):
    faux = FauxLLM({"opportunities": [{
        "title": "Formation IA — Ministère de l'Économie",
        "budget": "60M Ar",
        "deadline": "2026-12-15",
        "organizer": "Ministère de l'Économie",
    }]})
    activer_llm(monkeypatch, faux)

    resultat = service.analyser(contenu=TEXTE_IA)

    assert faux.appels == 1
    assert resultat["llm_utilise"] is True
    assert resultat["objet"] == "Formation IA — Ministère de l'Économie"
    assert resultat["budget"] == 60_000_000.0
    assert resultat["echeance"] == datetime(2026, 12, 15, tzinfo=timezone.utc)
    assert "Organisme (+15)" in resultat["raisons"]        # ministère lu par le LLM
    assert "Budget (+15)" in resultat["raisons"]           # 60 M → tranche 50-100 M


def test_le_llm_n_ecrase_pas_les_valeurs_saisies(monkeypatch, service):
    activer_llm(monkeypatch, FauxLLM({"opportunities": [{
        "title": "Titre du LLM", "budget": "999M Ar", "deadline": "2030-01-01",
    }]}))
    echeance = datetime(2026, 12, 1, tzinfo=timezone.utc)

    resultat = service.analyser(
        contenu=TEXTE_IA, objet="Titre saisi", budget=1000.0, echeance=echeance
    )

    assert resultat["objet"] == "Titre saisi"
    assert resultat["budget"] == 1000.0
    assert resultat["echeance"] == echeance


@pytest.mark.parametrize("faux", [
    FauxLLM(erreur=RuntimeError("quota dépassé")),
    FauxLLM(reponse=None),
    FauxLLM(reponse={"opportunities": []}),
    FauxLLM(reponse={"opportunities": ["pas un dict"]}),
])
def test_llm_en_echec_ou_vide_degrade_en_python_pur(monkeypatch, service, faux):
    activer_llm(monkeypatch, faux)

    resultat = service.analyser(contenu=TEXTE_IA)

    assert resultat["llm_utilise"] is False
    assert 0.0 < resultat["score_pertinence"] <= 1.0


def test_llm_trop_lent_degrade_en_python_pur(monkeypatch, service):
    monkeypatch.setenv("ANALYSE_LLM_TIMEOUT", "0.05")
    activer_llm(monkeypatch, FauxLLM({"opportunities": [{"title": "Trop tard"}]}, delai=1.0))

    resultat = service.analyser(contenu=TEXTE_IA)

    assert resultat["llm_utilise"] is False
    assert resultat["objet"] != "Trop tard"


def test_construction_du_llm_impossible_degrade_en_python_pur(monkeypatch, service):
    monkeypatch.setenv("ANALYSE_USE_LLM", "true")

    def echec():
        raise FileNotFoundError("veille.yaml introuvable")

    monkeypatch.setattr(module, "_creer_llm_service", echec)

    resultat = service.analyser(contenu=TEXTE_IA)

    assert resultat["llm_utilise"] is False


# ============================================================
# Appel synchrone depuis une boucle asyncio déjà active
# ============================================================

def test_analyser_fonctionne_meme_depuis_une_boucle_asyncio_active(service):
    async def appelant():
        return service.analyser(contenu=TEXTE_IA)

    resultat = asyncio.run(appelant())

    assert resultat["score"] > 0
