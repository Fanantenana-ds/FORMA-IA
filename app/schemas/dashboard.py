from typing import Dict, Optional

from pydantic import BaseModel


class StatistiquesResponse(BaseModel):
    # ---- Formations ----
    session_realisees: int
    participant: int
    taux_presence: float

    # ---- Opportunités ----
    opportunite_total: int
    opportunite_par_domaine: dict[str, int]
    opportunite_par_statut: dict[str, int]

    # ---- Documents générés ----
    tdr_generes: int
    offres_generees: int
    attestations_generees: int

    # ---- Facturation ----
    chiffre_affaires_facture: float
    chiffre_affaires_encaisse: float
    factures_en_retard: int
    montant_impaye: float
    relances_envoyees: int
