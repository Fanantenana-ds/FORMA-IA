import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


GRILLE_DEFAUT: Dict[str, Any] = {
    "devise": "MGA",
    "tva_taux": 20.0,
    "administration_pourcentage": 12.0,
    "formateurs": {
        "senior": {
            "tarif_journalier": 500_000,
            "label": "Formateur senior",
        },
        "junior": {
            "tarif_journalier": 300_000,
            "label": "Formateur junior",
        },
    },
    "salles": {
        "standard": {
            "tarif_journalier": 200_000,
            "label": "Salle standard équipée",
        },
        "premium": {
            "tarif_journalier": 350_000,
            "label": "Salle premium",
        },
    },
    "supports": {
        "forfait_participant": 25_000,
    },
    "logistique": {
        "forfait": 300_000,
    },
    "remises": {
        "seuil_participants": 15,
        "pourcentage_defaut": 5.0,
    },
}




class GrilleTarifaireService:
    """
    Service de gestion de la grille tarifaire ALTIORA Prest.

    Fournit :
        - calculer_couts()      → Détail des coûts + récapitulatif
        - calculer_echeancier() → Échéancier 30/40/30
        - get_grille()          → Grille brute
    """

    def __init__(self, grille_path: Optional[str] = None):
        """
        Args:
            grille_path: Chemin vers un fichier JSON de grille tarifaire.
                Si None, utilise la grille par défaut.
        """
        self.grille = self._load_grille(grille_path)
        vlog("=" * 70)
        vlog("✅ [GrilleTarifaire] Service initialisé")
        vlog(f"   💰 Devise : {self.grille.get('devise')}")
        vlog(f"   💰 TVA : {self.grille.get('tva_taux')}%")
        vlog(f"   💰 Admin : {self.grille.get('administration_pourcentage')}%")
        vlog("=" * 70)



    def _load_grille(self, path: Optional[str]) -> Dict[str, Any]:
        """Charge la grille depuis un fichier ou utilise la défaut."""
        if path and Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    grille = json.load(f)
                vlog(f"✅ [GrilleTarifaire] Grille chargée depuis : {path}")
                return grille
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"⚠️  [GrilleTarifaire] Erreur chargement : {e}")
                logger.info("   → Utilisation de la grille par défaut")
        return GRILLE_DEFAUT.copy()


    def calculer_couts(
        self,
        nb_jours: int,
        nb_participants: int,
        type_formateur: str = "senior",
        type_salle: str = "standard",
        inclure_logistique: bool = True,
        inclure_administration: bool = True,
        tva_applicable: bool = True,
    ) -> Dict[str, Any]:
        """
        Calcule les coûts totaux à partir des paramètres.

        Args:
            nb_jours: Nombre de jours de formation.
            nb_participants: Nombre de participants.
            type_formateur: "senior" ou "junior".
            type_salle: "standard" ou "premium".
            inclure_logistique: Inclure les frais logistiques.
            inclure_administration: Inclure les frais administratifs.
            tva_applicable: Appliquer la TVA.

        Returns:
            {
                "details_couts": {...},
                "recapitulatif": {...},
            }
        """
        vlog("=" * 70)
        vlog("💰 [GrilleTarifaire] calculer_couts()")
        vlog(f"   📊 nb_jours={nb_jours}, nb_participants={nb_participants}")
        vlog(f"   📊 formateur={type_formateur}, salle={type_salle}")
        vlog(f"   📊 TVA={tva_applicable}")
        vlog("=" * 70)

        # ── Honoraires formateur ──
        formateur_info = self.grille["formateurs"].get(
            type_formateur, self.grille["formateurs"]["senior"]
        )
        tarif_form = formateur_info["tarif_journalier"]
        cout_formateur = tarif_form * nb_jours

        # ── Location salle ──
        salle_info = self.grille["salles"].get(
            type_salle, self.grille["salles"]["standard"]
        )
        tarif_salle = salle_info["tarif_journalier"]
        cout_salle = tarif_salle * nb_jours

        # ── Supports ──
        forfait_support = self.grille["supports"]["forfait_participant"]
        cout_supports = forfait_support * nb_participants

        # ── Logistique ──
        cout_logistique = (
            self.grille["logistique"]["forfait"] if inclure_logistique else 0
        )

        # ── Sous-total AVANT administration ──
        sous_total_avant_admin = (
            cout_formateur + cout_salle + cout_supports + cout_logistique
        )

        # ── Administration ──
        if inclure_administration:
            pct_admin = self.grille["administration_pourcentage"]
            cout_admin = int(sous_total_avant_admin * pct_admin / 100)
        else:
            pct_admin = 0
            cout_admin = 0

        # ── Sous-total HT ──
        sous_total_ht = sous_total_avant_admin + cout_admin

        # ── TVA ──
        tva_taux = self.grille["tva_taux"] if tva_applicable else 0
        tva_montant = int(sous_total_ht * tva_taux / 100)

        # ── Total TTC ──
        total_ttc = sous_total_ht + tva_montant

        # ── Remise quantitative ──
        remises: List[Dict[str, Any]] = []
        seuil = self.grille["remises"]["seuil_participants"]
        if nb_participants >= seuil:
            pct_remise = self.grille["remises"]["pourcentage_defaut"]
            montant_remise = int(total_ttc * pct_remise / 100)
            remises.append({
                "type": "quantitative",
                "description": f"Remise pour {nb_participants}+ participants",
                "pourcentage": pct_remise,
                "montant": montant_remise,
            })

        # ── Net à payer ──
        total_remises = sum(r["montant"] for r in remises)
        net_a_payer = total_ttc - total_remises

        vlog("=" * 70)
        vlog("💰 [GrilleTarifaire] Résultats")
        vlog(f"   💵 Formateur : {cout_formateur:,} MGA")
        vlog(f"   💵 Salle     : {cout_salle:,} MGA")
        vlog(f"   💵 Supports  : {cout_supports:,} MGA")
        vlog(f"   💵 Logistique: {cout_logistique:,} MGA")
        vlog(f"   💵 Admin     : {cout_admin:,} MGA")
        vlog(f"   ─────────────────────────────")
        vlog(f"   💰 Sous-total HT : {sous_total_ht:,} MGA")
        vlog(f"   💰 TVA ({tva_taux}%)  : {tva_montant:,} MGA")
        vlog(f"   💰 Total TTC    : {total_ttc:,} MGA")
        vlog(f"   💰 Remises      : {total_remises:,} MGA")
        vlog(f"   💰 NET À PAYER  : {net_a_payer:,} MGA")
        vlog("=" * 70)

        return {
            "details_couts": {
                "honoraires_formateur": {
                    "tarif_journalier": tarif_form,
                    "nb_jours": nb_jours,
                    "sous_total": cout_formateur,
                },
                "location_salle": {
                    "tarif_journalier": tarif_salle,
                    "nb_jours": nb_jours,
                    "sous_total": cout_salle,
                },
                "supports_pedagogiques": {
                    "forfait_participant": forfait_support,
                    "nb_participants": nb_participants,
                    "sous_total": cout_supports,
                },
                "logistique": {
                    "description": "Déplacements, repas, pauses",
                    "montant": cout_logistique,
                },
                "administration": {
                    "pourcentage": pct_admin,
                    "base": sous_total_avant_admin,
                    "montant": cout_admin,
                },
            },
            "recapitulatif": {
                "sous_total_ht": sous_total_ht,
                "tva": {
                    "taux": tva_taux,
                    "montant": tva_montant,
                    "applicable": tva_applicable,
                },
                "total_ttc": total_ttc,
                "remises": remises,
                "net_a_payer": net_a_payer,
            },
        }

    # =========================================================================
    # ÉCHÉANCIER
    # =========================================================================

    def calculer_echeancier(self, net_a_payer: int) -> List[Dict[str, Any]]:
        """
        Génère un échéancier standard (30/40/30).

        Args:
            net_a_payer: Montant net à payer.

        Returns:
            Liste de 3 échéances.
        """
        vlog(f"📅 [GrilleTarifaire] calculer_echeancier(net={net_a_payer:,})")

        return [
            {
                "ordre": 1,
                "libelle": "Acompte à la commande",
                "pourcentage": 30,
                "montant": int(net_a_payer * 0.30),
                "delai": "À la signature",
            },
            {
                "ordre": 2,
                "libelle": "Jalon intermédiaire",
                "pourcentage": 40,
                "montant": int(net_a_payer * 0.40),
                "delai": "J+15",
            },
            {
                "ordre": 3,
                "libelle": "Solde à la livraison",
                "pourcentage": 30,
                "montant": int(net_a_payer * 0.30),
                "delai": "À la fin de la formation",
            },
        ]

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def get_grille(self) -> Dict[str, Any]:
        """Retourne la grille tarifaire brute."""
        return self.grille.copy()

    def _build_reference(self, prefix: str, index: int = 1) -> str:
        """Génère une référence : ALT-OFF-{PREFIX}-YYYY-NNNN."""
        year = datetime.now().year
        return f"ALT-OFF-{prefix}-{year}-{index:04d}"