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
from .grille_tarifaire_service import GrilleTarifaireService

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CONFIG
# =============================================================================
PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "m3" / "offre_financiere.yaml"
)

AGENT_ID = "agent_m3_financiere"


# =============================================================================
# SERVICE
# =============================================================================

class OffreFinanciereGeneratorService:
    """
    Agent M3-2 — Génère la trame financière d'une offre.

    Input  : offre technique + options + grille tarifaire
    Output : JSON OffreFinanciereResponse + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        self.grille_service = GrilleTarifaireService()
        vlog("✅ [OffreFinanciereAgent] Service initialisé")

    # =========================================================================
    # PROMPT
    # =========================================================================

    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")

        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")

        vlog(f"✅ [OffreFinanciereAgent] Prompt chargé : {PROMPT_PATH.name}")
        return config

    def _build_system_prompt(self) -> str:
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
        offre_technique: Dict[str, Any],
        options: Dict[str, Any],
        calculs: Dict[str, Any],
    ) -> str:
        """Construit le user prompt avec l'offre technique + calculs."""
        d = calculs["details_couts"]
        r = calculs["recapitulatif"]

        lines = [
            "Génère une offre financière basée sur les données suivantes :",
            "",
            "=== OFFRE TECHNIQUE ===",
            f"- Titre : {offre_technique.get('titre_offre', 'N/A')}",
            f"- Référence : {offre_technique.get('reference', 'N/A')}",
            f"- Durée totale : {offre_technique.get('programme', {}).get('duree_totale', 'N/A')}",
            "",
            "=== OPTIONS ===",
            f"- Type formateur : {options.get('type_formateur', 'senior')}",
            f"- Type salle : {options.get('type_salle', 'standard')}",
            f"- Nombre de participants : {options.get('nb_participants', 20)}",
            f"- TVA applicable : {options.get('tva_applicable', True)}",
            "",
            "=== CALCULS (déjà effectués par GrilleTarifaireService) ===",
            f"- Honoraires formateur : {d['honoraires_formateur']['sous_total']:,} MGA",
            f"- Location salle : {d['location_salle']['sous_total']:,} MGA",
            f"- Supports pédagogiques : {d['supports_pedagogiques']['sous_total']:,} MGA",
            f"- Logistique : {d['logistique']['montant']:,} MGA",
            f"- Administration : {d['administration']['montant']:,} MGA",
            f"- **Sous-total HT : {r['sous_total_ht']:,} MGA**",
            f"- TVA ({r['tva']['taux']}%) : {r['tva']['montant']:,} MGA",
            f"- **Total TTC : {r['total_ttc']:,} MGA**",
            f"- Remises : {sum(rm['montant'] for rm in r['remises']):,} MGA",
            f"- **Net à payer : {r['net_a_payer']:,} MGA**",
            "",
            "⚠️  IMPORTANT : Utilise CES chiffres exacts pour le récapitulatif.",
            "    Ne recalcule PAS — les calculs sont déjà validés.",
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        feedback = str(options.get("feedback") or "").strip()
        if feedback:
            # Régénération après rejet HITL (les montants restent ceux du calcul)
            lines[-1:-1] = [
                "=== CORRECTIONS DEMANDÉES PAR LE RÉVISEUR HUMAIN ===",
                feedback,
                "Tiens compte de ces corrections pour le TEXTE de l'offre ; "
                "les montants restent ceux ci-dessus.",
                "",
            ]
        return "\n".join(lines)

    # =========================================================================
    # GÉNÉRATION
    # =========================================================================

    async def generate(
        self,
        offre_technique: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: int = 6000,
    ) -> Dict[str, Any]:
        """
        Génère la trame financière d'une offre.

        Args:
            offre_technique: Offre technique (issue du M3-1).
            options: Options (type_formateur, type_salle, etc.).

        Returns:
            Dict avec la trame financière + HITL review_id.
        """
        start = datetime.now()
        options = options or {}

        # Valeurs par défaut
        nb_jours = offre_technique.get("programme", {}).get("duree_totale", "2 jours")
        try:
            nb_jours_int = int(str(nb_jours).split()[0])
        except (ValueError, IndexError):
            nb_jours_int = 2

        nb_participants = options.get("nb_participants", 20)
        type_formateur = options.get("type_formateur", "senior")
        type_salle = options.get("type_salle", "standard")
        tva_applicable = options.get("tva_applicable", True)
        inclure_logistique = options.get("inclure_logistique", True)
        inclure_administration = options.get("inclure_administration", True)

        vlog("=" * 70)
        vlog("🚀 [OffreFinanciereAgent] Génération de l'offre financière...")
        vlog(f"   📋 Offre : {offre_technique.get('titre_offre', 'N/A')}")
        vlog(f"   💰 nb_jours={nb_jours_int}, participants={nb_participants}")
        vlog(f"   💰 formateur={type_formateur}, salle={type_salle}")
        vlog("=" * 70)

        # ── ÉTAPE 1 : CALCUL DÉTERMINISTE 
        calculs = self.grille_service.calculer_couts(
            nb_jours=nb_jours_int,
            nb_participants=nb_participants,
            type_formateur=type_formateur,
            type_salle=type_salle,
            inclure_logistique=inclure_logistique,
            inclure_administration=inclure_administration,
            tva_applicable=tva_applicable,
        )

        echeancier = self.grille_service.calculer_echeancier(
            calculs["recapitulatif"]["net_a_payer"]
        )

        # ── ÉTAPE 2 : ENRICHISSEMENT LLM (optionnel)
        content = None
        source = "fallback_template"

        try:
            llm = get_llm_provider()
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(offre_technique, options, calculs)

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
                raise ValueError("Réponse LLM tronquée")

            cleaned = self._repair_json(raw)
            data = json.loads(cleaned)
            data = self._normalize_output(data)

            # 🔒 SÉCURITÉ : Forcer les montants calculés (le LLM ne doit pas inventer)
            data["details_couts"] = calculs["details_couts"]
            data["recapitulatif"] = calculs["recapitulatif"]
            data["echeancier"] = echeancier

            content = data
            source = "llm"
            vlog("   ✅ Contenu enrichi par LLM")

        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                f"Bascule sur le template Python."
            )
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        # ── ÉTAPE 3 : FALLBACK ──
        if content is None:
            content = self._generate_with_template(
                offre_technique, options, calculs, echeancier
            )
            vlog("   ✅ Contenu généré par template Python (fallback)")

        # ── ÉTAPE 4 : MÉTADONNÉES + HITL ──
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
        feedback = str(options.get("feedback") or "").strip()
        if feedback:
            # Le gabarit Python de secours ne sait pas exploiter le feedback
            result["metadata"]["feedback"] = feedback
            result["metadata"]["feedback_applied"] = source == "llm"

        review_id = create_review(
            agent_id=AGENT_ID,
            data=result,
            summary=(
                f"Offre financière — {result.get('titre_offre', 'N/A')[:80]} "
                f"— Net à payer : {calculs['recapitulatif']['net_a_payer']:,} MGA "
                f"— à valider avant envoi client"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog("=" * 70)
        vlog(
            f"✅ [OffreFinanciereAgent] Terminé en {elapsed}s "
            f"(source={source}, review={review_id})"
        )
        vlog("=" * 70)

        return result

    # =========================================================================
    # REPAIR + NORMALIZE
    # =========================================================================

    def _repair_json(self, raw: str) -> str:
        if not raw:
            return raw
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

    def _normalize_output(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, list):
            dict_items = [item for item in data if isinstance(item, dict)]
            if not dict_items:
                raise ValueError(f"Liste sans objet : {str(data)[:300]}")
            data = dict_items[0] if len(dict_items) == 1 else {
                k: v for item in dict_items for k, v in item.items()
            }
        if not isinstance(data, dict):
            raise ValueError(f"Attendu dict, reçu {type(data).__name__}")
        return data

    # =========================================================================
    # FALLBACK TEMPLATE
    # =========================================================================

    def _generate_with_template(
        self,
        offre_technique: Dict[str, Any],
        options: Dict[str, Any],
        calculs: Dict[str, Any],
        echeancier: list,
    ) -> Dict[str, Any]:
        """Template Python (fallback) — trame financière standard."""
        year = datetime.now().year
        titre = offre_technique.get("titre_offre", "Formation professionnelle")

        return {
            "titre_offre": f"Offre financière — {titre.replace('Offre technique — ', '')}",
            "reference": f"ALT-OFF-FIN-{year}-0001",
            "date_emission": datetime.now().strftime("%Y-%m-%d"),
            "devise": "MGA",
            "details_couts": calculs["details_couts"],
            "recapitulatif": calculs["recapitulatif"],
            "echeancier": echeancier,
            "conditions_financieres": {
                "validite_offre": "60 jours",
                "modalites_paiement": "Virement bancaire",
                "penalites_retard": "1% par mois de retard",
                "monnaie": "MGA",
                "autres": ["Devis payable à Antananarivo"],
            },
            "notes": [
                "TVA applicable selon la réglementation malgache.",
                "Les tarifs sont valables pour la durée indiquée.",
            ],
            "conclusion": (
                "Nous restons à votre disposition pour toute clarification."
            ),
        }