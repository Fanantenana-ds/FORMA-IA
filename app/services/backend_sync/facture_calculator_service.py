# app/services/backend_sync/facture_calculator_service.py
# ============================================================
# CALCULS FACTURATION — Python pur (sans LLM)
# ============================================================
# Sert l'endpoint IA prévu par le CDC (Étape finale) :
#   POST /ia/facturation/calculer-montants
#   Payload  : session_id, type_client, nb_participants, tarif_unitaire
#   Réponse  : total_ht, tva, total_ttc, remise, net
#
# Conventions alignées sur la grille tarifaire M3
# (app/services/offres/grille_tarifaire_service.py) :
#   HT → TVA → TTC → remise calculée sur le TTC → net à payer
#   TVA par défaut 20 %, remise quantitative 5 % dès 15 participants.
#
# ⚠️ Le CDC ne définit aucune règle de prix propre au type de client
#    ("participant" / "entreprise") : il est validé et renvoyé tel quel,
#    sans effet sur le calcul. Une règle métier pourra être ajoutée
#    après validation de l'encadreur.
# ============================================================

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TYPES_CLIENT = ("participant", "entreprise")

DEFAULTS: Dict[str, Any] = {
    "devise": "MGA",
    "tva_taux": 20.0,
    "remise_seuil_participants": 15,
    "remise_pct_defaut": 5.0,
}


class FactureCalculatorService:
    """Calcule les montants d'une facture (règles Python, sans LLM)."""

    def calculer(
        self,
        type_client: str,
        nb_participants: int,
        tarif_unitaire: float,
        tva_taux: Optional[float] = None,
        remise_pct: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Args:
            type_client: "participant" ou "entreprise".
            nb_participants: nombre de participants facturés (≥ 1).
            tarif_unitaire: tarif HT par participant (> 0).
            tva_taux: taux de TVA en % (défaut 20).
            remise_pct: remise en % sur le TTC. None → règle automatique
                (5 % dès 15 participants), 0 → aucune remise.
            session_id: recopié dans la réponse (référence Backend).

        Returns:
            {
              "success": True, "session_id", "type_client", "devise",
              "nb_participants", "tarif_unitaire",
              "total_ht", "tva", "tva_taux", "total_ttc",
              "remise", "remise_pct", "net",
              "ht_apres_remise"   # à envoyer au Backend (FactureCreate.montant)
            }

        Raises:
            ValueError: paramètre invalide.
        """
        type_norm = str(type_client or "").strip().lower()
        if type_norm not in TYPES_CLIENT:
            raise ValueError(
                f"type_client invalide '{type_client}' "
                f"(attendu : {', '.join(TYPES_CLIENT)})"
            )
        if nb_participants < 1:
            raise ValueError("nb_participants doit être ≥ 1")
        if tarif_unitaire <= 0:
            raise ValueError("tarif_unitaire doit être > 0")

        taux = DEFAULTS["tva_taux"] if tva_taux is None else float(tva_taux)
        if taux < 0:
            raise ValueError("tva_taux doit être ≥ 0")

        if remise_pct is None:
            remise_pct = (
                DEFAULTS["remise_pct_defaut"]
                if nb_participants >= DEFAULTS["remise_seuil_participants"]
                else 0.0
            )
        remise_pct = float(remise_pct)
        if not 0 <= remise_pct <= 100:
            raise ValueError("remise_pct doit être entre 0 et 100")

        total_ht = round(tarif_unitaire * nb_participants, 2)
        tva = round(total_ht * taux / 100, 2)
        total_ttc = round(total_ht + tva, 2)
        remise = round(total_ttc * remise_pct / 100, 2)
        net = round(total_ttc - remise, 2)

        # Le Backend (Facture) stocke un montant HT et calcule lui-même
        # le TTC = HT × (1 + TVA). Pour que son TTC égale le net à payer,
        # on lui envoie le HT après remise.
        ht_apres_remise = round(net / (1 + taux / 100), 2)

        logger.info(
            "💰 [FactureCalculator] %d × %s = HT %s | net %s %s",
            nb_participants, tarif_unitaire, total_ht, net, DEFAULTS["devise"],
        )

        return {
            "success": True,
            "session_id": session_id,
            "type_client": type_norm,
            "devise": DEFAULTS["devise"],
            "nb_participants": nb_participants,
            "tarif_unitaire": tarif_unitaire,
            "total_ht": total_ht,
            "tva": tva,
            "tva_taux": taux,
            "total_ttc": total_ttc,
            "remise": remise,
            "remise_pct": remise_pct,
            "net": net,
            "ht_apres_remise": ht_apres_remise,
        }

    @staticmethod
    def calculer_reste_du(facture: Dict[str, Any]) -> float:
        """
        Montant restant dû d'une facture Backend (GET /factures/{id}) :
        montant_ttc − somme des paiements (jamais négatif).
        """
        ttc = float(facture.get("montant_ttc") or 0)
        paye = sum(
            float(p.get("montant") or 0)
            for p in (facture.get("paiements") or [])
        )
        return round(max(ttc - paye, 0.0), 2)
