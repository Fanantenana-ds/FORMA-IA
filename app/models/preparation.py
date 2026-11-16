# app/models/preparation.py
# Alias de compatibilité : les tables projets / salles / edt_sessions / budgets_formation
# sont définies une seule fois dans app/models/projet.py (forme alignée sur la migration
# Alembic 84c43b7d26ae). Les redéclarer ici provoquait « Table already defined » à l'import.
from app.models.projet import BudgetFormation, Projet, Salle, StatutProjet
from app.models.projet import EdtSession as EDT

__all__ = ["EDT", "BudgetFormation", "Projet", "Salle", "StatutProjet"]
