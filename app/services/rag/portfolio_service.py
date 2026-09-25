# app/services/rag/portfolio_service.py
# ============================================================
# SERVICE — Portfolio (RAG, Étape G)
# ============================================================
# Totaux et données chiffrées : Python pur, EXCLUSIVEMENT depuis le
# catalogue (mission). Le LLM ne rédige QUE les descriptions, à partir
# des chunks RAG déjà indexés.
# ============================================================

import logging
from typing import Any, Dict, List, Optional

import yaml

from app.services.rag.catalogue_service import Formation, Realisation, CHEMIN_CATALOGUE_DEFAUT
from app.services.rag.knowledge_repository import KnowledgeRepository
from app.services.backend_sync.formation_sync import fetch_session

logger = logging.getLogger(__name__)

CHEMIN_PRESENTATION_ALTIORA = CHEMIN_CATALOGUE_DEFAUT.parent / "altiora_presentation.yaml"
TEXTE_A_COMPLETER = "[À compléter]"
TEXTE_A_COMPLETER_ALTIORA = "[À compléter par ALTIORA]"


def lire_presentation_altiora() -> str:
    """Texte FIXE (jamais rédigé par le LLM) — mission §Portfolio point 1."""
    if not CHEMIN_PRESENTATION_ALTIORA.exists():
        return TEXTE_A_COMPLETER_ALTIORA
    with open(CHEMIN_PRESENTATION_ALTIORA, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    texte = (data.get("presentation") or "").strip()
    return texte or TEXTE_A_COMPLETER_ALTIORA


def calculer_synthese_chiffree(formations: List[Formation]) -> Dict[str, Any]:
    """Python pur, aucune IA (mission §Portfolio point 2)."""
    realisations = [(f, r) for f in formations for r in f.realisations]

    identifiants_clients = {
        (r.secteur_public if r.client_confidentiel else r.client) or "?"
        for _, r in realisations
    }
    annees = [r.annee for _, r in realisations if r.annee]

    return {
        "nb_formations_realisees": len(realisations),
        "nb_participants_total": sum(r.participants or 0 for _, r in realisations),
        "nb_clients_distincts": len(identifiants_clients),
        "periode_debut": min(annees) if annees else None,
        "periode_fin": max(annees) if annees else None,
    }


def tableau_recapitulatif(formations: List[Formation]) -> List[Dict[str, Any]]:
    """Python pur — mission §Portfolio point 3."""
    lignes = []
    for f in formations:
        for r in f.realisations:
            lignes.append({
                "intitule": f.titre,
                "client": r.affichage_client(),
                "annee": r.annee or TEXTE_A_COMPLETER,
                "duree": f"{f.duree_jours} jour(s)" if f.duree_jours else TEXTE_A_COMPLETER,
                "participants": r.participants if r.participants is not None else TEXTE_A_COMPLETER,
                "lieu": r.lieu or TEXTE_A_COMPLETER,
            })
    return lignes


async def _verifier_session_backend(realisation: Realisation) -> Optional[Dict[str, Any]]:
    """
    'Résultats (satisfaction/progression Agents 2/3) SI la session existe
    dans le Backend, sinon rubrique absente' (mission §Portfolio point 4).

    LIMITE ASSUMÉE ET DOCUMENTÉE : seule l'EXISTENCE de la session est
    vérifiable via fetch_session() (contrat Backend confirmé, GET
    /sessions/{id}). Les résultats détaillés des Agents 2/3 (satisfaction,
    progression) ne sont accessibles via AUCUNE route Backend confirmée à
    ce jour — plutôt que d'inventer des chiffres, cette fonction indique
    seulement que la session est confirmée, sans invention de données.
    """
    if not realisation.session_id:
        return None

    session = await fetch_session(str(realisation.session_id))
    if not session:
        return None

    return {
        "session_confirmee": True,
        "titre_session": session.get("titre"),
        "note": (
            "Détail satisfaction/progression non disponible : aucune route "
            "Backend dédiée confirmée à ce jour."
        ),
    }


async def generer_fiche_reference(
    formation: Formation,
    realisation: Realisation,
    appeler_llm_json,
    repository: Optional[KnowledgeRepository] = None,
) -> Dict[str, Any]:
    """
    Une fiche de référence (mission §Portfolio point 4). `appeler_llm_json`
    est injecté (fonction async(nom_prompt, contenu) -> dict|None) pour
    éviter une dépendance circulaire avec chat_orchestrator.py.
    """
    from app.services.rag import recherche_service as recherche

    resultats_rag = await recherche.rechercher(
        f"{formation.titre} programme objectifs contenu", collection="support",
        formation_code=formation.code, top_k=6, attente_max_s=None, repository=repository,
    )

    contenus_cles: List[str] = []
    objectifs = TEXTE_A_COMPLETER

    if resultats_rag:
        contexte = "\n\n".join(f"[{r.fichier}]\n{r.contenu}" for r in resultats_rag)
        resultat_llm = await appeler_llm_json("portfolio.yaml", contexte)
        if resultat_llm:
            objectifs = resultat_llm.get("objectifs") or TEXTE_A_COMPLETER
            contenus_cles = resultat_llm.get("contenus_cles") or []

    resultats_backend = await _verifier_session_backend(realisation)

    return {
        "intitule": formation.titre,
        "client": realisation.affichage_client(),
        "periode": realisation.annee or TEXTE_A_COMPLETER,
        "duree": f"{formation.duree_jours} jour(s)" if formation.duree_jours else TEXTE_A_COMPLETER,
        "participants": realisation.participants if realisation.participants is not None else TEXTE_A_COMPLETER,
        "public": TEXTE_A_COMPLETER,  # non modélisé dans le catalogue actuel — assumé
        "lieu": realisation.lieu or TEXTE_A_COMPLETER,
        "objectifs": objectifs,
        "contenus_cles": contenus_cles,
        "resultats": resultats_backend,  # absent (None) si la session n'existe pas dans le Backend
        "attestation_disponible": "oui" if realisation.attestation_bonne_execution else "non",
    }
