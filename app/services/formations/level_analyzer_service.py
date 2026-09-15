import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

import pandas as pd
from openai import AsyncOpenAI
from app.services.hitl import create_review

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "level_analysis.yaml"

# Seuils de classification
SEUIL_DEBUTANT = 40      # < 40  → Débutant
SEUIL_INTERMEDIAIRE = 70 # < 70  → Intermédiaire
                         # >= 70 → Avancé


# ============================================================
# SERVICE
# ============================================================
class LevelAnalyzerService:
    """
    Agent 2 — Analyse les niveaux des participants.

    Input  : participants (avec réponses) + corrigé.
    Output : analyse complète (scores, distributions, progression, recommandations).
    """

    def __init__(self):
        if not GROQ_API_KEY:
            logger.warning("⚠️  GROQ_API_KEY manquant → mode fallback uniquement.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

        self.model = GROQ_MODEL
        self.prompt_config = self._load_prompt()
        logger.info(
            f"✅ LevelAnalyzerService initialisé "
            f"(model={self.model}, llm={'✅' if self.client else '❌ fallback only'})"
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
    ) -> str:
        """Construit le prompt utilisateur avec les stats déjà calculées."""
        lines = [
            "Analyse les résultats suivants et génère les recommandations.",
            "",
            "=== SESSION ===",
            f"- Titre : {session_info.get('titre', 'N/A')}",
            f"- Domaine : {session_info.get('domaine', 'N/A')}",
            f"- Niveau cible : {session_info.get('niveau_cible', 'N/A')}",
            "",
            "=== STATISTIQUES CALCULÉES (back-end) ===",
            f"- Score moyen AVANT : {stats['statistiques']['score_moyen_avant']}/100",
            f"- Score moyen APRÈS : {stats['statistiques']['score_moyen_apres']}/100",
            f"- Progression absolue : +{stats['statistiques']['progression_absolue']} points",
            f"- Progression relative : {stats['statistiques']['progression_relative']}",
            f"- Nombre de participants : {stats['statistiques']['nb_participants']}",
            "",
            "=== DISTRIBUTION AVANT ===",
            f"- Débutants : {stats['distribution_avant']['debutants']['pourcentage']}",
            f"- Intermédiaires : {stats['distribution_avant']['intermediaires']['pourcentage']}",
            f"- Avancés : {stats['distribution_avant']['avances']['pourcentage']}",
            "",
            "=== DISTRIBUTION APRÈS ===",
            f"- Débutants : {stats['distribution_apres']['debutants']['pourcentage']}",
            f"- Intermédiaires : {stats['distribution_apres']['intermediaires']['pourcentage']}",
            f"- Avancés : {stats['distribution_apres']['avances']['pourcentage']}",
            "",
            "Retourne UNIQUEMENT le JSON valide (resume + interpretation + recommandations).",
            "⚠️  Ne recalcule PAS les statistiques — utilise celles ci-dessus.",
        ]
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def analyze(
        self,
        session_info: Dict[str, Any],
        participants: List[Dict[str, Any]],
        corrige: Dict[str, str],
        temperature: float = 0.4,
        max_tokens: int = 2500,
    ) -> Dict[str, Any]:
        """
        Analyse complète des niveaux.

        Args:
            session_info: Infos de session (titre, domaine, niveau_cible).
            participants: Liste de dicts :
                {
                    "id": 1, "nom": "Jean",
                    "reponses_avant": {"av_01": "A", "av_02": "B", ...},
                    "reponses_apres": {"ap_01": "A", "ap_02": "B", ...}
                }
            corrige: Mapping question_id → bonne réponse (ex: {"av_01": "A"}).

        Returns:
            Dict conforme à LevelAnalysisResponse.
        """
        start = datetime.now()
        logger.info("=" * 70)
        logger.info("🚀 [LevelAgent] Analyse des niveaux...")
        logger.info(f"   📋 Session : {session_info.get('titre', 'N/A')}")
        logger.info(f"   👥 Participants : {len(participants)}")
        logger.info(f"   ✅ Corrigé : {len(corrige)} questions")
        logger.info("=" * 70)

        # ── ÉTAPE 1 : CALCUL DÉTERMINISTE (pandas) ──
        stats = self._compute_statistics(participants, corrige)
        prog = stats['statistiques']['progression_absolue']
        prog_str = f"{prog:+.1f}"  # +55.0 ou -55.0 automatiquement
        logger.info(
            f"   📊 Avant={stats['statistiques']['score_moyen_avant']}/100, "
            f"Après={stats['statistiques']['score_moyen_apres']}/100, "
            f"Progression={prog_str}"
        )
        # ── ÉTAPE 2 : ENRICHISSEMENT LLM (recommandations + interprétation) ──
        enrichment = None
        source = "fallback_template"

        if self.client:
            try:
                enrichment = await self._generate_with_llm(
                    session_info, stats, temperature, max_tokens
                )
                source = "llm"
                logger.info("   ✅ Recommandations générées par LLM")
            except Exception as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule sur le template."
                )

        if enrichment is None:
            enrichment = self._generate_with_template(stats)
            logger.info("   ✅ Recommandations générées par template Python")

        # ── FUSION ──
        elapsed = round((datetime.now() - start).total_seconds(), 2)
        result = {
            "success": True,
            "resume": enrichment.get("resume", ""),
            "statistiques": stats["statistiques"],
            "distribution_avant": stats["distribution_avant"],
            "distribution_apres": stats["distribution_apres"],
            "cas_remarquables": stats["cas_remarquables"],
            "recommandations": enrichment.get("recommandations", []),
            "interpretation": enrichment.get("interpretation", ""),
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "session_id": session_info.get("id"),
            },
        }
      
        review_id = create_review(
            agent_id="agent_2_levels",
            data=result,
            summary=(
                f"Analyse {len(participants)} participants — "
                f"progression {result['statistiques']['progression_absolue']:+.1f} pts"
            ),
            criticity="medium",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        logger.info("=" * 70)
        logger.info(f"✅ [LevelAgent] Analyse terminée en {elapsed}s (review={review_id})")
        logger.info(f"   💡 Recommandations : {len(result['recommandations'])}")
        logger.info("=" * 70)
        return result
        
    # --------------------------------------------------------
    # CALCUL DÉTERMINISTE (pandas)
    # --------------------------------------------------------
    def _compute_statistics(
        self,
        participants: List[Dict[str, Any]],
        corrige: Dict[str, str],
    ) -> Dict[str, Any]:
        """Calcule scores, distributions et cas remarquables (pur Python/pandas)."""
        rows = []
        for p in participants:
            score_avant = self._score(p.get("reponses_avant", {}), corrige)
            score_apres = self._score(p.get("reponses_apres", {}), corrige)
            rows.append({
                "nom": p.get("nom", "N/A"),
                "avant": score_avant,
                "apres": score_apres,
                "gain": round(score_apres - score_avant, 1),
            })

        if not rows:
            return self._empty_statistics()

        df = pd.DataFrame(rows)

        # Statistiques globales
        moy_avant = round(float(df["avant"].mean()), 1)
        moy_apres = round(float(df["apres"].mean()), 1)
        prog_abs = round(moy_apres - moy_avant, 1)
        prog_rel = f"{(prog_abs / moy_avant * 100):.1f}%" if moy_avant > 0 else "N/A"

        # Distributions
        dist_avant = self._distribution(df["avant"].tolist())
        dist_apres = self._distribution(df["apres"].tolist())

        # Cas remarquables
        meilleur = df.loc[df["gain"].idxmax()].to_dict()
        faibles = df[df["gain"] < 5].sort_values("gain").head(3).to_dict("records")

        return {
            "statistiques": {
                "score_moyen_avant": moy_avant,
                "score_moyen_apres": moy_apres,
                "progression_absolue": prog_abs,
                "progression_relative": prog_rel,
                "nb_participants": len(rows),
            },
            "distribution_avant": dist_avant,
            "distribution_apres": dist_apres,
            "cas_remarquables": {
                "meilleure_progression": {
                    "nom": meilleur["nom"],
                    "avant": meilleur["avant"],
                    "apres": meilleur["apres"],
                    "gain": meilleur["gain"],
                },
                "progressions_faibles": [
                    {
                        "nom": r["nom"], "avant": r["avant"],
                        "apres": r["apres"], "gain": r["gain"],
                    }
                    for r in faibles
                ],
            },
        }

    def _score(self, reponses: Dict[str, str], corrige: Dict[str, str]) -> float:
        """
        Calcule le score en % (0-100).

        ⚠️ Normalise les IDs : ap_XX est traité comme av_XX
        (le test AVANT et APRÈS ont les mêmes questions/concepts).
        """
        if not corrige:
            return 0.0

        # Normalisation : ap_01 → av_01 (pour matcher le corrigé)
        def normalize(qid: str) -> str:
            if qid.startswith("ap_"):
                return "av_" + qid[3:]
            return qid

        reponses_norm = {normalize(k): v for k, v in reponses.items()}

        bonnes = sum(
            1 for q, bonne in corrige.items()
            if reponses_norm.get(q, "").strip().upper() == bonne.strip().upper()
        )
        return round((bonnes / len(corrige)) * 100, 1)
    def _distribution(self, scores: List[float]) -> Dict[str, Any]:
        """Retourne la distribution Débutant / Intermédiaire / Avancé."""
        n = len(scores)
        if n == 0:
            return {
                "debutants": {"nb": 0, "pourcentage": "0%"},
                "intermediaires": {"nb": 0, "pourcentage": "0%"},
                "avances": {"nb": 0, "pourcentage": "0%"},
            }
        deb = sum(1 for s in scores if s < SEUIL_DEBUTANT)
        interm = sum(1 for s in scores if SEUIL_DEBUTANT <= s < SEUIL_INTERMEDIAIRE)
        av = sum(1 for s in scores if s >= SEUIL_INTERMEDIAIRE)
        return {
            "debutants": {"nb": deb, "pourcentage": f"{round(deb / n * 100)}%"},
            "intermediaires": {"nb": interm, "pourcentage": f"{round(interm / n * 100)}%"},
            "avances": {"nb": av, "pourcentage": f"{round(av / n * 100)}%"},
        }

    def _empty_statistics(self) -> Dict[str, Any]:
        """Retourne des stats vides si aucun participant."""
        empty = {"nb": 0, "pourcentage": "0%"}
        return {
            "statistiques": {
                "score_moyen_avant": 0.0, "score_moyen_apres": 0.0,
                "progression_absolue": 0.0, "progression_relative": "0%",
                "nb_participants": 0,
            },
            "distribution_avant": {
                "debutants": empty, "intermediaires": empty, "avances": empty,
            },
            "distribution_apres": {
                "debutants": empty, "intermediaires": empty, "avances": empty,
            },
            "cas_remarquables": {
                "meilleure_progression": None, "progressions_faibles": [],
            },
        }

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(
        self,
        session_info: Dict[str, Any],
        stats: Dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Appel Groq — génère resume + interpretation + recommandations."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": self._build_user_prompt(session_info, stats)},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        finish = response.choices[0].finish_reason

        if finish == "length":
            raise ValueError("Réponse LLM tronquée (finish_reason=length)")

        data = json.loads(raw)
        logger.debug(f"Réponse LLM brute (keys) : {list(data.keys())}")

        # ── Extraction robuste des recommandations ──
        recos = (
            data.get("recommandations")
            or data.get("recommendations")
            or data.get("recos")
            or []
        )
        # Si c'est un dict au lieu d'une liste → on prend ses valeurs
        if isinstance(recos, dict):
            recos = list(recos.values())

        recos = [str(r).strip() for r in recos if r and str(r).strip()][:5]

        resume = data.get("resume") or data.get("summary") or ""
        interpretation = (
            data.get("interpretation")
            or data.get("analyse")
            or data.get("analysis")
            or ""
        )

        # ── Si LLM n'a rien donné → fallback partiel ──
        if not recos:
            logger.warning("   ⚠️  LLM n'a pas fourni de recommandations → fallback template.")
            fallback = self._generate_with_template(stats)
            recos = fallback["recommandations"]
            if not resume:
                resume = fallback["resume"]
            if not interpretation:
                interpretation = fallback["interpretation"]

        return {
            "resume": resume,
            "interpretation": interpretation,
            "recommandations": recos,
        }

    # --------------------------------------------------------
    # FALLBACK TEMPLATE
    # --------------------------------------------------------
    def _generate_with_template(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Template Python (fallback) pour resume + interpretation + recos."""
        s = stats["statistiques"]
        d_av = stats["distribution_avant"]
        d_ap = stats["distribution_apres"]

        resume = (
            f"La formation a permis une progression moyenne de "
            f"+{s['progression_absolue']} points ({s['progression_relative']}). "
            f"Les débutants sont passés de {d_av['debutants']['pourcentage']} "
            f"à {d_ap['debutants']['pourcentage']} après la formation."
        )

        interpretation = (
            f"Le groupe a évolué de manière significative : le score moyen "
            f"est passé de {s['score_moyen_avant']}/100 à {s['score_moyen_apres']}/100. "
            f"Les participants classés « Avancé » représentent désormais "
            f"{d_ap['avances']['pourcentage']} du groupe."
        )

        recos = []
        if float(d_ap["debutants"]["pourcentage"].rstrip("%")) > 20:
            recos.append("Renforcer le temps d'accompagnement individuel pour les participants en difficulté.")
        if s["progression_absolue"] < 20:
            recos.append("Adapter le rythme pédagogique et proposer des exercices supplémentaires.")
        recos.append("Reconduire la formation en capitalisant sur les acquis du groupe.")
        if len(d_ap["avances"]["pourcentage"]) > 0:
            recos.append("Proposer un module avancé pour les participants ayant atteint le niveau Avancé.")

        return {
            "resume": resume,
            "interpretation": interpretation,
            "recommandations": recos[:5],
        }