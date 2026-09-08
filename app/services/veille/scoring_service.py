# # app/services/veille/scoring_service.py
# # ============================================================
# # SERVICE SCORING — décision déterministe Python
# # ============================================================
# # Le score final (0-100) est calculé en Python, pas par le LLM.
# # scoring.yaml reste chargé comme référence documentaire.
# # ============================================================

# import logging
# import re
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Dict, Optional

# import yaml

# logger = logging.getLogger(__name__)

# BASE_DIR = Path(__file__).resolve().parents[3]
# SCORING_YAML_PATH = BASE_DIR / "app" / "prompts" / "m1" / "scoring.yaml"


# def _load_yaml_reference(path: Path) -> Dict[str, Any]:
#     if not path.exists():
#         logger.warning("⚠️ Prompt de référence absent : %s", path)
#         return {}

#     try:
#         with open(path, "r", encoding="utf-8") as file:
#             data = yaml.safe_load(file)
#     except yaml.YAMLError as exc:
#         logger.error("❌ YAML invalide : %s", path)
#         raise ValueError(f"YAML invalide : {path}") from exc

#     return data if isinstance(data, dict) else {}


# def _score_domain(domain: str) -> int:
#     scores = {
#         "ia": 30, "data": 25, "devops": 20,
#         "developpement": 15, "bureautique": 5, "autre": 0,
#     }
#     return scores.get(str(domain).lower(), 0)


# def _score_budget(budget: Any) -> int:
#     if not budget:
#         return 0

#     text = str(budget).strip()
#     if text.lower() in {
#         "non précisé", "non precise", "n/a", "na",
#         "null", "unknown", "non disponible",
#     }:
#         return 0

#     try:
#         match = re.search(r"\d+(?:[\s.,]\d+)*", text)
#         if not match:
#             return 0

#         number = re.sub(r"[\s.,]", "", match.group(0))
#         value = int(number)

#         if value > 100_000_000:
#             return 20
#         if value >= 50_000_000:
#             return 15
#         if value >= 20_000_000:
#             return 10
#         if value >= 5_000_000:
#             return 5
#         return 2

#     except (TypeError, ValueError):
#         return 0


# def _score_organizer(organizer: Any) -> int:
#     if not organizer:
#         return 0

#     text = str(organizer).lower()

#     if any(w in text for w in ["ministère", "ministry", "gouvernement", "government"]):
#         return 15
#     if any(w in text for w in ["banque", "bank", "télécom", "telecom", "assurance", "insurance"]):
#         return 12
#     if any(w in text for w in ["pme", "sarl", "sas", "startup"]):
#         return 8
#     if any(w in text for w in ["ong", "association", "coopérative"]):
#         return 5

#     return 2


# def _score_deadline(deadline_str: Optional[str], current_date: datetime) -> int:
#     if not deadline_str:
#         return 0

#     try:
#         deadline = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
#         if deadline.tzinfo is not None:
#             deadline = deadline.replace(tzinfo=None)

#         if deadline < current_date:
#             return -10

#         delta_days = (deadline - current_date).days

#         if delta_days < 7:
#             return 10
#         if delta_days < 15:
#             return 8
#         if delta_days < 30:
#             return 5
#         if delta_days < 60:
#             return 3
#         return 1

#     except (TypeError, ValueError):
#         return 0


# def _score_alignment(title: str, summary: str) -> int:
#     text = f"{title} {summary or ''}".lower()

#     if any(t in text for t in ["formation ia", "formation claude", "prompt engineering", "agent ia"]):
#         return 15
#     if any(t in text for t in ["conseil ia", "digitalisation", "transformation digitale"]):
#         return 12
#     if any(t in text for t in ["agent ia", "api", "intégration"]):
#         return 12
#     if any(t in text for t in ["saas", "plateforme"]):
#         return 10
#     if any(t in text for t in ["n8n", "make", "automatisation"]):
#         return 10
#     if any(t in text for t in ["devops", "cloud", "kubernetes", "docker"]):
#         return 8
#     if any(t in text for t in ["data science", "python", "sql"]):
#         return 8
#     if any(t in text for t in ["développement", "developpement", "development", "web", "mobile"]):
#         return 5
#     if any(t in text for t in ["excel", "word", "bureautique"]):
#         return 3

#     return 0


# def _score_bonus(title: str, summary: str, url: str) -> int:
#     text = f"{title} {summary or ''}".lower()
#     bonus = 0

#     if len(summary or "") > 100:
#         bonus += 5

#     if any(t in text for t in [
#         "data scientist", "ingénieur", "développeur", "developpeur",
#         "developer", "consultant", "formateur",
#     ]):
#         bonus += 5

#     if "madagascar" in text:
#         bonus += 3

#     if "antananarivo" in text or "tana" in text:
#         bonus += 2

#     return min(bonus, 10)


# def _score_penalties(title: str, summary: str, budget: Any, deadline: Optional[str]) -> int:
#     missing = 0
#     if not budget:
#         missing += 1
#     if not deadline:
#         missing += 1
#     if not summary or len(summary) < 20:
#         missing += 1

#     return -5 if missing > 2 else 0


# class ScoringService:
#     """Calcul du score de pertinence (0-100) — logique déterministe."""

#     def __init__(self):
#         self.scoring_reference = _load_yaml_reference(SCORING_YAML_PATH)
#         logger.info("✅ scoring.yaml chargé (référence)")

#     def score(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
#         title = str(opportunity.get("title", ""))
#         summary = str(opportunity.get("summary", "") or "")
#         url = str(opportunity.get("url", ""))
#         budget = opportunity.get("budget")
#         deadline = opportunity.get("deadline")
#         domain = str(opportunity.get("domain", "autre"))
#         current_date = datetime.now()

#         score = 0
#         details = []

#         domain_points = _score_domain(domain)
#         score += domain_points
#         if domain_points:
#             details.append(f"Domaine {domain} (+{domain_points})")

#         budget_points = _score_budget(budget)
#         score += budget_points
#         if budget_points:
#             details.append(f"Budget (+{budget_points})")

#         organizer_points = _score_organizer(opportunity.get("organizer"))
#         score += organizer_points
#         if organizer_points:
#             details.append(f"Organisme (+{organizer_points})")

#         deadline_points = _score_deadline(deadline, current_date)
#         score += deadline_points
#         if deadline_points > 0:
#             details.append(f"Échéance (+{deadline_points})")
#         elif deadline_points < 0:
#             details.append(f"Échéance expirée ({deadline_points})")

#         alignment_points = _score_alignment(title, summary)
#         score += alignment_points
#         if alignment_points:
#             details.append(f"Alignement stratégique (+{alignment_points})")

#         text = f"{title} {summary}".lower()
#         if ".mg" in url.lower() or "madagascar" in text:
#             score += 5
#             details.append("Source Madagascar (+5)")

#         bonus_points = _score_bonus(title, summary, url)
#         score += bonus_points
#         if bonus_points:
#             details.append(f"Bonus (+{bonus_points})")

#         penalty = _score_penalties(title, summary, budget, deadline)
#         score += penalty
#         if penalty:
#             details.append(f"Pénalités ({penalty})")

#         score = max(0, min(100, score))

#         if score >= 80:
#             level = "Très pertinent"
#             recommendation = "Priorité absolue — Traiter immédiatement"
#         elif score >= 60:
#             level = "Pertinent"
#             recommendation = "À traiter rapidement — Suivi régulier"
#         elif score >= 40:
#             level = "Peu pertinent"
#             recommendation = "À surveiller — Réévaluer si modification"
#         else:
#             level = "Non pertinent"
#             recommendation = "À ignorer — Ne pas investir de temps"

#         return {
#             "score": score,
#             "level": level,
#             "recommendation": recommendation,
#             "details": details,
#             "reason": " + ".join(details) if details else "Score par défaut",
#         }




# app/services/veille/scoring_service.py
# ============================================================
# SERVICE SCORING — décision déterministe Python
# ============================================================
# Le score final (0-100) est calculé en Python, pas par le LLM.
# scoring.yaml reste chargé comme référence documentaire.
# ============================================================

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
SCORING_YAML_PATH = BASE_DIR / "app" / "prompts" / "m1" / "scoring.yaml"


def _load_yaml_reference(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("⚠️ Prompt de référence absent : %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        logger.error("❌ YAML invalide : %s", path)
        raise ValueError(f"YAML invalide : {path}") from exc

    return data if isinstance(data, dict) else {}


def _score_domain(domain: str) -> int:
    scores = {
        "ia": 30, "data": 25, "devops": 20,
        "developpement": 15, "bureautique": 5, "autre": 0,
    }
    return scores.get(str(domain).lower(), 0)


def _score_budget(budget: Any) -> int:
    if not budget:
        return 0

    text = str(budget).strip()
    if text.lower() in {
        "non précisé", "non precise", "n/a", "na",
        "null", "unknown", "non disponible",
    }:
        return 0

    try:
        match = re.search(r"\d+(?:[\s.,]\d+)*", text)
        if not match:
            return 0

        number = re.sub(r"[\s.,]", "", match.group(0))
        value = int(number)

        if value > 100_000_000:
            return 20
        if value >= 50_000_000:
            return 15
        if value >= 20_000_000:
            return 10
        if value >= 5_000_000:
            return 5
        return 2

    except (TypeError, ValueError):
        return 0


def _score_organizer(organizer: Any) -> int:
    if not organizer:
        return 0

    text = str(organizer).lower()

    if any(w in text for w in ["ministère", "ministry", "gouvernement", "government"]):
        return 15
    if any(w in text for w in ["banque", "bank", "télécom", "telecom", "assurance", "insurance"]):
        return 12
    if any(w in text for w in ["pme", "sarl", "sas", "startup"]):
        return 8
    if any(w in text for w in ["ong", "association", "coopérative"]):
        return 5

    return 2


def _score_deadline(deadline_str: Optional[str], current_date: datetime) -> int:
    if not deadline_str:
        return 0

    try:
        deadline = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
        if deadline.tzinfo is not None:
            deadline = deadline.replace(tzinfo=None)

        if deadline < current_date:
            return -10

        delta_days = (deadline - current_date).days

        if delta_days < 7:
            return 10
        if delta_days < 15:
            return 8
        if delta_days < 30:
            return 5
        if delta_days < 60:
            return 3
        return 1

    except (TypeError, ValueError):
        return 0


def _score_alignment(title: str, summary: str) -> int:
    text = f"{title} {summary or ''}".lower()

    if any(t in text for t in ["formation ia", "formation claude", "prompt engineering", "agent ia"]):
        return 15
    if any(t in text for t in ["conseil ia", "digitalisation", "transformation digitale"]):
        return 12
    if any(t in text for t in ["agent ia", "api", "intégration"]):
        return 12
    if any(t in text for t in ["saas", "plateforme"]):
        return 10
    if any(t in text for t in ["n8n", "make", "automatisation"]):
        return 10
    if any(t in text for t in ["devops", "cloud", "kubernetes", "docker"]):
        return 8
    if any(t in text for t in ["data science", "python", "sql"]):
        return 8
    if any(t in text for t in ["développement", "developpement", "development", "web", "mobile"]):
        return 5
    if any(t in text for t in ["excel", "word", "bureautique"]):
        return 3

    return 0


def _score_bonus(title: str, summary: str, url: str) -> int:
    text = f"{title} {summary or ''}".lower()
    bonus = 0

    if len(summary or "") > 100:
        bonus += 5

    if any(t in text for t in [
        "data scientist", "ingénieur", "développeur", "developpeur",
        "developer", "consultant", "formateur",
    ]):
        bonus += 5

    if "madagascar" in text:
        bonus += 3

    if "antananarivo" in text or "tana" in text:
        bonus += 2

    return min(bonus, 10)


def _score_penalties(title: str, summary: str, budget: Any, deadline: Optional[str]) -> int:
    missing = 0
    if not budget:
        missing += 1
    if not deadline:
        missing += 1
    if not summary or len(summary) < 20:
        missing += 1

    return -5 if missing > 2 else 0


class ScoringService:
    """Calcul du score de pertinence (0-100) — logique déterministe."""

    def __init__(self):
        self.scoring_reference = _load_yaml_reference(SCORING_YAML_PATH)
        logger.info("✅ scoring.yaml chargé (référence)")

    def score(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        title = str(opportunity.get("title", ""))
        summary = str(opportunity.get("summary", "") or "")
        url = str(opportunity.get("url", ""))
        budget = opportunity.get("budget")
        deadline = opportunity.get("deadline")
        domain = str(opportunity.get("domain", "autre"))
        current_date = datetime.now()

        score = 0
        details = []

        domain_points = _score_domain(domain)
        score += domain_points
        if domain_points:
            details.append(f"Domaine {domain} (+{domain_points})")

        budget_points = _score_budget(budget)
        score += budget_points
        if budget_points:
            details.append(f"Budget (+{budget_points})")

        # Organisateur — SAUF si son identité est marquée incertaine
        # (flag 'organizer_unclear' posé par validation_service quand
        # source == organizer et que source ressemble à une simple
        # plateforme d'hébergement plutôt qu'à un vrai employeur).
        # On ne récompense pas une information dont on n'est pas sûr.
        if "organizer_unclear" in (opportunity.get("flags") or []):
            organizer_points = 0
        else:
            organizer_points = _score_organizer(opportunity.get("organizer"))
        score += organizer_points
        if organizer_points:
            details.append(f"Organisme (+{organizer_points})")

        deadline_points = _score_deadline(deadline, current_date)
        score += deadline_points
        if deadline_points > 0:
            details.append(f"Échéance (+{deadline_points})")
        elif deadline_points < 0:
            details.append(f"Échéance expirée ({deadline_points})")

        alignment_points = _score_alignment(title, summary)
        score += alignment_points
        if alignment_points:
            details.append(f"Alignement stratégique (+{alignment_points})")

        text = f"{title} {summary}".lower()
        if ".mg" in url.lower() or "madagascar" in text:
            score += 5
            details.append("Source Madagascar (+5)")

        bonus_points = _score_bonus(title, summary, url)
        score += bonus_points
        if bonus_points:
            details.append(f"Bonus (+{bonus_points})")

        penalty = _score_penalties(title, summary, budget, deadline)
        score += penalty
        if penalty:
            details.append(f"Pénalités ({penalty})")

        score = max(0, min(100, score))

        if score >= 80:
            level = "Très pertinent"
            recommendation = "Priorité absolue — Traiter immédiatement"
        elif score >= 60:
            level = "Pertinent"
            recommendation = "À traiter rapidement — Suivi régulier"
        elif score >= 40:
            level = "Peu pertinent"
            recommendation = "À surveiller — Réévaluer si modification"
        else:
            level = "Non pertinent"
            recommendation = "À ignorer — Ne pas investir de temps"

        return {
            "score": score,
            "level": level,
            "recommendation": recommendation,
            "details": details,
            "reason": " + ".join(details) if details else "Score par défaut",
        }