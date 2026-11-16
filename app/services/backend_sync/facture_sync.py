# app/services/backend_sync/facture_sync.py
# ============================================================
# SYNC M7 — Facturation IA ↔ Backend
# ============================================================
# Routes Backend utilisées (contrat réel, app/api/v1/endpoints/facture.py) :
#   POST /factures               FactureCreate {client, montant (HT, > 0),
#                                tva_taux, date_echeance}  rôle DIRECTION/COMPTABLE
#   GET  /factures/{id}          FactureResponse (paiements inclus)
#   POST /factures/{id}/relances RelanceIACreate {niveau, objet, texte, review_id}
#                                rôle DIRECTION/COMPTABLE — retourne RelanceIAResponse
#
# Le numéro de facture, le TTC et le statut sont calculés par le Backend.
#
# ⚠️ HITL : n'appeler sync_*() qu'APRÈS approbation humaine.
# ============================================================

import logging
from typing import Any

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_CLIENT_MAX = 50  # Facture.client = String(50)


async def sync_facture_to_backend(
    client: str,
    montant_ht: float,
    tva_taux: float = 20.0,
    date_echeance: str | None = None,
) -> dict[str, Any]:
    """
    Crée la facture côté Backend (POST /factures).

    Args:
        client: nom du client (tronqué à 50 caractères).
        montant_ht: montant HT à facturer (> 0) — utiliser
            `ht_apres_remise` de FactureCalculatorService.calculer().
        tva_taux: taux de TVA en %.
        date_echeance: "YYYY-MM-DD" (optionnel).

    Returns:
        Résultat standard (base_sync.new_result) + "numero" si créée.
    """
    result = base_sync.new_result(numero=None)
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — facture non envoyée")
        return result

    client_name = base_sync.truncate(client, _CLIENT_MAX)
    if not client_name:
        result["error"] = "Client manquant"
        return result
    if not montant_ht or montant_ht <= 0:
        result["error"] = "montant_ht doit être > 0"
        return result

    payload: dict[str, Any] = {
        "client": client_name,
        "montant": montant_ht,
        "tva_taux": tva_taux,
    }
    if date_echeance:
        payload["date_echeance"] = str(date_echeance)[:10]

    sent = await base_sync.post_and_verify(
        "/factures", payload, label="facture"
    )
    result.update(sent)
    if isinstance(sent.get("data"), dict):
        result["numero"] = sent["data"].get("numero")
    return result


async def sync_relance_to_backend(
    facture_id: str,
    niveau: str,
    objet: str,
    texte: str,
    review_id: str | None = None,
) -> dict[str, Any]:
    """
    Enregistre la relance côté Backend (POST /factures/{id}/relances).

    Args:
        facture_id: UUID de la facture concernée.
        niveau: niveau de relance ("1", "2", "3"…).
        objet: objet/sujet de la relance.
        texte: corps du message de relance.
        review_id: ID du review HITL approuvé (optionnel).

    Returns:
        Résultat standard base_sync.new_result.
    """
    result = base_sync.new_result()
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — relance non envoyée")
        return result

    if not base_sync.is_valid_uuid(facture_id):
        result["error"] = f"facture_id invalide : {facture_id}"
        return result

    payload: dict[str, Any] = {
        "niveau": str(niveau),
        "objet": str(objet)[:255],
        "texte": str(texte),
    }
    if review_id:
        payload["review_id"] = review_id

    sent = await base_sync.post_and_verify(
        f"/factures/{facture_id}/relances", payload, label="relance"
    )
    result.update(sent)
    return result


async def fetch_facture(facture_id: str) -> dict[str, Any] | None:
    """
    Lit une facture Backend (GET /factures/{id}) — statut, TTC, paiements,
    échéance — pour préparer une relance.

    Returns:
        Le dict Backend, ou None (id invalide, introuvable, erreur).
    """
    if not base_sync.is_valid_uuid(facture_id):
        logger.warning("⚠️ fetch_facture : facture_id n'est pas un UUID")
        return None

    response = await base_sync.backend_request(
        "GET", f"/factures/{facture_id}"
    )
    if response["ok"] and isinstance(response["data"], dict):
        return response["data"]

    logger.warning("⚠️ Facture non récupérée : %s", response["error"])
    return None
