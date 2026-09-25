# app/services/rag/syllabus_service.py
# ============================================================
# SERVICE — Syllabus (RAG, Étape G)
# ============================================================
# Somme des durées des modules vérifiée en Python (mission) ; le LLM ne
# rédige que le contenu pédagogique, à partir des chunks RAG.
# ============================================================

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TEXTE_A_COMPLETER = "[À compléter]"

# Convention assumée et documentée : 1 jour = 7 heures (aucune norme
# ALTIORA connue à ce jour — à ajuster si une convention officielle existe).
HEURES_PAR_JOUR = 7.0

_MOTIF_HEURES = re.compile(r"(\d+(?:[.,]\d+)?)\s*h", re.IGNORECASE)
_MOTIF_JOURS = re.compile(r"(\d+(?:[.,]\d+)?)\s*j(?:our)?s?", re.IGNORECASE)


def _duree_en_heures(duree_texte: str) -> Optional[float]:
    """Parse '3h', '3 h', '1 jour', '2j' -> heures. None si non reconnu."""
    if not duree_texte:
        return None
    texte = duree_texte.strip().replace(",", ".")

    match_h = _MOTIF_HEURES.search(texte)
    if match_h:
        return float(match_h.group(1))

    match_j = _MOTIF_JOURS.search(texte)
    if match_j:
        return float(match_j.group(1)) * HEURES_PAR_JOUR

    return None


def verifier_somme_durees(
    modules: List[Dict[str, Any]], duree_totale_annoncee_jours: float,
) -> Tuple[bool, str]:
    """
    Vérifie (Python pur) que la somme des durées des modules du programme
    correspond à la durée totale annoncée. Retourne (conforme, message) —
    le message est destiné au review HITL (mission : "écart signalé dans
    le review"), pas une exception bloquante.
    """
    total_heures = 0.0
    non_reconnus = []

    for module in modules:
        duree_texte = module.get("duree", "")
        heures = _duree_en_heures(duree_texte)
        if heures is None:
            non_reconnus.append(module.get("titre", "?"))
        else:
            total_heures += heures

    total_annonce_heures = duree_totale_annoncee_jours * HEURES_PAR_JOUR
    ecart = abs(total_heures - total_annonce_heures)
    conforme = ecart < 0.5 and not non_reconnus

    if non_reconnus:
        message = (
            f"Durée non reconnue pour {len(non_reconnus)} module(s) : "
            f"{', '.join(non_reconnus)}. Vérification manuelle nécessaire."
        )
    elif not conforme:
        message = (
            f"Écart détecté : programme = {total_heures:.1f}h, "
            f"durée annoncée = {total_annonce_heures:.1f}h "
            f"({duree_totale_annoncee_jours} jour(s) × {HEURES_PAR_JOUR}h) — écart {ecart:.1f}h."
        )
    else:
        message = f"Conforme : {total_heures:.1f}h sur {duree_totale_annoncee_jours} jour(s)."

    return conforme, message


async def generer_contenu_pedagogique(
    formation_titre: str,
    modules: List[Dict[str, Any]],
    appeler_llm_json,
    formation_code: Optional[str] = None,
    repository=None,
) -> Dict[str, Any]:
    """Rédige les sections textuelles du syllabus à partir des chunks RAG
    de la formation (contexte/enjeux, objectifs, compétences, méthodes,
    évaluation, supports) — mission §Syllabus."""
    from app.services.rag import recherche_service as recherche

    valeurs_defaut = {
        "contexte_enjeux": TEXTE_A_COMPLETER,
        "objectif_general": TEXTE_A_COMPLETER,
        "objectifs_operationnels": [],
        "competences": [],
        "methodes_pedagogiques": TEXTE_A_COMPLETER,
        "modalites_evaluation": TEXTE_A_COMPLETER,
        "supports_remis": [],
    }

    resultats_rag = await recherche.rechercher(
        f"{formation_titre} programme objectifs pédagogiques", collection="support",
        formation_code=formation_code, top_k=8, attente_max_s=None, repository=repository,
    )

    if not resultats_rag:
        logger.info(f"ℹ️ Aucun contenu RAG pour le syllabus de '{formation_titre}'.")
        return valeurs_defaut

    contexte = "\n\n".join(f"[{r.fichier}]\n{r.contenu}" for r in resultats_rag)
    programme_texte = "\n".join(f"- {m.get('titre', '?')} ({m.get('duree', '?')})" for m in modules)

    resultat_llm = await appeler_llm_json(
        "syllabus.yaml", f"PROGRAMME :\n{programme_texte}\n\nEXTRAITS DE SUPPORTS :\n{contexte}",
    )

    if not resultat_llm:
        return valeurs_defaut

    return {**valeurs_defaut, **resultat_llm}
