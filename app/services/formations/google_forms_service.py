# app/services/formations/google_forms_service.py
# ============================================================
# M5 — Création Google Forms depuis le JSON HITL approuvé
# ============================================================
# Utilise le Service Account (GOOGLE_CREDENTIALS_PATH) pour appeler
# l'API Google Forms v1.
#
# Pré-requis côté Google Cloud :
#   - API "Google Forms API" activée sur le projet forma-ia-510012
#   - Service Account avec droits de création de formulaires
#     (impersonation d'un utilisateur du domaine via
#     délégation d'autorité — domain-wide delegation — OU
#     création sur le Service Account lui-même avec partage manuel)
#
# Variables d'environnement :
#   GOOGLE_CREDENTIALS_PATH : chemin vers secrets/google_credentials.json
#   GOOGLE_SUBJECT_EMAIL    : email de l'utilisateur à impersonner
#                             (domain-wide delegation).
#                             Absent → le SA crée le formulaire pour lui-même.
# ============================================================

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"

FORMS_SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

_QUESTION_TYPES = {
    "text":        "TEXT",
    "email":       "TEXT",
    "short_text":  "TEXT",
    "long_text":   "PARAGRAPH_TEXT",
    "textarea":    "PARAGRAPH_TEXT",
    "radio":       "RADIO",
    "multiple_choice": "RADIO",
    "checkbox":    "CHECKBOX",
    "select":      "DROP_DOWN",
    "dropdown":    "DROP_DOWN",
    "scale":       "SCALE",
    "rating":      "SCALE",
    "date":        "DATE",
    "time":        "TIME",
}


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class GoogleFormsService:
    """
    Crée les 4 formulaires Google Forms d'une session à partir du
    JSON approuvé par HITL (FormGeneratorService.generate()).
    """

    def __init__(self) -> None:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
        if not credentials_path or not Path(credentials_path).exists():
            raise FileNotFoundError(
                f"GOOGLE_CREDENTIALS_PATH introuvable : '{credentials_path}'. "
                "Définissez la variable dans .env."
            )
        self._credentials_path = credentials_path
        self._subject = os.getenv("GOOGLE_SUBJECT_EMAIL") or None
        vlog(
            f"✅ GoogleFormsService initialisé "
            f"(credentials={Path(credentials_path).name}, "
            f"subject={'<domain>' if self._subject else 'SA lui-même'})"
        )

    # ----------------------------------------------------------
    # AUTH
    # ----------------------------------------------------------
    def _get_service(self):
        """Retourne un client google-api-python-client pour Forms v1."""
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            self._credentials_path,
            scopes=FORMS_SCOPES,
        )
        if self._subject:
            creds = creds.with_subject(self._subject)

        return build("forms", "v1", credentials=creds, cache_discovery=False)

    # ----------------------------------------------------------
    # CONVERSION JSON → requêtes API
    # ----------------------------------------------------------
    @staticmethod
    def _question_type(q: Dict[str, Any]) -> str:
        raw = str(q.get("type") or "text").lower()
        return _QUESTION_TYPES.get(raw, "TEXT")

    @staticmethod
    def _build_question_item(q: Dict[str, Any], index: int) -> Dict[str, Any]:
        label = str(q.get("label") or q.get("question") or f"Question {index + 1}")
        q_type = GoogleFormsService._question_type(q)
        required = bool(q.get("required", True))

        question_body: Dict[str, Any] = {
            "required": required,
        }

        if q_type in ("RADIO", "CHECKBOX", "DROP_DOWN"):
            options = q.get("options") or []
            choices = [
                {"value": str(o)[:100]} for o in options if str(o).strip()
            ]
            if not choices:
                choices = [{"value": "Option A"}]
            question_body["choiceQuestion"] = {
                "type": q_type,
                "options": choices,
                "shuffle": False,
            }
        elif q_type == "SCALE":
            question_body["scaleQuestion"] = {
                "low": 1,
                "high": 5,
                "lowLabel": "Très insatisfait",
                "highLabel": "Très satisfait",
            }
        elif q_type == "PARAGRAPH_TEXT":
            question_body["textQuestion"] = {"paragraph": True}
        else:
            question_body["textQuestion"] = {"paragraph": False}

        return {
            "createItem": {
                "item": {
                    "title": label[:200],
                    "questionItem": {"question": question_body},
                },
                "location": {"index": index},
            }
        }

    # ----------------------------------------------------------
    # CRÉATION D'UN FORMULAIRE
    # ----------------------------------------------------------
    def _create_one_form(
        self,
        service,
        title: str,
        description: str,
        questions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Crée un formulaire Google Forms :
        1. POST /forms  → crée le formulaire vide
        2. POST /forms/{id}:batchUpdate → ajoute description + questions
        """
        form_body = {"info": {"title": title[:200], "documentTitle": title[:200]}}
        form = service.forms().create(body=form_body).execute()
        form_id = form["formId"]
        responder_uri = form.get("responderUri", "")
        vlog(f"   📋 Formulaire créé : {title} (id={form_id})")

        requests: List[Dict[str, Any]] = []

        if description:
            requests.append({
                "updateFormInfo": {
                    "info": {"description": description[:1000]},
                    "updateMask": "description",
                }
            })

        for i, q in enumerate(questions):
            requests.append(self._build_question_item(q, i))

        if requests:
            service.forms().batchUpdate(
                formId=form_id,
                body={"requests": requests},
            ).execute()
            vlog(f"   ✅ {len(questions)} question(s) ajoutée(s) au formulaire")

        return {
            "form_id": form_id,
            "title": title,
            "responder_uri": responder_uri,
            "questions_count": len(questions),
        }

    # ----------------------------------------------------------
    # POINT D'ENTRÉE PRINCIPAL
    # ----------------------------------------------------------
    async def create_forms(
        self,
        approved_data: Dict[str, Any],
        session_title: str = "",
    ) -> Dict[str, Any]:
        """
        Crée les 4 Google Forms à partir du JSON HITL approuvé.

        Args:
            approved_data: résultat de FormGeneratorService.generate()
                après approbation HITL (sections inscription, test_avant,
                test_apres, satisfaction).
            session_title: titre de la session (pour préfixer les noms).

        Returns:
            Dict avec une URL par formulaire + métadonnées.
        """
        service = self._get_service()

        sections = [
            ("inscription", "Inscription", "Formulaire d'inscription à la formation."),
            ("test_avant",  "Test AVANT",  "Évaluation diagnostique avant la formation."),
            ("test_apres",  "Test APRÈS",  "Évaluation sommative après la formation."),
            ("satisfaction","Satisfaction","Questionnaire de satisfaction post-formation."),
        ]

        results: Dict[str, Any] = {
            "success": True,
            "session_title": session_title,
            "forms": {},
        }

        prefix = f"[{session_title}] " if session_title else ""
        errors: List[str] = []

        for key, label, description in sections:
            section = approved_data.get(key)
            if not isinstance(section, dict):
                logger.warning(f"⚠️  Section '{key}' absente — formulaire ignoré")
                results["forms"][key] = {"skipped": True, "reason": "section absente"}
                continue

            title = f"{prefix}{section.get('title', label)}"
            questions = section.get("questions") or []

            try:
                form_result = self._create_one_form(
                    service, title, description, questions
                )
                results["forms"][key] = form_result
                vlog(f"✅ [{key}] Google Form créé : {form_result['responder_uri']}")
            except Exception as e:
                logger.error(f"❌ Erreur création formulaire '{key}' : {e}")
                errors.append(f"{key}: {type(e).__name__} — {e}")
                results["forms"][key] = {"error": str(e)}

        if errors:
            results["success"] = False
            results["errors"] = errors

        results["total_created"] = sum(
            1 for f in results["forms"].values()
            if "form_id" in f
        )
        return results

    # ----------------------------------------------------------
    # RÉCUPÉRATION DES RÉPONSES
    # ----------------------------------------------------------
    async def fetch_responses(
        self,
        form_ids: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Récupère les réponses de chaque formulaire via l'API Google Forms.

        Args:
            form_ids: dict {section_key: form_id}
                ex: {"inscription": "1abc...", "satisfaction": "1xyz..."}

        Returns:
            dict {section_key: {"form_id": ..., "responses": [...], "count": int}}
            Chaque réponse est un dict {question_id: réponse_brute}.
        """
        service = self._get_service()
        results: Dict[str, Any] = {}

        for key, form_id in form_ids.items():
            if not form_id:
                results[key] = {"form_id": form_id, "responses": [], "count": 0, "skipped": True}
                continue
            try:
                vlog(f"   📥 Récupération réponses [{key}] form_id={form_id}")
                resp = service.forms().responses().list(formId=form_id).execute()
                raw_responses = resp.get("responses", [])

                parsed = []
                for r in raw_responses:
                    answers: Dict[str, Any] = {}
                    for q_id, answer_obj in (r.get("answers") or {}).items():
                        # textAnswers → liste de valeurs
                        text_answers = answer_obj.get("textAnswers", {}).get("answers", [])
                        values = [a.get("value", "") for a in text_answers]
                        answers[q_id] = values[0] if len(values) == 1 else values
                    parsed.append({
                        "response_id": r.get("responseId"),
                        "submitted_at": r.get("lastSubmittedTime"),
                        "answers": answers,
                    })

                results[key] = {
                    "form_id": form_id,
                    "responses": parsed,
                    "count": len(parsed),
                }
                vlog(f"   ✅ [{key}] {len(parsed)} réponse(s) récupérée(s)")
            except Exception as e:
                logger.error(f"❌ Erreur fetch réponses '{key}' (form_id={form_id}) : {e}")
                results[key] = {
                    "form_id": form_id,
                    "responses": [],
                    "count": 0,
                    "error": str(e),
                }

        total = sum(v.get("count", 0) for v in results.values())
        vlog(f"✅ fetch_responses terminé — {total} réponse(s) au total")
        return results
