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


# =============================================================================
# CONFIG
# =============================================================================
PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "m3" / "offre_technique.yaml"
)

AGENT_ID = "agent_m3_technique"


# =============================================================================
# SERVICE
# =============================================================================

class OffreTechniqueGeneratorService:
    """
    Agent M3-1 — Génère la trame technique d'une offre de formation.

    Input  : TDR + session_info
    Output : JSON OffreTechniqueResponse + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [OffreTechniqueAgent] Service initialisé")

    # =========================================================================
    # PROMPT
    # =========================================================================

    def _load_prompt(self) -> Dict[str, Any]:
        """Charge le prompt RTFCE depuis le YAML."""
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")

        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")

        vlog(f"✅ [OffreTechniqueAgent] Prompt chargé : {PROMPT_PATH.name}")
        return config

    def _build_system_prompt(self) -> str:
        """Construit le system prompt à partir du YAML RTFCE."""
        cfg = self.prompt_config
        return "\n".join([
            "=== RÔLE ===",
            cfg.get("role", "").strip(),
            "",
            "=== TÂCHE ===",
            cfg.get("tache", "").strip(),
            "",
            "=== FORMAT ===",
            cfg.get("format", "").strip(),
            "",
            "=== CONTEXTE ===",
            cfg.get("contexte", "").strip(),
            "",
            "=== RÈGLES STRICTES ===",
            cfg.get("regles", "") if isinstance(cfg.get("regles"), str)
            else "\n".join(f"- {r}" for r in cfg.get("regles", [])),
        ])

    def _build_user_prompt(
        self,
        tdr_data: Dict[str, Any],
        session_info: Dict[str, Any],
        feedback: Optional[str] = None,
    ) -> str:
        """Construit le user prompt avec les données du TDR + session."""
        lines = [
            "Génère une offre technique pour la formation suivante :",
            "",
            "=== TDR (TERMES DE RÉFÉRENCE) ===",
            f"- Titre : {tdr_data.get('titre', 'N/A')}",
            f"- Domaine : {tdr_data.get('domaine', 'N/A')}",
            f"- Objectifs : {tdr_data.get('objectifs', 'N/A')}",
            f"- Public cible : {tdr_data.get('public_cible', 'N/A')}",
            f"- Durée (jours) : {tdr_data.get('duree_jours', 2)}",
            f"- Lieu : {tdr_data.get('lieu', 'Antananarivo')}",
            "",
            "=== SESSION ===",
            f"- Client : {session_info.get('client', 'N/A')}",
            f"- Formateur : {session_info.get('formateur', 'N/A')}",
            f"- Nombre de participants : {session_info.get('nb_participants', 20)}",
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        if feedback and feedback.strip():
            # Régénération après rejet HITL : le réviseur humain a demandé
            # des corrections (bloc placé avant la consigne de format).
            lines[-1:-1] = [
                "=== CORRECTIONS DEMANDÉES PAR LE RÉVISEUR HUMAIN ===",
                feedback.strip(),
                "Tiens compte de ces corrections dans cette nouvelle version.",
                "",
            ]
        return "\n".join(lines)

    # =========================================================================
    # GÉNÉRATION
    # =========================================================================

    async def generate(
        self,
        tdr_data: Dict[str, Any],
        session_info: Dict[str, Any],
        temperature: float = 0.4,
        max_tokens: int = 8000,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Génère la trame technique d'une offre.

        Args:
            tdr_data: Données du TDR (issu du M2).
            session_info: Informations de session.
            feedback: Corrections du réviseur humain (régénération après
                rejet HITL). Pris en compte uniquement par le LLM.

        Returns:
            Dict avec la trame technique + HITL review_id.
        """
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [OffreTechniqueAgent] Génération de l'offre technique...")
        vlog(f"   📋 TDR : {tdr_data.get('titre', 'N/A')}")
        vlog(f"   🏢 Client : {session_info.get('client', 'N/A')}")
        vlog("=" * 70)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(tdr_data, session_info, feedback)

        content = None
        source = "fallback_template"

        # ── ÉTAPE 1 : ESSAI LLM ──
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
            finish = response["finish_reason"]

            vlog(f"✅ Réponse LLM ({len(raw)} chars, finish={finish})")

            if finish == "length":
                raise ValueError("Réponse LLM tronquée (finish_reason=length)")

            # Réparer + parser le JSON
            cleaned = self._repair_json(raw)
            data = json.loads(cleaned)
            data = self._normalize_output(data)

            # Valider + compléter
            self._validate_minimal(data)
            content = data
            source = "llm"
            vlog("   ✅ Contenu généré par LLM")

        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                f"Bascule sur le template Python."
            )
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        # ── ÉTAPE 2 : FALLBACK ──
        if content is None:
            content = self._generate_with_template(tdr_data, session_info)
            vlog("   ✅ Contenu généré par template Python (fallback)")

        # ── ÉTAPE 3 : MÉTADONNÉES + HITL ──
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
        if feedback and feedback.strip():
            # Le gabarit Python de secours ne sait pas exploiter le feedback
            result["metadata"]["feedback"] = feedback.strip()
            result["metadata"]["feedback_applied"] = source == "llm"

        # Créer le review HITL
        review_id = create_review(
            agent_id=AGENT_ID,
            data=result,
            summary=(
                f"Offre technique — {result.get('titre_offre', 'N/A')[:80]} "
                f"— à valider avant envoi client"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog("=" * 70)
        vlog(
            f"✅ [OffreTechniqueAgent] Terminé en {elapsed}s "
            f"(source={source}, review={review_id})"
        )
        vlog("=" * 70)

        return result

    # =========================================================================
    # REPAIR JSON
    # =========================================================================

    def _repair_json(self, raw: str) -> str:
        """Corrige les erreurs JSON courantes du LLM."""
        if not raw:
            return raw

        # 1. Enlever markdown ```json ... ```
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw)

        # 2. Escapes invalides
        raw = raw.replace("\\'", "'")
        raw = raw.replace("\\/", "/")

        # 3. Extraire le premier { ... }
        start = raw.find("{")
        if start > 0:
            raw = raw[start:]

        end = raw.rfind("}")
        if end > 0:
            raw = raw[:end + 1]

        return raw

    # =========================================================================
    # NORMALISATION
    # =========================================================================

    def _normalize_output(self, data: Any) -> Dict[str, Any]:
        """Normalise la structure LLM (liste → dict)."""
        if isinstance(data, list):
            dict_items = [item for item in data if isinstance(item, dict)]
            if not dict_items:
                raise ValueError(f"Liste sans objet : {str(data)[:300]}")
            if len(dict_items) == 1:
                data = dict_items[0]
            else:
                merged = {}
                for item in dict_items:
                    merged.update(item)
                data = merged

        if not isinstance(data, dict):
            raise ValueError(f"Attendu dict, reçu {type(data).__name__}")

        return data

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        """Vérifie la présence des clés minimales."""
        required = [
            "titre_offre", "reference", "date_emission",
            "presentation_structure", "comprehension_besoin",
            "approche_methodologique", "programme",
            "ressources", "planning", "garanties",
            "points_forts", "conclusion",
        ]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    # =========================================================================
    # FALLBACK TEMPLATE
    # =========================================================================

    def _generate_with_template(
        self,
        tdr_data: Dict[str, Any],
        session_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Template Python (fallback) — trame technique standard."""
        year = datetime.now().year
        titre = tdr_data.get("titre", "Formation professionnelle")
        domaine = tdr_data.get("domaine", "Formation")
        duree_jours = tdr_data.get("duree_jours", 2)
        nb_participants = session_info.get("nb_participants", 20)

        return {
            "titre_offre": f"Offre technique — {titre}",
            "reference": f"ALT-OFF-TECH-{year}-0001",
            "date_emission": datetime.now().strftime("%Y-%m-%d"),
            "presentation_structure": {
                "nom": "ALTIORA Prest",
                "description": (
                    "ALTIORA Prest est une startup technologique malgache "
                    "spécialisée dans l'intelligence artificielle et la "
                    "formation professionnelle."
                ),
                "domaines_expertise": [
                    "Intelligence Artificielle",
                    "Data Science",
                    "Formation professionnelle",
                ],
            },
            "comprehension_besoin": {
                "objectifs_client": [
                    f"Former {nb_participants} participants en {domaine}",
                    "Développer les compétences techniques",
                ],
                "enjeux": [
                    "Montée en compétences rapide",
                    "Alignement avec les standards professionnels",
                ],
                "public_cible": tdr_data.get("public_cible", "Professionnels"),
                "contraintes": [
                    f"Durée limitée à {duree_jours} jours",
                    "Niveau hétérogène",
                ],
            },
            "approche_methodologique": {
                "pedagogie": "Pédagogie active par projets",
                "modalites": "Présentiel avec supports numériques",
                "outils_supports": [
                    "Slides interactifs",
                    "Exercices pratiques",
                    "Cas d'usage",
                ],
                "innovations": [
                    "Apprentissage par projet",
                    "Évaluation continue",
                ],
            },
            "architecture_technique": {
                "stack": {
                    "frontend": "N/A",
                    "backend": "Python 3.11+",
                    "base_donnees": "PostgreSQL",
                    "ia_ml": "Groq API, LangChain",
                },
                "composants": [
                    {"nom": "LLM Provider", "role": "Génération de contenu"},
                ],
                "securite": ["Authentification JWT", "HTTPS"],
                "conformite": ["RGPD"],
            },
            "programme": {
                "duree_totale": f"{duree_jours} jours",
                "modules": [
                    {
                        "numero": 1,
                        "titre": f"Introduction à {domaine}",
                        "duree": "3h",
                        "objectifs": ["Comprendre les concepts clés"],
                        "contenu": ["Notions de base", "Applications"],
                        "methode": "Cours + démo",
                    },
                    {
                        "numero": 2,
                        "titre": "Approfondissement",
                        "duree": "3h",
                        "objectifs": ["Maîtriser les cas avancés"],
                        "contenu": ["Techniques avancées", "Cas pratiques"],
                        "methode": "Atelier pratique",
                    },
                ],
            },
            "ressources": {
                "formateur": {
                    "nom": session_info.get("formateur", "M. RANAIVOSOA S."),
                    "profil": f"Expert en {domaine}",
                    "expertise": [domaine, "Pédagogie active"],
                },
                "support_technique": "Assistant technique",
                "materiel": ["Salle équipée", f"{nb_participants} postes"],
            },
            "planning": {
                "dates_proposees": [],
                "jalons": [],
                "livrables": ["Supports PDF", "Attestations", "Rapport final"],
            },
            "garanties": {
                "qualite": "Satisfaction garantie ≥ 85%",
                "suivi": "Suivi post-formation de 30 jours",
                "confidentialite": "Engagement de confidentialité",
            },
            "annexes": {
                "cv_formateur": "Disponible sur demande",
                "references": [],
            },
            "points_forts": [
                "Formateur expert",
                "Approche pratique",
                "Supports modernes",
            ],
            "conclusion": (
                f"ALTIORA Prest s'engage à fournir une formation de qualité "
                f"adaptée aux besoins spécifiques du client."
            ),
        }