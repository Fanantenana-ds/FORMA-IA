# app/services/backend_sync/tdr_sync.py
# ============================================================
# SYNC TDR → BACKEND (via API)
# ============================================================
# Envoie le TDR généré par M2 vers l'API Backend pour stockage
# dans la table `documents`.
#
# Authentification, re-login sur 401, skip gracieux (404/405) et
# vérification par GET sont gérés par base_sync.py.
#
# Route visée : POST /documents/tdr (TDRRequest, rôles DIRECTION /
# ASSISTANT), restaurée côté Backend. Si elle est absente (404/405),
# la sync est ignorée proprement (skipped=True).
#
# Le Backend ignore les champs qu'il ne connaît pas (« type »,
# « chemin_fichier ») : le chemin des fichiers Word/PDF n'y est pas stocké.
# ============================================================

import json
import logging
from typing import Any, Dict, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)


# ============================================================
# BUILD PAYLOAD
# ============================================================

def _build_tdr_payload(
    tdr_content: Dict[str, Any],
    docx_filename: Optional[str],
    pdf_filename: Optional[str],
    opportunite_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construit le payload pour POST /documents/tdr."""
    return {
        "type": "TDR",
        "contenu": json.dumps(tdr_content, ensure_ascii=False),
        # Le Backend exige client et objectifs non vides (min_length=1)
        "client": tdr_content.get("client") or "Client",
        "objectifs": tdr_content.get("objectif_general") or "Non précisé",
        # Enum Backend FormatExport = PDF | DOCX ("WORD" est refusé : HTTP 422)
        "format_export": "PDF" if pdf_filename else "DOCX",
        # UUID attendu : un identifiant invalide ferait refuser tout le TDR
        "opportunite_id": (
            opportunite_id if base_sync.is_valid_uuid(opportunite_id) else None
        ),
        "chemin_fichier": pdf_filename or docx_filename or "",
    }


# ============================================================
# SYNC
# ============================================================

async def sync_tdr_to_backend(
    tdr_content: Dict[str, Any],
    docx_filename: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    opportunite_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envoie le TDR vers le Backend.

    Retourne :
      {
        "enabled": bool,
        "success": bool,          # lu par tdr_orchestrator
        "sent": bool,
        "skipped": bool,          # endpoint Backend absent (404/405)
        "verified": bool,         # GET de contrôle réussi
        "document_id": str | None,
        "error": str | None
      }
    """
    def _legacy(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "enabled": result["enabled"],
            "success": result["sent"],
            "sent": result["sent"],
            "skipped": result["skipped"],
            "verified": result["verified"],
            "document_id": result["resource_id"],
            "error": result["error"],
        }

    result = base_sync.new_result()

    # 1. Vérifications
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ (BACKEND_SYNC_ENABLED=false)")
        return _legacy(result)

    if not tdr_content:
        result["error"] = "Aucun contenu TDR à synchroniser"
        return _legacy(result)

    # 2. Payload
    payload = _build_tdr_payload(
        tdr_content=tdr_content,
        docx_filename=docx_filename,
        pdf_filename=pdf_filename,
        opportunite_id=opportunite_id,
    )

    logger.info(
        "📤 Sync TDR vers Backend : client='%s', format=%s",
        payload["client"], payload["format_export"]
    )

    # 3. Envoi (auth, re-login, 404 gracieux et GET de contrôle : base_sync)
    sent = await base_sync.post_and_verify(
        "/documents/tdr",
        payload,
        verify_path="/documents/{id}",
        label="TDR",
    )
    return _legacy(sent)
