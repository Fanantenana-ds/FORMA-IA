import secrets
import uuid
import logging
import json
import random
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.core.tenant_context import set_tenant_id
from app.database import get_db
from app.models.formation import Inscription, Participant, Session as TrainingSession
from app.models.public_registration import PublicAssessmentAttempt, PublicRegistrationLink
from app.models.document import Document, StatutValidation, TypeDocument
from app.models.rh import Candidat, DecisionPreselection, Formateur, RecommandationEvaluation
from app.models.user import User
from app.services.llm import LLMRateLimitError, get_llm_provider

router = APIRouter(prefix="/public", tags=["Inscriptions publiques"])
logger = logging.getLogger(__name__)


async def _generate_llm_with_tpm_retry(provider, **kwargs):
    """Retry once only for a short per-minute TPM window, never for daily quota."""
    try:
        return await provider.generate(**kwargs)
    except LLMRateLimitError as exc:
        message = str(exc).lower()
        if "tokens per minute" not in message and "(tpm)" not in message:
            raise
        match = re.search(
            r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|milliseconds?|s|seconds?)\b",
            message,
        )
        if not match:
            raise
        delay_seconds = float(match.group(1))
        if match.group(2).startswith("m"):
            delay_seconds /= 1000
        if delay_seconds < 0 or delay_seconds > 8:
            raise
        import asyncio

        logger.info("Limite TPM temporaire ; reprise unique après %.3f s.", delay_seconds)
        await asyncio.sleep(delay_seconds + 0.1)
        return await provider.generate(**kwargs)


class CreateLinkRequest(BaseModel):
    kind: Literal["participant", "formateur", "post_formation"]
    session_id: UUID | None = None


class ParticipantRegistration(BaseModel):
    nom: str = Field(min_length=1, max_length=50)
    prenom: str = Field(min_length=1, max_length=50)
    email: EmailStr
    organisation: str | None = Field(default=None, max_length=30)
    poste: str | None = Field(default=None, max_length=100)
    assessment_attempt_id: str | None = Field(default=None, max_length=96)
    answers: list[dict[str, str]] = Field(default_factory=list)


class PostFormationSubmission(BaseModel):
    email: EmailStr
    assessment_attempt_id: str = Field(min_length=20, max_length=96)
    answers: list[dict[str, str]] = Field(default_factory=list)
    satisfaction_answers: list[dict[str, str]] = Field(default_factory=list)


SATISFACTION_QUESTIONS = [
    {"id": "sat_1", "label": "Maîtrise du sujet par le formateur", "type": "rating"},
    {"id": "sat_2", "label": "Clarté des explications", "type": "rating"},
    {"id": "sat_3", "label": "Qualité des exercices et mises en pratique", "type": "rating"},
    {"id": "sat_4", "label": "Écoute et disponibilité du formateur", "type": "rating"},
    {"id": "sat_5", "label": "Atteinte des objectifs de la formation", "type": "rating"},
    {"id": "sat_6", "label": "Recommanderiez-vous ce formateur ?", "type": "choice", "options": ["Oui", "Non"]},
    {"id": "sat_7", "label": "Votre commentaire ou suggestion", "type": "text"},
]


def _ensure_ten_assessment_questions(link: PublicRegistrationLink, session: TrainingSession, db: Session) -> list[dict]:
    """Return persisted questions without inventing generic replacements."""
    questions = list(link.assessment_questions or [])
    return questions[:10]


async def _rag_context_for_formation(
    formation_code: str | None, titre: str, session_id: UUID | str | None = None
) -> str:
    """Reuse the session's persisted chunks; never re-embed or query other sessions."""
    if not session_id:
        return ""
    try:
        from app.services.rag.knowledge_repository import KnowledgeRepository
        chunks = KnowledgeRepository().lister_chunks_session(
            session_id=str(session_id), collection="support", limit=80,
        )
        if not chunks:
            return ""
        passages = [
            (
                f"[Document : {chunk.get('fichier') or 'support'} ; "
                f"module : {chunk.get('module') or 'non précisé'} ; "
                f"passage {chunk.get('chunk_index') if chunk.get('chunk_index') is not None else i + 1}]\n"
                f"{str(chunk.get('contenu') or '')[:1200]}"
            )
            for i, chunk in enumerate(chunks)
            if str(chunk.get("contenu") or "").strip()
        ]
        return "\n\n".join(passages)
    except Exception:
        logger.exception("Lecture des chunks RAG déjà indexés impossible pour le questionnaire.")
        return ""


def _normaliser_preuve(value: str) -> str:
    sans_accents = "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z0-9]+", sans_accents))


def _assessment_est_ancre(questions: list[dict] | None) -> bool:
    return bool(questions) and len(questions) >= 10 and all(
        isinstance(question, dict) and isinstance(question.get("preuve_support"), str)
        and len(_normaliser_preuve(question["preuve_support"])) >= 5
        for question in questions[:10]
    )


def _question_est_naturelle(question: dict) -> bool:
    """Reject stems that talk about the source instead of asking the learner."""
    enonce_brut = str(question.get("enonce") or "").strip()
    if not enonce_brut.endswith("?"):
        return False
    enonce = _normaliser_preuve(enonce_brut)
    references_source = (
        "selon le texte", "dans le texte", "selon la citation", "dans la citation",
        "selon l extrait", "dans l extrait", "selon le support", "dans le support",
        "selon le document", "dans le document", "citation", "extrait indexe",
    )
    if any(reference in enonce for reference in references_source):
        return False
    if re.search(r"\bquel(?:le)? element\b", enonce) and not any(
        sujet in enonce for sujet in ("methode rtfce", "reseau de neurones", "machine learning")
    ):
        return False
    return True


def _assessment_est_pedagogiquement_presentable(questions: list[dict] | None) -> bool:
    return _assessment_est_ancre(questions) and all(
        isinstance(question, dict) and _question_est_naturelle(question)
        for question in (questions or [])[:10]
    )


def _contexte_compact_reparation(rag_context: str, questions: list[dict], limit: int = 4) -> str:
    """Choose short real indexed passages related to rejected questions."""
    passages = [
        passage.strip() for passage in re.split(r"(?=\[Document :)", rag_context)
        if passage.strip().startswith("[Document :")
    ]
    if not passages:
        return ""
    stopwords = {
        "avec", "dans", "pour", "plus", "quel", "quelle", "quels", "quelles",
        "comment", "pourquoi", "selon", "faire", "formation", "support",
        "module", "question", "reponse", "document", "citation", "extrait",
    }
    termes_requetes = {
        terme for question in questions
        for terme in _normaliser_preuve(" ".join([
            str(question.get("enonce") or ""), str(question.get("competence") or ""),
            *[str(option.get("label") or "") for option in question.get("options", []) if isinstance(option, dict)],
        ])).split()
        if len(terme) >= 4 and terme not in stopwords
    }
    classes = []
    for index, passage in enumerate(passages):
        termes_passage = set(_normaliser_preuve(passage).split())
        score = len(termes_requetes & termes_passage)
        lignes = passage.splitlines()
        contenu = "\n".join(lignes[1:]).strip()
        extrait = contenu[:350].rsplit(" ", 1)[0] if len(contenu) > 350 else contenu
        classes.append((score, -index, f"{lignes[0]}\n{extrait}"))
    selection = sorted(classes, key=lambda item: (item[0], item[1]), reverse=True)[:limit]
    return "\n\n".join(passage for _score, _ordre, passage in selection)


def _question_est_justifiee(question: dict, contexte_normalise: str) -> bool:
    preuve = question.get("preuve_support")
    if not isinstance(preuve, str):
        return False
    preuve_normalisee = _normaliser_preuve(preuve)
    if len(preuve_normalisee) < 5 or preuve_normalisee not in contexte_normalise:
        return False

    stopwords = {
        "avec", "dans", "pour", "plus", "quel", "quelle", "quels", "quelles",
        "comment", "pourquoi", "selon", "faire", "fait", "etre", "avoir", "cette",
        "cela", "leur", "leurs", "vous", "votre", "formation", "support",
        "module", "competence", "competences", "notion", "notions", "question",
        "reponse", "extrait", "document", "documente", "explique", "presente",
    }
    options = question.get("options") or []
    bonne_reponse = next(
        (option.get("label", "") for option in options
         if isinstance(option, dict) and str(option.get("id")) == str(question.get("correct_answer"))),
        "",
    )
    termes_question = {
        terme for terme in _normaliser_preuve(
            f"{question.get('competence', '')} {question.get('enonce', '')} {bonne_reponse}"
        ).split()
        if len(terme) >= 4 and terme not in stopwords
    }
    termes_preuve = {
        terme for terme in preuve_normalisee.split()
        if len(terme) >= 4 and terme not in stopwords
    }
    # Une notion centrale suffit : une question peut légitimement reformuler
    # le passage avec des synonymes, mais doit garder au moins un terme
    # pédagogique précis en commun avec sa preuve.
    return bool(termes_preuve) and bool(termes_question & termes_preuve)


def _normaliser_question_llm(question: object) -> dict | None:
    """Normalize harmless JSON shape variations without relaxing source checks."""
    if not isinstance(question, dict):
        return None
    raw_options = question.get("options")
    if isinstance(raw_options, dict):
        raw_options = [{"id": key, "label": value} for key, value in raw_options.items()]
    if not isinstance(raw_options, list) or len(raw_options) != 4:
        return None

    options = []
    for index, option in enumerate(raw_options):
        if isinstance(option, str):
            option_id, label = chr(ord("A") + index), option
        elif isinstance(option, dict):
            option_id = str(option.get("id") or option.get("key") or "").strip().upper()
            label = option.get("label") or option.get("text") or option.get("texte")
            match_id = re.search(r"\b([A-D])\b", option_id)
            option_id = match_id.group(1) if match_id else ""
        else:
            return None
        if option_id not in {"A", "B", "C", "D"} or not isinstance(label, str) or not label.strip():
            return None
        options.append({"id": option_id, "label": label.strip()})
    if {option["id"] for option in options} != {"A", "B", "C", "D"}:
        return None

    raw_answer = str(question.get("correct_answer") or "").strip().upper()
    answer_match = re.match(r"^(?:OPTION\s*)?([A-D])(?:\b|\s|[).:-])", raw_answer)
    if answer_match:
        correct_answer = answer_match.group(1)
    else:
        correct_answer = next(
            (option["id"] for option in options if option["label"].casefold() == raw_answer.casefold()),
            "",
        )

    enonce = question.get("enonce") or question.get("question")
    preuve = question.get("preuve_support")
    if not isinstance(enonce, str) or not enonce.strip() or not isinstance(preuve, str):
        return None
    return {
        "id": str(question.get("id") or "").strip(),
        "competence": str(question.get("competence") or question.get("objectif") or "").strip(),
        "enonce": enonce.strip(),
        "options": options,
        "correct_answer": correct_answer,
        "preuve_support": preuve.strip().strip("\"'«»“”"),
    }


async def _generate_assessment(session: TrainingSession, stage: str = "initial") -> list[dict]:
    """Generate a private, answer-key questionnaire for a training stage."""
    rag_context = await _rag_context_for_formation(
        session.formation_code, session.titre, session.id
    )
    if not rag_context.strip():
        raise HTTPException(
            status_code=409,
            detail=(
                "Aucun extrait pédagogique exploitable n’a été trouvé dans les supports indexés de cette session. "
                "Le lien d’évaluation n’a pas été généré afin d’éviter un questionnaire hors sujet."
            ),
        )
    context_block = (
        f"\n\nCONTENU PÉDAGOGIQUE INDEXÉ (extraits réels des supports de la formation) :\n{rag_context}\n\n"
        "Base chaque question exclusivement sur ces extraits. Le titre de session et le code client sont administratifs : "
        "ne les utilise jamais comme source de notions pédagogiques. Pour chaque question, fournis preuve_support : "
        "une citation courte, copiée mot pour mot d’un extrait qui justifie la question et sa bonne réponse. "
        "Produis exactement 10 questions distinctes : si les supports présentent peu de notions, reformule ces notions "
        "sous des angles pédagogiques différents (expliquer, distinguer, appliquer à un cas simple, repérer une limite, "
        "choisir une méthode), sans ajouter de nouveaux concepts, faits ou objectifs. La question et sa réponse attendue "
        "doivent toutes deux pouvoir être justifiées par la citation. La bonne réponse doit reprendre littéralement "
        "au moins un terme pédagogique distinctif de sa preuve_support ; évite les synonymes qui empêchent de vérifier "
        "le lien entre la réponse et l’extrait. Les questions sont destinées directement aux participants : écris-les "
        "comme un formateur les poserait naturellement, de façon autonome et précise. Ne mentionne jamais le texte, "
        "la citation, l’extrait ou le support. Évite les formulations vagues comme « quel élément ? », « quel terme ? » "
        "ou « quelle affirmation ? ». N’interroge qu’une notion clairement nommée et évite les questions tautologiques."
    )
    objectif_etape = (
        "Évalue les acquis après la formation : privilégie l’application à une situation simple lorsque les supports "
        "la permettent, sinon vérifie clairement une notion enseignée."
        if stage == "final"
        else "Évalue le niveau de départ : vérifie les notions fondamentales sans supposer que le participant a déjà suivi la formation."
    )
    try:
        llm_provider = get_llm_provider()
        response = await _generate_llm_with_tpm_retry(
            llm_provider,
            system_prompt=("Tu conçois une évaluation en français STRICTEMENT à partir des extraits fournis. N’ajoute aucune connaissance générale, aucun sujet tiré du nom du client ou du titre administratif, et refuse implicitement toute notion absente des extraits. "
                           "Écris pour les participants avec une formulation naturelle, claire et précise. Le test final mesure les acquis; le test initial mesure le niveau de départ, sans juger la personne."),
            user_prompt=(f"Crée exactement 10 QCM concis de {'validation des acquis après la formation' if stage == 'final' else 'positionnement avant la formation'} à partir des seuls extraits ci-dessous."
                         f"{objectif_etape}\n{context_block} Retourne uniquement un objet JSON avec une clé questions. "
                         "Chaque question doit avoir id (q1...), competence courte, enonce court, options (4 objets id A-D et label court), "
                         "correct_answer (A-D), preuve_support (citation exacte des extraits). Questions concrètes, progressives, "
                         "une seule bonne réponse. Varie l’angle, jamais le contenu. N’invente rien. "
                         "Réponse très concise : une phrase par énoncé, options brèves et preuve courte exacte."),
            temperature=0.1, max_tokens=1700, json_mode=True,
            reasoning_effort="low",
        )
        if response.get("finish_reason") == "length":
            raise ValueError("La réponse du modèle a été tronquée avant la fin du questionnaire.")
        contenu_json = str(response.get("content") or "").strip()
        if not contenu_json:
            raise ValueError("Le fournisseur IA a renvoyé une réponse vide pour le questionnaire.")
        data = json.loads(contenu_json)
        questions_brutes = data.get("questions", []) if isinstance(data, dict) else []
        questions = [_normaliser_question_llm(question) for question in questions_brutes]
        questions = [question for question in questions if question is not None]
        extrait_normalise = _normaliser_preuve(rag_context)
        structurellement_valides = [
            question for question in questions
            if question["correct_answer"] in {"A", "B", "C", "D"}
        ]
        preuves_exactes = [
            question for question in structurellement_valides
            if len(_normaliser_preuve(question["preuve_support"])) >= 5
            and _normaliser_preuve(question["preuve_support"]) in extrait_normalise
        ]
        valid = [question for question in preuves_exactes
                 if _question_est_justifiee(question, extrait_normalise)
                 and _question_est_naturelle(question)]
        questions_uniques = {}
        for question in valid:
            cle = _normaliser_preuve(str(question["enonce"]))
            if cle:
                questions_uniques.setdefault(cle, question)
        valid = list(questions_uniques.values())
        if len(valid) < 10:
            # Répare seulement les éléments rejetés par la qualité du libellé,
            # la preuve ou l'unicité, à partir du contexte RAG réellement indexé.
            candidats_reparation = []
            enonces_vus = set()
            for question in structurellement_valides:
                cle = _normaliser_preuve(str(question["enonce"]))
                if not cle:
                    continue
                preuve_exacte = (
                    len(_normaliser_preuve(question["preuve_support"])) >= 5
                    and _normaliser_preuve(question["preuve_support"]) in extrait_normalise
                )
                if (not preuve_exacte
                        or not _question_est_justifiee(question, extrait_normalise)
                        or not _question_est_naturelle(question)
                        or cle in enonces_vus):
                    candidats_reparation.append(question)
                enonces_vus.add(cle)

            nombre_a_reparer = 10 - len(valid)
            contexte_reparation = _contexte_compact_reparation(
                rag_context, candidats_reparation or structurellement_valides,
            )
            if nombre_a_reparer and contexte_reparation:
                stems_existants = [question["enonce"] for question in valid]
                reponse_reparation = await _generate_llm_with_tpm_retry(
                    llm_provider,
                    system_prompt=(
                        "Tu rédiges des questions de formation naturellement adressées aux participants, à partir des seuls extraits fournis. "
                        "La bonne réponse doit reprendre littéralement un terme distinctif de sa preuve exacte. N’ajoute aucun fait. "
                        "N’évoque jamais le texte, la citation, l’extrait ou le support dans la question. Retourne uniquement un objet JSON valide."
                    ),
                    user_prompt=(
                        f"Crée exactement {nombre_a_reparer} question(s) QCM distincte(s) à partir de ces extraits indexés. "
                        f"{objectif_etape} Chaque question doit nommer clairement la notion visée, avoir une formulation naturelle, "
                        "une seule bonne réponse clairement justifiée, quatre choix courts id A-D, et une preuve_support copiée "
                        "mot pour mot d’un extrait. Évite les formulations vagues ou tautologiques. "
                        f"Ne répète pas ces questions : {json.dumps(stems_existants, ensure_ascii=False)}. "
                        f"Extraits autorisés : {contexte_reparation}. "
                        '{"questions":[{"id":"r1","competence":"...","enonce":"...",'
                        '"options":[{"id":"A","label":"..."},{"id":"B","label":"..."},'
                        '{"id":"C","label":"..."},{"id":"D","label":"..."}],'
                        '"correct_answer":"A","preuve_support":"citation exacte"}]}'
                    ),
                    temperature=0.1,
                    max_tokens=min(600, max(350, nombre_a_reparer * 300)),
                    json_mode=True,
                    reasoning_effort="low",
                )
                contenu_reparation = str(reponse_reparation.get("content") or "").strip()
                if reponse_reparation.get("finish_reason") != "length" and contenu_reparation:
                    donnees_reparees = json.loads(contenu_reparation)
                    questions_reparees = donnees_reparees.get("questions", []) if isinstance(donnees_reparees, dict) else []
                    for brute in questions_reparees:
                        question = _normaliser_question_llm(brute)
                        if not question or question["correct_answer"] not in {"A", "B", "C", "D"}:
                            continue
                        preuve = _normaliser_preuve(question["preuve_support"])
                        cle = _normaliser_preuve(question["enonce"])
                        if (len(preuve) < 5 or preuve not in extrait_normalise or not cle
                                or cle in questions_uniques or not _question_est_justifiee(question, extrait_normalise)
                                or not _question_est_naturelle(question)):
                            continue
                        questions_uniques[cle] = question
                        if len(questions_uniques) == 10:
                            break
                valid = list(questions_uniques.values())
        if len(valid) >= 10:
            for index, question in enumerate(valid[:10], start=1):
                question["id"] = f"q{index}"
            return valid[:10]
        logger.warning(
            "Questionnaire rejeté après validation des preuves "
            "(session=%s, étape=%s, reçues=%s, format_valide=%s, preuve_exacte_initiale=%s, "
            "preuve_et_réponse_initiale=%s, réparées_acceptées=%s, distinctes_finales=%s).",
            session.id, stage, len(questions_brutes), len(structurellement_valides),
            len(preuves_exactes), len([question for question in preuves_exactes if _question_est_justifiee(question, extrait_normalise)]),
            max(0, len(valid) - len([question for question in preuves_exactes if _question_est_justifiee(question, extrait_normalise)])),
            len(questions_uniques),
        )
    except HTTPException:
        raise
    except LLMRateLimitError as exc:
        message_quota = str(exc).lower()
        quota_journalier = any(
            marqueur in message_quota
            for marqueur in ("tokens per day", "(tpd)", "quota journalier", "limite journalière")
        )
        logger.warning(
            "Limite LLM atteinte pour le questionnaire (type=%s, session=%s, étape=%s, extraits=%s, caractères_contexte=%s).",
            "journalier" if quota_journalier else "par minute",
            session.id, stage, rag_context.count("[Document :"), len(rag_context),
        )
        raise HTTPException(
            status_code=503,
            detail=(
                ("Le quota journalier du fournisseur IA est atteint. Aucun questionnaire générique n’a été créé. "
                 "Réessayez après le renouvellement du quota.")
                if quota_journalier else
                "La limite temporaire de requêtes IA est atteinte. Aucun questionnaire générique n’a été créé. Réessayez dans quelques secondes."
            ),
        ) from exc
    except Exception as exc:
        logger.exception(
            "La génération IA du questionnaire basé sur les supports a échoué "
            "(session=%s, étape=%s, extraits=%s, caractères_contexte=%s, erreur=%s).",
            session.id, stage, rag_context.count("[Document :"), len(rag_context), type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Le fournisseur IA n’a pas terminé le questionnaire à partir des supports. "
                "Aucun questionnaire générique n’a été créé ; vous pouvez relancer la génération."
            ),
        ) from exc
    raise HTTPException(
        status_code=422,
        detail=(
            "Les supports de cette session ne permettent pas de valider dix questions avec une preuve textuelle fiable. "
            "Aucun questionnaire hors sujet n’a été créé. Vérifiez le contenu indexé puis relancez la génération."
        ),
    )


def _public_question(question: dict) -> dict:
    return {"id": question["id"], "competence": question.get("competence", ""),
            "enonce": question["enonce"], "options": question["options"]}


def _individualize_assessment(pool: list[dict]) -> list[dict]:
    """Build a per-visit variant: a randomized subset, question order and answer order."""
    if not pool:
        return []
    count = min(10, len(pool))
    selected = random.sample(pool, count) if len(pool) > count else list(pool)
    randomized = []
    for question in selected:
        item = dict(question)
        old_options = list(question.get("options") or [])
        random.shuffle(old_options)
        remap = {str(option.get("id")): chr(65 + index) for index, option in enumerate(old_options)}
        item["options"] = [{"id": remap[str(option.get("id"))], "label": option.get("label", "")} for option in old_options]
        if question.get("correct_answer") is not None:
            item["correct_answer"] = remap.get(str(question["correct_answer"]))
        if question.get("options_scoring"):
            item["options_scoring"] = {remap[key]: value for key, value in question["options_scoring"].items() if key in remap}
        randomized.append(item)
    random.shuffle(randomized)
    return randomized


async def _classify_initial_level(session: TrainingSession, questions: list[dict], answers: dict[str, str], score: int, stage: str = "initial") -> str:
    """Use IA to classify a participant's initial or final level, with score fallback."""
    fallback = "Débutant" if score < 20 else "Intermédiaire" if score < 40 else "Normal" if score < 60 else "Avancé" if score < 80 else "Expert"
    summary = []
    for question in questions:
        answer = answers.get(question["id"])
        scoring = question.get("options_scoring") or {}
        summary.append({
            "question": question.get("enonce"),
            "reponse": answer,
            "points": scoring.get(answer) if scoring else (1 if answer == question.get("correct_answer") else 0),
            "bonne_reponse": None if scoring else answer == question.get("correct_answer"),
            "competence": question.get("competence"),
        })
    try:
        result = await get_llm_provider().generate(
            system_prompt=("Tu évalues objectivement les acquis d'un participant après une formation. "
                           "Ne juges pas la personne; classe uniquement les compétences démontrées." if stage == "final" else
                           "Tu classes un niveau initial de formation selon un diagnostic objectif. Ne juges pas la personne; choisis exclusivement une des catégories demandées."),
            user_prompt=(f"Formation: {session.titre}. Étape: {'test final après formation' if stage == 'final' else 'test initial avant formation'}. "
                         f"Score: {score}/100. Réponses: {json.dumps(summary, ensure_ascii=False)}. "
                         "Classe le niveau parmi exactement: Débutant, Intermédiaire, Normal, Avancé, Expert. "
                         "Retourne uniquement JSON: {\"niveau\":\"...\"}. Repères: 0-19 débutant, 20-39 intermédiaire, 40-59 normal, 60-79 avancé, 80-100 expert."),
            temperature=0, max_tokens=100, json_mode=True,
        )
        level = str(json.loads(result["content"]).get("niveau", "")).strip().lower()
        allowed = {"débutant":"Débutant", "debutant":"Débutant", "intermédiaire":"Intermédiaire", "intermediaire":"Intermédiaire", "normal":"Normal", "avancé":"Avancé", "avance":"Avancé", "expert":"Expert"}
        return allowed.get(level, fallback)
    except Exception:
        logger.exception("La classification IA du niveau initial a échoué; classement par score utilisé.")
        return fallback


@router.post("/links")
async def create_public_link(
    payload: CreateLinkRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    # require_role() s'appuie sur le contexte posé par une dépendance synchrone.
    # Reposer le tenant dans cette coroutine garantit que le registre RAG lu
    # ci-dessous est celui du directeur connecté.
    set_tenant_id(_user.owner_id or _user.id)
    if not payload.session_id:
        raise HTTPException(422, "session_id est obligatoire pour un lien lié à une formation.")
    session = db.query(TrainingSession).filter(TrainingSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(404, "Session introuvable.")
    if payload.kind in {"participant", "post_formation"} and not _session_has_indexed_support(session.id):
        raise HTTPException(
            status_code=409,
            detail=(
                "Indexez au moins un support pédagogique de cette session avant de générer "
                "un lien d'évaluation pour les participants."
            ),
        )
    existing_link = db.query(PublicRegistrationLink).filter(
        PublicRegistrationLink.kind == payload.kind,
        PublicRegistrationLink.session_id == payload.session_id,
        PublicRegistrationLink.active.is_(True),
    ).order_by(PublicRegistrationLink.date_creation.desc()).first()
    if existing_link:
        question_count = len(existing_link.assessment_questions or [])
        if payload.kind in {"participant", "post_formation"} and not _assessment_est_pedagogiquement_presentable(existing_link.assessment_questions):
            # Modernise les anciens questionnaires imprécis au prochain clic,
            # sans changer l'URL si la nouvelle génération aboutit.
            questions = await _generate_assessment(
                session, stage="final" if payload.kind == "post_formation" else "initial"
            )
            existing_link.assessment_questions = questions
            db.commit()
            question_count = len(questions)
        return {"token": existing_link.token, "kind": existing_link.kind,
                "session_id": str(existing_link.session_id) if existing_link.session_id else None,
                "path": f"/inscription-publique/{existing_link.token}",
                "assessment_question_count": question_count, "existing": True}
    token = secrets.token_urlsafe(36)
    questions = await _generate_assessment(session, stage="final" if payload.kind == "post_formation" else "initial") if payload.kind in {"participant", "post_formation"} else None
    link = PublicRegistrationLink(token=token, kind=payload.kind, session_id=payload.session_id,
                                 assessment_questions=questions)
    db.add(link)
    db.commit()
    return {"token": token, "kind": payload.kind, "session_id": str(payload.session_id) if payload.session_id else None,
            "path": f"/inscription-publique/{token}", "assessment_question_count": len(questions or [])}


def _session_has_indexed_support(session_id: UUID | str) -> bool:
    """Require every pedagogical support for the session to have indexed chunks."""
    from app.services.rag import registry_service

    supports = [
        entry
        for entry in registry_service.charger_registre().values()
        if str(entry.session_id) == str(session_id)
        and entry.collection == "support"
    ]
    return bool(supports) and all(
        entry.statut == "indexe" and (entry.nb_chunks or 0) > 0
        for entry in supports
    )


@router.get("/links/session/{session_id}")
def get_session_public_links(
    session_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    links = (db.query(PublicRegistrationLink)
             .filter(PublicRegistrationLink.session_id == session_id, PublicRegistrationLink.active.is_(True))
             .order_by(PublicRegistrationLink.date_creation.desc()).all())
    latest = {}
    for link in links:
        if link.kind not in latest:
            latest[link.kind] = {"token": link.token, "path": f"/inscription-publique/{link.token}"}
    return latest


@router.delete("/links/{token}", summary="Désactiver un lien public de session")
def revoke_public_link(
    token: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role("DIRECTION", "ADMIN", "ASSISTANT")),
):
    """Révoque le lien sans effacer les inscriptions ou réponses déjà reçues."""
    link = db.query(PublicRegistrationLink).filter(
        PublicRegistrationLink.token == token,
        PublicRegistrationLink.active.is_(True),
    ).first()
    if link is None:
        raise HTTPException(404, "Lien introuvable ou déjà désactivé.")
    link.active = False
    db.commit()
    return {"success": True, "message": "Le lien public a été désactivé."}


def _get_link(token: str, db: Session) -> PublicRegistrationLink:
    link = db.query(PublicRegistrationLink).filter(PublicRegistrationLink.token == token, PublicRegistrationLink.active.is_(True)).first()
    if not link:
        raise HTTPException(404, "Lien d’inscription invalide ou désactivé.")
    if link.owner_id is not None:
        # Public submissions have no user token; inherit the tenant from the
        # authenticated owner who created this public link.
        db.info["tenant_owner_id"] = link.owner_id
        set_tenant_id(link.owner_id)
    return link


def _public_formation_details(db: Session, session: TrainingSession, *, for_trainer: bool = False) -> dict:
    """Expose only approved, explicitly public-facing TDR fields on a public link."""
    content: dict = {}
    if session.opportunite_id:
        tdr = (db.query(Document)
               .filter(
                   Document.opportunite_id == session.opportunite_id,
                   Document.type == TypeDocument.TDR,
                   Document.statut_validation == StatutValidation.VALIDE,
               )
               .order_by(Document.date_generation.desc())
               .first())
        if tdr and tdr.contenu:
            try:
                parsed = json.loads(tdr.contenu)
                if isinstance(parsed, dict):
                    content = parsed
            except (TypeError, json.JSONDecodeError):
                pass
    if for_trainer and not content and session.opportunite_id:
        # La synchronisation M2 crée parfois un Document EN_ATTENTE côté Backend.
        # Seule l'approbation HITL de cette même opportunité autorise alors la
        # publication du profil sur le lien de candidature.
        from app.services.hitl import get_review as get_hitl_review
        from app.services.hitl import list_reviews as list_hitl_reviews

        for item in list_hitl_reviews(status="approved", agent_id="agent_m2_tdr"):
            approved = get_hitl_review(item["review_id"]) or {}
            brief = ((approved.get("data") or {}).get("_inputs") or {}).get("brief") or {}
            if str(brief.get("opportunite_id") or "") != str(session.opportunite_id):
                continue
            candidate_content = (approved.get("data") or {}).get("data")
            if approved.get("status") == "approved" and isinstance(candidate_content, dict):
                content = candidate_content
                break

    def public_text(value, max_length: int = 1500) -> str | None:
        if not isinstance(value, (str, int, float)):
            return None
        result = str(value).strip()
        return result[:max_length] or None

    def public_list(*values, item_limit: int = 12) -> list[str]:
        value = next((item for item in values if item), [])
        if isinstance(value, str):
            value = [line.strip(" •-\t") for line in value.splitlines() if line.strip(" •-\t")]
        if not isinstance(value, (list, tuple)):
            return []
        return [text for item in value[:item_limit] if (text := public_text(item, 400))]

    specific_objectives = public_list(
        content.get("objectifs_specifiques"), content.get("objectif_specifique"), content.get("objectifs")
    )
    details = {
        "titre": public_text(content.get("titre_formation") or content.get("titre"), 180) or session.titre,
        "contexte": public_text(content.get("contexte")),
        "client": public_text(session.client or content.get("client_nom"), 180),
        "client_description": public_text(content.get("client_description") or content.get("description_client")),
        "objectif_general": public_text(content.get("objectif_general") or content.get("objectif")),
        "objectifs_specifiques": specific_objectives,
        "competences_requises": public_list(content.get("competences_requises"), content.get("competences")),
        "benefices": public_list(content.get("benefices_participants"), content.get("benefices"), content.get("resultats_attendus")) or specific_objectives,
        "date_debut": session.date_debut.isoformat() if session.date_debut else None,
        "date_fin": session.date_fin.isoformat() if session.date_fin else None,
        "lieu": public_text(session.lieu, 180),
    }
    if for_trainer:
        details["formateur_profil"] = public_text(content.get("formateur_profil"))
    return details


@router.get("/links/{token}")
async def get_public_link(token: str, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    session = db.query(TrainingSession).filter(TrainingSession.id == link.session_id).first() if link.session_id else None
    if not session:
        raise HTTPException(404, "Session associée introuvable.")
    assessment_attempt = None
    public_assessment = None
    if link.kind in {"participant", "post_formation"}:
        stored_questions = _ensure_ten_assessment_questions(link, session, db)
        if not _assessment_est_ancre(stored_questions):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ce questionnaire ancien n’est pas vérifié par les supports de la session. "
                    "Le responsable doit régénérer le lien depuis la session avant sa diffusion."
                ),
            )
        questions = _individualize_assessment(stored_questions)
        assessment_attempt = secrets.token_urlsafe(36)
        db.add(PublicAssessmentAttempt(token=assessment_attempt, link_id=link.id, questions=questions))
        db.commit()
        public_assessment = {"enabled": True, "attempt_id": assessment_attempt,
                             "questions": [_public_question(q) for q in questions]}
    return {"kind": link.kind, "session": ({"id": str(session.id), "titre": session.titre, "client": session.client,
             "date_debut": session.date_debut.isoformat(), "date_fin": session.date_fin.isoformat() if session.date_fin else None,
             "lieu": session.lieu, "max_participants": session.nb_participants_max} if session else None),
            "formation_details": _public_formation_details(db, session, for_trainer=link.kind == "formateur"),
            "assessment": public_assessment if link.kind == "participant" else None,
            "post_formation": ({"enabled": True, **public_assessment, "satisfaction_questions": SATISFACTION_QUESTIONS}
                               if link.kind == "post_formation" else None)}


@router.post("/links/{token}/participant", status_code=201)
async def public_participant_registration(token: str, payload: ParticipantRegistration, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    if link.kind != "participant" or not link.session_id:
        raise HTTPException(400, "Ce lien n’est pas un lien d’inscription participant.")
    session = db.query(TrainingSession).filter(TrainingSession.id == link.session_id).first()
    if not session:
        raise HTTPException(404, "Session introuvable.")
    count = db.query(Inscription).filter(Inscription.session_id == session.id).count()
    if session.nb_participants_max and count >= session.nb_participants_max:
        raise HTTPException(409, "La session a atteint sa capacité maximale.")
    questions = link.assessment_questions or []
    if not _assessment_est_ancre(questions):
        raise HTTPException(409, "Ce questionnaire n’est pas validé par les supports de la session. Demandez sa régénération au responsable.")
    attempt = None
    if questions:
        if not payload.assessment_attempt_id:
            raise HTTPException(422, "Rechargez le formulaire pour obtenir votre test individuel.")
        attempt = db.query(PublicAssessmentAttempt).filter(
            PublicAssessmentAttempt.token == payload.assessment_attempt_id,
            PublicAssessmentAttempt.link_id == link.id,
            PublicAssessmentAttempt.submitted_at.is_(None),
        ).first()
        if not attempt:
            raise HTTPException(409, "Ce test individuel a déjà été utilisé ou a expiré. Rechargez le formulaire.")
        questions = attempt.questions or []
        if not _assessment_est_ancre(questions):
            raise HTTPException(409, "Ce test individuel n’est pas vérifié par les supports. Rechargez la page après régénération du lien par le responsable.")
    answer_map = {str(item.get("question_id")): str(item.get("answer")) for item in payload.answers if item.get("question_id") and item.get("answer")}
    if questions:
        if len(answer_map) < len(questions):
            raise HTTPException(422, "Répondez à toutes les questions du test de positionnement avant de valider l’inscription.")
        for question in questions:
            valid_answers = {str(option.get("id")) for option in question.get("options", [])}
            if question.get("id") not in answer_map or answer_map[question["id"]] not in valid_answers:
                raise HTTPException(422, "Une ou plusieurs réponses du test sont invalides.")
    email = str(payload.email).lower()
    participant = db.query(Participant).filter(Participant.email == email).first()
    if not participant:
        participant = Participant(nom=payload.nom.strip(), prenom=payload.prenom.strip(), email=email, entreprise=payload.organisation)
        db.add(participant)
        db.flush()
    elif payload.organisation:
        participant.entreprise = payload.organisation
    exists = db.query(Inscription).filter(Inscription.session_id == session.id, Inscription.participant_id == participant.id).first()
    if exists:
        raise HTTPException(409, "Cette adresse est déjà inscrite à cette session.")
    level = None
    score = None
    stored_answers = None
    if questions:
        points = 0.0
        maximum = 0.0
        stored_answers = []
        for question in questions:
            selected = answer_map[question["id"]]
            mapping = question.get("options_scoring") or {}
            if mapping:
                values = [float(v) for v in mapping.values()]
                maximum += max(values) if values else 0.0
                points += float(mapping.get(selected, 0))
                correct = None
            else:
                maximum += 1
                correct = selected == question.get("correct_answer")
                points += 1 if correct else 0
            stored_answers.append({"question_id": question["id"], "answer": selected, "correct": correct})
        score = round((points / maximum) * 100) if maximum else 0
        level = await _classify_initial_level(session, questions, answer_map, score)
    inscription = Inscription(
        session_id=session.id,
        participant_id=participant.id,
        poste=payload.poste,
        reponses_positionnement=stored_answers,
        score_positionnement=score,
        niveau_initial=level,
    )
    db.add(inscription)
    if attempt:
        attempt.submitted_at = datetime.now(UTC)
    db.commit()
    return {"success": True, "message": "Inscription et test de positionnement enregistrés.", "session": session.titre,
            "niveau_initial": level, "score_positionnement": score}


@router.post("/links/{token}/post-formation", status_code=201)
async def submit_post_formation(token: str, payload: PostFormationSubmission, db: Session = Depends(get_db)):
    """Persist the post-course assessment and feedback, then update trainer score."""
    link = _get_link(token, db)
    if link.kind != "post_formation" or not link.session_id:
        raise HTTPException(400, "Ce lien n’est pas un lien d’évaluation post-formation.")
    session = db.query(TrainingSession).filter(TrainingSession.id == link.session_id).first()
    if not session:
        raise HTTPException(404, "Formation introuvable.")
    email = str(payload.email).strip().lower()
    row = (db.query(Inscription, Participant)
           .join(Participant, Participant.id == Inscription.participant_id)
           .filter(Inscription.session_id == session.id, Participant.email == email)
           .first())
    if not row:
        raise HTTPException(404, "Aucune inscription à cette formation ne correspond à cette adresse e-mail.")
    inscription, participant = row
    if inscription.date_evaluation_finale:
        raise HTTPException(409, "Votre évaluation post-formation a déjà été envoyée.")
    attempt = db.query(PublicAssessmentAttempt).filter(
        PublicAssessmentAttempt.token == payload.assessment_attempt_id,
        PublicAssessmentAttempt.link_id == link.id,
    ).first()
    if not attempt or attempt.submitted_at:
        raise HTTPException(409, "Ce questionnaire a expiré ou a déjà été utilisé. Rechargez la page pour en obtenir un nouveau.")

    questions = list(attempt.questions or [])
    if not _assessment_est_ancre(questions):
        raise HTTPException(409, "Ce questionnaire n’est pas validé par les supports de la session. Demandez sa régénération au responsable.")
    answer_map = {str(item.get("question_id")): str(item.get("answer", "")).strip()
                  for item in payload.answers if item.get("question_id")}
    if not questions or len(answer_map) < len(questions):
        raise HTTPException(422, "Répondez à toutes les questions de l’évaluation finale.")
    points = 0.0
    maximum = 0.0
    stored_test_answers = []
    for question in questions:
        answer = answer_map.get(str(question.get("id")))
        valid_options = {str(option.get("id")) for option in question.get("options", [])}
        if answer not in valid_options:
            raise HTTPException(422, "Une réponse du test final est invalide.")
        scoring = question.get("options_scoring") or {}
        if scoring:
            values = [float(value) for value in scoring.values()]
            maximum += max(values) if values else 0.0
            question_points = float(scoring.get(answer, 0))
            correct = None
        else:
            maximum += 1.0
            correct = answer == question.get("correct_answer")
            question_points = 1.0 if correct else 0.0
        points += question_points
        stored_test_answers.append({"question_id": question["id"], "answer": answer, "correct": correct, "points": question_points})
    score = round((points / maximum) * 100) if maximum else 0
    final_level = await _classify_initial_level(session, questions, answer_map, score, stage="final")

    satisfaction_map = {str(item.get("question_id")): str(item.get("answer", "")).strip()
                        for item in payload.satisfaction_answers if item.get("question_id")}
    required_satisfaction = {item["id"] for item in SATISFACTION_QUESTIONS if item["id"] != "sat_7"}
    if not required_satisfaction.issubset(satisfaction_map):
        raise HTTPException(422, "Répondez à toutes les questions obligatoires de satisfaction.")
    scores = []
    normalized_satisfaction = []
    for item in SATISFACTION_QUESTIONS:
        answer = satisfaction_map.get(item["id"], "")
        if item["type"] == "rating":
            try:
                rating = int(answer)
            except ValueError as exc:
                raise HTTPException(422, "Les notes de satisfaction doivent être comprises entre 1 et 5.") from exc
            if rating < 1 or rating > 5:
                raise HTTPException(422, "Les notes de satisfaction doivent être comprises entre 1 et 5.")
            scores.append(rating)
        elif item["id"] == "sat_6" and answer not in {"Oui", "Non"}:
            raise HTTPException(422, "Indiquez si vous recommandez le formateur.")
        normalized_satisfaction.append({"question_id": item["id"], "question": item["label"], "answer": answer[:1500]})
    satisfaction_score = round(sum(scores) / len(scores)) if scores else None

    inscription.reponses_test_final = stored_test_answers
    inscription.score_test_final = score
    inscription.niveau_final = final_level
    inscription.reponses_satisfaction = normalized_satisfaction
    inscription.score_satisfaction = satisfaction_score
    inscription.date_evaluation_finale = datetime.now(UTC)
    attempt.submitted_at = datetime.now(UTC)

    trainer = db.query(Formateur).filter(Formateur.id == session.formateur_id).first() if session.formateur_id else None
    if trainer:
        from sqlalchemy import func
        aggregates = (db.query(func.avg(Inscription.score_satisfaction), func.count(Inscription.id), func.count(func.distinct(Inscription.session_id)))
                      .join(TrainingSession, TrainingSession.id == Inscription.session_id)
                      .filter(TrainingSession.formateur_id == trainer.id, Inscription.score_satisfaction.isnot(None))
                      .one())
        average_rating, response_count, rated_sessions = aggregates
        trainer.score_moyen = round(float(average_rating) * 20, 1) if average_rating is not None else None
        trainer.nb_sessions = str(rated_sessions or 0)
        if trainer.score_moyen is not None:
            if trainer.score_moyen >= 75:
                trainer.recommandation = RecommandationEvaluation.OUI
            elif trainer.score_moyen < 55:
                trainer.recommandation = RecommandationEvaluation.NON
            else:
                trainer.recommandation = RecommandationEvaluation.CONDITIONNEL
    db.commit()
    return {"success": True, "niveau_final": final_level, "score_test_final": score,
            "score_satisfaction": satisfaction_score,
            "formateur_evaluation": ({"score_moyen": trainer.score_moyen,
                                       "recommandation": trainer.recommandation.value if trainer.recommandation else None,
                                       "nombre_reponses": int(response_count or 0)} if trainer else None)}


@router.post("/links/{token}/formateur", status_code=201)
async def public_trainer_application(
    token: str,
    nom: str = Form(...),
    prenom: str = Form(...),
    email: str = Form(...),
    telephone: str | None = Form(default=None),
    specialite: str = Form(...),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    link = _get_link(token, db)
    if link.kind != "formateur":
        raise HTTPException(400, "Ce lien n’est pas un lien de candidature formateur.")
    from pathlib import Path
    from app.services.rh.cv_extractor_service import extraire_texte_cv
    ext = Path(fichier.filename or "").suffix.lower()
    if ext not in {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".txt"}:
        raise HTTPException(422, "Format de CV non pris en charge.")
    content = await fichier.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(422, "Le fichier est vide ou dépasse 10 Mo.")
    cv_text, _method, readable = await extraire_texte_cv(content, fichier.filename or "cv")
    if not readable:
        raise HTTPException(422, "Le CV n’a pas pu être lu. Envoyez un PDF texte ou un DOCX lisible.")
    cv_dir = Path(__file__).resolve().parents[3] / "uploads" / "candidats"
    cv_dir.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = cv_dir / saved_name
    saved_path.write_bytes(content)
    candidate = Candidat(nom=nom.strip(), prenom=prenom.strip(), email=email.strip().lower(), telephone=telephone,
                         poste_vise=specialite.strip(), cv_texte=cv_text, cv_filename=fichier.filename, cv_path=str(saved_path),
                         session_id=link.session_id,
                         decision_preselection=DecisionPreselection.A_DISCUTER)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    # Analyse immédiate du CV : la fiche RH reçoit le score et un lien vers
    # la review qui contient les questions d'entretien personnalisées.
    review_id = None
    questions = []
    score = None
    try:
        from app.orchestrator.rh_orchestrator import get_rh_orchestrator
        # Enrichir les critères avec le profil TDR de la session si disponible
        session_for_criteria = db.query(TrainingSession).filter(TrainingSession.id == candidate.session_id).first() if candidate.session_id else None
        criteres: dict = {
            "domaine": specialite.strip(),
            "poste": specialite.strip(),
            "competences": [item.strip() for item in specialite.split(",") if item.strip()],
            "niveau": "à évaluer",
        }
        if session_for_criteria:
            details = _public_formation_details(db, session_for_criteria, for_trainer=True)
            if details.get("formateur_profil"):
                criteres["profil_recherche"] = details["formateur_profil"]
            if details.get("competences_requises"):
                existing = set(criteres["competences"])
                criteres["competences"] = list(existing | set(details["competences_requises"]))
            if details.get("objectif_general"):
                criteres["contexte_mission"] = details["objectif_general"]
            if details.get("titre"):
                criteres["titre_formation"] = details["titre"]
        result = await get_rh_orchestrator().preselectionner_cv(
            cv_texte=cv_text,
            criteres_poste=criteres,
        )
        review_id = result.get("_review_id")
        score = result.get("score_global")
        questions = result.get("questions_entretien") or []
        candidate.score_preselection = score
        candidate.review_id_preselection = review_id
        db.commit()
        if review_id:
            from app.services.hitl import patch_review
            patch_review(review_id, {
                "candidat_id": str(candidate.id),
                "candidat_nom": f"{candidate.prenom or ''} {candidate.nom}".strip(),
                "session_id": str(candidate.session_id) if candidate.session_id else None,
                "session_title": session.titre if (session := db.query(TrainingSession).filter(TrainingSession.id == candidate.session_id).first()) else None,
            })
    except Exception:
        # La candidature et son CV restent enregistrés même si l'agent IA est
        # momentanément indisponible ; l'équipe RH pourra la relancer ensuite.
        logger.exception("Échec de la présélection IA pour le candidat %s", candidate.id)
        db.rollback()

    return {
        "success": True,
        "message": "Candidature reçue. Les questions d’entretien sont prêtes pour l’équipe RH." if review_id else "Candidature reçue. L’analyse IA sera à relancer par l’équipe RH.",
        "candidat_id": str(candidate.id),
        "session_id": str(candidate.session_id) if candidate.session_id else None,
        "review_id_preselection": review_id,
        "score_preselection": score,
        "questions_entretien": questions,
        "questions_count": len(questions),
    }
