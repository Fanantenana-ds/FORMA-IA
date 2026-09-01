# app/services/validation/validator.py
# ============================================================
# VALIDATION SERVICE — FORMA-IA / M1
# ============================================================
#
# Objectif :
#   Transformer la sortie du LLM en données fiables.
#
# Pipeline :
#
#   Résultats recherche
#          ↓
#      OpenRouter
#          ↓
#      JSON IA
#          ↓
#      Validator
#          ↓
#   ┌───────────────┐
#   │ Opportunité   │
#   │ réellement    │
#   │ actionnable ? │
#   └───────┬───────┘
#           │
#      ┌────┴────┐
#      ↓         ↓
#    NON       OUI
#      ↓         ↓
#   REJECT    BUSINESS
#                ↓
#           CONFIDENCE
#                ↓
#      validated / to_review
#
# ============================================================

from typing import Dict, List, Any, Tuple
from datetime import datetime
from urllib.parse import urlparse
import re
import logging

from app.models.opportunity import DomainEnum


logger = logging.getLogger(__name__)


class Validator:
    """
    Service de validation des opportunités M1.

    Responsabilités :

    1. Validation du schéma
    2. Validation du domaine
    3. Détection des vraies opportunités
    4. Rejet des articles / guides / contenus informatifs
    5. Détection des contenus non actionnables
    6. Vérification de l'URL
    7. Vérification de la deadline
    8. Validation de la confiance
    9. Ajout de flags
    10. Nettoyage des données
    """

    # ========================================================
    # INITIALISATION
    # ========================================================

    def __init__(self):

        # ----------------------------------------------------
        # Domaines autorisés
        # ----------------------------------------------------

        self.valid_domains = {
            str(domain.value).lower()
            for domain in DomainEnum
        }

        # ----------------------------------------------------
        # Types d'opportunités autorisés
        # ----------------------------------------------------

        self.valid_opportunity_types = {
            "emploi",
            "appel_offres",
            "prestation",
            "formation",
            "projet",
            "stage",
        }

        # ----------------------------------------------------
        # Mots indiquant une vraie opportunité
        # ----------------------------------------------------

        self.opportunity_keywords = [

            # ==============================
            # EMPLOI
            # ==============================

            "offre d'emploi",
            "offre emploi",
            "emploi",
            "recrute",
            "recrutement",
            "recrutons",
            "recherche un",
            "recherche une",
            "recherche de",
            "poste",
            "postulez",
            "candidature",
            "candidatez",
            "hiring",
            "job",
            "jobs",
            "vacancy",
            "vacancies",
            "we are hiring",
            "join our team",

            # ==============================
            # STAGE
            # ==============================

            "stage",
            "stagiaire",
            "internship",
            "intern",
            "alternance",
            "apprentissage",

            # ==============================
            # APPEL D'OFFRES
            # ==============================

            "appel d'offres",
            "appel d’offre",
            "appel à manifestation",
            "avis d'appel",
            "avis d’appel",
            "consultation",
            "marché public",
            "marché",
            "soumissionner",
            "soumission",
            "prestataire recherché",
            "prestataire recherche",
            "tender",
            "tenders",
            "procurement",
            "request for proposal",
            "request for proposals",
            "rfp",
            "request for quotation",
            "rfq",
            "expression of interest",
            "eoi",

            # ==============================
            # PRESTATION / FREELANCE
            # ==============================

            "mission freelance",
            "mission",
            "freelance",
            "consultant",
            "consultante",
            "consultance",
            "expert recherché",
            "expert recherche",
            "prestataire",
            "service provider",
            "contractor",
            "contract",
            "consulting",

            # ==============================
            # FORMATION DEMANDÉE
            # ==============================

            "formation recherchée",
            "formation demandée",
            "formation demandée pour",
            "recherche formateur",
            "recherche un formateur",
            "recherche une formatrice",
            "formateur recherché",
            "formatrice recherchée",
            "prestataire de formation",
            "formation pour les agents",
            "formation des agents",
            "former les agents",
            "former des agents",
            "former les employés",
            "former les collaborateurs",

            # ==============================
            # PROJET
            # ==============================

            "projet informatique",
            "projet numérique",
            "projet digital",
            "projet ia",
            "projet intelligence artificielle",
            "développer une plateforme",
            "développement d'une plateforme",
            "développement d’une plateforme",
            "développement d'application",
            "développement d’application",
            "développer une application",
            "création d'une plateforme",
            "création d’une plateforme",
            "création d'application",
            "création d’application",
            "intégration",
            "automatisation",
            "mise en place d'une solution",
            "mise en place d’une solution",
            "implémentation",
            "déploiement d'une solution",
            "déploiement d’une solution",
        ]

        # ----------------------------------------------------
        # Faux positifs : contenus éditoriaux
        # ----------------------------------------------------

        self.article_keywords = [

            "article",
            "articles",
            "actualités",
            "actualité",
            "news",
            "blog",
            "guide",
            "guides",
            "tutorial",
            "tutoriel",
            "comment devenir",
            "comment apprendre",
            "comment se former",
            "comment apprendre l'ia",
            "comment apprendre l’intelligence artificielle",
            "métiers de l'avenir",
            "métier d'avenir",
            "métiers d'avenir",
            "tendance",
            "tendances",
            "étude",
            "étude de marché",
            "rapport",
            "rapport de marché",
            "analyse",
            "statistiques",
            "statistique",
            "prévision",
            "prévisions",
            "perspectives",
            "conseils",
            "définition",
            "qu'est-ce que",
            "qu’est-ce que",
            "pourquoi",
            "découvrir les métiers",
            "opportunités futures",
            "marché de l'emploi",
            "marché de l’emploi",
            "avenir de l'emploi",
            "avenir de l’emploi",
            "les métiers",
            "les compétences",
            "salaires des",
            "salaire moyen",
            "formation à l'ia",
            "formation à l’intelligence artificielle",
            "apprendre l'intelligence artificielle",
            "apprendre l’intelligence artificielle",
            "initiation à",
            "présentation",
            "présente les",
            "explique",
            "expliqué",
            "explication",
            "dossier",
            "chronique",
            "podcast",
            "webinaire",
            "webinar",
            "événement",
            "évènement",
            "conférence",
        ]

        # ----------------------------------------------------
        # Mots indiquant explicitement une absence d'offre
        # ----------------------------------------------------

        self.non_actionable_keywords = [

            "aucune offre",
            "pas d'offre",
            "pas d’emploi",
            "pas d'emploi",
            "sans offre",
            "information générale",
            "informations générales",
            "contenu informatif",
            "contenu éducatif",
            "article informatif",
            "simple article",
            "guide informatif",
            "à titre informatif",
            "opportunité potentielle",
            "opportunités potentielles",
            "pourrait être une opportunité",
            "peut représenter une opportunité",
        ]

        # ----------------------------------------------------
        # URL génériques
        # ----------------------------------------------------

        self.generic_url_patterns = [

            "/search",
            "/search?",
            "/jobs",
            "/jobs/",
            "/job",
            "/job/",
            "/offers",
            "/offers/",
            "/offres",
            "/offres/",
            "/emploi",
            "/emplois",
            "/category",
            "/categories",
            "/tag",
            "/tags",
            "/topics",
            "/topic",
            "/jobs/ia",
            "/jobs/data",
            "/jobs/dev",
            "/jobs/development",
            "?q=",
            "?query=",
            "?search=",
        ]

    # ========================================================
    # UTILITAIRES
    # ========================================================

    @staticmethod
    def _normalize_text(value: Any) -> str:
        """
        Normalise un texte pour faciliter les recherches.
        """

        if value is None:
            return ""

        text = str(value).lower().strip()

        # espaces multiples
        text = re.sub(r"\s+", " ", text)

        return text

    @staticmethod
    def _add_flag(data: Dict, flag: str) -> None:
        """
        Ajoute un flag sans créer de doublon.
        """

        flags = data.get("flags", [])

        if not isinstance(flags, list):
            flags = []

        if flag not in flags:
            flags.append(flag)

        data["flags"] = flags

    @staticmethod
    def _remove_flag(data: Dict, flag: str) -> None:
        """
        Supprime un flag s'il existe.
        """

        flags = data.get("flags", [])

        if not isinstance(flags, list):
            flags = []

        data["flags"] = [
            item for item in flags
            if item != flag
        ]

    def _combined_text(self, data: Dict) -> str:
        """
        Construit le texte utilisé pour la détection.
        """

        fields = [
            data.get("title", ""),
            data.get("summary", ""),
            data.get("reason", ""),
            data.get("opportunity_type", ""),
            data.get("source", ""),
            data.get("organizer", ""),
        ]

        return self._normalize_text(
            " ".join(
                str(field)
                for field in fields
                if field is not None
            )
        )

    # ========================================================
    # VALIDATION SCHÉMA
    # ========================================================

    def validate_schema(self, data: Dict) -> Dict:
        """
        Vérifie et normalise la structure des données.
        """

        if not isinstance(data, dict):
            return {}

        required = [
            "title",
            "source",
            "domain",
            "summary",
            "score",
            "confidence",
        ]

        # ----------------------------------------------------
        # Champs obligatoires
        # ----------------------------------------------------

        for field in required:

            if field not in data or data[field] is None:

                data[f"{field}_missing"] = True

                self._add_flag(
                    data,
                    "partial_info"
                )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        if data.get("title") is not None:
            data["title"] = str(
                data["title"]
            ).strip()

        # ----------------------------------------------------
        # Source
        # ----------------------------------------------------

        if data.get("source") is not None:
            data["source"] = str(
                data["source"]
            ).strip()

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        if data.get("summary") is not None:
            data["summary"] = str(
                data["summary"]
            ).strip()

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        try:

            score = float(
                data.get("score", 0)
            )

            score = max(
                0.0,
                min(100.0, score)
            )

            data["score"] = (
                int(score)
                if score.is_integer()
                else round(score, 2)
            )

        except (ValueError, TypeError):

            data["score"] = 0

            self._add_flag(
                data,
                "invalid_score"
            )

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        try:

            confidence = float(
                data.get("confidence", 0)
            )

            confidence = max(
                0.0,
                min(1.0, confidence)
            )

            data["confidence"] = round(
                confidence,
                3
            )

        except (ValueError, TypeError):

            data["confidence"] = 0.0

            self._add_flag(
                data,
                "invalid_confidence"
            )

        # ----------------------------------------------------
        # Flags
        # ----------------------------------------------------

        if not isinstance(
            data.get("flags"),
            list
        ):
            data["flags"] = []

        # Nettoyage
        data["flags"] = sorted(
            set(
                str(flag)
                for flag in data["flags"]
                if flag
            )
        )

        return data

    # ========================================================
    # TYPE D'OPPORTUNITÉ
    # ========================================================

    def _detect_opportunity_type(
        self,
        data: Dict
    ) -> Tuple[str, bool]:
        """
        Détermine le type d'opportunité et indique
        si le contenu contient des signaux actionnables.
        """

        text = self._combined_text(data)

        provided_type = self._normalize_text(
            data.get("opportunity_type", "")
        )

        # ----------------------------------------------------
        # Type fourni par le LLM
        # ----------------------------------------------------

        if provided_type in self.valid_opportunity_types:

            # MAIS le type ne suffit pas à valider.
            # Nous vérifions également le contenu.

            if provided_type == "emploi":

                patterns = [
                    "emploi",
                    "recrute",
                    "recrutement",
                    "poste",
                    "hiring",
                    "vacancy",
                    "job",
                    "candidate",
                    "candidat",
                ]

            elif provided_type == "stage":

                patterns = [
                    "stage",
                    "stagiaire",
                    "internship",
                    "intern",
                    "alternance",
                ]

            elif provided_type == "appel_offres":

                patterns = [
                    "appel d'offres",
                    "appel d’offre",
                    "tender",
                    "procurement",
                    "rfp",
                    "rfq",
                    "consultation",
                    "soumission",
                    "marché public",
                ]

            elif provided_type == "prestation":

                patterns = [
                    "mission",
                    "freelance",
                    "consultant",
                    "consultance",
                    "prestataire",
                    "service provider",
                    "contractor",
                ]

            elif provided_type == "formation":

                patterns = [
                    "formation recherchée",
                    "formation demandée",
                    "recherche formateur",
                    "formateur recherché",
                    "prestataire de formation",
                    "former les agents",
                    "former des agents",
                    "formation pour",
                ]

            elif provided_type == "projet":

                patterns = [
                    "projet",
                    "développer",
                    "développement",
                    "création",
                    "intégration",
                    "automatisation",
                    "implémentation",
                    "déploiement",
                ]

            else:
                patterns = []

            if any(
                pattern in text
                for pattern in patterns
            ):
                return provided_type, True

        # ----------------------------------------------------
        # Détection automatique
        # ----------------------------------------------------

        type_patterns = {

            "emploi": [
                "offre d'emploi",
                "emploi",
                "recrute",
                "recrutement",
                "poste",
                "hiring",
                "vacancy",
            ],

            "stage": [
                "stage",
                "stagiaire",
                "internship",
                "alternance",
            ],

            "appel_offres": [
                "appel d'offres",
                "appel d’offre",
                "tender",
                "procurement",
                "rfp",
                "rfq",
                "soumissionner",
                "marché public",
            ],

            "prestation": [
                "mission freelance",
                "freelance",
                "consultant",
                "consultance",
                "prestataire",
                "contractor",
            ],

            "formation": [
                "recherche formateur",
                "formateur recherché",
                "formation recherchée",
                "formation demandée",
                "prestataire de formation",
                "former les agents",
                "former des agents",
            ],

            "projet": [
                "développer une plateforme",
                "développement d'une plateforme",
                "développement d’une plateforme",
                "développement d'application",
                "développement d’application",
                "développer une application",
                "projet informatique",
                "projet numérique",
                "automatisation",
                "intégration",
            ],
        }

        for opportunity_type, patterns in type_patterns.items():

            if any(
                pattern in text
                for pattern in patterns
            ):
                return opportunity_type, True

        return (
            provided_type
            if provided_type in self.valid_opportunity_types
            else "autre",
            False
        )

    # ========================================================
    # DÉTECTION OPPORTUNITÉ
    # ========================================================

    def validate_opportunity_type(
        self,
        data: Dict
    ) -> Dict:
        """
        Détermine si le contenu représente une vraie
        opportunité professionnelle/commerciale.

        IMPORTANT :
        `opportunity_type` fourni par le LLM n'est jamais
        considéré comme une preuve suffisante.
        """

        text = self._combined_text(data)

        detected_type, has_type_signal = (
            self._detect_opportunity_type(data)
        )

        data["opportunity_type"] = detected_type

        # ----------------------------------------------------
        # Détection explicite des faux positifs
        # ----------------------------------------------------

        article_hits = [
            keyword
            for keyword in self.article_keywords
            if keyword in text
        ]

        non_actionable_hits = [
            keyword
            for keyword in self.non_actionable_keywords
            if keyword in text
        ]

        opportunity_hits = [
            keyword
            for keyword in self.opportunity_keywords
            if keyword in text
        ]

        # ----------------------------------------------------
        # Ratio / force des signaux
        # ----------------------------------------------------

        has_article_signal = bool(
            article_hits
        )

        has_non_actionable_signal = bool(
            non_actionable_hits
        )

        # ----------------------------------------------------
        # Cas explicite : contenu informatif
        # ----------------------------------------------------

        if has_non_actionable_signal:

            data["is_actionable"] = False

            self._add_flag(
                data,
                "not_actionable"
            )

            self._add_flag(
                data,
                "informational_content"
            )

            data["rejection_reason"] = (
                "Le contenu indique explicitement qu'il "
                "s'agit d'une information générale et non "
                "d'une opportunité concrète."
            )

            return data

        # ----------------------------------------------------
        # Article sans véritable signal d'offre
        # ----------------------------------------------------

        if has_article_signal and not has_type_signal:

            data["is_actionable"] = False

            self._add_flag(
                data,
                "not_actionable"
            )

            self._add_flag(
                data,
                "article_or_guide"
            )

            data["rejection_reason"] = (
                "Le résultat ressemble à un article, "
                "guide, étude ou contenu informatif "
                "et ne présente pas de besoin concret."
            )

            return data

        # ----------------------------------------------------
        # Aucun signal concret
        # ----------------------------------------------------

        if not has_type_signal:

            data["is_actionable"] = False

            self._add_flag(
                data,
                "not_actionable"
            )

            data["rejection_reason"] = (
                "Aucun signal suffisamment fort ne permet "
                "d'identifier une opportunité concrète."
            )

            return data

        # ----------------------------------------------------
        # Opportunité + article
        # ----------------------------------------------------

        if has_article_signal and has_type_signal:

            # On ne rejette pas automatiquement.
            # Une page peut contenir une description éditoriale
            # autour d'une vraie mission.

            self._add_flag(
                data,
                "needs_human_review"
            )

            data["is_actionable"] = True

            return data

        # ----------------------------------------------------
        # Opportunité claire
        # ----------------------------------------------------

        if opportunity_hits or has_type_signal:

            data["is_actionable"] = True

            self._remove_flag(
                data,
                "not_actionable"
            )

            return data

        # ----------------------------------------------------
        # Sécurité
        # ----------------------------------------------------

        data["is_actionable"] = False

        self._add_flag(
            data,
            "not_actionable"
        )

        return data

    # ========================================================
    # REJET NON-OPPORTUNITÉ
    # ========================================================

    def reject_non_opportunity(
        self,
        data: Dict
    ) -> Dict:
        """
        Marque les contenus non actionnables comme rejetés.
        """

        if data.get("is_actionable") is False:

            data["status"] = "rejected"

            self._add_flag(
                data,
                "not_actionable"
            )

            if not data.get("rejection_reason"):

                data["rejection_reason"] = (
                    "Le résultat ne correspond pas à une "
                    "opportunité professionnelle ou commerciale "
                    "concrète et actionnable."
                )

        return data

    # ========================================================
    # VALIDATION BUSINESS
    # ========================================================

    def validate_business(
        self,
        data: Dict
    ) -> Dict:
        """
        Vérifie les règles métier.
        """

        # ----------------------------------------------------
        # Domaine
        # ----------------------------------------------------

        domain = self._normalize_text(
            data.get("domain", "")
        )

        if domain:

            if domain not in self.valid_domains:

                data["domain"] = "autre"

                self._add_flag(
                    data,
                    "invalid_domain"
                )

        else:

            data["domain"] = "autre"

            self._add_flag(
                data,
                "domain_missing"
            )

        # ----------------------------------------------------
        # Deadline
        # ----------------------------------------------------

        deadline = data.get("deadline")

        if deadline:

            try:

                deadline_text = str(
                    deadline
                ).strip()

                # ISO 8601
                deadline_dt = datetime.fromisoformat(
                    deadline_text.replace(
                        "Z",
                        "+00:00"
                    )
                )

                today = datetime.now().date()

                if deadline_dt.date() < today:

                    self._add_flag(
                        data,
                        "deadline_passed"
                    )

                    # Une opportunité expirée reste identifiable,
                    # mais ne doit normalement plus être présentée
                    # comme action immédiatement exploitable.

                    data["is_actionable"] = False

                    data["status"] = "rejected"

                    data["rejection_reason"] = (
                        "La deadline de cette opportunité "
                        "est dépassée."
                    )

            except (
                ValueError,
                TypeError,
                OverflowError
            ):

                data["deadline"] = None

                self._add_flag(
                    data,
                    "invalid_deadline"
                )

        # ----------------------------------------------------
        # Budget
        # ----------------------------------------------------

        budget = data.get("budget")

        if not budget or self._normalize_text(
            budget
        ) in {
            "non précisé",
            "non precise",
            "non spécifié",
            "non specifie",
            "unknown",
            "n/a",
            "na",
        }:

            self._add_flag(
                data,
                "budget_missing"
            )

        return data

    # ========================================================
    # VALIDATION URL
    # ========================================================

    def validate_url(
        self,
        data: Dict
    ) -> Dict:
        """
        Vérifie si l'URL semble valide et si elle ne correspond
        pas uniquement à une page générique de recherche.
        """

        url = data.get("url")

        # ----------------------------------------------------
        # URL absente
        # ----------------------------------------------------

        if not url:

            self._add_flag(
                data,
                "url_missing"
            )

            return data

        url = str(url).strip()

        # ----------------------------------------------------
        # Validation syntaxique
        # ----------------------------------------------------

        try:

            parsed = urlparse(url)

            if parsed.scheme not in {
                "http",
                "https",
            }:

                self._add_flag(
                    data,
                    "invalid_url"
                )

                return data

            if not parsed.netloc:

                self._add_flag(
                    data,
                    "invalid_url"
                )

                return data

        except Exception:

            self._add_flag(
                data,
                "invalid_url"
            )

            return data

        # ----------------------------------------------------
        # Détection URL générique
        # ----------------------------------------------------

        normalized_url = url.lower()

        generic = any(
            pattern in normalized_url
            for pattern in self.generic_url_patterns
        )

        if generic:

            self._add_flag(
                data,
                "url_generic"
            )

            # Ce n'est pas forcément une erreur :
            # certaines plateformes utilisent une URL générique.
            #
            # On demande donc une vérification humaine plutôt
            # que de rejeter automatiquement.

            self._add_flag(
                data,
                "needs_human_review"
            )

        return data

    # ========================================================
    # CONFIDENCE
    # ========================================================

    def validate_confidence(
        self,
        data: Dict
    ) -> Dict:
        """
        Détermine le statut selon la confiance.

        >= 0.70 → validated
        >= 0.50 → to_review
        < 0.50  → rejected
        """

        # ----------------------------------------------------
        # Non-actionnable
        # ----------------------------------------------------

        if data.get("is_actionable") is False:

            data["status"] = "rejected"

            return data

        confidence = float(
            data.get(
                "confidence",
                0.0
            )
        )

        # ----------------------------------------------------
        # Très bonne confiance
        # ----------------------------------------------------

        if confidence >= 0.70:

            data["status"] = "validated"

        # ----------------------------------------------------
        # Confiance moyenne
        # ----------------------------------------------------

        elif confidence >= 0.50:

            data["status"] = "to_review"

            self._add_flag(
                data,
                "low_confidence"
            )

        # ----------------------------------------------------
        # Faible confiance
        # ----------------------------------------------------

        else:

            data["status"] = "rejected"

            self._add_flag(
                data,
                "very_low_confidence"
            )

            data["rejection_reason"] = (
                "Niveau de confiance trop faible "
                "pour considérer cette opportunité comme fiable."
            )

        return data

    # ========================================================
    # FLAGS
    # ========================================================

    def flag_data(
        self,
        data: Dict
    ) -> Dict:
        """
        Ajoute les flags complémentaires.
        """

        # ----------------------------------------------------
        # Budget
        # ----------------------------------------------------

        budget = data.get("budget")

        if (
            not budget
            or self._normalize_text(budget)
            in {
                "non précisé",
                "non precise",
                "non spécifié",
                "non specifie",
                "unknown",
                "n/a",
                "na",
            }
        ):

            self._add_flag(
                data,
                "budget_missing"
            )

        # ----------------------------------------------------
        # Score faible
        # ----------------------------------------------------

        score = data.get(
            "score",
            0
        )

        try:

            score = float(score)

            if score < 40:

                self._add_flag(
                    data,
                    "low_score"
                )

        except (
            ValueError,
            TypeError
        ):

            self._add_flag(
                data,
                "invalid_score"
            )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if not data.get("url"):

            self._add_flag(
                data,
                "url_missing"
            )

        # ----------------------------------------------------
        # Deadline courte
        # ----------------------------------------------------

        deadline = data.get("deadline")

        if deadline:

            try:

                deadline_dt = datetime.fromisoformat(
                    str(deadline).replace(
                        "Z",
                        "+00:00"
                    )
                )

                days_left = (
                    deadline_dt.date()
                    - datetime.now().date()
                ).days

                if 0 <= days_left < 15:

                    self._add_flag(
                        data,
                        "deadline_short"
                    )

            except (
                ValueError,
                TypeError,
                OverflowError
            ):
                pass

        # ----------------------------------------------------
        # Informations importantes manquantes
        # ----------------------------------------------------

        important_fields = [
            "title",
            "source",
            "organizer",
            "domain",
            "summary",
        ]

        missing = [
            field
            for field in important_fields
            if not data.get(field)
        ]

        if missing:

            self._add_flag(
                data,
                "partial_info"
            )

            data["missing_fields"] = missing

        # ----------------------------------------------------
        # Score faible + confiance faible
        # ----------------------------------------------------

        confidence = data.get(
            "confidence",
            0
        )

        try:

            if (
                float(score) < 50
                and float(confidence) < 0.70
            ):

                self._add_flag(
                    data,
                    "needs_human_review"
                )

        except (
            ValueError,
            TypeError
        ):
            pass

        # ----------------------------------------------------
        # Nettoyage final
        # ----------------------------------------------------

        flags = data.get(
            "flags",
            []
        )

        if not isinstance(
            flags,
            list
        ):
            flags = []

        data["flags"] = sorted(
            set(
                str(flag)
                for flag in flags
                if flag
            )
        )

        return data

    # ========================================================
    # COHÉRENCE FINALE
    # ========================================================

    def validate_consistency(
        self,
        data: Dict
    ) -> Dict:
        """
        Vérifie la cohérence finale des champs.
        """

        # ----------------------------------------------------
        # Non-actionnable = jamais validated
        # ----------------------------------------------------

        if data.get("is_actionable") is False:

            data["status"] = "rejected"

        # ----------------------------------------------------
        # Rejeté = pas validated
        # ----------------------------------------------------

        if data.get("status") == "rejected":

            data["is_actionable"] = False

        # ----------------------------------------------------
        # URL invalide → human review
        # ----------------------------------------------------

        if "invalid_url" in data.get(
            "flags",
            []
        ):

            if data.get("status") == "validated":

                data["status"] = "to_review"

            self._add_flag(
                data,
                "needs_human_review"
            )

        # ----------------------------------------------------
        # URL générique → human review
        # ----------------------------------------------------

        if "url_generic" in data.get(
            "flags",
            []
        ):

            if data.get("status") == "validated":

                data["status"] = "to_review"

        # ----------------------------------------------------
        # Informations critiques manquantes
        # ----------------------------------------------------

        critical_missing = any(
            data.get(field + "_missing")
            for field in [
                "title",
                "source",
                "domain",
                "summary",
            ]
        )

        if critical_missing:

            data["status"] = "to_review"

            self._add_flag(
                data,
                "needs_human_review"
            )

        return data

    # ========================================================
    # VALIDATION COMPLÈTE
    # ========================================================

    def validate(
        self,
        data: Dict
    ) -> Dict:
        """
        Pipeline complet de validation.
        """

        # ----------------------------------------------------
        # Protection
        # ----------------------------------------------------

        if not isinstance(data, dict):

            return {
                "status": "rejected",
                "is_actionable": False,
                "flags": [
                    "invalid_data"
                ],
                "rejection_reason": (
                    "Donnée reçue invalide."
                ),
            }

        # ----------------------------------------------------
        # 1. Schéma
        # ----------------------------------------------------

        data = self.validate_schema(
            data
        )

        # ----------------------------------------------------
        # 2. Type / actionnabilité
        # ----------------------------------------------------

        data = self.validate_opportunity_type(
            data
        )

        # ----------------------------------------------------
        # 3. Rejet non-opportunité
        # ----------------------------------------------------

        data = self.reject_non_opportunity(
            data
        )

        # ----------------------------------------------------
        # 4. Business
        # ----------------------------------------------------

        data = self.validate_business(
            data
        )

        # ----------------------------------------------------
        # 5. URL
        # ----------------------------------------------------

        data = self.validate_url(
            data
        )

        # ----------------------------------------------------
        # 6. Confidence
        # ----------------------------------------------------

        data = self.validate_confidence(
            data
        )

        # ----------------------------------------------------
        # 7. Flags
        # ----------------------------------------------------

        data = self.flag_data(
            data
        )

        # ----------------------------------------------------
        # 8. Cohérence
        # ----------------------------------------------------

        data = self.validate_consistency(
            data
        )

        return data

    # ========================================================
    # VALIDATION BATCH
    # ========================================================

    def validate_batch(
        self,
        opportunities: List[Dict]
    ) -> List[Dict]:
        """
        Valide un ensemble d'opportunités.

        Retourne uniquement les opportunités :
            - validated
            - to_review

        Les contenus rejetés sont exclus du résultat final.

        Les statistiques sont conservées dans :
            self.last_batch_stats
        """

        validated = []

        stats = {
            "input": 0,
            "validated": 0,
            "to_review": 0,
            "rejected": 0,
            "invalid": 0,
            "articles": 0,
            "not_actionable": 0,
            "expired": 0,
        }

        # ----------------------------------------------------
        # Protection
        # ----------------------------------------------------

        if not isinstance(
            opportunities,
            list
        ):

            self.last_batch_stats = stats

            return []

        stats["input"] = len(
            opportunities
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        for opportunity in opportunities:

            if not isinstance(
                opportunity,
                dict
            ):

                stats["invalid"] += 1

                continue

            try:

                result = self.validate(
                    opportunity
                )

                status = result.get(
                    "status"
                )

                flags = result.get(
                    "flags",
                    []
                )

                # ------------------------------------------------
                # Statistiques
                # ------------------------------------------------

                if (
                    "article_or_guide"
                    in flags
                ):
                    stats["articles"] += 1

                if (
                    "not_actionable"
                    in flags
                ):
                    stats["not_actionable"] += 1

                if (
                    "deadline_passed"
                    in flags
                ):
                    stats["expired"] += 1

                # ------------------------------------------------
                # Résultat
                # ------------------------------------------------

                if status == "validated":

                    stats["validated"] += 1

                    validated.append(
                        result
                    )

                elif status == "to_review":

                    stats["to_review"] += 1

                    validated.append(
                        result
                    )

                else:

                    stats["rejected"] += 1

            except Exception as exc:

                stats["invalid"] += 1

                logger.exception(
                    "❌ Erreur validation opportunité: %s",
                    exc
                )

        # ----------------------------------------------------
        # Sauvegarde statistiques
        # ----------------------------------------------------

        self.last_batch_stats = stats

        logger.info(
            "📊 Validation M1: "
            "%s entrées → "
            "%s validées, "
            "%s à revoir, "
            "%s rejetées",
            stats["input"],
            stats["validated"],
            stats["to_review"],
            stats["rejected"],
        )

        return validated






# # app/services/validation/validator.py
# # ============================================================
# # VALIDATION SERVICE — FORMA-IA
# # ============================================================

# from typing import Dict, List, Any
# from datetime import datetime
# import re

# from app.models.opportunity import DomainEnum


# class Validator:
#     """
#     Validation des opportunités M1.

#     Objectifs :
#     - valider le schéma
#     - vérifier le domaine
#     - vérifier la deadline
#     - détecter les faux articles
#     - détecter les contenus non actionnables
#     - calculer le statut
#     - ajouter des flags
#     """

#     def __init__(self):
#         self.valid_domains = [d.value for d in DomainEnum]

#         # ====================================================
#         # MOTS-CLÉS INDICANT UNE VRAIE OPPORTUNITÉ
#         # ====================================================

#         self.opportunity_keywords = [
#             # Emploi
#             "recrute",
#             "recrutement",
#             "poste",
#             "offre d'emploi",
#             "emploi",
#             "job",
#             "hiring",
#             "vacancy",
#             "vacancies",
#             "candidate",
#             "candidat",

#             # Stage
#             "stage",
#             "stagiaire",
#             "alternance",
#             "internship",

#             # Appels d'offres
#             "appel d'offres",
#             "appel à manifestation",
#             "consultation",
#             "marché public",
#             "prestataire",
#             "soumissionner",
#             "tender",
#             "procurement",
#             "request for proposal",
#             "rfp",

#             # Missions
#             "mission",
#             "freelance",
#             "consultant",
#             "consultance",
#             "recherche un développeur",
#             "recherche un formateur",
#             "recherche un prestataire",

#             # Formation demandée
#             "formation recherchée",
#             "formation demandée",
#             "former",
#             "former des agents",
#             "former les employés",
#             "prestataire de formation",

#             # Projet
#             "développer une plateforme",
#             "développement d'une plateforme",
#             "développement d'application",
#             "développer une application",
#             "intégration",
#             "automatisation",
#             "projet informatique",
#         ]

#         # ====================================================
#         # MOTS-CLÉS DES FAUX POSITIFS
#         # ====================================================

#         self.article_keywords = [
#             "article",
#             "actualités",
#             "actualité",
#             "blog",
#             "guide",
#             "comment devenir",
#             "métiers de l'avenir",
#             "métier d'avenir",
#             "tendance",
#             "tendances",
#             "étude",
#             "étude de marché",
#             "rapport",
#             "analyse",
#             "statistiques",
#             "prévision",
#             "prévisions",
#             "perspectives",
#             "conseils",
#             "définition",
#             "qu'est-ce que",
#             "pourquoi",
#             "comment apprendre",
#             "comment se former",
#             "formation à l'ia",
#             "découvrir les métiers",
#             "opportunités futures",
#             "marché de l'emploi",
#         ]

#     # ========================================================
#     # SCHÉMA
#     # ========================================================

#     def validate_schema(self, data: Dict) -> Dict:

#         required = [
#             "title",
#             "source",
#             "domain",
#             "summary",
#             "score",
#             "confidence",
#         ]

#         for field in required:
#             if field not in data or data[field] is None:
#                 data[f"{field}_missing"] = True

#         # Score
#         if "score" in data and data["score"] is not None:
#             try:
#                 data["score"] = float(data["score"])
#                 data["score"] = max(0, min(100, data["score"]))

#                 # Retour entier si possible
#                 if data["score"].is_integer():
#                     data["score"] = int(data["score"])

#             except (ValueError, TypeError):
#                 data["score"] = 0

#         # Confidence
#         if "confidence" in data and data["confidence"] is not None:
#             try:
#                 data["confidence"] = float(data["confidence"])
#                 data["confidence"] = max(
#                     0.0,
#                     min(1.0, data["confidence"])
#                 )
#             except (ValueError, TypeError):
#                 data["confidence"] = 0.0

#         return data

#     # ========================================================
#     # DÉTECTION VRAIE OPPORTUNITÉ
#     # ========================================================

#     def validate_opportunity_type(self, data: Dict) -> Dict:
#         """
#         Détecte si le résultat représente réellement
#         une opportunité actionnable ou simplement un article.
#         """

#         title = str(data.get("title", "")).lower()
#         summary = str(data.get("summary", "")).lower()
#         reason = str(data.get("reason", "")).lower()

#         text = f"{title} {summary} {reason}"

#         opportunity_type = str(
#             data.get("opportunity_type", "")
#         ).lower()

#         # ----------------------------------------------------
#         # Type explicitement fourni par le LLM
#         # ----------------------------------------------------

#         valid_types = {
#             "emploi",
#             "appel_offres",
#             "prestation",
#             "formation",
#             "projet",
#             "stage",
#         }

#         if opportunity_type in valid_types:
#             data["is_actionable"] = True
#             return data

#         # ----------------------------------------------------
#         # Recherche de mots-clés d'opportunité
#         # ----------------------------------------------------

#         has_opportunity_keyword = any(
#             keyword in text
#             for keyword in self.opportunity_keywords
#         )

#         # ----------------------------------------------------
#         # Recherche de faux positifs
#         # ----------------------------------------------------

#         has_article_keyword = any(
#             keyword in text
#             for keyword in self.article_keywords
#         )

#         # ----------------------------------------------------
#         # Décision
#         # ----------------------------------------------------

#         if has_opportunity_keyword and not has_article_keyword:
#             data["is_actionable"] = True

#         elif has_opportunity_keyword and has_article_keyword:
#             # Ambigu :
#             # on demande une vérification humaine
#             data["is_actionable"] = True

#             data.setdefault("flags", [])
#             data["flags"].append("needs_human_review")

#         else:
#             data["is_actionable"] = False

#             data.setdefault("flags", [])
#             data["flags"].append("not_actionable")

#         return data

#     # ========================================================
#     # REJET ARTICLE
#     # ========================================================

#     def reject_non_opportunity(self, data: Dict) -> Dict:
#         """
#         Rejette les résultats qui ressemblent à des articles,
#         études ou contenus informatifs généraux.
#         """

#         if not data.get("is_actionable", False):

#             data["status"] = "rejected"

#             data.setdefault("flags", [])

#             if "not_actionable" not in data["flags"]:
#                 data["flags"].append("not_actionable")

#             data["rejection_reason"] = (
#                 "Le résultat ne correspond pas à une opportunité "
#                 "professionnelle ou commerciale concrète."
#             )

#         return data

#     # ========================================================
#     # VALIDATION BUSINESS
#     # ========================================================

#     def validate_business(self, data: Dict) -> Dict:

#         # Domaine
#         domain = data.get("domain")

#         if domain:
#             domain = str(domain).lower().strip()

#             if domain not in self.valid_domains:
#                 data["domain"] = "autre"

#                 data.setdefault("flags", [])
#                 data["flags"].append("invalid_domain")

#         # Deadline
#         deadline = data.get("deadline")

#         if deadline:

#             try:
#                 deadline_dt = datetime.fromisoformat(
#                     str(deadline).replace("Z", "")
#                 )

#                 # Comparaison uniquement date
#                 if deadline_dt.date() < datetime.now().date():

#                     data.setdefault("flags", [])
#                     data["flags"].append("deadline_passed")

#             except (ValueError, TypeError):

#                 data["deadline"] = None

#                 data.setdefault("flags", [])
#                 data["flags"].append("invalid_deadline")

#         return data

#     # ========================================================
#     # CONFIDENCE
#     # ========================================================

#     def validate_confidence(self, data: Dict) -> Dict:

#         confidence = data.get("confidence", 0.0)

#         # Une non-opportunité reste rejetée
#         if data.get("is_actionable") is False:
#             data["status"] = "rejected"
#             return data

#         if confidence >= 0.7:

#             data["status"] = "validated"

#         elif confidence >= 0.5:

#             data["status"] = "to_review"

#             data.setdefault("flags", [])
#             data["flags"].append("low_confidence")

#         else:

#             data["status"] = "rejected"

#             data.setdefault("flags", [])
#             data["flags"].append("very_low_confidence")

#         return data

#     # ========================================================
#     # FLAGS
#     # ========================================================

#     def flag_data(self, data: Dict) -> Dict:

#         flags = data.get("flags", [])

#         if not isinstance(flags, list):
#             flags = []

#         # Budget
#         budget = data.get("budget")

#         if not budget or str(budget).lower() == "non précisé":
#             flags.append("budget_missing")

#         # Score
#         if data.get("score", 0) < 40:
#             flags.append("low_score")

#         # URL
#         if not data.get("url"):
#             flags.append("url_missing")

#         # Deadline courte
#         deadline = data.get("deadline")

#         if deadline:

#             try:

#                 deadline_dt = datetime.fromisoformat(
#                     str(deadline).replace("Z", "")
#                 )

#                 days_left = (
#                     deadline_dt.date()
#                     - datetime.now().date()
#                 ).days

#                 if 0 <= days_left < 15:
#                     flags.append("deadline_short")

#             except (ValueError, TypeError):
#                 pass

#         # Informations partielles
#         important_fields = [
#             "title",
#             "source",
#             "organizer",
#             "domain",
#             "summary",
#         ]

#         missing = [
#             field
#             for field in important_fields
#             if not data.get(field)
#         ]

#         if missing:
#             flags.append("partial_info")

#         # Nettoyage des doublons
#         data["flags"] = sorted(set(flags))

#         return data

#     # ========================================================
#     # VALIDATION COMPLÈTE
#     # ========================================================

#     def validate(self, data: Dict) -> Dict:

#         data = self.validate_schema(data)

#         data = self.validate_opportunity_type(data)

#         data = self.reject_non_opportunity(data)

#         data = self.validate_business(data)

#         data = self.validate_confidence(data)

#         data = self.flag_data(data)

#         return data

#     # ========================================================
#     # VALIDATION BATCH
#     # ========================================================

#     def validate_batch(
#         self,
#         opportunities: List[Dict]
#     ) -> List[Dict]:

#         validated = []

#         for opportunity in opportunities:

#             if not isinstance(opportunity, dict):
#                 continue

#             try:

#                 result = self.validate(opportunity)

#                 # ------------------------------------------------
#                 # IMPORTANT :
#                 # On garde uniquement les vraies opportunités
#                 # ------------------------------------------------

#                 if result.get("status") == "rejected":
#                     continue

#                 validated.append(result)

#             except Exception:
#                 continue

#         return validated

