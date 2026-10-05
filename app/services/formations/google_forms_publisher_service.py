# app/services/formations/google_forms_publisher_service.py
# ============================================================
# GOOGLE FORMS PUBLISHER SERVICE — Agent 1b
# ============================================================
# Prend les formulaires générés par FormGeneratorService (après
# approbation HITL) et les publie sur Google Forms + Drive.
#
# Authentification : OAuth2 (refresh_token dans .env)
# Variables d'env requises :
#   GOOGLE_REFRESH_TOKEN       — obtenu via scripts/setup_google_oauth.py
#   GOOGLE_CREDENTIALS_PATH    — chemin vers google_oauth_client.json
#   GOOGLE_DRIVE_FOLDER_ID     — dossier Drive cible (optionnel)
# ============================================================

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"

OAUTH_CLIENT_PATH = Path(
    os.getenv("GOOGLE_OAUTH_CLIENT_PATH", "secrets/google_oauth_client.json")
)
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive",
]

# Types de questions Google Forms
_QUESTION_TYPES = {
    "text":          "TEXT",
    "textarea":      "PARAGRAPH_TEXT",
    "multiple":      "RADIO",
    "checkbox":      "CHECKBOX",
    "scale":         "SCALE",
    "date":          "DATE",
    "select":        "DROP_DOWN",
}


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class GoogleFormsPublisherService:
    """
    Publie les formulaires FORMA-IA sur Google Forms.

    Méthodes principales :
      - publish_all(forms_data, session_titre)  → dict {section: url}
      - publish_one(section_data, titre)        → str (URL du formulaire)
      - is_available()                          → bool
    """

    def __init__(self):
        self._forms_service = None
        self._drive_service = None
        self._init_clients()

    # ----------------------------------------------------------
    # INITIALISATION
    # ----------------------------------------------------------
    def _init_clients(self):
        """Initialise les clients Google API via OAuth2."""
        try:
            refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
            if not refresh_token:
                raise ValueError("GOOGLE_REFRESH_TOKEN absent dans .env")

            client_file = OAUTH_CLIENT_PATH
            if not client_file.exists():
                raise FileNotFoundError(f"OAuth client introuvable : {client_file}")

            import json
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            with open(client_file, "r") as f:
                client_data = json.load(f)

            installed = client_data.get("installed") or client_data.get("web") or {}
            client_id = installed.get("client_id")
            client_secret = installed.get("client_secret")
            token_uri = installed.get("token_uri", "https://oauth2.googleapis.com/token")

            if not client_id or not client_secret:
                raise ValueError("client_id ou client_secret manquant dans le JSON OAuth2")

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )

            self._forms_service = build("forms", "v1", credentials=creds)
            self._drive_service  = build("drive",  "v3", credentials=creds)
            vlog("✅ [GoogleFormsPublisher] Clients Google initialisés")

        except Exception as e:
            logger.warning(f"⚠️ [GoogleFormsPublisher] Init impossible : {e}")

    # ----------------------------------------------------------
    # DISPONIBILITÉ
    # ----------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        """Retourne True si le refresh_token est configuré."""
        return bool(os.getenv("GOOGLE_REFRESH_TOKEN"))

    # ----------------------------------------------------------
    # PUBLICATION COMPLÈTE (4 formulaires)
    # ----------------------------------------------------------
    async def publish_all(
        self,
        forms_data: Dict[str, Any],
        session_titre: str = "Formation",
    ) -> Dict[str, str]:
        """
        Publie les 4 formulaires d'une session sur Google Forms.

        Args:
            forms_data    : dict retourné par FormGeneratorService
                            (sections : inscription, test_avant, test_apres, satisfaction)
            session_titre : titre de la session (préfixe dans le nom du formulaire)

        Returns:
            dict {section: url} — ex: {"inscription": "https://forms.gle/...", ...}
        """
        if not self._forms_service:
            raise RuntimeError("GoogleFormsPublisherService non initialisé (token manquant ?)")

        sections = ["inscription", "test_avant", "test_apres", "satisfaction"]
        labels = {
            "inscription":  "📋 Fiche d'inscription",
            "test_avant":   "📝 Test de positionnement AVANT",
            "test_apres":   "📝 Test de positionnement APRÈS",
            "satisfaction": "⭐ Évaluation de satisfaction",
        }

        results: Dict[str, str] = {}
        errors: List[str] = []

        for section in sections:
            if section not in forms_data:
                vlog(f"⚠️ [GoogleFormsPublisher] Section '{section}' absente — ignorée")
                continue

            titre = f"{labels[section]} — {session_titre}"
            try:
                url = await self.publish_one(forms_data[section], titre, section)
                results[section] = url
                vlog(f"✅ [{section}] → {url}")
            except Exception as e:
                logger.error(f"❌ [{section}] Erreur publication : {e}")
                errors.append(f"{section}: {e}")

        if errors:
            logger.warning(f"⚠️ {len(errors)} formulaire(s) en erreur : {errors}")

        vlog(f"✅ [GoogleFormsPublisher] {len(results)}/4 formulaires publiés")
        return results

    # ----------------------------------------------------------
    # PUBLICATION D'UN SEUL FORMULAIRE
    # ----------------------------------------------------------
    async def publish_one(
        self,
        section_data: Dict[str, Any],
        titre: str,
        section_type: str = "generic",
    ) -> str:
        """
        Crée un Google Form à partir d'une section générée par l'IA.

        Args:
            section_data : dict avec "title", "questions": [...]
            titre        : titre complet du formulaire
            section_type : "inscription"|"test_avant"|"test_apres"|"satisfaction"

        Returns:
            URL de réponse du formulaire (https://docs.google.com/forms/d/.../viewform)
        """
        # 1. Créer le formulaire avec juste le titre
        form_body = {"info": {"title": titre}}
        form = self._forms_service.forms().create(body=form_body).execute()
        form_id = form["formId"]
        vlog(f"   📄 Formulaire créé : {form_id}")

        # 2. Ajouter les questions via batchUpdate
        questions = section_data.get("questions", [])
        if questions:
            requests = self._build_batch_requests(questions, section_type)
            if requests:
                self._forms_service.forms().batchUpdate(
                    formId=form_id,
                    body={"requests": requests},
                ).execute()
                vlog(f"   ✅ {len(questions)} questions ajoutées")

        # 3. Déplacer dans le dossier Drive si configuré
        if DRIVE_FOLDER_ID:
            self._move_to_folder(form_id, DRIVE_FOLDER_ID)

        # 4. Retourner l'URL de réponse publique
        url = f"https://docs.google.com/forms/d/{form_id}/viewform"
        return url

    # ----------------------------------------------------------
    # CONSTRUCTION DES REQUÊTES batchUpdate
    # ----------------------------------------------------------
    def _build_batch_requests(
        self,
        questions: List[Dict[str, Any]],
        section_type: str,
    ) -> List[Dict[str, Any]]:
        """Convertit les questions FORMA-IA en requêtes Google Forms batchUpdate."""
        requests = []
        is_test = section_type in ("test_avant", "test_apres")

        for idx, q in enumerate(questions):
            label   = q.get("label") or q.get("question") or f"Question {idx + 1}"
            q_type  = q.get("type", "text")
            options = q.get("options", [])
            required = q.get("required", True)

            item = self._build_question_item(label, q_type, options, required, is_test, q)
            if item:
                requests.append({
                    "createItem": {
                        "item": item,
                        "location": {"index": idx},
                    }
                })

        return requests

    def _build_question_item(
        self,
        label: str,
        q_type: str,
        options: List[str],
        required: bool,
        is_test: bool,
        raw_q: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Construit un item Google Forms à partir d'une question FORMA-IA."""

        # Mapping des types
        if q_type in ("multiple", "qcm") or options:
            gforms_type = "RADIO"
        elif q_type in ("textarea", "long_text"):
            gforms_type = "PARAGRAPH_TEXT"
        elif q_type == "scale":
            gforms_type = "SCALE"
        elif q_type == "date":
            gforms_type = "DATE"
        elif q_type == "checkbox":
            gforms_type = "CHECKBOX"
        else:
            gforms_type = "TEXT"

        # Structure de la question
        question_spec: Dict[str, Any] = {"required": required}

        if gforms_type in ("RADIO", "CHECKBOX", "DROP_DOWN") and options:
            question_spec["choiceQuestion"] = {
                "type": gforms_type,
                "options": [{"value": str(o)} for o in options],
                "shuffle": False,
            }
        elif gforms_type == "SCALE":
            question_spec["scaleQuestion"] = {
                "low": 1, "high": 5,
                "lowLabel": "Pas du tout satisfait",
                "highLabel": "Très satisfait",
            }
        elif gforms_type == "DATE":
            question_spec["dateQuestion"] = {"includeTime": False, "includeYear": True}
        else:
            question_spec["textQuestion"] = {
                "paragraph": gforms_type == "PARAGRAPH_TEXT"
            }

        return {
            "title": label,
            "questionItem": {"question": question_spec},
        }

    # ----------------------------------------------------------
    # DÉPLACEMENT DANS DRIVE
    # ----------------------------------------------------------
    def _move_to_folder(self, file_id: str, folder_id: str) -> None:
        """Déplace le formulaire dans le dossier Drive configuré."""
        try:
            file_meta = self._drive_service.files().get(
                fileId=file_id, fields="parents"
            ).execute()
            previous_parents = ",".join(file_meta.get("parents", []))
            self._drive_service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute()
            vlog(f"   📁 Formulaire déplacé dans le dossier Drive")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de déplacer dans Drive : {e}")

    # ----------------------------------------------------------
    # SUPPRESSION (utile pour les tests)
    # ----------------------------------------------------------
    def delete_form(self, form_id: str) -> bool:
        """Supprime un formulaire Google Forms (via Drive)."""
        try:
            self._drive_service.files().delete(fileId=form_id).execute()
            vlog(f"🗑️ Formulaire supprimé : {form_id}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Suppression impossible ({form_id}) : {e}")
            return False
