"""
Agent 6 — ReportGeneratorService
=================================
Génère le RAPPORT FINAL de formation (contenu JSON).

Stratégie (A + Fallback B) :
    1. ESSAI : Groq API (LLM) → rapport naturel
    2. FALLBACK : Template Python → rapport standard

📝 LOGS  : contrôle via .env → VERBOSE_LOGS=true|false
📝 HITL  : validation humaine via hitl_helper.create_review()

Auteur  : Équipe IA — ALTIORA Solutions
Version : 1.2.0 (verbose + HITL)
"""

import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

from openai import AsyncOpenAI

from app.services.formations.hitl_helper import create_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# ============================================================
# CONFIG
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "report_generation.yaml"


# ============================================================
# SERVICE
# ============================================================
class ReportGeneratorService:
    """Agent 6 — Génère le rapport final de formation."""

    def __init__(self):
        if not GROQ_API_KEY:
            logger.warning("⚠️  GROQ_API_KEY manquant → mode fallback uniquement.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

        self.model = GROQ_MODEL
        self.prompt_config = self._load_prompt()
        vlog(
            f"✅ ReportGeneratorService initialisé "
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
        vlog(f"✅ Prompt chargé : {PROMPT_PATH.name}")
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

    def _build_user_prompt(self, session_data: Dict[str, Any]) -> str:
        s = session_data
        lines = [
            "Génère le rapport final pour la session suivante :",
            "",
            "=== SESSION ===",
            f"- Titre : {s.get('titre', 'N/A')}",
            f"- Domaine : {s.get('domaine', 'N/A')}",
            f"- Niveau cible : {s.get('niveau_cible', 'N/A')}",
            f"- Date début : {s.get('date_debut', 'N/A')}",
            f"- Date fin : {s.get('date_fin', 'N/A')}",
            f"- Lieu : {s.get('lieu', 'N/A')}",
            f"- Formateur : {s.get('formateur', 'N/A')}",
            f"- Durée (jours) : {s.get('duree_jours', 2)}",
            f"- Public cible : {s.get('public_cible', 'N/A')}",
            "",
            "=== STATISTIQUES PARTICIPANTS ===",
            f"- Total inscrits : {s.get('total_inscrits', 0)}",
            f"- Total présents : {s.get('total_presents', 0)}",
            f"- Taux de présence moyen : {s.get('taux_presence', 'N/A')}",
            f"- Entreprises : {', '.join(s.get('entreprises', [])) or 'N/A'}",
            "",
            "=== NIVEAUX AVANT / APRÈS ===",
            f"- Avant : {s.get('niveaux_avant', 'N/A')}",
            f"- Après : {s.get('niveaux_apres', 'N/A')}",
            f"- Progression : {s.get('progression', 'N/A')}",
            "",
            "=== SATISFACTION ===",
            f"- Note globale : {s.get('note_globale', 'N/A')}",
            f"- Note formateur : {s.get('note_formateur', 'N/A')}",
            f"- Note contenu : {s.get('note_contenu', 'N/A')}",
            f"- Note supports : {s.get('note_supports', 'N/A')}",
            f"- Note organisation : {s.get('note_organisation', 'N/A')}",
            f"- Points forts : {', '.join(s.get('points_forts', [])) or 'N/A'}",
            f"- Axes d'amélioration : {', '.join(s.get('axes_amelioration', [])) or 'N/A'}",
            f"- Taux recommandation : {s.get('taux_recommandation', 'N/A')}",
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def generate(
        self,
        session_data: Dict[str, Any],
        temperature: float = 0.4,
        max_tokens: int = 3000,
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [ReportAgent] Génération du rapport final...")
        vlog(f"   📋 Session : {session_data.get('titre', 'N/A')}")
        vlog(f"   👥 Participants : {session_data.get('total_inscrits', 0)}")
        vlog("=" * 70)

        content = None
        source = "fallback_template"

        if self.client:
            try:
                content = await self._generate_with_llm(
                    session_data, temperature, max_tokens
                )
                source = "llm"
                vlog("   ✅ Rapport généré par LLM (Groq)")
            except Exception as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule template."
                )

        if content is None:
            content = self._generate_with_template(session_data)
            vlog("   ✅ Rapport généré par template Python (fallback)")

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        content["metadata"] = {
            "source": source,
            "generated_at": datetime.now().isoformat(),
            "duration_seconds": elapsed,
            "session_id": session_data.get("id"),
        }

        # ⏳ HITL — Créer un review (CRITIQUE)
        review_id = create_review(
            agent_id="agent_6_report",
            data=content,
            summary=(
                f"Rapport final — "
                f"{len(content.get('recommandations', []))} recos — "
                f"à valider avant envoi client"
            ),
            criticity="critical",
        )
        content["_review_id"] = review_id
        content["_review_status"] = "pending_review"

        vlog("=" * 70)
        vlog(f"✅ [ReportAgent] Rapport terminé en {elapsed}s (source={source}, review={review_id})")
        vlog(f"   📊 Recommandations : {len(content.get('recommandations', []))}")
        vlog("=" * 70)
        return content

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(
        self,
        session_data: Dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": self._build_user_prompt(session_data)},
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
        self._validate_llm_output(data)
        return data

    def _validate_llm_output(self, data: Dict[str, Any]) -> None:
        required = [
            "titre_rapport", "resume_executif", "presentation",
            "statistiques_participants", "analyse_niveaux",
            "satisfaction", "recommandations", "conclusion",
            "lieu_emission", "date_emission",
        ]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")
        if not isinstance(data["recommandations"], list) or len(data["recommandations"]) < 3:
            raise ValueError("'recommandations' : liste de 3 éléments minimum")

    # --------------------------------------------------------
    # FALLBACK TEMPLATE
    # --------------------------------------------------------
    def _generate_with_template(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        s = session_data
        date_fin = s.get("date_fin", datetime.now().strftime("%Y-%m-%d"))

        return {
            "titre_rapport": f"RAPPORT DE FORMATION — {s.get('titre', 'N/A')}",
            "resume_executif": (
                f"La formation « {s.get('titre', 'N/A')} » s'est déroulée du "
                f"{s.get('date_debut', 'N/A')} au {s.get('date_fin', 'N/A')} à "
                f"{s.get('lieu', 'N/A')}. Elle a réuni "
                f"{s.get('total_inscrits', 0)} participants pour un total de "
                f"{s.get('duree_jours', 2)} jours. Le taux de présence moyen "
                f"est de {s.get('taux_presence', 'N/A')} et la satisfaction "
                f"globale atteint {s.get('note_globale', 'N/A')}."
            ),
            "presentation": {
                "titre_formation": s.get("titre", "N/A"),
                "dates": self._format_date_range(
                    s.get("date_debut", ""), s.get("date_fin", "")
                ),
                "lieu": s.get("lieu", "N/A"),
                "duree": f"{s.get('duree_jours', 2)} jours",
                "formateur": f"Monsieur {s.get('formateur', 'N/A')}",
                "public_cible": s.get("public_cible", "N/A"),
                "nombre_participants": s.get("total_inscrits", 0),
            },
            "statistiques_participants": {
                "total_inscrits": s.get("total_inscrits", 0),
                "total_presents": s.get("total_presents", 0),
                "taux_presence_moyen": s.get("taux_presence", "N/A"),
                "entreprises": s.get("entreprises", []),
                "commentaire": (
                    f"Sur {s.get('total_inscrits', 0)} inscrits, "
                    f"{s.get('total_presents', 0)} ont effectivement participé."
                ),
            },
            "analyse_niveaux": {
                "avant": s.get("niveaux_avant", {
                    "debutants": "N/A", "intermediaires": "N/A", "avances": "N/A",
                }),
                "apres": s.get("niveaux_apres", {
                    "debutants": "N/A", "intermediaires": "N/A", "avances": "N/A",
                }),
                "progression_globale": s.get("progression", "N/A"),
                "commentaire": "Analyse de la progression des participants.",
            },
            "satisfaction": {
                "note_globale": s.get("note_globale", "N/A"),
                "note_formateur": s.get("note_formateur", "N/A"),
                "note_contenu": s.get("note_contenu", "N/A"),
                "note_supports": s.get("note_supports", "N/A"),
                "note_organisation": s.get("note_organisation", "N/A"),
                "points_forts": s.get("points_forts", []),
                "axes_amelioration": s.get("axes_amelioration", []),
                "taux_recommandation": s.get("taux_recommandation", "N/A"),
            },
            "recommandations": [
                "Reconduire cette formation pour d'autres promotions.",
                "Renforcer les exercices pratiques sur les concepts avancés.",
                "Adapter le rythme pour les participants débutants.",
            ],
            "conclusion": (
                f"La formation a atteint ses objectifs pédagogiques avec une "
                f"satisfaction de {s.get('note_globale', 'N/A')}. Les "
                f"recommandations ci-dessus permettront d'améliorer les "
                f"prochaines sessions."
            ),
            "lieu_emission": "Antananarivo",
            "date_emission": self._default_emission_date(date_fin),
        }

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------
    def _format_date_range(self, date_debut: str, date_fin: str) -> str:
        MOIS_FR = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ]
        try:
            d1 = datetime.strptime(date_debut, "%Y-%m-%d")
            d2 = datetime.strptime(date_fin, "%Y-%m-%d")
            if d1.month == d2.month and d1.year == d2.year:
                return f"{d1.day} au {d2.day} {MOIS_FR[d2.month - 1]} {d2.year}"
            return (
                f"{d1.day} {MOIS_FR[d1.month - 1]} au "
                f"{d2.day} {MOIS_FR[d2.month - 1]} {d2.year}"
            )
        except Exception:
            return f"{date_debut} au {date_fin}"

    def _default_emission_date(self, date_fin: str) -> str:
        try:
            d = datetime.strptime(date_fin, "%Y-%m-%d")
            return (d + timedelta(days=3)).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")