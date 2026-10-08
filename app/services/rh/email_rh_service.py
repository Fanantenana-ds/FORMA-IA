from app.utils.json_repair import repair_json
import os
import re
import json
import yaml
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.llm import get_llm_provider, LLMError
from app.services.hitl import create_review, get_review, patch_review

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m4" / "rh_email.yaml"
AGENT_ID = "agent_m4_email"

TYPE_EMAIL_VALID = {"ACCEPTATION", "REFUS", "DEMANDE_INFO", "CONVOCATION", "PROPOSITION_MISSION"}


class EmailRhService:
    """
    Agent M4-3 — Rédaction de brouillons d'emails RH.

    Input  : type_email + contexte (destinataire, décision, mission...)
    Output : JSON email prêt à envoyer + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [EmailRhAgent] Service initialisé")

    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")
        return config

    def _build_system_prompt(self) -> str:
        cfg = self.prompt_config
        return "\n".join([
            "=== RÔLE ===", cfg.get("role", "").strip(), "",
            "=== TÂCHE ===", cfg.get("tache", "").strip(), "",
            "=== FORMAT ===", cfg.get("format", "").strip(), "",
            "=== CONTEXTE ===", cfg.get("contexte", "").strip(), "",
            "=== RÈGLES STRICTES ===",
            cfg.get("regles", "") if isinstance(cfg.get("regles"), str)
            else "\n".join(f"- {r}" for r in cfg.get("regles", [])),
        ])

    def _build_user_prompt(
        self,
        type_email: str,
        destinataire: str,
        contexte: Dict[str, Any],
    ) -> str:
        lines = [
            f"Rédige un email de type : {type_email}",
            "",
            "=== DESTINATAIRE ===",
            f"- Nom : {destinataire}",
        ]
        for k, v in contexte.items():
            lines.append(f"- {k} : {v}")
        lines += ["", "Retourne UNIQUEMENT le JSON valide, sans texte autour."]
        return "\n".join(lines)

    async def generate(
        self,
        type_email: str,
        destinataire: str,
        contexte: Optional[Dict[str, Any]] = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        if type_email not in TYPE_EMAIL_VALID:
            raise ValueError(
                f"type_email invalide : '{type_email}'. "
                f"Valeurs acceptées : {TYPE_EMAIL_VALID}"
            )

        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [EmailRhAgent] Rédaction email {type_email} → {destinataire}")
        vlog("=" * 70)

        contexte = contexte or {}
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(type_email, destinataire, contexte)
        content = None
        source = "fallback_template"

        try:
            llm = get_llm_provider()
            response = await llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )
            raw = response["content"]
            if response["finish_reason"] == "length":
                raise ValueError("Réponse LLM tronquée")
            data = json.loads(self._repair_json(raw))
            self._validate_minimal(data)
            content = data
            source = "llm"
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). Bascule fallback.")
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        if content is None:
            content = self._generate_fallback(type_email, destinataire)

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        result = {
            "success": True,
            **content,
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "agent_id": AGENT_ID,
            },
        }

        review_id = create_review(
            agent_id=AGENT_ID,
            data=result,
            summary=(
                f"Email RH {type_email} → {destinataire} "
                f"— Objet : {result.get('objet', 'N/A')[:60]}"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog(f"✅ [EmailRhAgent] Terminé en {elapsed}s (source={source})")
        return result

    def envoyer(
        self,
        review_id: str,
        email_destinataire: str,
    ) -> Dict[str, Any]:
        """
        Envoie réellement l'email après approbation HITL.

        Args:
            review_id: ID du review approuvé (ex: HITL-AM4-0071)
            email_destinataire: Adresse email du destinataire

        Returns:
            {"success": True, "message": ..., "review_id": ...}
        """
        from app.config.settings import settings

        # 1. Vérifier que le review existe et est approuvé
        review = get_review(review_id)
        if not review:
            raise ValueError(f"Review '{review_id}' introuvable.")

        statut = review.get("status") or review.get("statut", "")
        if statut != "approved":
            raise PermissionError(
                f"Review '{review_id}' non approuvé (statut : {statut}). "
                "La validation humaine est obligatoire avant l'envoi."
            )

        agent_id = (review.get("meta") or {}).get("agent_id") or review.get("agent_id", "")
        if agent_id != AGENT_ID:
            raise PermissionError(
                f"Ce review n'appartient pas à l'agent email (agent={agent_id})."
            )

        # 2. Vérifier non déjà envoyé
        meta = review.get("meta") or {}
        if meta.get("email_sent"):
            raise ValueError(
                f"Email déjà envoyé pour review '{review_id}' "
                f"le {meta.get('email_sent_at', '?')}."
            )

        # 3. Récupérer objet + corps depuis les données du review
        data = review.get("data") or {}
        objet = data.get("objet", "Message de ALTIORA PREST")
        corps = data.get("corps", "")
        if not corps:
            raise ValueError("Le brouillon ne contient pas de corps d'email.")

        # 4. Vérifier config SMTP
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            raise RuntimeError(
                "SMTP non configuré. Renseignez SMTP_HOST, SMTP_USER, "
                "SMTP_PASSWORD dans le fichier .env."
            )

        # 5. Construire et envoyer l'email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = objet
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = email_destinataire
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as serveur:
                serveur.ehlo()
                serveur.starttls()
                serveur.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                serveur.sendmail(settings.SMTP_USER, email_destinataire, msg.as_string())
            vlog(f"📧 [EmailRhAgent] Email envoyé → {email_destinataire} (review={review_id})")
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError(
                "Échec authentification SMTP. Vérifiez SMTP_USER et SMTP_PASSWORD dans .env. "
                "Pour Gmail : utilisez un mot de passe d'application (16 caractères)."
            )
        except smtplib.SMTPException as e:
            raise RuntimeError(f"Erreur SMTP lors de l'envoi : {e}")

        # 6. Marquer comme envoyé dans le review (anti-doublon)
        patch_review(review_id, {
            "email_sent": True,
            "email_sent_at": datetime.now().isoformat(),
            "email_destinataire": email_destinataire,
        })

        return {
            "success": True,
            "message": f"Email envoyé avec succès à {email_destinataire}.",
            "review_id": review_id,
            "objet": objet,
            "destinataire": email_destinataire,
            "sent_at": datetime.now().isoformat(),
        }

    def _repair_json(self, raw: str) -> str:
        return repair_json(raw)
    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        for k in ("type_email", "objet", "corps"):
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    def _generate_fallback(self, type_email: str, destinataire: str) -> Dict[str, Any]:
        objets = {
            "ACCEPTATION": "Sélection pour mission de formation",
            "REFUS": "Suite à votre candidature",
            "DEMANDE_INFO": "Demande de documents complémentaires",
            "CONVOCATION": "Invitation à un entretien",
            "PROPOSITION_MISSION": "Proposition de mission de formation",
        }
        corps = {
            "ACCEPTATION": (
                f"Madame, Monsieur {destinataire},\n\n"
                "Nous avons le plaisir de vous informer que votre candidature "
                "a été retenue pour une mission de formation au sein d'ALTIORA PREST.\n\n"
                "Nous reviendrons vers vous très prochainement pour les détails pratiques.\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
            "REFUS": (
                f"Madame, Monsieur {destinataire},\n\n"
                "Nous vous remercions de l'intérêt que vous portez à ALTIORA PREST "
                "et du temps consacré à notre processus de sélection.\n\n"
                "Après examen attentif de votre candidature, nous ne sommes pas en "
                "mesure de donner une suite favorable à ce jour. Nous conservons "
                "votre profil pour de futures opportunités.\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
            "DEMANDE_INFO": (
                f"Madame, Monsieur {destinataire},\n\n"
                "Dans le cadre de l'examen de votre candidature, nous aurions besoin "
                "de documents ou d'informations complémentaires afin de compléter votre dossier.\n\n"
                "Merci de nous faire parvenir les éléments demandés dans les plus brefs délais.\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
            "CONVOCATION": (
                f"Madame, Monsieur {destinataire},\n\n"
                "Nous avons le plaisir de vous inviter à un entretien dans le cadre "
                "de notre processus de sélection de formateurs.\n\n"
                "Nous vous communiquerons prochainement les modalités pratiques "
                "(date, heure et lieu) de cette rencontre.\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
            "PROPOSITION_MISSION": (
                f"Madame, Monsieur {destinataire},\n\n"
                "Nous avons le plaisir de vous proposer une mission de formation "
                "au sein d'ALTIORA PREST. Cette opportunité correspond à votre profil "
                "et nous serions ravis de collaborer avec vous.\n\n"
                "Nous vous communiquerons prochainement les détails de la mission "
                "(dates, lieu, programme et conditions financières).\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
        }
        return {
            "type_email": type_email,
            "objet": objets.get(type_email, "Objet à compléter"),
            "destinataire": destinataire,
            "corps": corps.get(
                type_email,
                f"Madame, Monsieur {destinataire},\n\n"
                "[Contenu à compléter manuellement — analyse LLM indisponible]\n\n"
                "Cordialement,\nL'équipe Ressources Humaines\n"
                "ALTIORA PREST — Antananarivo, Madagascar"
            ),
            "ton": "professionnel",
            "points_cles": ["À compléter manuellement"],
        }
