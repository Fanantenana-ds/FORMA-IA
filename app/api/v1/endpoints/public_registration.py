import secrets
import uuid
import logging
import json
import random
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
from app.services.llm import get_llm_provider

router = APIRouter(prefix="/public", tags=["Inscriptions publiques"])
logger = logging.getLogger(__name__)


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


def _fallback_assessment(session: TrainingSession) -> list[dict]:
    topic = session.formation_code or session.titre
    return [
        {"id":"q1","competence":"Connaissances initiales","enonce":f"Quel est votre niveau de familiarité avec {topic} ?","options":[{"id":"A","label":"Je découvre le sujet"},{"id":"B","label":"J’en connais quelques notions"},{"id":"C","label":"Je l’ai déjà pratiqué"},{"id":"D","label":"Je peux l’enseigner ou l’utiliser à un niveau expert"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q2","competence":"Expérience pratique","enonce":"Face à une tâche nouvelle dans ce domaine, quelle approche vous décrit le mieux ?","options":[{"id":"A","label":"J’attends une démonstration pas à pas"},{"id":"B","label":"Je peux suivre un exemple guidé"},{"id":"C","label":"Je peux adapter une méthode déjà apprise"},{"id":"D","label":"Je conçois une méthode et peux accompagner d’autres personnes"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q3","competence":"Autonomie","enonce":"À quelle fréquence utilisez-vous les outils ou méthodes liés à cette formation ?","options":[{"id":"A","label":"Jamais"},{"id":"B","label":"Rarement, avec aide"},{"id":"C","label":"Régulièrement, de façon autonome"},{"id":"D","label":"Très souvent, y compris pour résoudre des cas complexes"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q4","competence":"Résolution de problèmes","enonce":"Quand un résultat est incorrect, que faites-vous en premier ?","options":[{"id":"A","label":"Je ne sais pas comment procéder"},{"id":"B","label":"Je recommence en suivant les consignes"},{"id":"C","label":"Je vérifie les étapes et corrige la cause"},{"id":"D","label":"J’analyse les causes possibles et compare plusieurs solutions"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q5","competence":"Vocabulaire métier","enonce":f"Pouvez-vous expliquer les concepts principaux de {topic} ?","options":[{"id":"A","label":"Pas encore"},{"id":"B","label":"Quelques termes simples"},{"id":"C","label":"Oui, les notions et leur usage"},{"id":"D","label":"Oui, avec nuances, limites et cas avancés"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q6","competence":"Transfert des acquis","enonce":"Avez-vous déjà appliqué ces compétences dans une situation réelle ?","options":[{"id":"A","label":"Non"},{"id":"B","label":"Dans un exercice accompagné"},{"id":"C","label":"Oui, sur une tâche ou un projet"},{"id":"D","label":"Oui, sur plusieurs projets et avec transmission à d’autres"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q7","competence":"Confiance","enonce":"Comment vous sentez-vous pour réaliser seul une tâche courante de cette formation ?","options":[{"id":"A","label":"Je ne suis pas encore prêt"},{"id":"B","label":"Je peux essayer avec un guide"},{"id":"C","label":"Je peux la réaliser seul"},{"id":"D","label":"Je peux la réaliser, l’optimiser et aider un collègue"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q8","competence":"Objectif d’apprentissage","enonce":"Quel objectif vous correspond le mieux pour cette formation ?","options":[{"id":"A","label":"Découvrir les bases"},{"id":"B","label":"Comprendre les méthodes essentielles"},{"id":"C","label":"Être autonome dans des cas d’usage courants"},{"id":"D","label":"Approfondir et maîtriser des cas complexes"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q9","competence":"Application métier","enonce":f"Dans quelle mesure pouvez-vous appliquer {topic} à une situation concrète de votre travail ?","options":[{"id":"A","label":"Je ne sais pas encore par où commencer"},{"id":"B","label":"Je peux appliquer une consigne simple avec accompagnement"},{"id":"C","label":"Je peux traiter seul un cas courant"},{"id":"D","label":"Je peux adapter la démarche à un cas complexe"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
        {"id":"q10","competence":"Analyse et prise de recul","enonce":f"Comment vérifiez-vous la qualité d’un résultat obtenu avec {topic} ?","options":[{"id":"A","label":"Je ne sais pas encore quels critères utiliser"},{"id":"B","label":"Je vérifie quelques points avec une liste fournie"},{"id":"C","label":"Je contrôle les critères essentiels de façon autonome"},{"id":"D","label":"Je définis des critères, détecte les limites et propose des améliorations"}],"options_scoring":{"A":0,"B":1,"C":2,"D":3}},
    ]


def _ensure_ten_assessment_questions(link: PublicRegistrationLink, session: TrainingSession, db: Session) -> list[dict]:
    """Upgrade older persisted links that still contain fewer than ten questions."""
    questions = list(link.assessment_questions or [])
    if len(questions) >= 10:
        return questions[:10]
    existing_ids = {str(question.get("id")) for question in questions if question.get("id")}
    for fallback in _fallback_assessment(session):
        if len(questions) >= 10:
            break
        if str(fallback["id"]) not in existing_ids:
            questions.append(fallback)
            existing_ids.add(str(fallback["id"]))
    link.assessment_questions = questions
    db.commit()
    return questions


async def _generate_assessment(session: TrainingSession, stage: str = "initial") -> list[dict]:
    """Generate a private, answer-key questionnaire for a training stage."""
    topic = session.formation_code or session.titre
    try:
        response = await get_llm_provider().generate(
            system_prompt=("Tu es un concepteur d'évaluations de formation. Tu produis des questions à choix multiple en français, adaptées au thème. "
                           "Le questionnaire de fin mesure les compétences acquises; il ne note pas la valeur de la personne." if stage == "final" else
                           "Tu es un concepteur de tests diagnostiques de formation. Tu produis des questions à choix multiple en français, adaptées au thème. Le test évalue le niveau initial, il ne note pas la valeur de la personne."),
            user_prompt=(f"Crée 10 questions de {'validation des acquis après la formation' if stage == 'final' else 'positionnement avant la formation'} pour la formation « {session.titre} » "
                         f"(code/domaine : {topic}). Retourne uniquement un objet JSON avec une clé questions. "
                         "Chaque question doit avoir id (q1...), competence, enonce, options (4 objets id A-D et label), "
                         "correct_answer (A-D). Questions concrètes et progressives, une seule bonne réponse."),
            temperature=0.2, max_tokens=3500, json_mode=True,
        )
        data = json.loads(response["content"])
        questions = data.get("questions", []) if isinstance(data, dict) else []
        valid = [q for q in questions if isinstance(q, dict) and q.get("enonce")
                 and q.get("correct_answer") in {"A", "B", "C", "D"}
                 and isinstance(q.get("options"), list) and len(q["options"]) == 4
                 and {str(option.get("id")) for option in q["options"] if isinstance(option, dict)} == {"A", "B", "C", "D"}]
        if len(valid) >= 10:
            for index, question in enumerate(valid[:10], start=1):
                question["id"] = f"q{index}"
            return valid[:10]
    except Exception:
        logger.exception("La génération IA du test de positionnement a échoué; questionnaire de secours utilisé.")
    return _fallback_assessment(session)


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
    if payload.kind == "participant":
        if not payload.session_id:
            raise HTTPException(422, "session_id est obligatoire pour une inscription participant.")
        session = db.query(TrainingSession).filter(TrainingSession.id == payload.session_id).first()
        if not session:
            raise HTTPException(404, "Session introuvable.")
    elif not payload.session_id:
        raise HTTPException(422, "session_id est obligatoire pour un lien lié à une formation.")
    else:
        session = db.query(TrainingSession).filter(TrainingSession.id == payload.session_id).first()
        if not session:
            raise HTTPException(404, "Session introuvable.")
    existing_link = db.query(PublicRegistrationLink).filter(
        PublicRegistrationLink.kind == payload.kind,
        PublicRegistrationLink.session_id == payload.session_id,
        PublicRegistrationLink.active.is_(True),
    ).order_by(PublicRegistrationLink.date_creation.desc()).first()
    if existing_link:
        question_count = len(existing_link.assessment_questions or [])
        if payload.kind == "participant":
            question_count = len(_ensure_ten_assessment_questions(existing_link, session, db))
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
        result = await get_rh_orchestrator().preselectionner_cv(
            cv_texte=cv_text,
            criteres_poste={
                "domaine": specialite.strip(),
                "poste": specialite.strip(),
                "competences": [item.strip() for item in specialite.split(",") if item.strip()],
                "niveau": "à évaluer",
            },
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
