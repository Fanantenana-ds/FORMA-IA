import asyncio
import json
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import public_registration as routes
from app.services.rag import registry_service


def test_assessment_links_require_all_session_supports_to_be_indexed(monkeypatch):
    entries = {
        "indexed": SimpleNamespace(session_id="session-1", collection="support", statut="indexe", nb_chunks=8),
        "failed": SimpleNamespace(session_id="session-1", collection="support", statut="erreur", nb_chunks=0),
        "other-session": SimpleNamespace(session_id="session-2", collection="support", statut="erreur", nb_chunks=0),
        "platform-guide": SimpleNamespace(session_id="session-1", collection="aide_plateforme", statut="erreur", nb_chunks=0),
    }
    monkeypatch.setattr(registry_service, "charger_registre", lambda: entries)

    assert routes._session_has_indexed_support("session-1") is False

    entries.pop("failed")
    assert routes._session_has_indexed_support("session-1") is True
    assert routes._session_has_indexed_support("session-without-support") is False


def test_assessment_link_creation_is_rejected_without_indexed_support(monkeypatch):
    session_id = UUID("00000000-0000-0000-0000-000000000001")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=session_id)
    monkeypatch.setattr(routes, "_session_has_indexed_support", lambda _: False)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            routes.create_public_link(
                routes.CreateLinkRequest(kind="participant", session_id=session_id),
                db=db,
                _user=SimpleNamespace(id=session_id, owner_id=None),
            )
        )

    assert error.value.status_code == 409
    assert "support pédagogique" in error.value.detail


def test_assessment_link_sets_authenticated_tenant_before_reading_registry(monkeypatch):
    session_id = UUID("00000000-0000-0000-0000-000000000001")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=session_id)
    tenant_ids = []
    monkeypatch.setattr(routes, "set_tenant_id", tenant_ids.append)
    monkeypatch.setattr(routes, "_session_has_indexed_support", lambda _: False)

    with pytest.raises(HTTPException):
        asyncio.run(routes.create_public_link(
            routes.CreateLinkRequest(kind="participant", session_id=session_id),
            db=db,
            _user=SimpleNamespace(id=session_id, owner_id=None),
        ))

    assert tenant_ids == [session_id]


def test_rag_context_for_assessment_is_scoped_to_session(monkeypatch):
    captured = {}

    class FauxKnowledgeRepository:
        def lister_chunks_session(self, **kwargs):
            captured.update(kwargs)
            return [{
                "contenu": "Les quatre fonctions sont percevoir, analyser, générer et assister.",
                "fichier": "module-1.pptx",
                "module": "MODULE 1",
                "chunk_index": 2,
            }]

    from app.services.rag import knowledge_repository
    monkeypatch.setattr(knowledge_repository, "KnowledgeRepository", FauxKnowledgeRepository)
    monkeypatch.setattr(
        "app.services.rag.recherche_service.rechercher",
        lambda **_kwargs: pytest.fail("La génération du test ne doit pas appeler Voyage"),
    )

    async def execute():
        return await routes._rag_context_for_formation("FID", "Formation FID", "session-fid")

    context = asyncio.run(execute())

    assert captured["session_id"] == "session-fid"
    assert captured["collection"] == "support"
    assert captured["limit"] == 80
    assert "quatre fonctions" in context
    assert "module-1.pptx" in context


def test_rag_context_without_session_does_not_query_any_documents():
    context = asyncio.run(routes._rag_context_for_formation("FID", "Formation FID"))

    assert context == ""


def test_assessment_does_not_fall_back_to_generic_questions_without_rag_context(monkeypatch):
    async def no_context(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(routes, "_rag_context_for_formation", no_context)
    monkeypatch.setattr(routes, "get_llm_provider", lambda: pytest.fail("Le LLM ne doit pas être appelé sans extrait"))
    session = SimpleNamespace(id="session-fid", formation_code="FID", titre="Opportunité FID")

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes._generate_assessment(session))

    assert error.value.status_code == 409
    assert "Aucun extrait pédagogique" in error.value.detail


def test_assessment_requires_support_proofs_and_rejects_legacy_generic_questions():
    legacy = [{"id": f"q{i}", "enonce": "Question générique"} for i in range(1, 11)]
    grounded = [{"id": f"q{i}", "preuve_support": "RTFCE rôle tâche format contexte exemple"} for i in range(1, 11)]

    assert routes._assessment_est_ancre(legacy) is False
    assert routes._assessment_est_ancre(grounded) is True


def test_assessment_requires_natural_participant_facing_question_stems():
    questions = [{
        "enonce": "Selon la citation, quel est le deuxième élément à connaître ?",
        "preuve_support": "La méthode RTFCE comprend le rôle, la tâche, le format et le contexte.",
    } for _ in range(10)]
    assert routes._assessment_est_ancre(questions) is True
    assert routes._assessment_est_pedagogiquement_presentable(questions) is False
    assert routes._question_est_naturelle({
        "enonce": "Dans la méthode RTFCE, quelle composante précise la forme attendue ?",
    }) is True


@pytest.mark.parametrize(("kind", "stage"), [
    ("participant", "initial"),
    ("post_formation", "final"),
])
def test_existing_assessment_link_refreshes_unnatural_questions(monkeypatch, kind, stage):
    session_id = UUID("00000000-0000-0000-0000-000000000001")
    citation = "La méthode RTFCE précise le rôle, la tâche, le format et le contexte."
    ancien = [{
        "id": f"q{i}", "enonce": "Selon la citation, quel élément faut-il retenir ?",
        "options": [{"id": "A", "label": "Le rôle"}],
        "correct_answer": "A", "preuve_support": citation,
    } for i in range(10)]
    actualise = [{
        "id": f"q{i}", "enonce": f"Quelle notion de la méthode RTFCE est évaluée dans la question {i} ?",
        "options": [{"id": "A", "label": "Le rôle"}],
        "correct_answer": "A", "preuve_support": citation,
    } for i in range(10)]
    session = SimpleNamespace(id=session_id, titre="Session FID", formation_code="FID")
    link = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        token="lien-existant", kind=kind, session_id=session_id,
        active=True, assessment_questions=ancien,
    )
    rows = iter([session, link])

    class FauxQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return next(rows)

    db = SimpleNamespace(query=lambda *_args, **_kwargs: FauxQuery(), commit=lambda: None)
    stages = []

    async def regenerate(_session, stage):
        stages.append(stage)
        return actualise

    monkeypatch.setattr(routes, "_session_has_indexed_support", lambda _session_id: True)
    monkeypatch.setattr(routes, "_generate_assessment", regenerate)

    result = asyncio.run(routes.create_public_link(
        routes.CreateLinkRequest(kind=kind, session_id=session_id),
        db=db,
        _user=SimpleNamespace(id=session_id, owner_id=None),
    ))

    assert result["token"] == "lien-existant"
    assert result["existing"] is True
    assert stages == [stage]
    assert link.assessment_questions == actualise


def test_assessment_rejects_question_without_semantic_overlap_with_its_source():
    context = routes._normaliser_preuve(
        "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et des exemples."
    )
    question_hors_sujet = {
        "competence": "Décision d’embauche",
        "enonce": "Quel critère est déterminant pour recruter un formateur ?",
        "correct_answer": "A",
        "options": [{"id": "A", "label": "Son adéquation avec les besoins pédagogiques"}],
        "preuve_support": "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et des exemples.",
    }

    assert routes._question_est_justifiee(question_hors_sujet, context) is False


def test_assessment_accepts_reformulation_from_a_cited_support_concept():
    citation = "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et l’exemple."
    context = routes._normaliser_preuve(citation)
    question = {
        "competence": "Méthode de prompting",
        "enonce": "Quel élément RTFCE précise la forme attendue de la réponse ?",
        "correct_answer": "B",
        "options": [
            {"id": "A", "label": "Le rôle"},
            {"id": "B", "label": "Le format"},
            {"id": "C", "label": "Le contexte"},
            {"id": "D", "label": "L’exemple"},
        ],
        "preuve_support": citation,
    }

    assert routes._question_est_justifiee(question, context) is True


@pytest.mark.parametrize("stage", ["initial", "final"])
def test_assessment_generates_ten_questions_from_existing_session_chunks(monkeypatch, stage):
    citation = "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et l’exemple."
    questions = []
    for index in range(10):
        questions.append({
            "id": f"q{index + 1}",
            "competence": "Méthode RTFCE",
            "enonce": f"Question distincte {index + 1} sur la méthode RTFCE ?",
            "options": [
                {"id": "A", "label": "Le rôle"}, {"id": "B", "label": "La tâche"},
                {"id": "C", "label": "Le format"}, {"id": "D", "label": "Le contexte"},
            ],
            "correct_answer": "A",
            "preuve_support": citation,
        })

    async def existing_context(*_args, **_kwargs):
        return citation

    class FauxLLM:
        async def generate(self, **kwargs):
            assert kwargs["max_tokens"] == 1700
            assert kwargs["reasoning_effort"] == "low"
            assert "exactement 10" in kwargs["user_prompt"]
            return {"content": json.dumps({"questions": questions})}

    monkeypatch.setattr(routes, "_rag_context_for_formation", existing_context)
    monkeypatch.setattr(routes, "get_llm_provider", lambda: FauxLLM())
    session = SimpleNamespace(id="session-ia", formation_code="FID", titre="Titre administratif")

    generated = asyncio.run(routes._generate_assessment(session, stage=stage))

    assert len(generated) == 10
    assert all(question.get("preuve_support") == citation for question in generated)


def test_assessment_normalizes_option_labels_without_weakening_source_proof():
    question = routes._normaliser_question_llm({
        "question": "Quel élément décrit la forme attendue ?",
        "competence": "Méthode RTFCE",
        "options": {
            "option a": "Le rôle",
            "option b": "Le format",
            "option c": "Le contexte",
            "option d": "La tâche",
        },
        "correct_answer": "option b",
        "preuve_support": "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et l’exemple.",
    })

    assert question is not None
    assert question["correct_answer"] == "B"
    assert {option["id"] for option in question["options"]} == {"A", "B", "C", "D"}
    assert routes._question_est_justifiee(
        question,
        routes._normaliser_preuve(question["preuve_support"]),
    ) is True


def test_assessment_repairs_missing_questions_from_real_context_for_final_stage(monkeypatch):
    citation = "La méthode RTFCE comprend le rôle, la tâche, le format, le contexte et l’exemple."
    options = [
        {"id": "A", "label": "Le rôle"}, {"id": "B", "label": "La tâche"},
        {"id": "C", "label": "Le format"}, {"id": "D", "label": "Le contexte"},
    ]
    questions = [{
        "id": f"q{index}", "competence": "Méthode RTFCE",
        "enonce": f"Quelle notion RTFCE est visée, question {index} ?",
        "options": options, "correct_answer": "A", "preuve_support": citation,
    } for index in range(1, 9)]
    questions.extend([{
        "id": "q9", "competence": "Méthode RTFCE", "enonce": "Quelle notion RTFCE précise le contexte ?",
        "options": options, "correct_answer": "D", "preuve_support": "La méthode propose le contexte.",
    }, {
        "id": "q10", "competence": "Choix", "enonce": "Quel élément est visé ?",
        "options": [{"id": "A", "label": "Banane"}, *options[1:]],
        "correct_answer": "A", "preuve_support": citation,
    }])
    repaired = [
        {
            "id": "r1", "competence": "Méthode RTFCE",
            "enonce": "Dans la méthode RTFCE, quelle composante précise la forme attendue ?",
            "options": options, "correct_answer": "C", "preuve_support": citation,
        },
        {
            "id": "r2", "competence": "Méthode RTFCE",
            "enonce": "Dans la méthode RTFCE, quelle composante donne les informations utiles à la demande ?",
            "options": options, "correct_answer": "D", "preuve_support": citation,
        },
    ]
    calls = []

    async def existing_context(*_args, **_kwargs):
        return f"[Document : module.pptx ; module : MODULE 1 ; passage 1] {citation}"

    class FauxLLM:
        async def generate(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {"content": json.dumps({"questions": questions})}
            assert kwargs["max_tokens"] == 600
            assert "2 question(s)" in kwargs["user_prompt"]
            assert "Extraits autorisés" in kwargs["user_prompt"]
            return {"content": json.dumps({"questions": repaired})}

    monkeypatch.setattr(routes, "_rag_context_for_formation", existing_context)
    monkeypatch.setattr(routes, "get_llm_provider", lambda: FauxLLM())
    session = SimpleNamespace(id="session-ia", formation_code="FID", titre="Titre administratif")

    generated = asyncio.run(routes._generate_assessment(session, stage="final"))

    assert len(generated) == 10
    assert len(calls) == 2
    assert all(question["preuve_support"] == citation for question in generated[-2:])


@pytest.mark.parametrize("response", [
    {"content": "", "finish_reason": "stop"},
    {"content": '{"questions":', "finish_reason": "length"},
])
def test_assessment_reports_empty_or_truncated_llm_output_without_generic_fallback(monkeypatch, response):
    async def existing_context(*_args, **_kwargs):
        return "[Document : module.pptx ; module : MODULE 1 ; passage 1] La méthode RTFCE précise le rôle, la tâche, le format, le contexte et l’exemple."

    class FauxLLM:
        async def generate(self, **_kwargs):
            return response

    monkeypatch.setattr(routes, "_rag_context_for_formation", existing_context)
    monkeypatch.setattr(routes, "get_llm_provider", lambda: FauxLLM())
    session = SimpleNamespace(id="session-ia", formation_code="FID", titre="Titre administratif")

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes._generate_assessment(session))

    assert error.value.status_code == 503
    assert "Aucun questionnaire générique" in error.value.detail


def test_assessment_reports_daily_provider_quota_without_retry_or_generic_fallback(monkeypatch):
    async def existing_context(*_args, **_kwargs):
        return "[Document : module.pptx ; module : MODULE 1 ; passage 1] La méthode RTFCE précise le rôle, la tâche, le format, le contexte et l’exemple."

    calls = []

    class FauxLLM:
        async def generate(self, **_kwargs):
            calls.append(True)
            raise routes.LLMRateLimitError("Rate limit reached on tokens per day (TPD)")

    monkeypatch.setattr(routes, "_rag_context_for_formation", existing_context)
    monkeypatch.setattr(routes, "get_llm_provider", lambda: FauxLLM())
    session = SimpleNamespace(id="session-ia", formation_code="FID", titre="Titre administratif")

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes._generate_assessment(session))

    assert error.value.status_code == 503
    assert "quota journalier" in error.value.detail
    assert len(calls) == 1


def test_tpm_retry_waits_once_then_retries_provider(monkeypatch):
    calls = []
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    class FauxLLM:
        async def generate(self, **_kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise routes.LLMRateLimitError(
                    "Rate limit reached on tokens per minute (TPM). Please try again in 3.39s."
                )
            return {"content": "ok"}

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    result = asyncio.run(routes._generate_llm_with_tpm_retry(FauxLLM(), prompt="test"))

    assert result == {"content": "ok"}
    assert len(calls) == 2
    assert delays == [3.49]


def test_tpm_retry_parses_millisecond_delay(monkeypatch):
    calls = []
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    class FauxLLM:
        async def generate(self, **_kwargs):
            calls.append(True)
            if len(calls) == 1:
                raise routes.LLMRateLimitError(
                    "Rate limit reached on tokens per minute (TPM). Please try again in 292.5ms."
                )
            return {"content": "ok"}

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    result = asyncio.run(routes._generate_llm_with_tpm_retry(FauxLLM(), prompt="test"))

    assert result == {"content": "ok"}
    assert len(calls) == 2
    assert delays == [pytest.approx(0.3925)]


def test_tpm_retry_does_not_retry_daily_quota():
    calls = []

    class FauxLLM:
        async def generate(self, **_kwargs):
            calls.append(True)
            raise routes.LLMRateLimitError("Rate limit reached on tokens per day (TPD)")

    with pytest.raises(routes.LLMRateLimitError):
        asyncio.run(routes._generate_llm_with_tpm_retry(FauxLLM(), prompt="test"))

    assert len(calls) == 1


def test_public_link_revocation_disables_url_and_preserves_history():
    db = MagicMock()
    link = SimpleNamespace(active=True)
    db.query.return_value.filter.return_value.first.return_value = link

    result = routes.revoke_public_link("token-test", db=db, _user=SimpleNamespace())

    assert link.active is False
    db.commit.assert_called_once_with()
    assert result["success"] is True


def test_public_link_revocation_returns_404_when_link_is_missing_or_inactive():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as error:
        routes.revoke_public_link("token-test", db=db, _user=SimpleNamespace())

    assert error.value.status_code == 404
