# app/services/facturation/relance_generator_service.py
# ============================================================
# AGENT M7 — RelanceGeneratorService
# ============================================================
# Stratégie identique aux Agents 2/3 du M5 :
#   1. CALCUL DÉTERMINISTE (Python) : jours de retard, niveau
#      d'escalade (1/2/3).
#   2. RÉDACTION LLM (Groq) : texte de la relance, adapté au niveau.
#   3. FALLBACK : gabarit Python si le LLM est indisponible ou
#      renvoie une réponse inexploitable — jamais d'échec.
#
# ⚠️ Seuils d'escalade (SEUIL_NIVEAU_2 / SEUIL_NIVEAU_3) : HYPOTHÈSE,
#    le CDC ne fixe aucun barème précis. À valider avec la direction
#    avant mise en production réelle (envoi à de vrais clients).
# ============================================================

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from app.services.llm import LLMError, LLMNotAvailableError, get_llm_provider

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m7" / "relance.yaml"

# Seuils d'escalade en jours de retard — HYPOTHÈSE (non fournie par le CDC),
# choisie sur une logique de pratique professionnelle française/malgache :
# la "mise en demeure" a un poids quasi juridique (art. 1344 du Code civil) et
# ne doit pas être envoyée trop tôt, surtout avec des clients institutionnels
# (ministères...) aux cycles de paiement lents. Rythme retenu : ~2 semaines
# avant une relance ferme, ~1 mois et demi avant la mise en demeure.
SEUIL_NIVEAU_2 = 15   # jours de retard >= 15  -> niveau 2 (relance ferme)
SEUIL_NIVEAU_3 = 45   # jours de retard >= 45  -> niveau 3 (mise en demeure)

TONS = {
    1: "rappel courtois",
    2: "relance ferme",
    3: "mise en demeure formelle",
}


# ============================================================
# SERVICE
# ============================================================
class RelanceGeneratorService:
    """Agent M7 — Génère le texte d'une relance de facture (niveau 1/2/3)."""

    def __init__(self):
        try:
            self.llm = get_llm_provider()
        except LLMNotAvailableError:
            logger.warning("⚠️  Aucun provider LLM disponible → mode fallback uniquement.")
            self.llm = None

        self.prompt_config = self._load_prompt()
        logger.info(
            f"✅ RelanceGeneratorService initialisé "
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
            cfg.get("security", "") if isinstance(cfg.get("security"), str)
            else "\n".join(f"- {r}" for r in cfg.get("security", [])),
        ])

    def _build_user_prompt(self, facts: Dict[str, Any]) -> str:
        return "\n".join([
            "Rédige la relance pour les faits suivants (déjà calculés).",
            "",
            "=== FAITS (NE PAS RECALCULER) ===",
            f"- Numéro de facture : {facts['numero']}",
            f"- Client : {facts['client']}",
            f"- Montant restant dû : {facts['montant_restant_du']} {facts.get('devise', 'MGA')}",
            f"- Échéance dépassée le : {facts['date_echeance']}",
            f"- Jours de retard : {facts['jours_retard']}",
            f"- Niveau de relance : {facts['niveau']} ({TONS[facts['niveau']]})",
            "",
            "Retourne UNIQUEMENT le JSON (objet + texte).",
        ])

    # --------------------------------------------------------
    # CALCUL DÉTERMINISTE
    # --------------------------------------------------------
    @staticmethod
    def calculer_jours_retard(
        date_echeance: Optional[Union[str, date]],
        aujourdhui: Optional[date] = None,
    ) -> int:
        """0 si pas d'échéance ou échéance non dépassée."""
        if not date_echeance:
            return 0
        if isinstance(date_echeance, str):
            try:
                date_echeance = date.fromisoformat(date_echeance[:10])
            except ValueError:
                return 0
        aujourdhui = aujourdhui or date.today()
        return max(0, (aujourdhui - date_echeance).days)

    @staticmethod
    def calculer_niveau(jours_retard: int) -> Optional[int]:
        """None = pas de retard, aucune relance à générer."""
        if jours_retard <= 0:
            return None
        if jours_retard < SEUIL_NIVEAU_2:
            return 1
        if jours_retard < SEUIL_NIVEAU_3:
            return 2
        return 3

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def generate(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            facts: {numero, client, montant_restant_du, devise,
                    date_echeance, jours_retard, niveau} — déjà calculés
                    par l'orchestrateur.
        """
        start = datetime.now()
        enrichment = None
        source = "fallback_template"

        if self.llm:
            try:
                enrichment = await self._generate_with_llm(facts)
                source = "llm"
                logger.info("   ✅ Relance rédigée par LLM")
            except Exception as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule sur le gabarit."
                )

        if enrichment is None:
            enrichment = self._generate_with_template(facts)
            logger.info("   ✅ Relance rédigée par gabarit Python (fallback)")

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        return {
            "objet": enrichment["objet"],
            "texte": enrichment["texte"],
            "niveau": facts["niveau"],
            "ton": TONS[facts["niveau"]],
            "faits": facts,
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
            },
        }

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.llm.generate(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(facts),
            temperature=0.3,
            max_tokens=1200,
            json_mode=True,
        )

        raw = response["content"]
        finish = response["finish_reason"]
        if finish == "length":
            raise ValueError("Réponse LLM tronquée (finish_reason=length)")

        data = json.loads(raw)
        texte = str(data.get("texte") or data.get("corps") or data.get("body") or "").strip()
        if not texte:
            raise ValueError("Réponse LLM sans texte exploitable")

        objet = str(data.get("objet") or data.get("subject") or "").strip()
        if not objet:
            objet = self._objet_defaut(facts)

        return {"objet": objet, "texte": texte}

    # --------------------------------------------------------
    # FALLBACK GABARIT
    # --------------------------------------------------------
    @staticmethod
    def _objet_defaut(facts: Dict[str, Any]) -> str:
        return f"Relance facture {facts['numero']} — {TONS[facts['niveau']]}"

    def _generate_with_template(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        niveau = facts["niveau"]
        objet = self._objet_defaut(facts)

        en_tete = {
            1: "Nous nous permettons de vous rappeler",
            2: "Malgré un précédent rappel resté sans effet, nous constatons",
            3: (
                "Mise en demeure — Malgré nos relances précédentes restées "
                "infructueuses, nous constatons formellement"
            ),
        }[niveau]

        formule = {
            1: "Nous vous remercions de bien vouloir procéder au règlement dans les meilleurs délais.",
            2: "Nous vous demandons de bien vouloir régulariser cette situation sous 8 jours.",
            3: (
                "À défaut de règlement sous 8 jours à compter de la présente, nous nous "
                "réserverons le droit d'engager toute action utile au recouvrement de cette créance."
            ),
        }[niveau]

        texte = (
            f"{en_tete} que la facture {facts['numero']} (client : {facts['client']}), "
            f"d'un montant restant dû de {facts['montant_restant_du']} {facts.get('devise', 'MGA')}, "
            f"demeure impayée à ce jour (échéance dépassée le {facts['date_echeance']}, "
            f"soit {facts['jours_retard']} jour(s) de retard).\n\n"
            f"{formule}\n\n"
            f"Cordialement,\nALTIORA Prest"
        )
        return {"objet": objet, "texte": texte}
