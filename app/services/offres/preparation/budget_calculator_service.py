import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CONFIG — Valeurs par défaut
# =============================================================================

DEFAULTS = {
    "devise": "MGA",
    "forfait_support_par_participant": 25_000,
    "forfait_logistique": 300_000,
    "pourcentage_administration": 12.0,
}


# =============================================================================
# SERVICE
# =============================================================================

class BudgetCalculatorService:
    """
    Service de calcul du budget prévisionnel d'une formation.

    Fournit :
        - calculer() : calcul complet avec détails
    """

    def __init__(self):
        vlog("=" * 70)
        vlog("✅ [BudgetCalculator] Service initialisé (Python pur)")
        vlog(f"   💰 Devise : {DEFAULTS['devise']}")
        vlog(f"   💰 Support/participant : {DEFAULTS['forfait_support_par_participant']:,} MGA")
        vlog(f"   💰 Logistique : {DEFAULTS['forfait_logistique']:,} MGA")
        vlog(f"   💰 Administration : {DEFAULTS['pourcentage_administration']}%")
        vlog("=" * 70)

    # =========================================================================
    # CALCUL PRINCIPAL
    # =========================================================================

    def calculer(
        self,
        formateur_info: Dict[str, Any],
        salle_info: Dict[str, Any],
        nb_jours: int,
        nb_participants: int,
        inclure_logistique: bool = True,
        inclure_administration: bool = True,
        forfait_support: Optional[int] = None,
        forfait_logistique: Optional[int] = None,
        pourcentage_administration: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calcule le budget prévisionnel d'une formation.

        Args:
            formateur_info: {nom, tarif_journalier}
            salle_info: {nom, tarif_journalier}
            nb_jours: Nombre de jours de formation
            nb_participants: Nombre de participants
            inclure_logistique: Ajouter les frais logistiques
            inclure_administration: Ajouter les frais administratifs
            forfait_support: Override du forfait par participant
            forfait_logistique: Override du forfait logistique
            pourcentage_administration: Override du % admin

        Returns:
            {
                "devise": "MGA",
                "cout_formateur": int,
                "cout_salle": int,
                "cout_supports": int,
                "cout_logistique": int,
                "cout_administration": int,
                "cout_total": int,
                "details": [...]
            }
        """
        vlog("=" * 70)
        vlog("💰 [BudgetCalculator] calculer()")
        vlog(f"   📋 Formateur : {formateur_info.get('nom', 'N/A')}")
        vlog(f"   🏛️  Salle     : {salle_info.get('nom', 'N/A')}")
        vlog(f"   📅 Jours     : {nb_jours}")
        vlog(f"   👥 Participants : {nb_participants}")
        vlog("=" * 70)

        # ── Validation ──
        if nb_jours < 1:
            raise ValueError("❌ nb_jours doit être ≥ 1")
        if nb_participants < 1:
            raise ValueError("❌ nb_participants doit être ≥ 1")

        # ── Récupération des tarifs ──
        tarif_formateur = int(formateur_info.get("tarif_journalier", 0))
        tarif_salle = int(salle_info.get("tarif_journalier", 0))

        if tarif_formateur <= 0:
            raise ValueError("❌ tarif_journalier formateur manquant ou nul")
        if tarif_salle <= 0:
            raise ValueError("❌ tarif_journalier salle manquant ou nul")

        # ── ① Honoraires formateur ──
        cout_formateur = tarif_formateur * nb_jours
        vlog(f"   💵 Formateur  : {tarif_formateur:,} × {nb_jours} = {cout_formateur:,} MGA")

        # ── ② Location salle ──
        cout_salle = tarif_salle * nb_jours
        vlog(f"   💵 Salle      : {tarif_salle:,} × {nb_jours} = {cout_salle:,} MGA")

        # ── ③ Supports pédagogiques ──
        f_support = forfait_support or DEFAULTS["forfait_support_par_participant"]
        cout_supports = f_support * nb_participants
        vlog(f"   💵 Supports   : {f_support:,} × {nb_participants} = {cout_supports:,} MGA")

        # ── ④ Logistique ──
        if inclure_logistique:
            f_logistique = forfait_logistique or DEFAULTS["forfait_logistique"]
            cout_logistique = f_logistique
        else:
            cout_logistique = 0
        vlog(f"   💵 Logistique : {cout_logistique:,} MGA")

        # ── ⑤ Sous-total AVANT admin ──
        sous_total = (
            cout_formateur + cout_salle + cout_supports + cout_logistique
        )

        # ── ⑥ Administration ──
        if inclure_administration:
            pct_admin = (
                pourcentage_administration
                if pourcentage_administration is not None
                else DEFAULTS["pourcentage_administration"]
            )
            cout_admin = int(sous_total * pct_admin / 100)
        else:
            pct_admin = 0
            cout_admin = 0
        vlog(f"   💵 Admin      : {pct_admin}% × {sous_total:,} = {cout_admin:,} MGA")

        # ── ⑦ Total ──
        cout_total = sous_total + cout_admin

        vlog("   ─────────────────────────────────────")
        vlog(f"   💰 TOTAL      : {cout_total:,} MGA")
        vlog("=" * 70)

        # ── Détails ──
        details = [
            {
                "libelle": "Honoraires formateur",
                "base": tarif_formateur,
                "quantite": nb_jours,
                "montant": cout_formateur,
                "description": f"{formateur_info.get('nom', 'N/A')} — {nb_jours} jour(s)",
            },
            {
                "libelle": "Location salle",
                "base": tarif_salle,
                "quantite": nb_jours,
                "montant": cout_salle,
                "description": f"{salle_info.get('nom', 'N/A')} — {nb_jours} jour(s)",
            },
            {
                "libelle": "Supports pédagogiques",
                "base": f_support,
                "quantite": nb_participants,
                "montant": cout_supports,
                "description": f"{nb_participants} participant(s)",
            },
        ]
        if inclure_logistique:
            details.append({
                "libelle": "Logistique",
                "base": cout_logistique,
                "quantite": 1,
                "montant": cout_logistique,
                "description": "Déplacements, repas, pauses",
            })
        if inclure_administration:
            details.append({
                "libelle": "Administration",
                "base": pct_admin,
                "quantite": 1,
                "montant": cout_admin,
                "description": f"{pct_admin}% du sous-total",
            })

        return {
            "devise": DEFAULTS["devise"],
            "cout_formateur": cout_formateur,
            "cout_salle": cout_salle,
            "cout_supports": cout_supports,
            "cout_logistique": cout_logistique,
            "cout_administration": cout_admin,
            "cout_total": cout_total,
            "details": details,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "methode": "python_deterministic",
            },
        }