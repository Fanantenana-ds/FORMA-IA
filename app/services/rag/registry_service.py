# app/services/rag/registry_service.py
# ============================================================
# REGISTRE D'INDEXATION — data/rag/index_registry.json (RAG, Étape C)
# ============================================================
# Même principe que app/services/backend_sync/review_sync.py (registre
# JSON, écriture atomique). Porte : l'idempotence (SHA-256 du fichier),
# la reprise après interruption (dernier lot terminé) et le suivi des
# résumés Groq (Étape C §9-11).
# ============================================================

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHEMIN_REGISTRE_DEFAUT = (
    Path(__file__).resolve().parents[3] / "data" / "rag" / "index_registry.json"
)

STATUTS_VALIDES = (
    "en_attente", "en_cours", "indexe", "erreur",
    "non_indexable_image", "ocr_necessaire",
)


@dataclass
class EntreeRegistre:
    hash: str
    fichier: str
    formation_code: Optional[str] = None
    collection: str = "support"
    statut: str = "en_attente"

    nb_pages: Optional[int] = None
    nb_chunks: Optional[int] = None
    tokens_estimes: Optional[int] = None
    modele_embed: Optional[str] = None
    message: Optional[str] = None

    date_debut: Optional[str] = None
    date_fin: Optional[str] = None

    # Résumé (Étape C §9)
    resume: Optional[str] = None
    plan: List[Dict[str, Any]] = field(default_factory=list)
    mots_cles: List[str] = field(default_factory=list)
    resume_statut: str = "a_generer"  # a_generer | genere | echec

    # Reprise après interruption : index (0-based) du dernier lot de chunks
    # inséré en base avec succès. -1 = rien encore inséré.
    dernier_lot_termine: int = -1


def calculer_hash_fichier(chemin: str) -> str:
    """SHA-256 du contenu du fichier (idempotence)."""
    sha256 = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            sha256.update(bloc)
    return sha256.hexdigest()


def _charger_brut(chemin: Path) -> Dict[str, Any]:
    if not chemin.exists():
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"❌ Registre RAG illisible : {exc}")
        return {}


def _sauvegarder_brut(registre: Dict[str, Any], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registre, f, indent=2, ensure_ascii=False)
    os.replace(tmp, chemin)  # écriture atomique


def charger_registre(chemin: Optional[Path] = None) -> Dict[str, EntreeRegistre]:
    chemin = chemin or CHEMIN_REGISTRE_DEFAUT
    brut = _charger_brut(chemin)
    return {h: EntreeRegistre(**v) for h, v in brut.items()}


def obtenir_entree(hash_fichier: str, chemin: Optional[Path] = None) -> Optional[EntreeRegistre]:
    return charger_registre(chemin).get(hash_fichier)


def enregistrer_entree(entree: EntreeRegistre, chemin: Optional[Path] = None) -> None:
    chemin = chemin or CHEMIN_REGISTRE_DEFAUT
    registre = _charger_brut(chemin)
    registre[entree.hash] = asdict(entree)
    _sauvegarder_brut(registre, chemin)


def supprimer_entree(hash_fichier: str, chemin: Optional[Path] = None) -> None:
    chemin = chemin or CHEMIN_REGISTRE_DEFAUT
    registre = _charger_brut(chemin)
    registre.pop(hash_fichier, None)
    _sauvegarder_brut(registre, chemin)


def deja_indexe(hash_fichier: str, chemin: Optional[Path] = None) -> bool:
    """True si ce fichier (par son SHA-256) est déjà indexé avec succès :
    aucun appel Voyage à refaire."""
    entree = obtenir_entree(hash_fichier, chemin)
    return entree is not None and entree.statut == "indexe"


def initialiser_entree(
    hash_fichier: str,
    fichier: str,
    formation_code: Optional[str],
    collection: str = "support",
    chemin: Optional[Path] = None,
) -> EntreeRegistre:
    """Crée (ou retourne) l'entrée pour ce fichier, statut 'en_attente' si
    nouvelle, INCHANGÉE si elle existe déjà (reprise après interruption)."""
    existante = obtenir_entree(hash_fichier, chemin)
    if existante is not None:
        return existante

    entree = EntreeRegistre(
        hash=hash_fichier, fichier=fichier, formation_code=formation_code,
        collection=collection, statut="en_attente",
        date_debut=datetime.now().isoformat(),
    )
    enregistrer_entree(entree, chemin)
    return entree


def marquer_lot_termine(hash_fichier: str, numero_lot: int, chemin: Optional[Path] = None) -> None:
    """Enregistre qu'un lot de chunks a été inséré en base avec succès —
    permet de reprendre exactement là en cas d'interruption."""
    entree = obtenir_entree(hash_fichier, chemin)
    if entree is None:
        return
    entree.dernier_lot_termine = numero_lot
    entree.statut = "en_cours"
    enregistrer_entree(entree, chemin)


def marquer_termine(
    hash_fichier: str, nb_pages: int, nb_chunks: int, tokens_estimes: int,
    modele_embed: str, chemin: Optional[Path] = None,
) -> None:
    entree = obtenir_entree(hash_fichier, chemin)
    if entree is None:
        return
    entree.statut = "indexe"
    entree.nb_pages = nb_pages
    entree.nb_chunks = nb_chunks
    entree.tokens_estimes = tokens_estimes
    entree.modele_embed = modele_embed
    entree.date_fin = datetime.now().isoformat()
    enregistrer_entree(entree, chemin)


def marquer_statut_special(
    hash_fichier: str, fichier: str, formation_code: Optional[str],
    statut: str, message: str, chemin: Optional[Path] = None,
) -> None:
    """Pour non_indexable_image / ocr_necessaire / erreur : crée ou met à
    jour l'entrée avec le statut et un message clair, sans chunk ni appel
    Voyage."""
    if statut not in STATUTS_VALIDES:
        raise ValueError(f"Statut de registre invalide : '{statut}'.")

    entree = obtenir_entree(hash_fichier, chemin) or EntreeRegistre(
        hash=hash_fichier, fichier=fichier, formation_code=formation_code,
        date_debut=datetime.now().isoformat(),
    )
    entree.statut = statut
    entree.message = message
    entree.date_fin = datetime.now().isoformat()
    enregistrer_entree(entree, chemin)


def entrees_pour_formation(formation_code: str, chemin: Optional[Path] = None) -> List[EntreeRegistre]:
    return [
        e for e in charger_registre(chemin).values()
        if e.formation_code == formation_code
    ]


def entrees_sans_resume(chemin: Optional[Path] = None) -> List[EntreeRegistre]:
    return [
        e for e in charger_registre(chemin).values()
        if e.statut == "indexe" and e.resume_statut == "a_generer"
    ]
