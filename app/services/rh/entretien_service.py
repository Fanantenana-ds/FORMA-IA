import os
import re
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.services.llm import get_llm_provider, LLMError
from app.services.hitl import create_review

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m4" / "rh_entretien.yaml"
AGENT_ID = "agent_m4_entretien"


class EntretienService:
    """
    Agent M4-2 — Rédaction de compte-rendu d'entretien structuré.

    Input  : notes_brutes (texte libre) + contexte candidat
    Output : JSON compte-rendu + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [EntretienAgent] Service initialisé")

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
        notes_brutes: str,
        candidat: str,
        poste: str,
        interviewers: List[str],
        date_entretien: Optional[str],
    ) -> str:
        return "\n".join([
            "Rédige le compte-rendu pour cet entretien :",
            "",
            "=== INFORMATIONS GÉNÉRALES ===",
            f"- Candidat : {candidat}",
            f"- Poste : {poste}",
            f"- Date : {date_entretien or 'non précisée'}",
            f"- Interviewers : {', '.join(interviewers) if interviewers else 'non précisés'}",
            "",
            "=== NOTES BRUTES DE L'ENTRETIEN ===",
            notes_brutes.strip()[:6000],
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ])

    async def generate(
        self,
        notes_brutes: str,
        candidat: str,
        poste: str,
        interviewers: Optional[List[str]] = None,
        date_entretien: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [EntretienAgent] Rédaction CR entretien — {candidat}")
        vlog("=" * 70)

        interviewers = interviewers or []
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            notes_brutes, candidat, poste, interviewers, date_entretien
        )
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
            content = self._generate_fallback(candidat, poste, interviewers, date_entretien)

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
                f"CR Entretien — {candidat} — {poste} "
                f"— Décision : {result.get('decision', 'N/A')}"
            ),
            criticity="high",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog(f"✅ [EntretienAgent] Terminé en {elapsed}s (source={source})")
        return result

    def _repair_json(self, raw: str) -> str:
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw)
        raw = raw.replace("\\'", "'").replace("\\/", "/")
        start = raw.find("{")
        if start > 0:
            raw = raw[start:]
        end = raw.rfind("}")
        if end > 0:
            raw = raw[:end + 1]
        return raw

    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        for k in ("candidat", "decision", "points_forts", "resume_entretien"):
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    def _generate_fallback(
        self,
        candidat: str,
        poste: str,
        interviewers: List[str],
        date_entretien: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "candidat": candidat,
            "poste": poste,
            "date_entretien": date_entretien,
            "duree_minutes": None,
            "interviewers": interviewers,
            "resume_entretien": "Compte-rendu à rédiger manuellement (analyse LLM indisponible).",
            "parcours_canditat": "À compléter manuellement.",
            "motivations": "Non capturé automatiquement.",
            "competences_evaluees": [],
            "adequation_culturelle": {"score": None, "commentaire": "Non évalué"},
            "points_forts": ["À compléter manuellement"],
            "points_vigilance": ["Analyse automatique indisponible"],
            "decision": "APPROFONDIR",
            "justification_decision": "Analyse automatique indisponible. Vérification manuelle requise.",
            "prochaines_etapes": ["Compléter ce CR manuellement avant décision"],
        }
