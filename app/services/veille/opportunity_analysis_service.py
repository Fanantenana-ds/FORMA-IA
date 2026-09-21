# app/services/veille/opportunity_analysis_service.py
# ============================================================
# M1 — ANALYSE IA D'UNE OPPORTUNITÉ DÉJÀ ENREGISTRÉE
# ============================================================
# Point d'intégration : POST /api/v1/opportunites/{id}/analyse
# (contrat : docs/contrat-integration-ia.md, « point B »).
#
# Ce service remplace le résultat codé en dur (score 0.0) de la route.
# Il réutilise les briques M1 existantes, SANS le pipeline complet
# (la sync Backend de M1 recréerait l'opportunité en doublon) :
#
#   1. Extraction LLM (optionnelle) : objet, budget, échéance,
#      organisme lus dans le texte brut  → LLMAnalysisService
#   2. Classification du domaine (Python) → ClassificationService
#   3. Score 0-100 (Python)               → ScoringService
#
# Le LLM comprend, Python décide : le score reste déterministe.
# Le contrat Backend attend un score entre 0.0 et 1.0 : le score
# M1 (0-100) est donc divisé par 100.
#
# Dégradation gracieuse : sans clé Groq, en cas d'erreur ou de
# dépassement de délai, l'analyse continue en Python pur à partir
# des champs déjà renseignés + du texte (jamais d'échec de la route
# à cause du LLM).
#
# Variables d'environnement :
#   ANALYSE_USE_LLM      (défaut "true")  active l'extraction LLM
#   ANALYSE_LLM_TIMEOUT  (défaut "30")    délai max en secondes
# ============================================================

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.opportunite import Domaine
from app.services.backend_sync.opportunity_sync import (
    _map_domain,
    _parse_budget,
    _parse_deadline,
)
from app.services.veille.classification_service import ClassificationService
from app.services.veille.llm_analysis_service import (
    LLMAnalysisService,
    MAX_SOURCE_CHARS_EACH,
    MAX_SOURCE_CHARS_TOTAL,
)
from app.services.veille.scoring_service import ScoringService

logger = logging.getLogger(__name__)

MAX_TITRE_CHARS = 255       # colonne opportunites.objet = String(255)
MAX_RESUME_CHARS = 4000     # texte pris en compte par le scoring


def _llm_actif() -> bool:
    return os.getenv("ANALYSE_USE_LLM", "true").strip().lower() in {
        "1", "true", "yes", "oui",
    }


def _timeout_llm() -> float:
    try:
        return float(os.getenv("ANALYSE_LLM_TIMEOUT", "30"))
    except ValueError:
        return 30.0


def _creer_llm_service() -> LLMAnalysisService:
    """
    Une instance par analyse (pas de cache) : le client AsyncOpenAI est lié
    à la boucle asyncio qui l'a créé, et chaque analyse ouvre la sienne.
    """
    return LLMAnalysisService()


def _run(coro):
    """Exécute une coroutine depuis du code synchrone (route FastAPI en `def`)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Appelé depuis une boucle déjà active : exécution dans un thread dédié.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _titre_depuis_contenu(contenu: str) -> str:
    for ligne in contenu.splitlines():
        ligne = ligne.strip()
        if ligne:
            return ligne[:MAX_TITRE_CHARS]
    return ""


def _decouper_en_sources(contenu: str) -> List[Dict[str, Any]]:
    """Même découpage que M1 « texte collé » : blocs bornés pour le prompt."""
    sources: List[Dict[str, Any]] = []
    total = 0
    for debut in range(0, len(contenu), MAX_SOURCE_CHARS_EACH):
        bloc = contenu[debut:debut + MAX_SOURCE_CHARS_EACH]
        if total + len(bloc) > MAX_SOURCE_CHARS_TOTAL:
            break
        sources.append({
            "title": f"Opportunité (partie {len(sources) + 1})",
            "url": "",
            "content": bloc,
        })
        total += len(bloc)
    return sources or [{"title": "Opportunité", "url": "", "content": contenu[:MAX_SOURCE_CHARS_EACH]}]


def _date_vers_datetime(date_iso: Optional[str]) -> Optional[datetime]:
    """'YYYY-MM-DD' → datetime UTC (le contrat recommande un fuseau explicite)."""
    if not date_iso:
        return None
    try:
        return datetime.fromisoformat(date_iso).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class OpportuniteAnalyseIAService:
    """Analyse IA (extraction + classification + scoring) d'une opportunité."""

    def __init__(self) -> None:
        self.classification = ClassificationService()
        self.scoring = ScoringService()

    # --------------------------------------------------------
    # EXTRACTION LLM (optionnelle)
    # --------------------------------------------------------

    async def _extraire_par_llm(self, contenu: str, source: str) -> Optional[Dict[str, Any]]:
        """Retourne la première opportunité lue par le LLM, ou None."""
        try:
            llm = _creer_llm_service()
            reponse = await asyncio.wait_for(
                llm.analyze(
                    query=(
                        "Analyse directe d'un document fourni par l'utilisateur "
                        f"(source : {source}). Pas de recherche web associée."
                    ),
                    results=_decouper_en_sources(contenu),
                ),
                timeout=_timeout_llm(),
            )
        except Exception as exc:  # réseau, quota, délai, clé absente…
            logger.warning("⚠️ Analyse LLM indisponible (%s) — scoring Python seul",
                           type(exc).__name__)
            return None

        opportunites = (reponse or {}).get("opportunities") or []
        return opportunites[0] if opportunites and isinstance(opportunites[0], dict) else None

    # --------------------------------------------------------
    # ANALYSE
    # --------------------------------------------------------

    async def analyser_async(
        self,
        *,
        contenu: str,
        objet: Optional[str] = None,
        budget: Optional[float] = None,
        echeance: Optional[datetime] = None,
        domaine: Optional[Domaine] = None,
        source: str = "TEXTE",
    ) -> Dict[str, Any]:
        contenu = str(contenu or "").strip()

        # Valeurs déjà renseignées par l'utilisateur : jamais écrasées.
        extrait: Optional[Dict[str, Any]] = None
        if contenu and _llm_actif():
            extrait = await self._extraire_par_llm(contenu, source)
        extrait = extrait or {}

        objet_final = (
            (objet or "").strip()
            or str(extrait.get("title") or "").strip()
            or _titre_depuis_contenu(contenu)
            or "Opportunité sans intitulé"
        )[:MAX_TITRE_CHARS]

        budget_final: Optional[float] = budget if budget else (
            _parse_budget(extrait.get("budget")) or None
        )

        echeance_iso = (
            echeance.isoformat() if echeance else _parse_deadline(extrait.get("deadline"))
        )
        echeance_final = echeance or _date_vers_datetime(echeance_iso)

        # ---- Classification (Python) : le domaine saisi prime ----
        entree: Dict[str, Any] = {
            "title": objet_final,
            "summary": contenu[:MAX_RESUME_CHARS],
            "url": "",
            "organizer": extrait.get("organizer"),
        }
        if domaine is not None:
            domaine_m1 = domaine.value.lower()
        else:
            domaine_m1 = self.classification.classify(entree)["domain"]
        domaine_final = Domaine[_map_domain(domaine_m1)]

        # ---- Scoring (Python) ----
        # Le budget est passé en entier : le scoring M1 lit les chiffres d'une
        # chaîne, et "5000000.0" serait lu 50 000 000 (×10).
        entree.update({
            "domain": domaine_m1,
            "budget": str(int(budget_final)) if budget_final else None,
            "deadline": echeance_iso,
        })
        resultat = self.scoring.score(entree)

        return {
            "objet": objet_final,
            "budget": budget_final,
            "echeance": echeance_final,
            "domaine": domaine_final,
            # Contrat Backend : 0.0 <= score_pertinence <= 1.0
            "score_pertinence": round(resultat["score"] / 100, 2),
            "score": resultat["score"],
            "niveau": resultat["level"],
            "recommandation": resultat["recommendation"],
            "raisons": resultat["details"],
            "llm_utilise": bool(extrait),
        }

    def analyser(self, **kwargs) -> Dict[str, Any]:
        """Version synchrone (les routes FastAPI de ce projet sont en `def`)."""
        return _run(self.analyser_async(**kwargs))
