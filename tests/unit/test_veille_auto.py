"""
Tests M1 — les deux modes d'obtention des opportunités :
  MODE 1  POST /ia/veille/rechercher   (requête saisie, existant)
  MODE 2  POST /ia/veille/detecter     (détection automatique, sans requête)

Aucun appel Tavily / Groq / Backend / base de données : orchestrateur simulé,
faux Backend, état de la détection redirigé vers un dossier temporaire.

Exécution :
    python -m pytest tests/unit/test_veille_auto.py -q
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import routes_veille
from app.orchestrator import veille_orchestrator as orch_module
from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.backend_sync import base_sync, opportunity_sync
from app.services.veille import auto_detection_service as auto

VARIABLES_AUTO = (
    "VEILLE_AUTO_ENABLED", "VEILLE_AUTO_INTERVAL_HOURS", "VEILLE_AUTO_QUERIES",
    "VEILLE_AUTO_MAX_QUERIES", "VEILLE_AUTO_MIN_SCORE", "VEILLE_AUTO_LIMIT",
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    """État de la détection dans un dossier temporaire, configuration par défaut."""
    monkeypatch.setattr(auto, "STATE_PATH", tmp_path / "veille_auto_state.json")
    monkeypatch.setattr(auto, "_en_cours", False)
    monkeypatch.setattr(auto, "_tache", None)
    monkeypatch.setattr(auto, "_demarre_a", None)
    for nom in VARIABLES_AUTO:
        monkeypatch.delenv(nom, raising=False)


def opp(titre, url, score, **extra):
    return {"title": titre, "url": url, "score": score, "summary": "", **extra}


class OrchestrateurSimule(VeilleOrchestrator):
    """Vrai orchestrateur dont seule la recherche par requête est simulée."""

    def __init__(self, reponses):
        super().__init__()
        self.reponses = reponses          # {requête: dict | Exception}
        self.appels = []

    async def analyser_opportunites(self, query, sync_backend=True):
        self.appels.append((query, sync_backend))
        reponse = self.reponses[query]
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def reponse(status="success", opps=()):
    return {"status": status, "opportunities": list(opps), "total": len(opps)}


@pytest.fixture
def espion_sync(monkeypatch):
    appels = []

    async def faux(opportunites):
        appels.append(list(opportunites))
        return {"enabled": True, "sent": len(opportunites), "failed": 0,
                "already_present": 0}

    monkeypatch.setattr(orch_module, "sync_new_opportunities_to_backend", faux)
    return appels


# ============================================================
# Configuration
# ============================================================

def test_profil_par_defaut_couvre_les_domaines_altiora():
    requetes = auto.get_queries()

    assert len(requetes) == 5
    texte = " ".join(requetes).lower()
    for mot in ("intelligence artificielle", "data", "devops", "développement"):
        assert mot in texte


def test_requetes_personnalisees_via_env(monkeypatch):
    monkeypatch.setenv("VEILLE_AUTO_QUERIES", " formation Excel ; audit SI ;; ")

    assert auto.get_queries() == ["formation Excel", "audit SI"]


def test_nombre_de_requetes_borne(monkeypatch):
    monkeypatch.setenv("VEILLE_AUTO_MAX_QUERIES", "2")

    assert len(auto.get_queries()) == 2


def test_valeurs_par_defaut_et_env_invalide(monkeypatch):
    assert (auto.score_minimum(), auto.limite(), auto.intervalle_heures()) == (40, 20, 24)
    assert auto.planification_activee() is False

    monkeypatch.setenv("VEILLE_AUTO_MIN_SCORE", "abc")
    monkeypatch.setenv("VEILLE_AUTO_INTERVAL_HOURS", "0")
    assert auto.score_minimum() == 40
    assert auto.intervalle_heures() == 1      # minimum 1 h : pas de boucle serrée


# ============================================================
# Orchestrateur — detecter_automatiquement
# ============================================================

def test_chaque_requete_est_lancee_sans_sync_puis_une_seule_sync_finale(espion_sync):
    orch = OrchestrateurSimule({
        "q1": reponse(opps=[opp("A", "https://a.mg", 80)]),
        "q2": reponse(opps=[opp("B", "https://b.mg", 60)]),
    })

    resultat = run(orch.detecter_automatiquement(["q1", "q2"]))

    assert orch.appels == [("q1", False), ("q2", False)]     # jamais de sync par requête
    assert len(espion_sync) == 1                              # une seule sync, à la fin
    assert [o["title"] for o in espion_sync[0]] == ["A", "B"]
    assert resultat["mode"] == "automatique"
    assert resultat["statistics"]["backend_sync"]["sent"] == 2


def test_fusion_dedoublonnage_tri_seuil_et_limite(espion_sync):
    orch = OrchestrateurSimule({
        "q1": reponse(opps=[opp("Formation IA", "https://a.mg", 70),
                            opp("Excel", "https://x.mg", 20)]),
        "q2": reponse(opps=[opp("Formation IA (bis)", "https://a.mg", 90),  # même URL
                            opp("Data", "https://d.mg", 55),
                            opp("DevOps", "https://o.mg", 45)]),
    })

    resultat = run(orch.detecter_automatiquement(
        ["q1", "q2"], min_score=40, limit=2))

    titres = [o["title"] for o in resultat["opportunities"]]
    assert titres == ["Formation IA (bis)", "Data"]           # meilleur score gardé, limite 2
    stats = resultat["statistics"]
    assert stats["collected"] == 5
    assert stats["after_dedup"] == 4                          # doublon d'URL fusionné
    assert stats["below_min_score"] == 1                      # « Excel » (20 < 40)
    assert resultat["opportunities"][0]["detected_by_query"] == "q2"


def test_une_requete_en_echec_n_interrompt_pas_les_suivantes(espion_sync):
    orch = OrchestrateurSimule({
        "q1": RuntimeError("Tavily HS"),
        "q2": reponse(opps=[opp("B", "https://b.mg", 60)]),
    })

    resultat = run(orch.detecter_automatiquement(["q1", "q2"]))

    assert resultat["status"] == "partial"
    assert resultat["total"] == 1
    assert resultat["queries"][0]["status"] == "error"
    assert "Tavily HS" not in json.dumps(resultat["queries"])  # pas de détail interne exposé


def test_toutes_les_requetes_en_echec_donne_degraded_sans_sync(espion_sync):
    orch = OrchestrateurSimule({
        "q1": RuntimeError("x"),
        "q2": reponse(status="degraded"),
    })

    resultat = run(orch.detecter_automatiquement(["q1", "q2"]))

    assert resultat["status"] == "degraded"
    assert resultat["total"] == 0
    assert espion_sync == []                                  # rien à envoyer


def test_aucun_resultat_n_est_pas_une_erreur(espion_sync):
    orch = OrchestrateurSimule({"q1": reponse(status="no_results")})

    resultat = run(orch.detecter_automatiquement(["q1"]))

    assert resultat["status"] == "success"
    assert resultat["total"] == 0


def test_sync_backend_false_donne_un_apercu_sans_envoi(espion_sync):
    orch = OrchestrateurSimule({"q1": reponse(opps=[opp("A", "https://a.mg", 80)])})

    resultat = run(orch.detecter_automatiquement(["q1"], sync_backend=False))

    assert espion_sync == []
    assert resultat["total"] == 1
    assert resultat["statistics"]["backend_sync"]["deferred"] is True


def test_sans_requete_configuree_erreur_explicite(espion_sync):
    resultat = run(OrchestrateurSimule({}).detecter_automatiquement(["", "  "]))

    assert resultat["status"] == "error"
    assert "requête" in resultat["notes"].lower()


# ============================================================
# Mode 1 inchangé : la sync par requête reste le comportement par défaut
# ============================================================

DONNEES_LLM = {
    "title": "Formateur IA — Ministère de l'Économie",
    "url": "https://asako.mg/offre-1",
    "summary": ("Le Ministère recherche un formateur en intelligence artificielle "
                "et prompt engineering à Antananarivo pour former 30 agents publics."),
    "budget": "60 000 000 Ar",
    "deadline": "2030-12-01",
    "organizer": "Ministère de l'Économie",
    "confidence": 0.8,
    "score": 70,
    "is_actionable": True,
}


def test_mode_recherche_synchronise_toujours_par_defaut(monkeypatch):
    envois = []

    async def faux_sync(opportunites):
        envois.append(list(opportunites))
        return {"enabled": True, "sent": len(opportunites), "failed": 0}

    monkeypatch.setattr(orch_module, "sync_opportunities_to_backend", faux_sync)

    resultat = run(VeilleOrchestrator()._finalize_opportunities(
        groq_opportunities=[dict(DONNEES_LLM)], groq_response={}, start_total=0.0))

    assert resultat["total"] == 1
    assert len(envois) == 1                                   # comportement du mode 1
    assert resultat["statistics"]["backend_sync"]["sent"] == 1


def test_finalisation_sans_sync_quand_demandee(monkeypatch):
    async def interdit(opportunites):
        raise AssertionError("sync interdite")

    monkeypatch.setattr(orch_module, "sync_opportunities_to_backend", interdit)

    resultat = run(VeilleOrchestrator()._finalize_opportunities(
        groq_opportunities=[dict(DONNEES_LLM)], groq_response={}, start_total=0.0,
        sync_backend=False))

    assert resultat["total"] == 1
    assert resultat["statistics"]["backend_sync"]["deferred"] is True


# ============================================================
# Sync sans doublons (opportunity_sync)
# ============================================================

class FauxBackend:
    def __init__(self, existantes=None, get_ok=True):
        self.existantes = existantes if existantes is not None else []
        self.get_ok = get_ok
        self.posts = []
        self.gets = 0

    async def __call__(self, method, path, *, json=None, params=None,
                       timeout=None, transport=None):
        if method == "GET":
            self.gets += 1
            if not self.get_ok:
                return {"ok": False, "status_code": 503, "data": None,
                        "error": "HTTP 503", "absent": False}
            return {"ok": True, "status_code": 200, "data": self.existantes,
                    "error": None, "absent": False}
        self.posts.append(json)
        return {"ok": True, "status_code": 201, "data": {"id": "x"},
                "error": None, "absent": False}


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "true")
    monkeypatch.setenv("BACKEND_API_URL", "http://backend.test/api/v1")

    def _installer(**kw):
        faux = FauxBackend(**kw)
        monkeypatch.setattr(base_sync, "backend_request", faux)
        return faux

    return _installer


def test_sync_sans_doublons_envoie_seulement_les_nouvelles(backend):
    faux = backend(existantes=[
        {"objet": "Formation  IA", "contenu": "..."},                 # même titre (espaces)
        {"objet": "Autre", "contenu": "Lien : https://B.mg/offre"},   # même URL (casse)
    ])
    opps = [
        opp("formation ia", "https://a.mg", 80),
        opp("Titre différent", "https://b.mg/offre", 70),
        opp("Nouvelle", "https://n.mg", 60),
    ]

    resultat = run(opportunity_sync.sync_new_opportunities_to_backend(opps))

    assert resultat == {"enabled": True, "sent": 1, "failed": 0, "already_present": 2}
    assert [p["objet"] for p in faux.posts] == ["Nouvelle"]


def test_sync_sans_doublons_accepte_la_reponse_en_dictionnaire(backend):
    faux = backend(existantes={"opportunites": [{"objet": "A", "contenu": ""}],
                               "total": 1})

    resultat = run(opportunity_sync.sync_new_opportunities_to_backend(
        [opp("A", "https://a.mg", 80), opp("B", "https://b.mg", 60)]))

    assert resultat["already_present"] == 1 and resultat["sent"] == 1


def test_liste_backend_illisible_rien_n_est_envoye(backend):
    faux = backend(get_ok=False)

    resultat = run(opportunity_sync.sync_new_opportunities_to_backend(
        [opp("A", "https://a.mg", 80)]))

    assert resultat["sent"] == 0 and resultat["failed"] == 0
    assert "Doublons non vérifiables" in resultat["error"]
    assert faux.posts == []


def test_sync_desactivee_ou_liste_vide_aucun_appel(backend, monkeypatch):
    faux = backend()

    assert run(opportunity_sync.sync_new_opportunities_to_backend([])) ["sent"] == 0
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "false")
    resultat = run(opportunity_sync.sync_new_opportunities_to_backend(
        [opp("A", "https://a.mg", 80)]))

    assert resultat["enabled"] is False and resultat["sent"] == 0
    assert faux.gets == 0 and faux.posts == []


def test_deuxieme_passage_identique_ne_cree_aucun_doublon(backend):
    """Scénario réel de la planification : mêmes annonces à chaque passage."""
    faux = backend()
    opps = [opp("A", "https://a.mg", 80), opp("B", "https://b.mg", 60)]

    premier = run(opportunity_sync.sync_new_opportunities_to_backend(opps))
    # Le Backend contient maintenant ce qui vient d'être envoyé
    faux.existantes = [{"objet": p["objet"], "contenu": p["contenu"]} for p in faux.posts]
    second = run(opportunity_sync.sync_new_opportunities_to_backend(opps))

    assert premier["sent"] == 2
    assert second["sent"] == 0 and second["already_present"] == 2


# ============================================================
# auto_detection_service — exécution, verrou, état
# ============================================================

def test_executer_detection_enregistre_l_etat(espion_sync):
    orch = OrchestrateurSimule({q: reponse(opps=[opp(q, f"https://{i}.mg", 70)])
                                for i, q in enumerate(auto.get_queries())})

    run(auto.executer_detection(orch, declenchement="manuel"))

    etat = auto.lire_etat()
    assert etat["declenchement"] == "manuel"
    assert etat["statut"] == "success"
    assert etat["total"] == 5 and etat["envoyees"] == 5
    assert auto.est_en_cours() is False


def test_deux_detections_en_parallele_sont_refusees(monkeypatch):
    monkeypatch.setattr(auto, "_en_cours", True)

    with pytest.raises(auto.DetectionAutoEnCours):
        run(auto.executer_detection(OrchestrateurSimule({})))


def test_echec_liberer_le_verrou_et_enregistre_l_erreur():
    class Casse:
        async def detecter_automatiquement(self, **kw):
            raise RuntimeError("panne")

    with pytest.raises(RuntimeError):
        run(auto.executer_detection(Casse()))

    assert auto.est_en_cours() is False
    assert "RuntimeError" in auto.lire_etat()["erreur"]
    assert auto.lire_etat()["statut"] == "error"


def test_les_parametres_explicites_priment_sur_la_configuration(monkeypatch):
    recu = {}

    class Espion:
        async def detecter_automatiquement(self, **kw):
            recu.update(kw)
            return {"status": "success", "queries": [], "total": 0, "statistics": {}}

    monkeypatch.setenv("VEILLE_AUTO_MIN_SCORE", "50")
    run(auto.executer_detection(Espion(), min_score=10, limit=3, sync_backend=False))

    assert (recu["min_score"], recu["limit"], recu["sync_backend"]) == (10, 3, False)
    assert recu["queries"] == auto.get_queries()


# ============================================================
# Planification
# ============================================================

def ecrire_etat(**kw):
    auto.STATE_PATH.write_text(json.dumps(kw), encoding="utf-8")


def test_jamais_execute_premier_passage_apres_le_delai_de_demarrage(monkeypatch):
    maintenant = datetime.now(timezone.utc)
    monkeypatch.setattr(auto, "_demarre_a", maintenant - timedelta(seconds=20))

    attente = auto.secondes_avant_prochaine_execution(maintenant)

    assert attente == pytest.approx(auto.DELAI_PREMIER_PASSAGE_S - 20, abs=1)


def test_premier_passage_du_une_fois_le_delai_ecoule(monkeypatch):
    maintenant = datetime.now(timezone.utc)
    monkeypatch.setattr(auto, "_demarre_a", maintenant - timedelta(minutes=5))

    assert auto.secondes_avant_prochaine_execution(maintenant) == 0.0


def test_derniere_execution_recente_prochain_passage_dans_l_intervalle(monkeypatch):
    maintenant = datetime.now(timezone.utc)
    ecrire_etat(derniere_execution=(maintenant - timedelta(hours=2)).isoformat())
    monkeypatch.setenv("VEILLE_AUTO_INTERVAL_HOURS", "24")

    attente = auto.secondes_avant_prochaine_execution(maintenant)

    assert attente == pytest.approx(22 * 3600, abs=1)


def test_apres_redemarrage_un_passage_en_retard_est_du_tout_de_suite():
    maintenant = datetime.now(timezone.utc)
    ecrire_etat(derniere_execution=(maintenant - timedelta(hours=30)).isoformat())

    assert auto.secondes_avant_prochaine_execution(maintenant) == 0.0


def test_etat_illisible_traite_comme_jamais_execute(monkeypatch):
    auto.STATE_PATH.write_text("pas du json", encoding="utf-8")
    maintenant = datetime.now(timezone.utc)
    monkeypatch.setattr(auto, "_demarre_a", maintenant)

    assert auto.secondes_avant_prochaine_execution(maintenant) == pytest.approx(
        auto.DELAI_PREMIER_PASSAGE_S, abs=1)


def test_planification_desactivee_par_defaut_aucune_tache():
    async def scenario():
        return auto.demarrer_planification(OrchestrateurSimule({}))

    assert run(scenario()) is None


def test_planification_activee_cree_puis_arrete_la_tache(monkeypatch):
    monkeypatch.setenv("VEILLE_AUTO_ENABLED", "true")

    async def scenario():
        tache = auto.demarrer_planification(OrchestrateurSimule({}))
        assert tache is not None and not tache.done()
        assert auto.demarrer_planification(OrchestrateurSimule({})) is tache  # idempotent
        await auto.arreter_planification()
        return tache

    tache = run(scenario())

    assert tache.cancelled() or tache.done()


def test_la_boucle_lance_un_passage_quand_il_est_du(monkeypatch):
    """Passage dû (jamais exécuté, délai écoulé) → executer_detection est appelé."""
    appels = []

    async def faux_executer(orchestrator, declenchement="manuel", **kw):
        appels.append(declenchement)
        raise asyncio.CancelledError      # arrête la boucle après le 1er passage

    monkeypatch.setattr(auto, "executer_detection", faux_executer)
    monkeypatch.setattr(auto, "_demarre_a",
                        datetime.now(timezone.utc) - timedelta(minutes=5))

    with pytest.raises(asyncio.CancelledError):
        run(auto._boucle_planifiee(object()))

    assert appels == ["planifie"]


# ============================================================
# Routes
# ============================================================

@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.include_router(routes_veille.router, prefix="/api/v1")
    recu = {}

    async def faux_detecter(queries, min_score, limit, sync_backend):
        recu.update(queries=queries, min_score=min_score,
                    limit=limit, sync_backend=sync_backend)
        return {"mode": "automatique", "status": "success", "total": 1,
                "opportunities": [opp("A", "https://a.mg", 80)],
                "queries": [], "statistics": {"backend_sync": {"sent": 1}}}

    monkeypatch.setattr(routes_veille.orchestrator, "detecter_automatiquement",
                        faux_detecter)
    return TestClient(app), recu


def test_route_detecter_sans_corps_ni_requete(api):
    client, recu = api

    response = client.post("/api/v1/ia/veille/detecter")

    assert response.status_code == 200
    corps = response.json()
    assert corps["success"] is True and corps["data"]["mode"] == "automatique"
    assert recu["queries"] == auto.get_queries()               # profil ALTIORA
    assert (recu["min_score"], recu["limit"], recu["sync_backend"]) == (40, 20, True)


def test_route_detecter_avec_parametres(api):
    client, recu = api

    response = client.post("/api/v1/ia/veille/detecter",
                           json={"min_score": 15, "limit": 5, "sync_backend": False})

    assert response.status_code == 200
    assert (recu["min_score"], recu["limit"], recu["sync_backend"]) == (15, 5, False)


def test_route_detecter_parametres_invalides(api):
    client, _ = api

    assert client.post("/api/v1/ia/veille/detecter",
                       json={"min_score": 150}).status_code == 422
    assert client.post("/api/v1/ia/veille/detecter",
                       json={"limit": 0}).status_code == 422


def test_route_detecter_409_si_deja_en_cours(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(auto, "_en_cours", True)

    assert client.post("/api/v1/ia/veille/detecter").status_code == 409


def test_route_detecter_500_sans_detail_interne(api, monkeypatch):
    client, _ = api

    async def casse(**kw):
        raise RuntimeError("secret interne")

    monkeypatch.setattr(routes_veille.orchestrator, "detecter_automatiquement", casse)
    response = client.post("/api/v1/ia/veille/detecter")

    assert response.status_code == 500
    assert "secret interne" not in response.text


def test_route_statut(api):
    client, _ = api
    client.post("/api/v1/ia/veille/detecter")                  # crée l'état

    data = client.get("/api/v1/ia/veille/detecter/statut").json()["data"]

    assert data["en_cours"] is False
    assert data["configuration"]["planification_activee"] is False
    assert data["configuration"]["requetes"] == auto.get_queries()
    assert data["derniere_execution"]["declenchement"] == "manuel"


def test_les_deux_modes_sont_montes_dans_l_application_reelle():
    """Garde-fou : mode 1 (recherche) et mode 2 (détection) coexistent."""
    from app.main import app

    chemins = {route.path for route in app.routes}
    assert {"/api/v1/ia/veille/rechercher",
            "/api/v1/ia/veille/detecter",
            "/api/v1/ia/veille/detecter/statut"} <= chemins
