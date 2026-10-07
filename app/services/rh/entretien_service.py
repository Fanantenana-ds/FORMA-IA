from app.utils.json_repair import repair_json
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
        contexte_a1: Optional[Dict[str, Any]] = None,
    ) -> str:
        lignes = [
            "Rédige le compte-rendu pour cet entretien :",
            "",
            "=== INFORMATIONS GÉNÉRALES ===",
            f"- Candidat : {candidat}",
            f"- Poste : {poste}",
            f"- Date : {date_entretien or 'non précisée'}",
            f"- Interviewers : {', '.join(interviewers) if interviewers else 'non précisés'}",
        ]

        # Injection contexte A1 si disponible
        if contexte_a1:
            score = contexte_a1.get("score_global")
            decision_a1 = contexte_a1.get("decision")
            questions = contexte_a1.get("questions_entretien") or []
            points_forts_cv = contexte_a1.get("points_forts") or []
            reserves_cv = contexte_a1.get("reserves") or []

            lignes += [
                "",
                "=== CONTEXTE PRÉSÉLECTION CV (A1) ===",
                f"- Score CV : {score}/100" if score is not None else "",
                f"- Décision initiale : {decision_a1}" if decision_a1 else "",
            ]
            if points_forts_cv:
                lignes.append(f"- Points forts CV : {', '.join(points_forts_cv[:3])}")
            if reserves_cv:
                lignes.append(f"- Réserves CV : {', '.join(reserves_cv[:3])}")
            if questions:
                lignes += [
                    "",
                    "Questions d'entretien suggérées par A1 (à utiliser comme fil conducteur) :",
                ]
                for i, q in enumerate(questions[:5], 1):
                    lignes.append(f"  {i}. {q}")

        lignes += [
            "",
            "=== NOTES BRUTES DE L'ENTRETIEN ===",
            notes_brutes.strip()[:8000],
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        return "\n".join(l for l in lignes if l is not None)

    async def generate(
        self,
        notes_brutes: str,
        candidat: str,
        poste: str,
        interviewers: Optional[List[str]] = None,
        date_entretien: Optional[str] = None,
        review_id_a1: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [EntretienAgent] Rédaction CR entretien — {candidat}")
        vlog("=" * 70)

        interviewers = interviewers or []

        # Récupération contexte A1 si review_id fourni
        contexte_a1 = None
        if review_id_a1:
            try:
                from app.services.hitl import get_review
                review = get_review(review_id_a1)
                if review:
                    contexte_a1 = review.get("data", {})
                    vlog(f"   📋 Contexte A1 injecté (review={review_id_a1})")
            except Exception as exc:
                vlog(f"   ⚠️ Contexte A1 non récupéré : {exc}", "warning")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            notes_brutes, candidat, poste, interviewers, date_entretien, contexte_a1
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
        if review_id_a1:
            result["_review_id_a1"] = review_id_a1

        vlog(f"✅ [EntretienAgent] Terminé en {elapsed}s (source={source})")
        return result

    def _repair_json(self, raw: str) -> str:
        return repair_json(raw)
    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        for k in ("candidat", "decision", "points_forts", "resume_entretien", "parcours_candidat"):
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
            "parcours_candidat": "À compléter manuellement.",
            "motivations": "Non capturé automatiquement.",
            "competences_evaluees": [],
            "adequation_culturelle": {"score": None, "commentaire": "Non évalué"},
            "points_forts": ["À compléter manuellement"],
            "points_vigilance": ["Analyse automatique indisponible"],
            "decision": "APPROFONDIR",
            "justification_decision": "Analyse automatique indisponible. Vérification manuelle requise.",
            "prochaines_etapes": ["Compléter ce CR manuellement avant décision"],
        }
