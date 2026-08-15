# app/services/validation/validator.py
# ============================================================
# VALIDATION SERVICE
# ============================================================
# Ce service valide les données des opportunités et ajoute
# des flags pour les anomalies.
# ============================================================

from typing import Dict, List, Any
from datetime import datetime, timedelta
from app.models.opportunity import DomainEnum

class Validator:
    """Service de validation des données"""

    def __init__(self):
        self.valid_domains = [d.value for d in DomainEnum]

    def validate_schema(self, data: Dict) -> Dict:
        """
        Valide le schéma des données

        Vérifie :
        - Présence des champs obligatoires
        - Types corrects
        """
        required = ["title", "source", "domain", "summary", "score", "confidence"]
        for field in required:
            if field not in data or data[field] is None:
                data[f"{field}_missing"] = True

        # Validation des types
        if "score" in data and data["score"] is not None:
            if not isinstance(data["score"], (int, float)):
                data["score"] = 0
            data["score"] = max(0, min(100, data["score"]))

        if "confidence" in data and data["confidence"] is not None:
            if not isinstance(data["confidence"], (int, float)):
                data["confidence"] = 0.0
            data["confidence"] = max(0.0, min(1.0, data["confidence"]))

        return data

    def validate_business(self, data: Dict) -> Dict:
        """
        Valide les règles métier

        Vérifie :
        - Score entre 0 et 100
        - Domaine valide
        - Budget valide
        - Deadline > aujourd'hui
        """
        # Validation du domaine
        if "domain" in data and data["domain"]:
            if data["domain"].lower() not in self.valid_domains:
                data["domain"] = "autre"
                data["flags"] = data.get("flags", []) + ["invalid_domain"]

        # Validation de la deadline
        if "deadline" in data and data["deadline"]:
            try:
                deadline = datetime.fromisoformat(data["deadline"])
                if deadline < datetime.now():
                    data["flags"] = data.get("flags", []) + ["deadline_passed"]
            except ValueError:
                data["deadline"] = None
                data["flags"] = data.get("flags", []) + ["invalid_deadline"]

        return data

    def validate_confidence(self, data: Dict) -> Dict:
        """
        Valide le niveau de confiance

        - confidence ≥ 0.7 → VALIDATED
        - confidence ≥ 0.5 et < 0.7 → TO_REVIEW
        - confidence < 0.5 → REJECTED
        """
        confidence = data.get("confidence", 0.0)

        if confidence >= 0.7:
            data["status"] = "validated"
        elif confidence >= 0.5:
            data["status"] = "to_review"
            data["flags"] = data.get("flags", []) + ["low_confidence"]
        else:
            data["status"] = "rejected"
            data["flags"] = data.get("flags", []) + ["very_low_confidence"]

        return data

    def flag_data(self, data: Dict) -> Dict:
        """
        Ajoute des flags pour les anomalies
        """
        flags = []

        # Budget manquant
        if not data.get("budget") or data.get("budget") == "Non précisé":
            flags.append("budget_missing")

        # Score faible
        if data.get("score", 0) < 30:
            flags.append("low_score")

        # Deadline courte (< 15 jours)
        if data.get("deadline"):
            try:
                deadline = datetime.fromisoformat(data["deadline"])
                if (deadline - datetime.now()).days < 15:
                    flags.append("deadline_short")
            except (ValueError, TypeError):
                pass

        # Mettre à jour les flags
        if flags:
            existing = data.get("flags", [])
            data["flags"] = list(set(existing + flags))

        return data

    def validate_batch(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Valide un lot d'opportunités
        """
        validated = []
        for opp in opportunities:
            # Appliquer toutes les validations
            opp = self.validate_schema(opp)
            opp = self.validate_business(opp)
            opp = self.validate_confidence(opp)
            opp = self.flag_data(opp)
            validated.append(opp)
        return validated