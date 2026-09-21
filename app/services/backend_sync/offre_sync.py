# app/services/backend_sync/offre_sync.py
# ============================================================
# SYNC M3 — Offres IA → Backend
# ============================================================
# Route Backend utilisée (contrat réel, app/api/v1/endpoints/document.py) :
#   POST /documents/offre   OffreRequest {opportunite_id (UUID, obligatoire),
#                           montant (>= 0), contenu (texte, <= 500 000 car.)}
#                           rôle DIRECTION/ASSISTANT
#   GET  /documents/{id}    contrôle après création
#
# `contenu` = offre technique + financière générées par l'IA. Le
# Backend imprime ce texte tel quel dans son export Word/PDF : on lui
# envoie donc un TEXTE LISIBLE (build_contenu) et non un bloc JSON.
# Sans `contenu`, le Backend retombe sur son texte par défaut.
#
# ⚠️ HITL : à n'appeler qu'APRÈS approbation humaine de l'offre.
# ============================================================

import logging
from typing import Any, Dict, List, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_CONTENU_MAX = 500_000  # OffreRequest.contenu (max_length côté Backend)

# Clés internes de l'IA, sans intérêt pour le lecteur de l'offre
_CLES_IGNOREES = {"success", "metadata", "reviews_individuels"}

# Libellés français (avec accents) des clés produites par les agents M3.
# Clé inconnue → libellé déduit du nom de la clé (voir _libelle).
_LIBELLES = {
    "approche_methodologique": "Approche méthodologique",
    "architecture_technique": "Architecture technique",
    "base_donnees": "Base de données",
    "comprehension_besoin": "Compréhension du besoin",
    "confidentialite": "Confidentialité",
    "conformite": "Conformité",
    "cv_formateur": "CV du formateur",
    "date_emission": "Date d'émission",
    "dates_proposees": "Dates proposées",
    "domaines_expertise": "Domaines d'expertise",
    "duree": "Durée",
    "duree_totale": "Durée totale",
    "ia_ml": "IA / ML",
    "materiel": "Matériel",
    "methode": "Méthode",
    "modalites": "Modalités",
    "numero": "Numéro",
    "objectifs_client": "Objectifs du client",
    "outils_supports": "Outils et supports",
    "pedagogie": "Pédagogie",
    "presentation_structure": "Présentation de la structure",
    "public_cible": "Public cible",
    "qualite": "Qualité",
    "reference": "Référence",
    "references": "Références",
    "role": "Rôle",
    "securite": "Sécurité",
    "stack": "Stack technique",
    "titre_offre": "Titre de l'offre",
    "administration_pourcentage": "Administration (%)",
    "conditions_financieres": "Conditions financières",
    "delai": "Délai",
    "details_couts": "Détail des coûts",
    "echeancier": "Échéancier",
    "forfait_participant": "Forfait par participant",
    "honoraires_formateur": "Honoraires du formateur",
    "libelle": "Libellé",
    "location_salle": "Location de salle",
    "modalites_paiement": "Modalités de paiement",
    "nb_jours": "Nombre de jours",
    "nb_participants": "Nombre de participants",
    "net_a_payer": "Net à payer",
    "penalites_retard": "Pénalités de retard",
    "recapitulatif": "Récapitulatif",
    "sous_total": "Sous-total",
    "sous_total_ht": "Sous-total HT",
    "supports_pedagogiques": "Supports pédagogiques",
    "tarif_journalier": "Tarif journalier",
    "total_ttc": "Total TTC",
    "tva": "TVA",
    "tva_taux": "Taux de TVA",
    "validite_offre": "Validité de l'offre",
}


def _libelle(key: Any) -> str:
    name = str(key)
    return _LIBELLES.get(name) or name.replace("_", " ").capitalize()


def _render(value: Any, indent: int = 0) -> List[str]:
    """Rend un dict/une liste en lignes de texte indentées (générique)."""
    pad = "  " * indent
    lines: List[str] = []

    if isinstance(value, dict):
        for key, val in value.items():
            if str(key).startswith("_") or key in _CLES_IGNOREES:
                continue
            if val is None or val == "" or val == [] or val == {}:
                continue
            label = _libelle(key)
            if isinstance(val, (dict, list)):
                lines.append(f"{pad}{label} :")
                lines.extend(_render(val, indent + 1))
            else:
                lines.append(f"{pad}{label} : {val}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)):
                sub = _render(item, indent + 1)
                if sub:
                    lines.append(f"{pad}-")
                    lines.extend(sub)
            elif item is not None and item != "":
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{value}")

    return lines


def build_contenu(offre_result: Dict[str, Any]) -> str:
    """
    Texte lisible de l'offre à partir du résultat de
    OffreOrchestrator.generate_complete() (offre_technique + offre_financiere)
    ou d'une offre seule (generate_technique / generate_financiere).
    """
    parts: List[str] = []
    for titre, cle in (
        ("OFFRE TECHNIQUE", "offre_technique"),
        ("OFFRE FINANCIÈRE", "offre_financiere"),
    ):
        bloc = offre_result.get(cle)
        if isinstance(bloc, dict) and bloc:
            parts += [titre, "=" * len(titre), *_render(bloc), ""]

    if not parts:  # une seule offre fournie directement
        parts = _render(offre_result)

    return "\n".join(parts).strip()


def extract_montant(offre_result: Dict[str, Any]) -> Optional[float]:
    """
    Extrait le montant proposé au client depuis le résultat de
    OffreOrchestrator.generate_complete() :
    net à payer, à défaut total TTC, à défaut sous-total HT.
    """
    candidates = [
        offre_result.get("resume_financier") or {},
        (offre_result.get("offre_financiere") or {}).get("recapitulatif") or {},
        offre_result.get("recapitulatif") or {},
    ]
    for source in candidates:
        for key in ("net_a_payer", "total_ttc", "sous_total_ht"):
            value = source.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                return float(value)
    return None


async def sync_offre_to_backend(
    opportunite_id: Optional[str],
    montant: Optional[float] = None,
    contenu: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enregistre l'offre côté Backend (POST /documents/offre).

    Args:
        opportunite_id: UUID de l'opportunité Backend liée (obligatoire
            côté Backend). Absent ou invalide → aucun envoi.
        montant: montant proposé (voir extract_montant()).
        contenu: texte de l'offre (voir build_contenu()) ; tronqué à
            500 000 caractères. Absent → texte par défaut du Backend.

    Returns:
        Résultat standard (base_sync.new_result).
    """
    result = base_sync.new_result()
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — offre non envoyée")
        return result

    if not base_sync.is_valid_uuid(opportunite_id):
        result["error"] = "opportunite_id manquant ou invalide (UUID attendu)"
        logger.warning("⚠️ Sync offre non envoyée : %s", result["error"])
        return result
    if montant is not None and montant < 0:
        result["error"] = "montant doit être >= 0"
        return result

    payload: Dict[str, Any] = {"opportunite_id": str(opportunite_id)}
    if montant is not None:
        payload["montant"] = montant
    if contenu and contenu.strip():
        payload["contenu"] = contenu[:_CONTENU_MAX]

    return await base_sync.post_and_verify(
        "/documents/offre",
        payload,
        verify_path="/documents/{id}",
        label="offre",
    )
