"""
Tests de la synchronisation IA → Backend (app/services/backend_sync/).

Aucun réseau réel, aucune base de données, aucun LLM :
  - base_sync est testé avec un faux transport HTTP (httpx.MockTransport) ;
  - les services de sync sont testés en remplaçant base_sync.backend_request.

Exécution (sans le conftest.py, qui importe app.main et ouvre la base) :
    python -m pytest tests/unit/test_backend_sync.py --noconftest -q
"""

import asyncio
import json
import uuid

import httpx
import pytest

from app.services.backend_sync import (
    base_sync,
    facture_calculator_service,
    facture_sync,
    formation_sync,
    offre_sync,
    opportunity_sync,
    preparation_sync,
    tdr_sync,
)


def run(coro):
    return asyncio.run(coro)


def new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(autouse=True)
def env_sync(monkeypatch):
    """Sync activée, URL fictive, aucun identifiant réel."""
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "true")
    monkeypatch.setenv("BACKEND_API_URL", "http://backend.test/api/v1")
    for var in (
        "BACKEND_SYNC_TOKEN",
        "BACKEND_SERVICE_EMAIL",
        "BACKEND_SERVICE_PASSWORD",
    ):
        monkeypatch.delenv(var, raising=False)
    base_sync.reset_token_cache()
    yield
    base_sync.reset_token_cache()


# ============================================================
# Faux Backend pour les services (remplace base_sync.backend_request)
# ============================================================

def ok(data=None, status=201):
    return {"ok": True, "status_code": status, "data": data,
            "error": None, "absent": False}


def absent(status=404):
    return {"ok": False, "status_code": status, "data": None,
            "error": f"HTTP {status} : introuvable", "absent": True}


class FakeBackend:
    """Enregistre les appels et répond via `handler(method, path, json)`."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    async def __call__(self, method, path, *, json=None, params=None,
                       timeout=None, transport=None):
        self.calls.append((method, path, json))
        return self.handler(method, path, json)

    def paths(self, method):
        return [p for m, p, _ in self.calls if m == method]


@pytest.fixture
def patch_backend(monkeypatch):
    def _patch(handler):
        fake = FakeBackend(handler)
        monkeypatch.setattr(base_sync, "backend_request", fake)
        return fake
    return _patch


# ============================================================
# base_sync — HTTP réel simulé
# ============================================================

def test_sync_desactivee_n_envoie_rien(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_ENABLED", "false")

    def handler(request):
        raise AssertionError("Aucune requête ne doit partir")

    result = run(base_sync.post_and_verify(
        "/sessions", {"titre": "x"},
        transport=httpx.MockTransport(handler),
    ))
    assert result["enabled"] is False
    assert result["sent"] is False


def test_post_puis_verification_get(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_TOKEN", "jeton-de-test")
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path,
                     request.headers.get("authorization")))
        if request.method == "POST":
            return httpx.Response(201, json={"id": "abc"})
        return httpx.Response(200, json={"id": "abc"})

    result = run(base_sync.post_and_verify(
        "/sessions", {"titre": "x"},
        transport=httpx.MockTransport(handler),
    ))

    assert result["sent"] and result["verified"]
    assert result["resource_id"] == "abc"
    assert seen == [
        ("POST", "/api/v1/sessions", "Bearer jeton-de-test"),
        ("GET", "/api/v1/sessions/abc", "Bearer jeton-de-test"),
    ]


def test_endpoint_absent_est_ignore_sans_erreur_levee(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_TOKEN", "jeton-de-test")
    transport = httpx.MockTransport(lambda r: httpx.Response(404, json={}))

    result = run(base_sync.post_and_verify(
        "/projets", {}, transport=transport
    ))
    assert result["skipped"] is True
    assert result["sent"] is False
    assert "absent" in result["error"]


def test_erreur_de_validation_n_est_pas_un_skip(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_TOKEN", "jeton-de-test")
    transport = httpx.MockTransport(lambda r: httpx.Response(422, text="bad"))

    result = run(base_sync.post_and_verify(
        "/sessions", {}, transport=transport
    ))
    assert result["skipped"] is False
    assert result["sent"] is False
    assert "422" in result["error"]


def test_relogin_automatique_sur_401(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_TOKEN", "vieux-jeton")
    monkeypatch.setenv("BACKEND_SERVICE_EMAIL", "service@test.local")
    monkeypatch.setenv("BACKEND_SERVICE_PASSWORD", "mot-de-passe-de-test")
    logins = []

    def handler(request):
        if request.url.path.endswith("/auth/login"):
            logins.append(json.loads(request.content))
            return httpx.Response(200, json={"access_token": "nouveau-jeton"})
        if request.headers.get("authorization") == "Bearer vieux-jeton":
            return httpx.Response(401, json={"detail": "expiré"})
        return httpx.Response(201, json={"id": "1"})

    result = run(base_sync.post_and_verify(
        "/factures", {"client": "X"},
        transport=httpx.MockTransport(handler),
    ))

    assert len(logins) == 1
    assert result["sent"] is True
    assert result["verified"] is True


def test_401_sans_identifiants_echoue_proprement(monkeypatch):
    monkeypatch.setenv("BACKEND_SYNC_TOKEN", "vieux-jeton")
    transport = httpx.MockTransport(lambda r: httpx.Response(401, text="no"))

    result = run(base_sync.post_and_verify(
        "/factures", {}, transport=transport
    ))
    assert result["sent"] is False
    assert result["skipped"] is False
    assert "401" in result["error"]


def test_utilitaires():
    assert base_sync.is_valid_uuid(new_id())
    assert not base_sync.is_valid_uuid("123")
    assert not base_sync.is_valid_uuid(None)
    assert base_sync.truncate("x" * 80, 50) == "x" * 50
    assert base_sync.truncate(None, 50) == ""


# ============================================================
# FactureCalculatorService
# ============================================================

def test_calcul_facture_avec_remise_quantitative():
    svc = facture_calculator_service.FactureCalculatorService()
    r = svc.calculer("entreprise", nb_participants=20, tarif_unitaire=100_000,
                     session_id="S1")

    assert r["total_ht"] == 2_000_000
    assert r["tva"] == 400_000
    assert r["total_ttc"] == 2_400_000
    assert r["remise"] == 120_000          # 5 % du TTC dès 15 participants
    assert r["net"] == 2_280_000
    assert r["ht_apres_remise"] == 1_900_000
    assert r["session_id"] == "S1"


def test_calcul_facture_sans_remise_sous_le_seuil():
    svc = facture_calculator_service.FactureCalculatorService()
    r = svc.calculer("participant", 10, 100_000)
    assert r["remise"] == 0
    assert r["net"] == r["total_ttc"] == 1_200_000


def test_calcul_facture_remise_explicite_et_validations():
    svc = facture_calculator_service.FactureCalculatorService()
    assert svc.calculer("entreprise", 20, 100_000, remise_pct=0)["remise"] == 0

    for kwargs in (
        {"type_client": "autre", "nb_participants": 5, "tarif_unitaire": 1},
        {"type_client": "entreprise", "nb_participants": 0, "tarif_unitaire": 1},
        {"type_client": "entreprise", "nb_participants": 5, "tarif_unitaire": 0},
        {"type_client": "entreprise", "nb_participants": 5,
         "tarif_unitaire": 1, "remise_pct": 150},
    ):
        with pytest.raises(ValueError):
            svc.calculer(**kwargs)


def test_reste_du_facture():
    calc = facture_calculator_service.FactureCalculatorService
    facture = {"montant_ttc": 1000, "paiements": [{"montant": 300}, {"montant": 200}]}
    assert calc.calculer_reste_du(facture) == 500
    assert calc.calculer_reste_du({"montant_ttc": 100, "paiements": [{"montant": 500}]}) == 0


# ============================================================
# offre_sync (M3)
# ============================================================

def test_offre_sync_envoie_opportunite_et_montant(patch_backend):
    opp_id, doc_id = new_id(), new_id()
    fake = patch_backend(lambda m, p, j: ok({"id": doc_id}))

    result = run(offre_sync.sync_offre_to_backend(opp_id, montant=2_280_000))

    assert result["sent"] and result["verified"]
    assert result["resource_id"] == doc_id
    assert fake.calls[0] == (
        "POST", "/documents/offre",
        {"opportunite_id": opp_id, "montant": 2_280_000},
    )
    assert fake.calls[1][:2] == ("GET", f"/documents/{doc_id}")


def test_offre_sync_transmet_le_contenu_ia(patch_backend):
    opp_id = new_id()
    fake = patch_backend(lambda m, p, j: ok({"id": new_id()}))

    run(offre_sync.sync_offre_to_backend(opp_id, 10, contenu="OFFRE TECHNIQUE\nx"))
    assert fake.calls[0][2]["contenu"] == "OFFRE TECHNIQUE\nx"

    # Trop long : tronqué à la limite du Backend (500 000)
    run(offre_sync.sync_offre_to_backend(opp_id, 10, contenu="y" * 600_000))
    assert len(fake.calls[2][2]["contenu"]) == 500_000

    # Vide ou blanc : champ omis (le Backend garde son texte par défaut)
    run(offre_sync.sync_offre_to_backend(opp_id, 10, contenu="   "))
    assert "contenu" not in fake.calls[4][2]


def test_build_contenu_texte_lisible_sans_cles_internes():
    texte = offre_sync.build_contenu({
        "success": True,
        "offre_technique": {
            "reference": "ALT-OFF-TECH-2026-0001",
            "modules": [{"titre": "Introduction", "duree": "3h"}, "Bonus"],
            "vide": [],
            "_review_id": "HITL-AM3-0001",
            "metadata": {"generated_at": "2026"},
        },
        "offre_financiere": {"recapitulatif": {"net_a_payer": 2_280_000, "tva": 0}},
        "reviews_individuels": {"technique": "HITL-AM3-0002"},
    })

    assert texte.index("OFFRE TECHNIQUE") < texte.index("OFFRE FINANCIÈRE")
    assert "Référence : ALT-OFF-TECH-2026-0001" in texte
    assert "Titre : Introduction" in texte and "- Bonus" in texte
    assert "Durée : 3h" in texte                   # libellé français accentué
    assert "Net à payer : 2280000" in texte
    assert "TVA : 0" in texte                      # une valeur 0 est conservée
    for absent_du_texte in ("HITL", "metadata", "generated_at", "Vide", "success"):
        assert absent_du_texte not in texte


def test_build_contenu_offre_unique_sans_enveloppe():
    texte = offre_sync.build_contenu({"reference": "R1", "_review_id": "X"})
    assert texte == "Référence : R1"
    assert offre_sync.build_contenu({}) == ""
    # Clé inconnue : libellé déduit du nom
    assert offre_sync.build_contenu({"cle_inconnue": "v"}) == "Cle inconnue : v"


def test_offre_sync_refuse_un_opportunite_id_invalide(patch_backend):
    fake = patch_backend(lambda m, p, j: ok({}))
    result = run(offre_sync.sync_offre_to_backend("pas-un-uuid", 10))
    assert result["sent"] is False
    assert "opportunite_id" in result["error"]
    assert fake.calls == []


def test_extract_montant_priorite_net_a_payer():
    assert offre_sync.extract_montant(
        {"resume_financier": {"net_a_payer": 500, "total_ttc": 600}}
    ) == 500
    assert offre_sync.extract_montant(
        {"offre_financiere": {"recapitulatif": {"total_ttc": 700}}}
    ) == 700
    assert offre_sync.extract_montant({}) is None


# ============================================================
# facture_sync (M7)
# ============================================================

def test_facture_sync_cree_la_facture(patch_backend):
    fac_id = new_id()
    fake = patch_backend(lambda m, p, j: ok({"id": fac_id, "numero": "FAC-2026-001"}))

    result = run(facture_sync.sync_facture_to_backend(
        "C" * 80, 1_900_000, tva_taux=20.0, date_echeance="2026-10-30T00:00:00"
    ))

    assert result["sent"] and result["numero"] == "FAC-2026-001"
    payload = fake.calls[0][2]
    assert payload["client"] == "C" * 50            # Facture.client = String(50)
    assert payload["montant"] == 1_900_000
    assert payload["date_echeance"] == "2026-10-30"


def test_facture_sync_refuse_montant_nul(patch_backend):
    fake = patch_backend(lambda m, p, j: ok({}))
    result = run(facture_sync.sync_facture_to_backend("Client", 0))
    assert result["sent"] is False and fake.calls == []


def test_fetch_facture(patch_backend):
    fac_id = new_id()
    patch_backend(lambda m, p, j: ok({"id": fac_id}, status=200))
    assert run(facture_sync.fetch_facture(fac_id)) == {"id": fac_id}
    assert run(facture_sync.fetch_facture("xx")) is None


# ============================================================
# preparation_sync
# ============================================================

def test_preparation_sync_session_seances_et_budget_non_persiste(patch_backend):
    sid = new_id()

    def handler(method, path, payload):
        if method == "POST" and path == "/sessions":
            return ok({"id": sid})
        if method == "GET":
            return ok({"id": sid}, status=200)
        return ok({"id": new_id()})

    fake = patch_backend(handler)
    edt = {
        "titre_formation": "T" * 80,
        "jours": [
            {"date": "2026-10-16", "sessions": [
                {"module": "Apprentissage", "duree_minutes": 90},
                {"module": "Atelier", "duree_minutes": 90}]},
            {"date": "2026-10-15", "sessions": [
                {"module": "Introduction", "duree_minutes": 180}]},
        ],
    }

    result = run(preparation_sync.sync_preparation_to_backend(
        edt, projet_info={"client": "Ministère"}, budget={"cout_total": 1}
    ))

    session_payload = fake.calls[0][2]
    assert session_payload["titre"] == "T" * 50
    assert session_payload["date_debut"] == "2026-10-15"
    assert session_payload["date_fin"] == "2026-10-16"   # NOT NULL côté Backend
    assert session_payload["client"] == "Ministère"
    assert result["sent"] and result["verified"]
    assert result["seances"] == {"sent": 2, "failed": 0}
    assert result["budget"]["skipped"] is True

    seance_calls = [c for c in fake.calls if c[1].endswith("/seances")]
    assert seance_calls[0][2] == {
        "date": "2026-10-16", "duree": "3h", "theme": "Apprentissage, Atelier"
    }


def test_preparation_sync_edt_sans_date(patch_backend):
    fake = patch_backend(lambda m, p, j: ok({}))
    result = run(preparation_sync.sync_preparation_to_backend({"jours": [{}]}))
    assert result["sent"] is False and "EDT" in result["error"]
    assert fake.calls == []


def test_preparation_sync_endpoint_absent_ignore(patch_backend):
    patch_backend(lambda m, p, j: absent(404))
    result = run(preparation_sync.sync_preparation_to_backend(
        {"titre_formation": "F", "jours": [{"date": "2026-10-15"}]}
    ))
    assert result["skipped"] is True and result["sent"] is False


# ============================================================
# formation_sync (M5)
# ============================================================

def test_map_statut_presence():
    m = formation_sync.map_statut_presence
    assert m("présent") == "PRESENT" and m("PRESENT") == "PRESENT"
    assert m("Absent") == "ABSENT" and m("excusé") == "EXCUSE"
    assert m("peut-être") is None and m(None) is None


def test_presences_sync_compte_les_entrees_invalides(patch_backend):
    seance, p1 = new_id(), new_id()
    fake = patch_backend(lambda m, p, j: ok({"id": new_id()}))

    result = run(formation_sync.sync_presences_to_backend(seance, [
        {"participant_id": p1, "statut": "présent"},
        {"participant_id": "x", "statut": "présent"},        # UUID invalide
        {"participant_id": new_id(), "statut": "??"},        # statut inconnu
    ]))

    assert result["sent"] is True
    assert (result["sent_count"], result["failed_count"]) == (1, 2)
    assert fake.calls == [(
        "POST", f"/sessions/seances/{seance}/presences",
        {"participant_id": p1, "statut": "PRESENT", "source": "GOOGLE_FORMS"},
    )]


def test_presences_sync_endpoint_absent_arrete_la_boucle(patch_backend):
    fake = patch_backend(lambda m, p, j: absent(404))
    result = run(formation_sync.sync_presences_to_backend(new_id(), [
        {"participant_id": new_id(), "statut": "absent"},
        {"participant_id": new_id(), "statut": "absent"},
    ]))
    assert result["skipped"] is True
    assert len(fake.calls) == 1


def test_attestations_sync(patch_backend):
    sid, a1, a2 = new_id(), new_id(), new_id()

    def handler(method, path, payload):
        if method == "POST":
            return ok([{"id": a1}, {"id": a2}])
        return ok({"id": a1}, status=200)

    fake = patch_backend(handler)
    result = run(formation_sync.sync_attestations_to_backend(sid))

    assert result["sent"] and result["verified"]
    assert result["count"] == 2 and result["ids"] == [a1, a2]
    assert fake.calls[0][:2] == ("POST", f"/documents/attestations/{sid}")


def test_fetch_session(patch_backend):
    sid = new_id()
    patch_backend(lambda m, p, j: ok({"id": sid, "titre": "F"}, status=200))
    assert run(formation_sync.fetch_session(sid))["titre"] == "F"
    assert run(formation_sync.fetch_session("nope")) is None


# ============================================================
# tdr_sync / opportunity_sync (fichiers existants alignés)
# ============================================================

def test_tdr_sync_format_export_docx_et_cles_historiques(patch_backend):
    payload = tdr_sync._build_tdr_payload({"client": "C"}, "a.docx", None)
    assert payload["format_export"] == "DOCX"      # "WORD" était refusé (422)
    assert tdr_sync._build_tdr_payload({}, "a.docx", "a.pdf")["format_export"] == "PDF"

    fake = patch_backend(lambda m, p, j: ok({"id": "d1"}))
    result = run(tdr_sync.sync_tdr_to_backend({"client": "C"}, "a.docx"))
    assert result["success"] is True and result["document_id"] == "d1"
    assert {"enabled", "sent", "document_id", "error"} <= set(result)
    assert fake.calls[0][:2] == ("POST", "/documents/tdr")
    assert fake.calls[1][:2] == ("GET", "/documents/d1")   # contrôle


def test_tdr_payload_evite_les_refus_du_backend():
    """client / objectifs vides ou opportunite_id invalide → 422 côté Backend."""
    payload = tdr_sync._build_tdr_payload(
        {"client": "", "objectif_general": ""}, "a.docx", None,
        opportunite_id="pas-un-uuid",
    )
    assert payload["client"] == "Client"
    assert payload["objectifs"] == "Non précisé"
    assert payload["opportunite_id"] is None

    valid = new_id()
    assert tdr_sync._build_tdr_payload(
        {}, None, None, opportunite_id=valid
    )["opportunite_id"] == valid


def test_tdr_sync_route_absente_est_ignoree(patch_backend):
    patch_backend(lambda m, p, j: absent(404))
    result = run(tdr_sync.sync_tdr_to_backend({"client": "C"}, "a.docx"))
    assert result["success"] is False and result["skipped"] is True


def test_opportunity_sync_source_valide_pour_le_backend(patch_backend):
    build = opportunity_sync._build_backend_payload
    assert build({"title": "AO", "url": "https://x.mg/ao"})["source"] == "URL"
    assert build({"title": "AO"})["source"] == "TEXTE"   # "VEILLE_IA" → 422

    fake = patch_backend(lambda m, p, j: ok({"id": "o1"}))
    result = run(opportunity_sync.sync_opportunities_to_backend(
        [{"title": "AO", "budget": "5M Ar"}]
    ))
    assert result == {"enabled": True, "sent": 1, "failed": 0}
    assert fake.calls[0][1] == "/opportunites"


# ============================================================
# Budget : lecture des formats « 5M », « 500K » (régression)
# ============================================================

@pytest.mark.parametrize("texte, attendu", [
    ("5M Ar", 5_000_000.0),          # échouait : lu 5.0 (pas de frontière chiffre/M)
    ("60M Ar", 60_000_000.0),
    ("1,5M Ar", 1_500_000.0),
    ("5 M Ar", 5_000_000.0),
    ("500K Ar", 500_000.0),
    ("2 millions Ar", 2_000_000.0),
    ("15 000 000 Ar", 15_000_000.0),
    ("Non précisé", 0.0),
    ("150 m2 de salle", 150.0),      # mètres carrés : pas des millions
    ("5 MGA", 5.0),                  # M suivi d'une lettre : pas un multiplicateur
])
def test_parse_budget_formats_avec_multiplicateur(texte, attendu):
    assert opportunity_sync._parse_budget(texte) == attendu
