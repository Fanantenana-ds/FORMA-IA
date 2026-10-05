from app.utils.json_repair import repair_json
import os
import re
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.llm import get_llm_provider, LLMError
from app.services.hitl import create_review

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
