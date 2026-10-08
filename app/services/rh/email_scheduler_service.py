# app/services/rh/email_scheduler_service.py
# ============================================================
# M4 — SCHEDULER AUTOMATIQUE : lecture candidatures email IMAP
# ============================================================
# Toutes les RH_EMAIL_CHECK_INTERVAL_MINUTES minutes, lit la
# boîte IMAP et lance la présélection A1 pour chaque nouveau CV.
#
# Variables d'environnement :
#   RH_EMAIL_AUTO_ENABLED           "false"  active le scheduler
#   RH_EMAIL_CHECK_INTERVAL_MINUTES "30"     intervalle en minutes (min 5)
# ============================================================

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_tache: asyncio.Task | None = None


def _get_config() -> tuple[bool, int]:
    enabled = os.getenv("RH_EMAIL_AUTO_ENABLED", "false").lower() == "true"
    interval = max(5, int(os.getenv("RH_EMAIL_CHECK_INTERVAL_MINUTES", "30")))
    return enabled, interval


async def _executer_traitement() -> None:
    """Lance le traitement des candidatures email IMAP."""
    from app.orchestrator.rh_orchestrator import get_rh_orchestrator
    from app.services.rh.candidature_service import envoyer_accuse_reception, get_poste, lire_candidatures_email
    from app.services.rh.cv_extractor_service import extraire_texte_cv

    logger.info("=" * 60)
    logger.info("📧 [EmailScheduler] Vérification candidatures IMAP...")
    logger.info("=" * 60)

    try:
        candidatures = lire_candidatures_email()
    except Exception as exc:
        logger.error(f"❌ [EmailScheduler] Erreur lecture IMAP : {exc}")
        return

    if not candidatures:
        logger.info("📭 [EmailScheduler] Aucune nouvelle candidature.")
        return

    logger.info(f"📬 [EmailScheduler] {len(candidatures)} candidature(s) trouvée(s).")
    orchestrator = get_rh_orchestrator()
    traites = 0

    for c in candidatures:
        try:
            poste = get_poste(c["poste_code"])
            if not poste:
                logger.warning(
                    f"   ⚠️  Poste '{c['poste_code']}' introuvable — "
                    f"candidature {c['email']} ignorée."
                )
                continue

            texte, methode, lisible = await extraire_texte_cv(
                c["fichier_contenu"], c["fichier_nom"]
            )
            if not lisible:
                logger.warning(
                    f"   ⚠️  CV illisible ({methode}) — "
                    f"candidature {c['email']} ignorée."
                )
                continue

            result = await orchestrator.preselectionner_cv(
                cv_texte=texte,
                criteres_poste=poste["criteres"],
            )

            await envoyer_accuse_reception(
                nom_candidat=c["nom"],
                email_candidat=c["email"],
                titre_poste=poste["titre"],
            )

            traites += 1
            logger.info(
                f"   ✅ {c['nom']} ({c['email']}) → "
                f"review={result.get('_review_id')} "
                f"score={result.get('score_global')} "
                f"décision={result.get('decision')}"
            )

        except Exception as exc:
            logger.error(
                f"   ❌ Erreur traitement {c.get('email')} : {exc}"
            )

    logger.info(
        f"✅ [EmailScheduler] Terminé — {traites}/{len(candidatures)} traité(s)."
    )


async def _boucle(interval_minutes: int) -> None:
    """Boucle infinie : attend l'intervalle puis traite."""
    interval_seconds = interval_minutes * 60
    logger.info(
        f"🔄 [EmailScheduler] Démarré — "
        f"vérification toutes les {interval_minutes} min."
    )

    # Premier passage après 60 secondes (laisse le temps au serveur de démarrer)
    await asyncio.sleep(60)

    while True:
        debut = datetime.now()
        try:
            await _executer_traitement()
        except Exception as exc:
            logger.error(f"❌ [EmailScheduler] Erreur inattendue : {exc}")

        elapsed = (datetime.now() - debut).total_seconds()
        attente = max(0, interval_seconds - elapsed)
        logger.info(
            f"⏳ [EmailScheduler] Prochain passage dans "
            f"{interval_minutes} min ({attente:.0f}s)."
        )
        await asyncio.sleep(attente)


def demarrer(app=None) -> asyncio.Task | None:
    """
    Démarre le scheduler si RH_EMAIL_AUTO_ENABLED=true.
    Appeler depuis le startup FastAPI.
    """
    global _tache
    enabled, interval = _get_config()

    if not enabled:
        logger.info(
            "📧 [EmailScheduler] Désactivé "
            "(RH_EMAIL_AUTO_ENABLED=false dans .env)."
        )
        return None

    if _tache is not None and not _tache.done():
        logger.warning("⚠️  [EmailScheduler] Déjà en cours.")
        return _tache

    _tache = asyncio.create_task(_boucle(interval))
    logger.info(
        f"✅ [EmailScheduler] Tâche créée — "
        f"intervalle={interval} min."
    )
    return _tache


async def arreter() -> None:
    """Arrête le scheduler proprement. Appeler depuis le shutdown FastAPI."""
    global _tache
    if _tache is not None and not _tache.done():
        _tache.cancel()
        try:
            await _tache
        except asyncio.CancelledError:
            pass
        logger.info("🛑 [EmailScheduler] Arrêté.")
    _tache = None


def statut() -> dict:
    """Retourne l'état courant du scheduler."""
    enabled, interval = _get_config()
    return {
        "enabled": enabled,
        "interval_minutes": interval,
        "running": _tache is not None and not _tache.done(),
    }
