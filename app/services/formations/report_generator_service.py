"""
Agent 6 — ReportGeneratorService
=================================
Génère le RAPPORT FINAL de formation (contenu JSON).

Stratégie (A + Fallback B) :
    1. ESSAI : Groq API (LLM) → rapport naturel
    2. FALLBACK : Template Python → rapport standard

📝 LOGS  : contrôle via .env → VERBOSE_LOGS=true|false
📝 HITL  : validation humaine via hitl_helper.create_review()

Auteur  : Équipe IA — ALTIORA PREST
Version : 1.2.0 (verbose + HITL)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.services.hitl import create_review
from app.services.llm import LLMNotAvailableError, get_llm_provider

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# ============================================================
# CONFIG
# ============================================================
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "report_generation.yaml"


# ============================================================
# SERVICE
# ============================================================
class ReportGeneratorService:
    """Agent 6 — Génère le rapport final de formation."""

    def __init__(self):
        try:
            self.llm = get_llm_provider()
        except LLMNotAvailableError:
            logger.warning("⚠️  Aucun provider LLM disponible → mode fallback uniquement.")
            self.llm = None

        self.prompt_config = self._load_prompt()
        vlog(
            f"✅ ReportGeneratorService initialisé "
            f"(provider={self.llm.get_provider_name() if self.llm else 'aucun'}, "
            f"llm={'✅' if self.llm else '❌ fallback only'})"
        )

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------
    def _load_prompt(self) -> dict[str, Any]:
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

    @staticmethod
    def _val(s: dict[str, Any], key: str, fallback: str = "Non renseigné") -> str:
        """Retourne la valeur ou le fallback — jamais 'N/A' brut dans le prompt."""
        v = s.get(key)
        if v is None or v == "" or v == {} or v == []:
            return fallback
        if isinstance(v, dict):
            # ex. niveaux_avant = {"moyenne": 42}
            parts = [f"{k}: {val}" for k, val in v.items() if val is not None]
            return ", ".join(parts) if parts else fallback
        return str(v)

    def _build_user_prompt(
        self, session_data: dict[str, Any], contexte_rag: str = ""
    ) -> str:
        s = session_data
        v = self._val  # raccourci
        # Satisfaction : si non mesurée, on l'indique clairement au LLM
        nb_sat = int(s.get("nb_reponses_satisfaction") or 0)
        sat_intro = (
            f"({nb_sat} réponse(s) reçue(s))"
            if nb_sat > 0
            else "(aucune réponse reçue — section à omettre ou signaler comme non disponible)"
        )
        # Niveaux : si pas de scores, indiquer au LLM
        nb_scores = int(s.get("nb_scores_complets") or len(s.get("resultats_individuels") or []))
        niveaux_intro = (
            f"({nb_scores} participant(s) avec scores initiaux et finaux)"
            if nb_scores > 0
            else "(aucun score enregistré — section à omettre ou signaler comme non disponible)"
        )
        lines = [
            "INSTRUCTION : Si une donnée est absente ou marquée 'Non renseigné', rédige une phrase adaptée",
            "dans le rapport (ex. « Les évaluations de satisfaction n'ont pas été collectées lors de cette session. »).",
            "Ne répète jamais littéralement 'N/A', 'Non renseigné' ou 'Non mesurée' dans le texte final.",
            "",
            "Génère le rapport final pour la session suivante :",
            "",
            "=== SESSION ===",
            f"- Titre : {v(s, 'titre', 'Formation professionnelle')}",
            f"- Domaine : {v(s, 'domaine', 'Formation professionnelle')}",
            f"- Niveau cible : {v(s, 'niveau_cible', 'Tous niveaux')}",
            f"- Date début : {v(s, 'date_debut', 'Date non communiquée')}",
            f"- Date fin : {v(s, 'date_fin', 'Date non communiquée')}",
            f"- Lieu : {v(s, 'lieu', 'Lieu non renseigné')}",
            f"- Formateur : {v(s, 'formateur', 'Non renseigné')}",
            f"- Durée (jours) : {s.get('duree_jours') or 'Non calculée'}",
            f"- Public cible : {v(s, 'public_cible', 'Non précisé')}",
            "",
            "=== STATISTIQUES PARTICIPANTS ===",
            f"- Total inscrits : {s.get('total_inscrits', 0)}",
            f"- Total présents : {s.get('total_presents', 0)}",
            f"- Taux de présence moyen : {v(s, 'taux_presence', 'Non calculé (pointages manquants)')}",
            f"- Entreprises : {', '.join(s.get('entreprises') or []) or 'Non renseignées'}",
            "",
            f"=== NIVEAUX AVANT / APRÈS {niveaux_intro} ===",
            f"- Avant : {v(s, 'niveaux_avant', 'Données non disponibles')}",
            f"- Après : {v(s, 'niveaux_apres', 'Données non disponibles')}",
            f"- Progression : {v(s, 'progression', 'Non calculée')}",
            "",
            f"=== SATISFACTION {sat_intro} ===",
            f"- Note globale : {v(s, 'note_globale', 'Non mesurée')}",
            f"- Note formateur : {v(s, 'note_formateur', 'Non mesurée')}",
            f"- Note contenu : {v(s, 'note_contenu', 'Non mesurée')}",
            f"- Note supports : {v(s, 'note_supports', 'Non mesurée')}",
            f"- Note organisation : {v(s, 'note_organisation', 'Non mesurée')}",
            f"- Points forts : {', '.join(s.get('points_forts') or []) or 'Non renseignés'}",
            f"- Axes d'amélioration : {', '.join(s.get('axes_amelioration') or []) or 'Non renseignés'}",
            f"- Taux recommandation : {v(s, 'taux_recommandation', 'Non calculé')}",
            f"- Nombre de réponses : {nb_sat}",
        ]

        if s.get("objectifs"):
            lines += ["", "=== OBJECTIFS PÉDAGOGIQUES RENSEIGNÉS ===", *[f"- {item}" for item in s["objectifs"]]]
        if s.get("deroulement"):
            lines += ["", "=== SÉANCES RÉELLEMENT PLANIFIÉES ==="]
            lines.extend(
                f"- {item.get('date', 'Date non renseignée')} {item.get('horaires', '')} — {item.get('theme', '')} ({item.get('duree', '')})"
                for item in s["deroulement"][:40]
            )
        if s.get("resultats_individuels"):
            lines += ["", "=== SCORES INDIVIDUELS ENREGISTRÉS ==="]
            lines.extend(
                f"- {item.get('nom', 'Participant')} : initial {item.get('score_avant', 'non renseigné')}/100, final {item.get('score_apres', 'non renseigné')}/100"
                for item in s["resultats_individuels"][:60]
            )
        if s.get("observations_formateur"):
            lines += ["", "=== OBSERVATIONS DU FORMATEUR ===", str(s["observations_formateur"])]
        if s.get("methodes_pedagogiques"):
            lines += ["", "=== MÉTHODES RENSEIGNÉES ===", *[f"- {item}" for item in s["methodes_pedagogiques"]]]
        if s.get("outils"):
            lines += ["", "=== OUTILS / SUPPORTS RENSEIGNÉS ===", *[f"- {item}" for item in s["outils"]]]
        if s.get("recommandations_formateur"):
            lines += ["", "=== RECOMMANDATIONS DU FORMATEUR ===", *[f"- {item}" for item in s["recommandations_formateur"]]]

        if contexte_rag:
            lines += [
                "",
                "=== CONTENU DE LA FORMATION (extraits des supports indexés) ===",
                contexte_rag,
                "",
                "→ Utilise ces extraits pour personnaliser les recommandations "
                "en mentionnant des thèmes, modules ou compétences spécifiques "
                "abordés pendant la formation.",
            ]

        lines += ["", "Retourne UNIQUEMENT le JSON valide, sans texte autour."]
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def generate(
        self,
        session_data: dict[str, Any],
        temperature: float = 0.4,
        max_tokens: int = 3000,
    ) -> dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [ReportAgent] Génération du rapport final...")
        vlog(f"   📋 Session : {session_data.get('titre', 'N/A')}")
        vlog(f"   👥 Participants : {session_data.get('total_inscrits', 0)}")
        vlog("=" * 70)

        # ── ÉTAPE 0 : CONTEXTE RAG (même pattern qu'Agents 2 et 3) ──
        contexte_rag = ""
        try:
            from app.services.formations.knowledge_base_service import KnowledgeBaseService
            kb = KnowledgeBaseService()
            contexte_rag = await kb.get_formation_context(
                formation_titre=session_data.get("titre", ""),
                domaine=session_data.get("domaine", ""),
                formation_code=session_data.get("formation_code"),
            )
            if contexte_rag:
                vlog("   📚 [ReportAgent] Contexte RAG injecté dans le prompt")
        except Exception as exc:
            logger.warning(f"   ⚠️  [ReportAgent] RAG non disponible : {exc}")

        content = None
        source = "fallback_template"

        if self.llm:
            try:
                content = await self._generate_with_llm(
                    session_data, temperature, max_tokens,
                    contexte_rag=contexte_rag,
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
        content["titre_rapport"] = f"RAPPORT DE FORMATION — {session_data.get('titre') or 'Formation'}"
        presentation = dict(content.get("presentation") or {})
        try:
            date_range = self._format_date_range(
                str(session_data.get("date_debut") or ""),
                str(session_data.get("date_fin") or ""),
            )
        except (TypeError, ValueError):
            date_range = "Période non renseignée"
        presentation.update({
            "titre_formation": session_data.get("titre") or "Non renseigné",
            "dates": date_range,
            "lieu": session_data.get("lieu") or "Non renseigné",
            "formateur": session_data.get("formateur") or "Non renseigné",
            "public_cible": session_data.get("public_cible") or "Non renseigné",
            "duree": f"{session_data['duree_jours']} jour(s)" if session_data.get("duree_jours") else "Non renseignée",
            "nombre_participants": session_data.get("total_inscrits", 0),
        })
        content["presentation"] = presentation
        for key in (
            "client", "domaine", "objectifs", "deroulement", "methodes_pedagogiques",
            "outils", "participants", "resultats_individuels", "observations_formateur",
            "recommandations_formateur", "pointages_manquants", "statistiques_participants",
            "satisfaction", "analyse_niveaux",
        ):
            if key in session_data:
                content[key] = session_data[key]
        content.setdefault("participants", [])
        content.setdefault("resultats_individuels", [])
        content.setdefault("objectifs", [])
        content.setdefault("deroulement", [])

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
        session_data: dict[str, Any],
        temperature: float,
        max_tokens: int,
        contexte_rag: str = "",
    ) -> dict[str, Any]:
        response = await self.llm.generate(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(session_data, contexte_rag=contexte_rag),
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        raw = response["content"]
        finish = response["finish_reason"]

        if finish == "length":
            raise ValueError("Réponse LLM tronquée (finish_reason=length)")

        data = json.loads(raw)
        self._validate_llm_output(data)
        return data

    def _validate_llm_output(self, data: dict[str, Any]) -> None:
        required = [
            "titre_rapport", "resume_executif", "presentation",
            "statistiques_participants", "analyse_niveaux",
            "satisfaction", "recommandations", "conclusion",
            "lieu_emission", "date_emission",
        ]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")
        if not isinstance(data["recommandations"], list):
            raise ValueError("'recommandations' doit être une liste")

    # --------------------------------------------------------
    # FALLBACK TEMPLATE
    # --------------------------------------------------------
    def _generate_with_template(self, session_data: dict[str, Any]) -> dict[str, Any]:
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
                f"est de {s.get('taux_presence', 'Non calculé')}. "
                f"La satisfaction a été mesurée auprès de {s.get('nb_reponses_satisfaction', 0)} répondant(s)."
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
                "commentaire": (
                    f"{s.get('nb_scores_complets', 0)} participant(s) disposent des deux scores nécessaires."
                    if s.get('nb_scores_complets') else
                    "Aucun ensemble complet de scores initiaux et finaux n’est disponible pour une comparaison."
                ),
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
            "recommandations": s.get("recommandations_formateur", []),
            "conclusion": (
                f"La session « {s.get('titre', 'Formation')} » s'est déroulée du "
                f"{s.get('date_debut', 'date non renseignée')} au {s.get('date_fin', 'date non renseignée')}. "
                f"{s.get('total_inscrits', 0)} participant(s) étaient inscrits ; "
                f"{s.get('total_presents', 0)} ont été présents à au moins une séance. "
                "Les résultats d’apprentissage et retours de satisfaction sont détaillés "
                "uniquement lorsqu’ils sont disponibles."
            ),
            "lieu_emission": s.get("lieu_emission", "Antananarivo"),
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
