# tests/unit/test_m5_agent5_attestations.py
# ============================================================
# Correction 1a — Mission "Étape 1"
# ============================================================
# L'Agent 5 (attestations) doit REVÉRIFIER le seuil de 75% de présence
# avant de générer un PDF, même si l'appelant HTTP fournit un participant
# sous le seuil dans eligible_participants. AVANT cette correction,
# generate_batch_with_pdf() faisait une confiance aveugle à la liste
# fournie par l'appelant : un participant à 50% de présence recevait
# quand même une attestation (non-conformité au CDC : "attestation à
# partir de 75% de présence").
#
# Aucun réseau : LLM désactivé (service.llm = None), fallback template
# Python pur, déterministe.
# ============================================================

import asyncio

import pytest

from app.services.formations.attestation_generator_service import AttestationGeneratorService
from app.services.hitl import hitl_helper


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")
    monkeypatch.setattr(AttestationGeneratorService, "OUTPUT_DIR", tmp_path / "attestations")
    from app.services.formations.knowledge_base_service import KnowledgeBaseService

    async def no_rag_context(*args, **kwargs):
        return ""

    monkeypatch.setattr(KnowledgeBaseService, "get_formation_context", no_rag_context)


@pytest.fixture
def service():
    s = AttestationGeneratorService()
    s.llm = None  # force le fallback template Python (déterministe, sans réseau)
    return s


SESSION = {
    "id": "sess-1", "titre": "IA Fondamentaux", "domaine": "IA",
    "date_debut": "2026-10-01", "date_fin": "2026-10-03", "duree_jours": 3,
}


def test_participant_sous_le_seuil_est_refuse_et_signale(service):
    participants = [
        {"id": 1, "nom": "Eligible Un", "genre": "m", "taux_presence": "85.0%", "eligible_attestation": True},
        {"id": 2, "nom": "Ineligible Deux", "genre": "f", "taux_presence": "50.0%", "eligible_attestation": False},
    ]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    noms_generes = {a["participant"]["nom"] for a in resultat["attestations"]}
    assert noms_generes == {"Eligible Un"}
    assert resultat["total_generated"] == 1

    assert resultat["total_rejetes_seuil"] == 1
    noms_rejetes = {r["participant"]["nom"] for r in resultat["rejected_ineligible"]}
    assert noms_rejetes == {"Ineligible Deux"}
    raison = resultat["rejected_ineligible"][0]["raison"]
    assert "75" in raison or "seuil" in raison.lower()


def test_participant_exactement_au_seuil_est_accepte(service):
    participants = [{"id": 1, "nom": "Pile Au Seuil", "taux_presence": "75.0%"}]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    assert resultat["total_generated"] == 1
    assert resultat["total_rejetes_seuil"] == 0


def test_participant_juste_sous_le_seuil_est_refuse(service):
    resultat = run(service.generate_batch_with_pdf(
        SESSION, [{"id": 1, "nom": "Sous le seuil", "taux_presence": "74.9%"}]
    ))
    assert resultat["total_generated"] == 0
    assert resultat["total_rejetes_seuil"] == 1


def test_taux_presence_numerique_egalement_accepte(service):
    """taux_presence peut être un nombre (75.5) ou une chaîne ("75.5%")."""
    participants = [{"id": 1, "nom": "Numerique", "taux_presence": 90.0}]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    assert resultat["total_generated"] == 1
    assert resultat["total_rejetes_seuil"] == 0


def test_participant_sans_donnee_de_presence_est_refuse_non_verifiable(service):
    """Aucune donnée inventée : si l'éligibilité n'est pas vérifiable,
    on refuse plutôt que de supposer un participant éligible."""
    participants = [{"id": 1, "nom": "Sans Donnee"}]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    assert resultat["total_generated"] == 0
    assert resultat["total_rejetes_seuil"] == 1
    raison = resultat["rejected_ineligible"][0]["raison"]
    assert "non vérifiable" in raison.lower() or "non fourni" in raison.lower()


def test_tous_eligibles_aucun_rejet_regression(service):
    """Cas nominal : tous au-dessus du seuil -> comportement inchangé."""
    participants = [
        {"id": 1, "nom": "A", "taux_presence": "100%"},
        {"id": 2, "nom": "B", "taux_presence": "82%"},
    ]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    assert resultat["total_generated"] == 2
    assert resultat["total_rejetes_seuil"] == 0
    assert resultat["rejected_ineligible"] == []


def test_eligible_attestation_false_prioritaire_meme_avec_taux_incoherent(service):
    """Si le booléen eligible_attestation=False est fourni (calculé par
    l'Agent 4), il fait foi même si un taux_presence incohérent est
    présent -- on fait confiance au calcul déjà fait par l'Agent 4."""
    participants = [{"id": 1, "nom": "X", "taux_presence": "95%", "eligible_attestation": False}]

    resultat = run(service.generate_batch_with_pdf(SESSION, participants))

    assert resultat["total_generated"] == 0
    assert resultat["total_rejetes_seuil"] == 1


def test_taux_reel_sous_seuil_refuse_meme_si_indicateur_eligible_est_vrai(service):
    resultat = run(service.generate_batch_with_pdf(
        SESSION, [{"id": 1, "nom": "Taux incohérent", "taux_presence": "60%", "eligible_attestation": True}]
    ))
    assert resultat["total_generated"] == 0
    assert resultat["total_rejetes_seuil"] == 1


def test_numeros_sont_uniques_et_pdf_paysage_sur_une_page(service):
    resultat = run(service.generate_batch_with_pdf(SESSION, [
        {"id": 1, "nom": "Participant 1", "taux_presence": "100%"},
        {"id": 2, "nom": "Participant 2", "taux_presence": "100%"},
    ]))
    numeros = [item["numero_unique"] for item in resultat["attestations"]]
    assert len(numeros) == len(set(numeros)) == 2

    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4, landscape

    for item in resultat["attestations"]:
        page = PdfReader(item["pdf_path"]).pages
        assert len(page) == 1
        assert tuple(round(value) for value in page[0].mediabox[2:]) == tuple(round(value) for value in landscape(A4))


def test_attestation_participation_generee_sans_inventer_des_competences(service):
    session = {**SESSION, "require_grounded_competencies": True, "themes": []}
    participant = {
        "id": "participant-1",
        "nom": "Hantamalala NAMBININA",
        "taux_presence": 100,
        "eligible_attestation": True,
    }

    result = run(service.generate_batch_with_pdf(session, [participant]))

    assert result["total_pdf_generated"] == 1
    item = result["attestations"][0]
    assert item["metadata"]["competencies_source"] == "participation_only"
    assert item["content"]["competences"] == []
    assert item["content"]["titre_attestation"] == "ATTESTATION DE PARTICIPATION"

    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(item["pdf_path"]).pages)
    assert "Hantamalala NAMBININA" in text
    assert "PRÉSENCE ET PARTICIPATION CONFIRMÉES" in text
    assert "100 %" in text
    assert "CONTENUS DE FORMATION DOCUMENTÉS" not in text


def test_aucun_review_hitl_vide_si_aucun_pdf_nest_produit(service, monkeypatch):
    def fail_pdf(self, result, participant, output_path=None):
        raise RuntimeError("erreur PDF simulée")

    monkeypatch.setattr(AttestationGeneratorService, "_build_attestation_pdf", fail_pdf)
    result = run(service.generate_batch_with_pdf(
        SESSION,
        [{"id": 1, "nom": "Participant", "taux_presence": 90}],
    ))

    assert result["total_pdf_generated"] == 0
    assert result["_review_status"] == "generation_failed"
    assert "_review_id" not in result
    assert result["failed_participants"][0]["error"] == "erreur PDF simulée"
