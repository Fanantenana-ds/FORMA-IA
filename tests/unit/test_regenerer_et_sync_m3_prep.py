"""
Tests M3 (offres) et Préparation : /regenerer réparé + synchronisation Backend
APRÈS approbation HITL.

Rien de réel n'est touché :
  - le store HITL et le registre de sync sont redirigés vers un dossier temporaire ;
  - le LLM est désactivé (les générateurs retombent sur leurs gabarits Python) ;
  - le Backend est simulé (base_sync.backend_request remplacé).
Pas de base de données, pas de réseau.
"""

import asyncio
import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import offre_ia, preparation_ia
from app.orchestrator.offre_orchestrator import OffreOrchestrator
from app.orchestrator.preparation_orchestrator import PreparationOrchestrator
from app.services.backend_sync import base_sync, review_sync
from app.services.hitl import hitl_helper
from app.services.llm import LLMNotAvailableError
from app.services.offres import offre_financiere_service, offre_technique_service
from app.services.preparation import edt_generator_service

TDR = {
    "id": 1, "titre": "Introduction à l'IA", "domaine": "IA",
    "objectifs": ["Comprendre les concepts", "Pratiquer"],
    "public_cible": "Développeurs juniors", "duree_jours": 2,
}
SESSION = {"id": 1, "client": "Ministère de l'Éducation", "client_id": 1,
           "formateur": "M. RANAIVOSOA"}
OPTIONS_M3 = {"nb_participants": 20, "type_formateur": "senior",
              "type_salle": "standard", "tva_applicable": True}

OFFRE = {
    "reference": "ALT-OFF-TECH-2026-0001", "titre": "Introduction à l'IA",
    "duree_jours": 2,
    "modules": [{"titre": "Introduction", "duree": "3h"},
                {"titre": "Apprentissage", "duree": "3h"}],
}
PROJET = {"id": 1, "client": "Ministère de l'Éducation", "client_id": 1,
          "nb_participants": 20}
RESSOURCES = {
    "formateur": {"nom": "M. RANAIVOSOA", "tarif_journalier": 500_000},
    "salle": {"nom": "Salle A", "tarif_journalier": 200_000},
}
OPTIONS_PREP = {"date_debut": "2026-10-15", "date_fin": "2026-10-16"}

FEEDBACK = "Ajouter davantage d'exercices pratiques"


def run(coro):
    return asyncio.run(coro)


def new_id() -> str:
    return str(uuid.uuid4())


# ============================================================
# Isolation : stores temporaires, LLM coupé, faux Backend
# ============================================================

@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")
    monkeypatch.setattr(review_sync, "REGISTRY_PATH", tmp_path / "registry.json")

    def llm_indisponible():
        raise LLMNotAvailableError("LLM coupé pour les tests")

    for module in (offre_technique_service, offre_financiere_service,
                   edt_generator_service):
        monkeypatch.setattr(module, "get_llm_provider", llm_indisponible)
    monkeypatch.delenv("EDT_USE_LLM", raising=False)

    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "true")
    monkeypatch.setenv("BACKEND_API_URL", "http://backend.test/api/v1")
    base_sync.reset_token_cache()
    yield
    base_sync.reset_token_cache()


class FakeBackend:
    def __init__(self):
        self.calls = []

    async def __call__(self, method, path, *, json=None, params=None,
                       timeout=None, transport=None):
        self.calls.append((method, path, json))
        if method == "POST":
            return {"ok": True, "status_code": 201, "data": {"id": new_id()},
                    "error": None, "absent": False}
        return {"ok": True, "status_code": 200, "data": {}, "error": None,
                "absent": False}

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


@pytest.fixture
def backend(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(base_sync, "backend_request", fake)
    return fake


def offre_generee(tdr=TDR):
    orch = OffreOrchestrator()
    return orch, run(orch.generate_complete(dict(tdr), dict(SESSION), dict(OPTIONS_M3)))


def prep_generee(offre=OFFRE, options=OPTIONS_PREP):
    orch = PreparationOrchestrator()
    return orch, run(orch.generate_complete(dict(offre), dict(PROJET),
                                            dict(RESSOURCES), dict(options)))


# ============================================================
# M3 — /regenerer réparé
# ============================================================

def test_m3_generate_complete_memorise_les_entrees():
    _, result = offre_generee()
    inputs = result["_inputs"]
    assert inputs["tdr_data"] == TDR
    assert inputs["session_info"] == SESSION
    assert inputs["options"] == OPTIONS_M3
    assert "feedback" not in inputs["options"]


def test_m3_regenerer_reutilise_les_entrees_et_transmet_le_feedback(monkeypatch):
    orch, r1 = offre_generee()
    hitl_helper.reject_review(r1["_review_id"], "trop théorique")

    vus = {}
    original_tech = orch.offre_technique.generate
    original_fin = orch.offre_financiere.generate

    async def espion_tech(*args, **kwargs):
        vus["technique"] = kwargs
        return await original_tech(*args, **kwargs)

    async def espion_fin(*args, **kwargs):
        vus["financiere"] = kwargs
        return await original_fin(*args, **kwargs)

    monkeypatch.setattr(orch.offre_technique, "generate", espion_tech)
    monkeypatch.setattr(orch.offre_financiere, "generate", espion_fin)

    r2 = run(orch.regenerate(r1["_review_id"], FEEDBACK))

    assert r2["_review_id"] != r1["_review_id"]
    assert r2["_inputs"]["tdr_data"] == TDR                       # entrées retrouvées
    assert vus["technique"]["tdr_data"] == TDR
    assert vus["technique"]["feedback"] == FEEDBACK               # feedback transmis
    assert vus["financiere"]["options"]["feedback"] == FEEDBACK
    assert "feedback" not in r2["_inputs"]["options"]             # non recopié plus tard

    meta = r2["offre_technique"]["metadata"]
    assert meta["feedback"] == FEEDBACK
    assert meta["feedback_applied"] is False                      # gabarit Python : honnête


def test_m3_regenerer_refuse_un_review_non_rejete():
    orch, r1 = offre_generee()
    with pytest.raises(ValueError, match="pas rejeté"):
        run(orch.regenerate(r1["_review_id"], FEEDBACK))


def test_m3_regenerer_review_individuel_donne_un_message_clair():
    orch, r1 = offre_generee()
    review_technique = r1["offre_technique"]["_review_id"]
    hitl_helper.reject_review(review_technique, "à revoir")

    with pytest.raises(ValueError, match="agent_m3_complete"):
        run(orch.regenerate(review_technique, FEEDBACK))


def test_les_prompts_contiennent_le_feedback():
    tech = offre_technique_service.OffreTechniqueGeneratorService()
    avec = tech._build_user_prompt(TDR, SESSION, FEEDBACK)
    sans = tech._build_user_prompt(TDR, SESSION)
    assert "CORRECTIONS DEMANDÉES PAR LE RÉVISEUR HUMAIN" in avec and FEEDBACK in avec
    assert avec.rstrip().endswith("Retourne UNIQUEMENT le JSON valide, sans texte autour.")
    assert "CORRECTIONS" not in sans

    fin = offre_financiere_service.OffreFinanciereGeneratorService()
    calculs = fin.grille_service.calculer_couts(nb_jours=2, nb_participants=20)
    assert FEEDBACK in fin._build_user_prompt({}, {"feedback": FEEDBACK}, calculs)
    assert "CORRECTIONS" not in fin._build_user_prompt({}, {}, calculs)

    edt = edt_generator_service.EDTGeneratorService()
    args = ("F", [{"titre": "M1", "duree": "3h"}], ["2026-10-15"], None, None)
    assert FEEDBACK in edt._build_user_prompt(*args, feedback=FEEDBACK)
    assert "CORRECTIONS" not in edt._build_user_prompt(*args)


# ============================================================
# Préparation — /regenerer réparé + dates par défaut
# ============================================================

def test_prep_regenerer_reutilise_les_entrees_et_signale_le_feedback():
    orch, r1 = prep_generee()
    assert r1["_inputs"]["projet_info"] == PROJET
    hitl_helper.reject_review(r1["_review_id"], "planning trop chargé")

    r2 = run(orch.regenerate(r1["_review_id"], FEEDBACK))

    assert r2["_review_id"] != r1["_review_id"]
    assert r2["_inputs"]["ressources"] == RESSOURCES
    assert [j["date"] for j in r2["edt"]["jours"]] == ["2026-10-15", "2026-10-16"]
    assert r2["budget"]["cout_total"] == r1["budget"]["cout_total"]
    assert r2["edt"]["metadata"]["feedback"] == FEEDBACK
    # EDT_USE_LLM=false : le planning ne peut pas tenir compte du feedback
    assert r2["edt"]["metadata"]["feedback_applied"] is False


def test_prep_regenerer_review_sans_entrees_memorisees():
    orch = PreparationOrchestrator()
    ancien = hitl_helper.create_review("agent_preparation", {"budget": {}}, "ancien")
    hitl_helper.reject_review(ancien, "x")
    with pytest.raises(ValueError, match="sans données d'entrée"):
        run(orch.regenerate(ancien, FEEDBACK))


def test_prep_regenerer_refuse_le_review_d_un_autre_agent():
    orch = PreparationOrchestrator()
    autre = hitl_helper.create_review("agent_m3_complete", {}, "offre")
    hitl_helper.reject_review(autre, "x")
    with pytest.raises(ValueError, match="pas par la Préparation"):
        run(orch.regenerate(autre, FEEDBACK))


def test_prep_dates_par_defaut_toujours_valides_meme_apres_17_jours():
    offre = {**OFFRE, "duree_jours": 20}
    _, result = prep_generee(offre=offre, options={})

    dates = [j["date"] for j in result["edt"]["jours"]]
    assert len(dates) == 20
    for d in dates:                                   # avant : « 2026-10-32 »…
        datetime.strptime(d, "%Y-%m-%d")
    assert dates[0] == "2026-10-15" and dates[-1] == "2026-11-03"


# ============================================================
# Synchronisation APRÈS approbation HITL
# ============================================================

def test_m3_sync_refuse_un_review_non_approuve(backend):
    orch, r1 = offre_generee()
    with pytest.raises(ValueError, match="non approuvé"):
        run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))
    assert backend.calls == []


def test_m3_sync_refuse_un_review_rejete(backend):
    orch, r1 = offre_generee()
    hitl_helper.reject_review(r1["_review_id"], "non")
    with pytest.raises(ValueError, match="non approuvé"):
        run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))


def test_m3_sync_review_individuel_refuse(backend):
    orch, r1 = offre_generee()
    technique = r1["offre_technique"]["_review_id"]
    hitl_helper.approve_review(technique)
    with pytest.raises(ValueError, match="agent_m3_complete"):
        run(orch.synchroniser_backend(technique, opportunite_id=new_id()))


def test_m3_sync_approuve_envoie_contenu_montant_et_une_seule_fois(backend):
    orch, r1 = offre_generee()
    hitl_helper.approve_review(r1["_review_id"])
    opp_id = new_id()

    premier = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id))

    assert premier["already_synced"] is False
    assert premier["backend_sync"]["sent"] and premier["backend_sync"]["verified"]
    assert "data" not in premier["backend_sync"]              # corps Backend non stocké
    post = backend.posts()[0]
    assert post[1] == "/documents/offre"
    assert post[2]["opportunite_id"] == opp_id
    assert post[2]["montant"] == r1["resume_financier"]["net_a_payer"]
    assert "OFFRE TECHNIQUE" in post[2]["contenu"]
    assert "OFFRE FINANCIÈRE" in post[2]["contenu"]
    assert "Net à payer" in post[2]["contenu"]
    assert "HITL" not in post[2]["contenu"]                   # clés internes exclues

    # 2e appel : aucun nouvel envoi
    deuxieme = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id))
    assert deuxieme["already_synced"] is True
    assert len(backend.posts()) == 1

    # force=True : nouvel envoi volontaire
    run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=opp_id, force=True))
    assert len(backend.posts()) == 2


def test_m3_sync_lit_opportunite_id_dans_les_entrees(backend):
    opp_id = new_id()
    orch = OffreOrchestrator()
    r1 = run(orch.generate_complete({**TDR, "opportunite_id": opp_id},
                                    dict(SESSION), dict(OPTIONS_M3)))
    hitl_helper.approve_review(r1["_review_id"])

    run(orch.synchroniser_backend(r1["_review_id"]))
    assert backend.posts()[0][2]["opportunite_id"] == opp_id


def test_m3_sync_sans_opportunite_id_n_envoie_rien_et_n_est_pas_memorise(backend):
    orch, r1 = offre_generee()
    hitl_helper.approve_review(r1["_review_id"])

    result = run(orch.synchroniser_backend(r1["_review_id"]))

    assert result["backend_sync"]["sent"] is False
    assert "opportunite_id" in result["backend_sync"]["error"]
    assert backend.calls == []
    assert review_sync.get_synced(r1["_review_id"]) is None    # pourra être renvoyé


def test_sync_desactivee_n_envoie_rien_et_n_est_pas_memorisee(backend, monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "false")
    orch, r1 = offre_generee()
    hitl_helper.approve_review(r1["_review_id"])

    result = run(orch.synchroniser_backend(r1["_review_id"], opportunite_id=new_id()))

    assert result["backend_sync"]["enabled"] is False
    assert backend.calls == []
    assert review_sync.get_synced(r1["_review_id"]) is None
    assert "désactivée" in review_sync.describe_sync(result)[1]


def test_prep_sync_approuve_cree_session_seances_et_signale_le_budget(backend):
    orch, r1 = prep_generee()

    with pytest.raises(ValueError, match="non approuvé"):
        run(orch.synchroniser_backend(r1["_review_id"]))
    assert backend.calls == []

    hitl_helper.approve_review(r1["_review_id"])
    result = run(orch.synchroniser_backend(r1["_review_id"]))

    sync = result["backend_sync"]
    assert sync["sent"] and sync["verified"]
    assert sync["seances"] == {"sent": 2, "failed": 0}
    assert sync["budget"]["skipped"] is True                   # pas de route Backend

    session = backend.posts()[0]
    assert session[1] == "/sessions"
    assert session[2]["titre"] == "Introduction à l'IA"
    assert session[2]["client"] == "Ministère de l'Éducation"
    assert (session[2]["date_debut"], session[2]["date_fin"]) == ("2026-10-15", "2026-10-16")
    assert len(backend.posts()) == 3                           # 1 session + 2 séances

    again = run(orch.synchroniser_backend(r1["_review_id"]))
    assert again["already_synced"] is True and len(backend.posts()) == 3


# ============================================================
# Routes POST /ia/offres/synchroniser et /ia/preparation/synchroniser
# ============================================================

@pytest.fixture
def api():
    offre_orch, prep_orch = OffreOrchestrator(), PreparationOrchestrator()
    app = FastAPI()
    app.include_router(offre_ia.router, prefix="/api/v1")
    app.include_router(preparation_ia.router, prefix="/api/v1")
    app.dependency_overrides[offre_ia.get_offre_orchestrator] = lambda: offre_orch
    app.dependency_overrides[preparation_ia.get_preparation_orchestrator] = lambda: prep_orch
    return TestClient(app), offre_orch, prep_orch


def test_route_offres_synchroniser(api, backend):
    client, offre_orch, _ = api
    r1 = run(offre_orch.generate_complete(dict(TDR), dict(SESSION), dict(OPTIONS_M3)))

    refuse = client.post("/api/v1/ia/offres/synchroniser",
                         json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    assert refuse.status_code == 422 and "non approuvé" in refuse.json()["detail"]

    hitl_helper.approve_review(r1["_review_id"])
    ok = client.post("/api/v1/ia/offres/synchroniser",
                     json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    body = ok.json()
    assert ok.status_code == 200 and body["success"] is True
    assert body["message"].startswith("Synchronisé avec le Backend")
    assert body["data"]["backend_sync"]["resource_id"]

    encore = client.post("/api/v1/ia/offres/synchroniser",
                         json={"review_id": r1["_review_id"], "opportunite_id": new_id()})
    assert "Déjà synchronisé" in encore.json()["message"]
    assert len(backend.posts()) == 1


def test_route_preparation_synchroniser(api, backend):
    client, _, prep_orch = api
    r1 = run(prep_orch.generate_complete(dict(OFFRE), dict(PROJET),
                                         dict(RESSOURCES), dict(OPTIONS_PREP)))
    hitl_helper.approve_review(r1["_review_id"])

    ok = client.post("/api/v1/ia/preparation/synchroniser",
                     json={"review_id": r1["_review_id"]})
    body = ok.json()
    assert ok.status_code == 200 and body["success"] is True
    assert body["data"]["backend_sync"]["seances"]["sent"] == 2

    inconnu = client.post("/api/v1/ia/preparation/synchroniser",
                          json={"review_id": "HITL-XXX-9999"})
    assert inconnu.status_code == 422
