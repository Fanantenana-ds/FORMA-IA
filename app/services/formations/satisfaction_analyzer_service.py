"""
Agent 3 — SatisfactionAnalyzerService
======================================
Analyse la satisfaction des participants (notes + feedbacks textuels).

Stratégie :
    1. CALCUL DÉTERMINISTE (pandas) : moyennes, taux, compteurs
    2. ENRICHISSEMENT LLM (Groq) : points forts, axes, thèmes, recos
    3. FALLBACK : template Python si LLM indisponible

Pattern : identique à LevelAnalyzerService (Agent 2).
"""

import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
from app.services.hitl import create_review
from app.services.llm import LLMNotAvailableError, get_llm_provider

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "satisfaction_analysis.yaml"


# ============================================================
# SERVICE
# ============================================================
class SatisfactionAnalyzerService:
    """
    Agent 3 — Analyse la satisfaction des participants.

    Input  : réponses enquête (notes + feedbacks textuels).
    Output : analyse complète (stats + thèmes + recos).
    """

    # Mapping des clés internes → labels
    NOTES_KEYS = {
        "note_globale": "globale",
        "note_formateur": "formateur",
        "note_contenu": "contenu",
        "note_supports": "supports",
        "note_organisation": "organisation",
    }

    def __init__(self):
        try:
            self.llm = get_llm_provider()
        except LLMNotAvailableError:
            logger.warning("⚠️  Aucun provider LLM disponible → mode fallback uniquement.")
            self.llm = None

        self.prompt_config = self._load_prompt()
        logger.info(
            f"✅ SatisfactionAnalyzerService initialisé "
            f"(provider={self.llm.get_provider_name() if self.llm else 'aucun'}, "
            f"llm={'✅' if self.llm else '❌ fallback only'})"
        )

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------
    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")
        logger.info(f"✅ Prompt chargé : {PROMPT_PATH.name}")
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
        session_info: Dict[str, Any],
        stats: Dict[str, Any],
        feedbacks: List[Dict[str, Any]],
    ) -> str:
        """Prompt avec stats calculées + feedbacks bruts."""
        s = stats["statistiques"]
        n = s["notes"]

        lines = [
            "Analyse les réponses de satisfaction suivantes.",
            "",
            "=== SESSION ===",
            f"- Titre : {session_info.get('titre', 'N/A')}",
            f"- Domaine : {session_info.get('domaine', 'N/A')}",
            f"- Formateur : {session_info.get('formateur', 'N/A')}",
            "",
            "=== NOTES MOYENNES (déjà calculées) ===",
            f"- Globale : {n['note_globale']}/5",
            f"- Formateur : {n['note_formateur']}/5",
            f"- Contenu : {n['note_contenu']}/5",
            f"- Supports : {n['note_supports']}/5",
            f"- Organisation : {n['note_organisation']}/5",
            f"- Taux de recommandation : {s['taux_recommandation']}",
            f"- Nombre de réponses : {s['nb_reponses']}",
            "",
            "=== FEEDBACKS TEXTUELS ===",
        ]

        # Limiter à 20 feedbacks pour économiser tokens
        for i, fb in enumerate(feedbacks[:20], 1):
            lines.append(f"\n--- Participant {i} ---")
            if fb.get("points_forts"):
                lines.append(f"Points forts : {fb['points_forts']}")
            if fb.get("points_faibles"):
                lines.append(f"Points faibles : {fb['points_faibles']}")
            if fb.get("suggestions"):
                lines.append(f"Suggestions : {fb['suggestions']}")

        lines.extend([
            "",
            "Retourne UNIQUEMENT un JSON valide avec EXACTEMENT ces 5 clés :",
            "{",
            '  "resume": "Synthèse 2-3 phrases",',
            '  "points_forts": ["Point 1", "Point 2", "Point 3"],',
            '  "axes_amelioration": ["Axe 1", "Axe 2"],',
            '  "themes_recurrents": [',
            '    {"theme": "...", "frequence": "faible|moyenne|élevée", "sentiment": "positif|négatif|neutre"}',
            '  ],',
            '  "recommandations": ["Reco 1", "Reco 2", "Reco 3"],',
            '  "interpretation": "Analyse qualitative 2-4 phrases"',
            "}",
            "",
            "⚠️  NE PAS recalculer les notes — utilise celles ci-dessus.",
        ])
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def analyze(
        self,
        session_info: Dict[str, Any],
        responses: List[Dict[str, Any]],
        temperature: float = 0.4,
        max_tokens: int = 3000,
    ) -> Dict[str, Any]:
        """
        Analyse complète de la satisfaction.

        Args:
            session_info: Infos de session.
            responses: Liste de réponses :
                {
                    "note_globale": 4,
                    "note_formateur": 5,
                    "note_contenu": 4,
                    "note_supports": 3,
                    "note_organisation": 4,
                    "points_forts": "Formateur clair, exemples concrets",
                    "points_faibles": "Trop rapide sur la fin",
                    "suggestions": "Plus d'exercices pratiques",
                    "recommandation": "Oui" | "Non" | "Peut-être"
                }

        Returns:
            Dict conforme à SatisfactionAnalysisResponse.
        """
        start = datetime.now()
        logger.info("=" * 70)
        logger.info("🚀 [SatisfactionAgent] Analyse de la satisfaction...")
        logger.info(f"   📋 Session : {session_info.get('titre', 'N/A')}")
        logger.info(f"   👥 Réponses : {len(responses)}")
        logger.info("=" * 70)

        # ── ÉTAPE 1 : CALCUL DÉTERMINISTE ──
        stats = self._compute_statistics(responses)
        logger.info(
            f"   📊 Note globale={stats['statistiques']['notes']['note_globale']}/5, "
            f"Recommandation={stats['statistiques']['taux_recommandation']}"
        )

        # ── ÉTAPE 2 : ENRICHISSEMENT LLM ──
        enrichment = None
        source = "fallback_template"

        if self.llm and responses:
            try:
                enrichment = await self._generate_with_llm(
                    session_info, stats, responses, temperature, max_tokens
                )
                source = "llm"
                logger.info("   ✅ Analyse qualitative générée par LLM")
            except Exception as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule sur le template."
                )

        if enrichment is None:
            enrichment = self._generate_with_template(stats)
            logger.info("   ✅ Analyse générée par template Python (fallback)")

        # ── FUSION ──
        elapsed = round((datetime.now() - start).total_seconds(), 2)
        result = {
            "success": True,
            "resume": enrichment.get("resume", ""),
            "statistiques": stats["statistiques"],
            "points_forts": enrichment.get("points_forts", [])[:3],
            "axes_amelioration": enrichment.get("axes_amelioration", [])[:3],
            "themes_recurrents": enrichment.get("themes_recurrents", []),
            "recommandations": enrichment.get("recommandations", [])[:5],
            "interpretation": enrichment.get("interpretation", ""),
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "session_id": session_info.get("id"),
            },
        }
    
        review_id = create_review(
            agent_id="agent_3_satisfaction",
            data=result,
            summary=(
                f"Satisfaction {len(responses)} réponses — "
                f"note {result['statistiques']['notes']['note_globale']}/5"
            ),
            criticity="medium",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        logger.info("=" * 70)
        logger.info(f"✅ [SatisfactionAgent] Analyse terminée en {elapsed}s (review={review_id})")
        logger.info(
            f"   💡 Points forts={len(result['points_forts'])}, "
            f"Axes={len(result['axes_amelioration'])}, "
            f"Recos={len(result['recommandations'])}"
        )
        logger.info("=" * 70)
        return result

    # --------------------------------------------------------
    # CALCUL DÉTERMINISTE 
    # --------------------------------------------------------
    def _compute_statistics(self, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calcule notes moyennes + taux de recommandation (pur Python/pandas)."""
        if not responses:
            return self._empty_statistics()

        df = pd.DataFrame(responses)

        # Moyennes des notes (avec valeurs par défaut = 0)
        notes = {}
        for key, _ in self.NOTES_KEYS.items():
            if key in df.columns:
                notes[key] = round(float(df[key].dropna().astype(float).mean()), 2) if not df[key].dropna().empty else 0.0
            else:
                notes[key] = 0.0

        # Recommandations
        reco_col = df.get("recommandation", pd.Series(dtype=str)).fillna("").astype(str).str.lower().str.strip()
        nb_oui = int((reco_col == "oui").sum())
        nb_non = int((reco_col == "non").sum())
        nb_peut = int(((reco_col == "peut-être") | (reco_col == "peut etre") | (reco_col == "peut-être")).sum())
        nb_total_reco = nb_oui + nb_non + nb_peut

        taux = round(nb_oui / nb_total_reco * 100) if nb_total_reco > 0 else 0

        return {
            "statistiques": {
                "notes": notes,
                "taux_recommandation": f"{taux}%",
                "nb_reponses": len(responses),
                "nb_recommandent": nb_oui,
                "nb_neutres": nb_peut,
                "nb_deconseillent": nb_non,
            }
        }

    def _empty_statistics(self) -> Dict[str, Any]:
        return {
            "statistiques": {
                "notes": {k: 0.0 for k in self.NOTES_KEYS},
                "taux_recommandation": "0%",
                "nb_reponses": 0,
                "nb_recommandent": 0,
                "nb_neutres": 0,
                "nb_deconseillent": 0,
            }
        }

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(
        self,
        session_info: Dict[str, Any],
        stats: Dict[str, Any],
        responses: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Appel Groq — analyse qualitative uniquement."""
        # Extraire les feedbacks textuels
        feedbacks = []
        for r in responses:
            fb = {}
            for k in ("points_forts", "points_faibles", "suggestions"):
                if r.get(k) and str(r[k]).strip():
                    fb[k] = str(r[k]).strip()
            if fb:
                feedbacks.append(fb)

        response = await self.llm.generate(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(session_info, stats, feedbacks),
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        raw = response["content"]
        finish = response["finish_reason"]

        if finish == "length":
            raise ValueError("Réponse LLM tronquée (finish_reason=length)")

        data = json.loads(raw)
        logger.debug(f"Réponse LLM brute (keys) : {list(data.keys())}")

        # ── Extraction robuste ──
        points_forts = data.get("points_forts") or data.get("strengths") or []
        axes = (
            data.get("axes_amelioration")
            or data.get("axes_amélioration")
            or data.get("improvements")
            or data.get("weaknesses")
            or []
        )
        themes = data.get("themes_recurrents") or data.get("themes") or []
        recos = (
            data.get("recommandations")
            or data.get("recommendations")
            or data.get("recos")
            or []
        )

        def to_list(x):
            if isinstance(x, dict):
                return list(x.values())
            if isinstance(x, list):
                return [str(i).strip() for i in x if i and str(i).strip()]
            return []

        points_forts = to_list(points_forts)[:3]
        axes = to_list(axes)[:3]
        recos = to_list(recos)[:5]

        # Normaliser les thèmes
        themes_norm = []
        for t in themes if isinstance(themes, list) else []:
            if isinstance(t, dict) and t.get("theme"):
                themes_norm.append({
                    "theme": str(t["theme"]).strip(),
                    "frequence": t.get("frequence", "moyenne"),
                    "sentiment": t.get("sentiment", "neutre"),
                })

        # Fallback partiel si vide
        if not recos or not points_forts:
            logger.warning("   ⚠️  LLM incomplet → complétion avec template.")
            fb = self._generate_with_template(stats)
            if not points_forts:
                points_forts = fb["points_forts"]
            if not axes:
                axes = fb["axes_amelioration"]
            if not recos:
                recos = fb["recommandations"]
            if not themes_norm:
                themes_norm = fb["themes_recurrents"]

        return {
            "resume": data.get("resume") or data.get("summary") or "",
            "points_forts": points_forts,
            "axes_amelioration": axes,
            "themes_recurrents": themes_norm,
            "recommandations": recos,
            "interpretation": data.get("interpretation") or data.get("analysis") or "",
        }

    # --------------------------------------------------------
    # FALLBACK TEMPLATE
    # --------------------------------------------------------
    def _generate_with_template(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Template Python (fallback)."""
        s = stats["statistiques"]
        n = s["notes"]

        resume = (
            f"La satisfaction globale est de {n['note_globale']}/5. "
            f"{s['taux_recommandation']} des participants recommandent la formation."
        )

        points_forts = [
            f"Qualité du formateur notée {n['note_formateur']}/5",
            f"Contenu jugé satisfaisant ({n['note_contenu']}/5)",
            f"Organisation appréciée ({n['note_organisation']}/5)",
        ]

        axes = []
        if n["note_supports"] < 4.0:
            axes.append("Améliorer la qualité des supports pédagogiques.")
        if n["note_contenu"] < 4.0:
            axes.append("Enrichir le contenu avec plus de cas pratiques.")
        if n["note_globale"] < 4.0:
            axes.append("Renforcer l'accompagnement des participants.")
        if not axes:
            axes = ["Maintenir la qualité actuelle et capitaliser sur les acquis."]

        themes = [
            {"theme": "Qualité du formateur", "frequence": "élevée", "sentiment": "positif"},
            {"theme": "Contenu de la formation", "frequence": "moyenne", "sentiment": "positif"},
            {"theme": "Organisation", "frequence": "moyenne", "sentiment": "positif"},
        ]

        recos = [
            "Reconduire la formation en capitalisant sur les points forts identifiés.",
            "Intégrer davantage d'exercices pratiques dans les prochaines sessions.",
            "Prévoir un temps de feedback individuel en fin de formation.",
        ]
        if n["note_supports"] < 4.0:
            recos.append("Réviser et enrichir les supports pédagogiques.")
        if s["nb_deconseillent"] > 0:
            recos.append("Analyser les retours négatifs pour comprendre les points de friction.")

        interpretation = (
            f"Les participants ont globalement apprécié la formation, avec une "
            f"note globale de {n['note_globale']}/5. Les notes détaillées montrent "
            f"une satisfaction homogène sur les différents critères."
        )

        return {
            "resume": resume,
            "points_forts": points_forts,
            "axes_amelioration": axes,
            "themes_recurrents": themes,
            "recommandations": recos[:5],
            "interpretation": interpretation,
        }