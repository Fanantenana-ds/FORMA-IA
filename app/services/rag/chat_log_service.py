# app/services/rag/chat_log_service.py
# ============================================================
# JOURNAL DU CHAT — data/rag/chat_logs.jsonl (Étape E §6)
# ============================================================

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHEMIN_JOURNAL_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "chat_logs.jsonl"


def enregistrer(
    question: str,
    type_detecte: str,
    formation_code: Optional[str],
    nb_sources: int,
    modele_requete: Optional[str],
    cache_utilise: bool,
    duree_ms: float,
    statut: str,
    chemin: Optional[Path] = None,
) -> None:
    chemin = chemin or CHEMIN_JOURNAL_DEFAUT
    chemin.parent.mkdir(parents=True, exist_ok=True)

    ligne = {
        "date": datetime.now().isoformat(),
        "question": question,
        "type_detecte": type_detecte,
        "formation_code": formation_code,
        "nb_sources": nb_sources,
        "modele_requete": modele_requete,
        "cache_utilise": cache_utilise,
        "duree_ms": round(duree_ms, 1),
        "statut": statut,
    }
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


def lire_toutes_les_lignes(chemin: Optional[Path] = None) -> List[Dict[str, Any]]:
    chemin = chemin or CHEMIN_JOURNAL_DEFAUT
    if not chemin.exists():
        return []

    lignes = []
    with open(chemin, "r", encoding="utf-8") as f:
        for ligne_brute in f:
            ligne_brute = ligne_brute.strip()
            if not ligne_brute:
                continue
            try:
                lignes.append(json.loads(ligne_brute))
            except json.JSONDecodeError:
                logger.warning("⚠️ Ligne de journal illisible ignorée.")
    return lignes
