# app/orchestrator/rh_orchestrator.py
# ============================================================
# ORCHESTRATEUR M4 — Assistance RH (bonus)
# ============================================================
# 5 agents :
#   A1 — CvPreselecteurService      (présélection CV → HITL)
#   A2 — EntretienService           (CR entretien → HITL)
#   A3 — EmailRhService             (brouillon email → HITL)
#   A4 — ContratFormateurService    (contrat formateur → HITL)
#   A5 — EvaluationFormateurService (évaluation post-session → interne)
#
# Liaison pipeline :
#   A1 → vivier formateurs → M3 Préparation (formateur_id)
#   A4 → lit données M3 (formateur + session) pour le contrat
#   A5 → lit résultats M5 (satisfaction + présences) → enrichit profil
# ============================================================

import os
import time
import logging
from typing import Any, Dict, List, Optional

from app.services.backend_sync import rh_sync, review_sync
from app.services.rh import (
    CvPreselecteurService,
    EntretienService,
    EmailRhService,
    ContratFormateurService,
    EvaluationFormateurService,
)

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class RhOrchestrator:
    """Orchestrateur du module M4 — Assistance RH."""

    def __init__(self):
        vlog("=" * 70)
        vlog("🚀 Initialisation de RhOrchestrator...")

        self.preselection = self._safe_init(CvPreselecteurService, "Agent M4-1 — CvPreselecteur")
        self.entretien    = self._safe_init(EntretienService,        "Agent M4-2 — Entretien")
        self.email        = self._safe_init(EmailRhService,          "Agent M4-3 — EmailRh")
        self.contrat      = self._safe_init(ContratFormateurService, "Agent M4-4 — ContratFormateur")
        self.evaluation   = self._safe_init(EvaluationFormateurService, "Agent M4-5 — EvaluationFormateur")

        self._log_startup_summary()

    def _safe_init(self, cls, label: str):
        try:
            instance = cls()
            vlog(f"   ✅ {label} prêt")
            return instance
        except Exception as e:
            logger.error(f"   ❌ {label} indisponible : {type(e).__name__} — {e}")
            return None

    def _log_startup_summary(self) -> None:
        agents = {
            "CvPreselecteur":      self.preselection,
            "Entretien":           self.entretien,
            "EmailRh":             self.email,
            "ContratFormateur":    self.contrat,
            "EvaluationFormateur": self.evaluation,
        }
        actifs = [k for k, v in agents.items() if v]
        vlog(f"📊 Bilan : {len(actifs)}/5 agents actifs — {actifs}")
        vlog("✅ RhOrchestrator initialisé.")

    def _start(self, method: str, **kw) -> float:
        vlog("=" * 70)
        vlog(f"🎬 [RhOrchestrator] → {method}()")
        for k, v in kw.items():
            vlog(f"   {k} : {v}")
        return time.perf_counter()

    def _end(self, method: str, t0: float, **kw) -> float:
        elapsed = round(time.perf_counter() - t0, 2)
        vlog(f"✅ [RhOrchestrator] {method}() — {elapsed}s")
        return elapsed

    # =========================================================================
    # A1 — Présélection CV
    # =========================================================================

    async def preselectionner_cv(
        self,
        cv_texte: str,
        criteres_poste: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyse un CV et produit une fiche de présélection + review HITL.

        Args:
            cv_texte: Texte brut du CV (copié/collé ou extrait PDF).
            criteres_poste: {"domaine", "competences", "niveau", ...}

        Returns:
            Fiche présélection JSON + _review_id + _review_status.
        """
        if not self.preselection:
            raise RuntimeError("Agent M4-1 (présélection) non disponible.")
        t0 = self._start("preselectionner_cv", Domaine=criteres_poste.get("domaine"))
        result = await self.preselection.generate(cv_texte, criteres_poste)
        self._end("preselectionner_cv", t0)
        return result

    # =========================================================================
    # A2 — Compte-rendu entretien
    # =========================================================================

    async def rediger_cr_entretien(
        self,
        notes_brutes: str,
        candidat: str,
        poste: str,
        interviewers: Optional[List[str]] = None,
        date_entretien: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rédige un compte-rendu d'entretien structuré + review HITL.

        Args:
            notes_brutes: Notes prises pendant/après l'entretien.
            candidat: Nom du candidat.
            poste: Intitulé du poste / domaine.
            interviewers: Liste des personnes présentes.
            date_entretien: "YYYY-MM-DD".
        """
        if not self.entretien:
            raise RuntimeError("Agent M4-2 (entretien) non disponible.")
        t0 = self._start("rediger_cr_entretien", Candidat=candidat, Poste=poste)
        result = await self.entretien.generate(
            notes_brutes=notes_brutes,
            candidat=candidat,
            poste=poste,
            interviewers=interviewers,
            date_entretien=date_entretien,
        )
        self._end("rediger_cr_entretien", t0)
        return result

    # =========================================================================
    # A3 — Brouillon email RH
    # =========================================================================

    async def rediger_email_rh(
        self,
        type_email: str,
        destinataire: str,
        contexte: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rédige un brouillon d'email RH + review HITL.

        Args:
            type_email: ACCEPTATION | REFUS | DEMANDE_INFO |
                        CONVOCATION | PROPOSITION_MISSION
            destinataire: Nom du destinataire.
            contexte: Informations supplémentaires pour personnaliser l'email.
        """
        if not self.email:
            raise RuntimeError("Agent M4-3 (email) non disponible.")
        t0 = self._start("rediger_email_rh", Type=type_email, Destinataire=destinataire)
        result = await self.email.generate(
            type_email=type_email,
            destinataire=destinataire,
            contexte=contexte,
        )
        self._end("rediger_email_rh", t0)
        return result

    # =========================================================================
    # A4 — Contrat formateur
    # =========================================================================

    async def generer_contrat_formateur(
        self,
        formateur: Dict[str, Any],
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Génère un contrat de prestation formateur + review HITL.

        Liaison M3 : les données formateur et session proviennent de la
        Préparation (M3). Passer les données directement dans le payload.

        Args:
            formateur: {"nom", "adresse", "telephone", "email", "tarif_journalier"}
            session: {"titre", "dates", "nb_jours", "lieu", "nb_participants", "description"}
        """
        if not self.contrat:
            raise RuntimeError("Agent M4-4 (contrat formateur) non disponible.")
        t0 = self._start(
            "generer_contrat_formateur",
            Formateur=formateur.get("nom"),
            Session=session.get("titre"),
        )
        result = await self.contrat.generate(formateur=formateur, session=session)
        self._end("generer_contrat_formateur", t0)
        return result

    # =========================================================================
    # A5 — Évaluation formateur post-session
    # =========================================================================

    async def evaluer_formateur(
        self,
        formateur: str,
        session: str,
        donnees_session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Évalue un formateur après une session (données M5) — document interne.

        Liaison M5 : donnees_session contient les résultats des agents M5
        (satisfaction, présences, rapport).

        Args:
            formateur: Nom du formateur.
            session: Titre de la session.
            donnees_session: {
                "satisfaction": {"score_moyen": 4.2, "points_positifs": [...], ...},
                "presences":    {"taux_moyen_pct": 88.5, "anomalies": False},
                "rapport":      "extrait du rapport final (optionnel)"
            }
        """
        if not self.evaluation:
            raise RuntimeError("Agent M4-5 (évaluation formateur) non disponible.")
        t0 = self._start("evaluer_formateur", Formateur=formateur, Session=session)
        result = await self.evaluation.generate(
            formateur=formateur,
            session=session,
            donnees_session=donnees_session,
        )
        self._end("evaluer_formateur", t0)
        return result

    # =========================================================================
    # SYNC BACKEND — A1 : Candidat après présélection approuvée
    # =========================================================================

    async def synchroniser_candidat(
        self,
        review_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Enregistre un candidat côté Backend après approbation HITL A1.
        (POST /rh/candidats)
        """
        t0 = self._start("synchroniser_candidat", Review=review_id)
        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_m4_preselection",)
        )
        data = review.get("data") or {}

        async def _envoyer() -> Dict[str, Any]:
            return await rh_sync.sync_candidat_to_backend(
                nom=str(data.get("nom_candidat") or "Candidat inconnu")[:200],
                poste_vise=str(data.get("poste_vise") or "N/A")[:200],
                score_preselection=data.get("score_global"),
                decision_preselection=str(data.get("decision") or "")[:50] or None,
                review_id_preselection=review_id,
            )

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._end("synchroniser_candidat", t0)
        return result

    # =========================================================================
    # SYNC BACKEND — A2 : CR entretien après approbation
    # =========================================================================

    async def synchroniser_entretien_cr(
        self,
        review_id: str,
        candidat_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Persiste le CR d'entretien côté Backend après approbation HITL A2.
        (POST /rh/candidats/{id}/entretiens)
        """
        t0 = self._start(
            "synchroniser_entretien_cr", Review=review_id, Candidat=candidat_id
        )
        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_m4_entretien",)
        )
        data = review.get("data") or {}

        async def _envoyer() -> Dict[str, Any]:
            return await rh_sync.sync_entretien_cr_to_backend(
                candidat_id=candidat_id,
                compte_rendu=str(data.get("resume_entretien") or "")[:10000],
                decision=str(data.get("decision") or "")[:50] or None,
                review_id_entretien=review_id,
            )

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._end("synchroniser_entretien_cr", t0)
        return result

    # =========================================================================
    # SYNC BACKEND — A5 : Évaluation formateur (POST ou PATCH)
    # =========================================================================

    async def synchroniser_evaluation_formateur(
        self,
        review_id: str,
        formateur_id: str,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Met à jour le profil formateur Backend après évaluation A5.
        (PATCH /rh/formateurs/{id})

        Args:
            formateur_id: UUID Backend du formateur (obligatoire).
        """
        t0 = self._start(
            "synchroniser_evaluation_formateur",
            Review=review_id, FormateurID=formateur_id
        )
        review = review_sync.load_approved_review(
            review_id, agent_ids=("agent_m4_evaluation",)
        )
        data = review.get("data") or {}

        async def _envoyer() -> Dict[str, Any]:
            return await rh_sync.sync_evaluation_formateur(
                formateur_id=formateur_id,
                score_moyen=data.get("score_global"),
                nb_sessions=None,
                recommandation=str(data.get("recommandation") or "")[:200] or None,
                notes_internes=str(data.get("justification_recommandation") or "")[:2000] or None,
            )

        result = await review_sync.sync_once(review_id, _envoyer, force=force)
        self._end("synchroniser_evaluation_formateur", t0)
        return result


# =============================================================================
# SINGLETON
# =============================================================================

_rh_orchestrator_instance: Optional[RhOrchestrator] = None


def get_rh_orchestrator() -> RhOrchestrator:
    global _rh_orchestrator_instance
    if _rh_orchestrator_instance is None:
        logger.info("🔧 Création du singleton RhOrchestrator...")
        _rh_orchestrator_instance = RhOrchestrator()
    return _rh_orchestrator_instance
