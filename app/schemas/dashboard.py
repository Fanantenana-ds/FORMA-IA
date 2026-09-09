from pydantic import BaseModel

class StatistiquesResponse(BaseModel):
    session_realisees: int
    participant_total: int
    taux_presence: float
    chiffre_affaire: float
    opportunite_total: int
    opportunite_analysees: int