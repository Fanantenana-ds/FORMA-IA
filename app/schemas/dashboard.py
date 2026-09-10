from pydantic import BaseModel

class StatistiquesResponse(BaseModel):
    session_realisees: int
    participant: int
    taux_presence: float
    opportunite_par_domaine: dict[str, int]
    chiffre_affaires_facture: float
    chiffre_affaires_encaisse: float