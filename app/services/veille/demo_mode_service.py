"""Chargement des avis réels archivés et Plan B synthétique pour M1.

DEMO_MODE=true rejoue d'abord les avis publics archivés dans
``opportunites_demo_reelles.json``. Chaque fiche conserve séparément les
dates de publication, de capture et de clôture. Le pool synthétique reste
disponible uniquement si l'archive réelle est vide ou illisible et chaque
fiche de ce pool est explicitement marquée comme fictive.
"""

import json
import logging
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from app.services.veille.scoring_service import ScoringService

logger = logging.getLogger(__name__)

ARCHIVE_REELLE_PATH = Path(__file__).with_name("opportunites_demo_reelles.json")


def _charger_demo_mode() -> bool:
    """Lit DEMO_MODE depuis l'environnement, puis depuis le .env du projet."""
    valeur = os.getenv("DEMO_MODE")
    if valeur is None:
        fichier_env = Path(__file__).resolve().parents[3] / ".env"
        try:
            for ligne in fichier_env.read_text(encoding="utf-8-sig").splitlines():
                ligne = ligne.strip()
                if ligne.startswith("export "):
                    ligne = ligne[7:].strip()
                nom, separateur, contenu = ligne.partition("=")
                if separateur and nom.strip() == "DEMO_MODE":
                    valeur = contenu.strip().strip("\"'")
                    break
        except OSError:
            valeur = None

    return (valeur or "false").strip().strip("\"'").lower() in {
        "1", "true", "yes", "on",
    }


DEMO_MODE = _charger_demo_mode()

# ──────────────────────────────────────────────────────────────
# Pool de 20 opportunités fictives — organisations non vérifiables
# ──────────────────────────────────────────────────────────────
_POOL: list[dict] = [
    {
        "title": "Formation IA générative et Prompt Engineering — équipe technique",
        "organizer": "Cabinet TANA-DIGITAL Consulting",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "ia",
        "opportunity_type": "demande_formation",
        "budget": "8 500 000 Ar",
        "score": 88,
        "confidence": 0.91,
        "summary": "Cabinet de conseil en transformation digitale recherche un prestataire pour former 12 consultants aux outils d'IA générative (ChatGPT, Claude, outils métier). Durée : 3 jours. Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Appel d'offres — Plateforme de gestion de la formation professionnelle",
        "organizer": "Institut HERITERA de Formation Continue",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "appel_offres",
        "budget": "45 000 000 Ar",
        "score": 82,
        "confidence": 0.87,
        "summary": "Institut de formation continue recherche un prestataire pour développer une plateforme numérique de gestion des inscriptions, sessions et attestations. Délai de remise : 20 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation DevOps et déploiement cloud — équipe SI",
        "organizer": "Groupement NUMERIA Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "devops",
        "opportunity_type": "demande_formation",
        "budget": "12 000 000 Ar",
        "score": 79,
        "confidence": 0.85,
        "summary": "Groupement d'entreprises du secteur numérique recherche un formateur certifié pour une session DevOps (Docker, CI/CD, déploiement cloud). 8 participants, 4 jours, Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Mission de conseil — Audit et transformation digitale",
        "organizer": "ONG FIVEAMPELA Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "autre",
        "opportunity_type": "mission_conseil",
        "budget": "28 000 000 Ar",
        "score": 74,
        "confidence": 0.82,
        "summary": "ONG active dans le développement rural cherche un prestataire pour auditer son système d'information et proposer une feuille de route de transformation digitale. Durée estimée : 3 semaines.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation analyse de données avec Python — data analysts",
        "organizer": "Cabinet MASOANDRO Data & Analytics",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "data",
        "opportunity_type": "demande_formation",
        "budget": "9 200 000 Ar",
        "score": 77,
        "confidence": 0.88,
        "summary": "Cabinet spécialisé en conseil data recherche une formation Python pour l'analyse de données (pandas, visualisation, machine learning de base). 6 participants, 5 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Appel d'offres — Développement application mobile de gestion RH",
        "organizer": "Réseau AVOTRA Entreprises Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "appel_offres",
        "budget": "62 000 000 Ar",
        "score": 85,
        "confidence": 0.90,
        "summary": "Réseau d'entreprises membres cherche un prestataire pour développer une application mobile de gestion RH (congés, présences, fiches de paie). Délai de remise : 15 jours. Livraison en 3 mois.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation cybersécurité — sensibilisation et bonnes pratiques",
        "organizer": "Institution financière MALAZA Finances",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "autre",
        "opportunity_type": "demande_formation",
        "budget": "7 500 000 Ar",
        "score": 71,
        "confidence": 0.83,
        "summary": "Institution de microfinance recherche une formation en cybersécurité pour ses 20 agents (sensibilisation, protection des données clients, gestion des mots de passe). 1 journée.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Mission de développement — Portail intranet et gestion documentaire",
        "organizer": "Association professionnelle TEKNÀ Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "mission_conseil",
        "budget": "38 000 000 Ar",
        "score": 80,
        "confidence": 0.86,
        "summary": "Association professionnelle cherche un prestataire pour développer un portail intranet avec gestion documentaire et espace collaboratif. 15 utilisateurs, Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation agents IA et RAG — équipe innovation",
        "organizer": "Groupe SARY Technology Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "ia",
        "opportunity_type": "demande_formation",
        "budget": "15 000 000 Ar",
        "score": 91,
        "confidence": 0.93,
        "summary": "Groupe technologique cherche une formation avancée sur les agents LLM et la RAG (LangChain, FastAPI, vectorisation) pour son équipe de 8 développeurs. 4 jours, Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Appel d'offres — Système de suivi et évaluation des projets",
        "organizer": "Fondation VOLA MAHASOA Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "appel_offres",
        "budget": "52 000 000 Ar",
        "score": 83,
        "confidence": 0.89,
        "summary": "Fondation de développement cherche un prestataire pour développer un système de suivi-évaluation de ses projets de terrain (indicateurs, tableaux de bord, rapports automatiques). Délai : 18 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation bureautique avancée — Pack Microsoft 365",
        "organizer": "Cabinet comptable FARITRA Expertise",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "bureautique",
        "opportunity_type": "demande_formation",
        "budget": "4 800 000 Ar",
        "score": 65,
        "confidence": 0.80,
        "summary": "Cabinet comptable recherche une formation Microsoft 365 complète (Excel avancé, Teams, SharePoint) pour ses 15 collaborateurs. 3 jours, Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Mission — Mise en place d'un ERP de gestion commerciale",
        "organizer": "Entreprise RARY Commerce & Distribution",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "autre",
        "opportunity_type": "mission_conseil",
        "budget": "75 000 000 Ar",
        "score": 78,
        "confidence": 0.84,
        "summary": "Entreprise de distribution cherche un intégrateur pour déployer un ERP de gestion commerciale (stocks, commandes, facturation). Formation des utilisateurs incluse. Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation React et développement frontend moderne",
        "organizer": "Agence digitale TSIKY Web Agency",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "demande_formation",
        "budget": "11 000 000 Ar",
        "score": 76,
        "confidence": 0.87,
        "summary": "Agence web cherche une formation React (hooks, state management, intégration API REST) pour 5 développeurs juniors. 5 jours, possibilité remote.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Appel d'offres — Plateforme e-learning pour formation continue",
        "organizer": "Fédération MIARA-MANDROSO des PME Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "appel_offres",
        "budget": "95 000 000 Ar",
        "score": 87,
        "confidence": 0.92,
        "summary": "Fédération de PME cherche un prestataire pour développer une plateforme e-learning (cours vidéo, quiz, certificats) destinée à 500 membres. Délai de remise : 25 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation machine learning appliqué — équipe R&D",
        "organizer": "Laboratoire d'innovation NIRY Tech Solutions",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "data",
        "opportunity_type": "demande_formation",
        "budget": "18 500 000 Ar",
        "score": 84,
        "confidence": 0.90,
        "summary": "Laboratoire de recherche appliquée cherche une formation machine learning (scikit-learn, modèles supervisés, évaluation de modèles) pour 10 ingénieurs. 6 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Mission — Audit sécurité et conformité RGPD des systèmes",
        "organizer": "Réseau hospitalier FAHASALAMANA Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "autre",
        "opportunity_type": "mission_conseil",
        "budget": "32 000 000 Ar",
        "score": 72,
        "confidence": 0.81,
        "summary": "Réseau de cliniques cherche un prestataire pour auditer la sécurité de ses systèmes d'information et assurer la conformité avec les réglementations sur la protection des données de santé.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation Python pour l'automatisation des processus métier",
        "organizer": "Coopérative agricole HASINA Digital",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "demande_formation",
        "budget": "6 500 000 Ar",
        "score": 69,
        "confidence": 0.79,
        "summary": "Coopérative souhaitant automatiser ses reportings cherche une formation Python (scripts d'automatisation, traitement de fichiers Excel, envoi d'emails). 4 participants, 3 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Fianarantsoa",
    },
    {
        "title": "Appel d'offres — Développement API REST pour intégration partenaires",
        "organizer": "Plateforme logistique SERASERA Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "developpement",
        "opportunity_type": "appel_offres",
        "budget": "41 000 000 Ar",
        "score": 81,
        "confidence": 0.88,
        "summary": "Plateforme logistique cherche un prestataire pour développer une API REST d'intégration avec ses partenaires transporteurs (suivi colis, notifications, facturation automatique). Délai : 21 jours.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Formation administration système Linux et réseaux",
        "organizer": "Centre éducatif FAHAZAVANA Formation",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "autre",
        "opportunity_type": "demande_formation",
        "budget": "8 000 000 Ar",
        "score": 70,
        "confidence": 0.82,
        "summary": "Centre de formation cherche un formateur certifié Linux pour une formation administration système (Ubuntu Server, Bash, réseaux TCP/IP). 8 stagiaires, 5 jours, Antananarivo.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
    {
        "title": "Mission conseil IA — Stratégie d'intégration LLM dans les processus RH",
        "organizer": "Cabinet DRH RINDRA Conseil Madagascar",
        "source": "Demande directe — réseau partenaires ALTIORA",
        "source_site": "Réseau partenaires",
        "source_priority": "niveau_2",
        "url": None,
        "domain": "ia",
        "opportunity_type": "mission_conseil",
        "budget": "22 000 000 Ar",
        "score": 86,
        "confidence": 0.91,
        "summary": "Cabinet RH cherche un consultant spécialisé IA pour définir une stratégie d'intégration des LLM dans les processus de recrutement et d'évaluation des compétences. Mission 2 semaines.",
        "is_actionable": True,
        "flags": [],
        "location": "Antananarivo",
    },
]


def charger_opportunites_demo_reelles() -> list[dict]:
    """Charge et score les avis publics archivés pour la démonstration.

    Le score est calculé par le ScoringService M1 avec la date de capture,
    afin que la même archive conserve le même score après la clôture des avis.
    ``current_status`` est, lui, actualisé à chaque chargement.
    """
    try:
        with ARCHIVE_REELLE_PATH.open(encoding="utf-8") as fichier:
            donnees = json.load(fichier)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        logger.warning("Archive réelle de démonstration indisponible : %s", exc)
        return []

    if not isinstance(donnees, list):
        logger.warning("Archive réelle de démonstration invalide : une liste était attendue.")
        return []

    try:
        scoring = ScoringService()
    except Exception as exc:
        logger.warning("Scoring M1 indisponible pour l'archive de démonstration : %s", exc)
        scoring = None
    aujourd_hui = date.today()
    opportunites: list[dict] = []

    for fiche in donnees:
        if not isinstance(fiche, dict):
            logger.warning("Fiche d'avis ignorée : format invalide.")
            continue

        opportunite = dict(fiche)
        try:
            date_capture = date.fromisoformat(opportunite["date_capture"])
            date_limite = date.fromisoformat(opportunite["date_limite"])
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Fiche d'avis ignorée : date_capture ou date_limite invalide (%s).",
                opportunite.get("reference", opportunite.get("title", "sans titre")),
            )
            continue

        date_heure_limite = opportunite.get("date_heure_limite")
        if date_heure_limite:
            try:
                echeance = datetime.fromisoformat(date_heure_limite)
                maintenant = datetime.now(echeance.tzinfo) if echeance.tzinfo else datetime.now()
                if maintenant >= echeance:
                    statut_actuel = "clôturée"
                elif maintenant.date() == echeance.date():
                    statut_actuel = "échéance aujourd’hui"
                else:
                    statut_actuel = "ouverte"
            except ValueError:
                logger.warning("Date/heure limite invalide : %s", date_heure_limite)
                statut_actuel = "à vérifier"
        elif date_limite < aujourd_hui:
            statut_actuel = "clôturée"
        elif date_limite == aujourd_hui:
            statut_actuel = "échéance aujourd’hui"
        else:
            statut_actuel = "ouverte"

        opportunite.update({
            "deadline": opportunite["date_limite"],
            "current_status": statut_actuel,
            "is_actionable": statut_actuel == "ouverte",
            "is_synthetic": False,
            "demo_data_type": "archive_reelle",
            "score_reference_date": date_capture.isoformat(),
            "score_source": "ScoringService M1 déterministe",
        })

        if scoring is not None:
            try:
                reference_score = datetime.combine(date_capture, datetime.min.time())
                opportunite.update(scoring.score(opportunite, date_reference=reference_score))
            except Exception as exc:
                logger.warning(
                    "Score M1 non calculé pour %s : %s",
                    opportunite.get("reference", opportunite.get("title", "sans titre")),
                    exc,
                )

        opportunites.append(opportunite)

    return opportunites


def generer_opportunites_demo(nb_min: int = 3, nb_max: int = 5) -> list[dict]:
    """Tire des exemples fictifs lorsque l'archive réelle est indisponible."""
    import time
    graine = int(time.time() // 600)  # change toutes les 10 min
    rng = random.Random(graine)
    nb = rng.randint(nb_min, nb_max)
    selection = rng.sample(_POOL, min(nb, len(_POOL)))

    # Ajuste les délais pour paraître récents
    aujourd_hui = date.today()
    for i, opp in enumerate(selection):
        opp = dict(opp)  # copie pour ne pas modifier le pool
        jours = rng.randint(5, 28)
        deadline = (aujourd_hui + timedelta(days=jours)).isoformat()
        opp.update({
            "deadline": deadline,
            "date_limite": deadline,
            "date_capture": None,
            "date_publication": None,
            "source_url": None,
            "status_at_capture": "ouverte",
            "current_status": "ouverte",
            "is_actionable": True,
            "demo_data_type": "synthetic_fallback",
            "is_synthetic": True,
        })
        selection[i] = opp

    return selection
