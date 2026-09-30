# app/services/backend_sync/offre_sync.py
# ============================================================
# SYNC M3 — Offres IA → Backend
# ============================================================
# Route Backend utilisée (contrat réel, app/api/v1/endpoints/offre.py) :
#   POST /offres    OffreCreate {titre (obligatoire), client (obligatoire),
#                   trame_technique, trame_financiere, montant_ht,
#                   opportunite_id, tva_taux, statut}
#   GET  /offres/{id}    contrôle après création
#
# trame_technique / trame_financiere = texte lisible extrait de l'IA.
# Le Backend persiste ces colonnes dans la table Offre et les expose
# dans son export Word/PDF.
#
# ⚠️ HITL : à n'appeler qu'APRÈS approbation humaine de l'offre.
# ============================================================

import logging
from typing import Any, Dict, List, Optional

from app.services.backend_sync import base_sync

logger = logging.getLogger(__name__)

_TRAME_MAX = 500_000  # trame_technique / trame_financiere (colonnes TEXT)

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


def build_trame_technique(offre_result: Dict[str, Any]) -> Optional[str]:
    """Texte lisible de la partie technique uniquement."""
    bloc = offre_result.get("offre_technique")
    if not isinstance(bloc, dict) or not bloc:
        return None
    lines = ["OFFRE TECHNIQUE", "=" * 16, *_render(bloc)]
    return "\n".join(lines).strip() or None


def build_trame_financiere(offre_result: Dict[str, Any]) -> Optional[str]:
    """Texte lisible de la partie financière uniquement."""
    bloc = offre_result.get("offre_financiere")
    if not isinstance(bloc, dict) or not bloc:
        return None
    lines = ["OFFRE FINANCIÈRE", "=" * 16, *_render(bloc)]
    return "\n".join(lines).strip() or None


def build_contenu(offre_result: Dict[str, Any]) -> str:
    """Texte complet (technique + financière) — conservé pour compatibilité."""
    parts: List[str] = []
    for titre, cle in (
        ("OFFRE TECHNIQUE", "offre_technique"),
        ("OFFRE FINANCIÈRE", "offre_financiere"),
    ):
        bloc = offre_result.get(cle)
        if isinstance(bloc, dict) and bloc:
            parts += [titre, "=" * len(titre), *_render(bloc), ""]

    if not parts:
        parts = _render(offre_result)

    return "\n".join(parts).strip()


def extract_titre(offre_result: Dict[str, Any]) -> str:
    """Titre de l'offre depuis les inputs IA ou la référence technique."""
    inputs = offre_result.get("_inputs") or {}
    tdr = inputs.get("tdr_data") or {}
    titre = tdr.get("titre") or ""
    if not titre:
        offre_tech = offre_result.get("offre_technique") or {}
        titre = offre_tech.get("titre_offre") or offre_tech.get("reference") or ""
    return titre[:255] if titre else "Offre sans titre"


def extract_client(offre_result: Dict[str, Any]) -> str:
    """Client depuis session_info ou offre_technique."""
    inputs = offre_result.get("_inputs") or {}
    session = inputs.get("session_info") or {}
    client = session.get("client") or ""
    if not client:
        offre_tech = offre_result.get("offre_technique") or {}
        client = offre_tech.get("client") or ""
    return client[:100] if client else "Client inconnu"


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
    titre: str,
    client: str,
    opportunite_id: Optional[str] = None,
    trame_technique: Optional[str] = None,
    trame_financiere: Optional[str] = None,
    montant_ht: Optional[float] = None,
    statut: str = "brouillon",
) -> Dict[str, Any]:
    """
    Enregistre l'offre côté Backend (POST /offres).

    Args:
        titre: titre de l'offre (obligatoire, max 255 car.).
        client: nom du client (obligatoire, max 100 car.).
        opportunite_id: UUID de l'opportunité liée (optionnel).
        trame_technique: texte lisible de la partie technique.
        trame_financiere: texte lisible de la partie financière.
        montant_ht: montant HT en devise locale (> 0).
        statut: statut initial de l'offre (défaut : brouillon).

    Returns:
        Résultat standard (base_sync.new_result).
    """
    result = base_sync.new_result()
    if not result["enabled"]:
        logger.info("ℹ️ Backend sync DÉSACTIVÉ — offre non envoyée")
        return result

    if not titre or not titre.strip():
        result["error"] = "titre manquant ou vide"
        logger.warning("⚠️ Sync offre non envoyée : %s", result["error"])
        return result
    if not client or not client.strip():
        result["error"] = "client manquant ou vide"
        logger.warning("⚠️ Sync offre non envoyée : %s", result["error"])
        return result
    if montant_ht is not None and montant_ht <= 0:
        result["error"] = "montant_ht doit être > 0"
        return result
    if opportunite_id is not None and not base_sync.is_valid_uuid(opportunite_id):
        result["error"] = "opportunite_id invalide (UUID attendu)"
        logger.warning("⚠️ Sync offre non envoyée : %s", result["error"])
        return result

    payload: Dict[str, Any] = {
        "titre": titre[:255],
        "client": client[:100],
        "statut": statut,
    }
    if opportunite_id and base_sync.is_valid_uuid(opportunite_id):
        payload["opportunite_id"] = str(opportunite_id)
    if trame_technique and trame_technique.strip():
        payload["trame_technique"] = trame_technique[:_TRAME_MAX]
    if trame_financiere and trame_financiere.strip():
        payload["trame_financiere"] = trame_financiere[:_TRAME_MAX]
    if montant_ht is not None:
        payload["montant_ht"] = montant_ht

    return await base_sync.post_and_verify(
        "/offres",
        payload,
        verify_path="/offres/{id}",
        label="offre",
    )
