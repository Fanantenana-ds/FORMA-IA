import os
import re
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from app.services.llm import get_llm_provider, LLMError

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "m4" / "rh_evaluation_formateur.yaml"
)
AGENT_ID = "agent_m4_evaluation"


class EvaluationFormateurService:
    """
    Agent M4-5 — Évaluation formateur post-session (données M5).

    Input  : données_session (résultats M5 : satisfaction, présences, rapport)
    Output : JSON fiche évaluation (document interne, pas de HITL requis)

    Pas de HITL : document interne RH, non diffusé au formateur sans décision
    humaine explicite. La fiche est stockée localement et peut enrichir le
    profil formateur dans le Backend (PATCH /formateurs/{id}) si disponible.
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [EvaluationFormateurAgent] Service initialisé")

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
        formateur: str,
        session: str,
        donnees_session: Dict[str, Any],
    ) -> str:
        lines = [
            "Évalue ce formateur à partir des données de la session :",
            "",
            f"=== FORMATEUR : {formateur} ===",
            f"=== SESSION : {session} ===",
            "",
            "=== DONNÉES DE LA SESSION (issues des agents M5) ===",
        ]
        # Satisfaction
        satis = donnees_session.get("satisfaction", {})
        if satis:
            lines += [
                "— Satisfaction participants :",
                f"  Score moyen : {satis.get('score_moyen', 'N/A')} / 5",
                f"  Points positifs : {satis.get('points_positifs', [])}",
                f"  Points négatifs : {satis.get('points_negatifs', [])}",
            ]
        # Présences
        presences = donnees_session.get("presences", {})
        if presences:
            lines += [
                "— Présences :",
                f"  Taux moyen : {presences.get('taux_moyen_pct', 'N/A')} %",
                f"  Anomalies : {presences.get('anomalies', False)}",
            ]
        # Rapport
        rapport = donnees_session.get("rapport", "")
        if rapport:
            lines += ["— Extrait rapport final :", str(rapport)[:1000]]

        lines += ["", "Retourne UNIQUEMENT le JSON valide, sans texte autour."]
        return "\n".join(lines)

    async def generate(
        self,
        formateur: str,
        session: str,
        donnees_session: Dict[str, Any],
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [EvaluationFormateurAgent] Évaluation — {formateur}")
        vlog(f"   📋 Session : {session}")
        vlog("=" * 70)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(formateur, session, donnees_session)
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
            content = self._generate_fallback(formateur, session, donnees_session)

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

        vlog(
            f"✅ [EvaluationFormateurAgent] Terminé en {elapsed}s "
            f"(source={source}, score={result.get('score_global')})"
        )
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
        for k in ("formateur", "score_global", "recommandation"):
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    def _generate_fallback(
        self,
        formateur: str,
        session: str,
        donnees_session: Dict[str, Any],
    ) -> Dict[str, Any]:
        satis = donnees_session.get("satisfaction", {})
        presences = donnees_session.get("presences", {})

        score_satis = satis.get("score_moyen")
        taux = presences.get("taux_moyen_pct")

        # Score simplifié (fallback Python)
        score_global: Optional[float] = None
        if score_satis is not None and taux is not None:
            score_global = round(
                (float(score_satis) / 5 * 100 * 0.5) + (float(taux) * 0.3), 1
            )

        recommandation = "CONDITIONNEL"
        if score_global is not None:
            if score_global >= 75:
                recommandation = "OUI"
            elif score_global < 55:
                recommandation = "NON"

        return {
            "formateur": formateur,
            "session": session,
            "date_session": None,
            "score_global": score_global,
            "recommandation": recommandation,
            "satisfaction": {
                "score_moyen": score_satis,
                "sur_5": True,
                "points_positifs": satis.get("points_positifs", []),
                "points_negatifs": satis.get("points_negatifs", []),
            },
            "presences": {
                "taux_moyen_pct": taux,
                "anomalies_detectees": presences.get("anomalies", False),
                "commentaire": None,
            },
            "points_forts_session": [],
            "axes_amelioration": ["Évaluation détaillée indisponible (LLM hors ligne)"],
            "justification_recommandation": (
                f"Score calculé automatiquement : {score_global}. "
                "Évaluation qualitative à compléter manuellement."
            ),
            "note_interne_rh": "Généré par fallback Python — vérification manuelle recommandée.",
        }
