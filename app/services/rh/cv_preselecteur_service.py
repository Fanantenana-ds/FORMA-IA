import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from app.utils.json_repair import repair_json

from app.services.hitl import create_review
from app.services.llm import LLMError, get_llm_provider

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m4" / "rh_preselection.yaml"
AGENT_ID = "agent_m4_preselection"


class CvPreselecteurService:
    """
    Agent M4-1 — Présélection de profils formateurs/candidats sur CV.

    Input  : cv_texte (texte brut du CV) + criteres_poste
    Output : JSON fiche présélection + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [CvPreselecteurAgent] Service initialisé")

    def _load_prompt(self) -> dict[str, Any]:
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

    def _build_user_prompt(self, cv_texte: str, criteres_poste: dict[str, Any]) -> str:
        return "\n".join([
            "Analyse ce profil pour le poste suivant :",
            "",
            "=== CRITÈRES DU POSTE ===",
            f"- Domaine : {criteres_poste.get('domaine', 'N/A')}",
            f"- Compétences requises : {', '.join(criteres_poste.get('competences', []))}",
            f"- Expérience min. en formation : {criteres_poste.get('experience_formation_min', 'N/A')}",
            f"- Niveau requis : {criteres_poste.get('niveau', 'N/A')}",
            "",
            "=== CV (TEXTE BRUT) ===",
            cv_texte.strip()[:8000],
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ])

    async def generate(
        self,
        cv_texte: str,
        criteres_poste: dict[str, Any],
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [CvPreselecteurAgent] Analyse CV en cours...")
        vlog(f"   📋 Domaine : {criteres_poste.get('domaine', 'N/A')}")
        vlog("=" * 70)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(cv_texte, criteres_poste)
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
            vlog("   ✅ Présélection générée par LLM")
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). Bascule fallback.")
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        if content is None:
            content = self._generate_fallback(cv_texte, criteres_poste)
            vlog("   ✅ Présélection générée par template Python (fallback)")

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
                f"Présélection CV — {result.get('nom_candidat', 'Candidat')} "
                f"— {result.get('poste_vise', 'N/A')} "
                f"— Décision : {result.get('decision', 'N/A')}"
            ),
            criticity="high",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog(f"✅ [CvPreselecteurAgent] Terminé en {elapsed}s (source={source})")
        return result

    def _repair_json(self, raw: str) -> str:
        return repair_json(raw)
    def _validate_minimal(self, data: dict[str, Any]) -> None:
        for k in ("nom_candidat", "score_global", "decision", "points_forts", "synthese"):
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    def _generate_fallback(
        self, cv_texte: str, criteres_poste: dict[str, Any]
    ) -> dict[str, Any]:
        domaine = criteres_poste.get("domaine", "Formation")
        return {
            "nom_candidat": "À identifier",
            "poste_vise": domaine,
            "score_global": 50,
            "decision": "À_DISCUTER",
            "points_forts": ["Profil à analyser manuellement"],
            "reserves": ["Analyse LLM indisponible — vérification manuelle requise"],
            "questions_entretien": [
                "Quelle est votre expérience en formation professionnelle ?",
                f"Maîtrisez-vous les outils liés à {domaine} ?",
                "Quelle est votre disponibilité pour des missions de courte durée ?",
            ],
            "adequation_domaine": {"score": 50, "justification": "Non évalué (fallback)"},
            "experience_formation": {"annees_estimees": None, "types": [], "justification": "Non évalué"},
            "competences_techniques": [],
            "synthese": (
                "Analyse automatique indisponible. "
                "Ce profil doit être évalué manuellement par l'équipe RH."
            ),
        }
