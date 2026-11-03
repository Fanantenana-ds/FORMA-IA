# app/services/rag/conversation_service.py
# ============================================================
# MÉMOIRE DE CONVERSATION — data/rag/conversations/{id}.json
# ============================================================
# 25 échanges max par conversation, max 20 conversations par
# utilisateur (les plus anciennes sont purgées automatiquement).
# Chaque fichier porte un titre (1er message utilisateur tronqué),
# la date de création et de mise à jour.
# ============================================================

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DOSSIER_CONVERSATIONS_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "conversations"
NB_ECHANGES_MEMORISES = 25
TTL_CONVERSATIONS_JOURS = 30
MAX_CONVERSATIONS_PAR_UTILISATEUR = 20


@dataclass
class Echange:
    role: str  # "utilisateur" | "assistant"
    texte: str
    feedback: str | None = None  # "positif" | "negatif" | None
    type_reponse: str | None = None  # type détecté (aide_plateforme, question_fond, etc.)


@dataclass
class Conversation:
    conversation_id: str
    echanges: list[Echange] = field(default_factory=list)
    derniere_formation_code: str | None = None
    user_id: str | None = None
    titre: str | None = None
    cree_le: float = field(default_factory=time.time)
    mis_a_jour_le: float = field(default_factory=time.time)


def nouveau_id() -> str:
    return str(uuid.uuid4())


def _chemin(conversation_id: str, dossier: Path | None = None) -> Path:
    dossier = dossier or DOSSIER_CONVERSATIONS_DEFAUT
    return dossier / f"{conversation_id}.json"


def charger_conversation(conversation_id: str, dossier: Path | None = None) -> Conversation:
    chemin = _chemin(conversation_id, dossier)
    if not chemin.exists():
        return Conversation(conversation_id=conversation_id)

    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        champs_echange = {f for f in Echange.__dataclass_fields__}
        return Conversation(
            conversation_id=conversation_id,
            echanges=[Echange(**{k: v for k, v in e.items() if k in champs_echange}) for e in data.get("echanges", [])],
            derniere_formation_code=data.get("derniere_formation_code"),
            user_id=data.get("user_id"),
            titre=data.get("titre"),
            cree_le=data.get("cree_le", time.time()),
            mis_a_jour_le=data.get("mis_a_jour_le", time.time()),
        )
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"❌ Conversation illisible ({conversation_id}) : {exc}")
        return Conversation(conversation_id=conversation_id)


def sauvegarder_conversation(
    conversation: Conversation,
    dossier: Path | None = None,
) -> None:
    dossier = dossier or DOSSIER_CONVERSATIONS_DEFAUT
    dossier.mkdir(parents=True, exist_ok=True)

    # Titre auto depuis le premier message utilisateur
    if not conversation.titre:
        for echange in conversation.echanges:
            if echange.role == "utilisateur" and echange.texte.strip():
                conversation.titre = echange.texte.strip()[:80]
                break

    conversation.mis_a_jour_le = time.time()

    # Écriture atomique
    chemin = _chemin(conversation.conversation_id, dossier)
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(conversation), f, ensure_ascii=False)
    os.replace(tmp, chemin)

    # Purge : garder au plus MAX_CONVERSATIONS_PAR_UTILISATEUR par utilisateur
    if conversation.user_id:
        _purger_exces_utilisateur(conversation.user_id, conversation.conversation_id, dossier)


def _purger_exces_utilisateur(
    user_id: str,
    garder_id: str,
    dossier: Path,
) -> None:
    """Supprime les conversations les plus anciennes si l'utilisateur en a > MAX."""
    fichiers = []
    for fichier in dossier.glob("*.json"):
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("user_id") == user_id:
                fichiers.append((data.get("mis_a_jour_le", 0), fichier))
        except (OSError, json.JSONDecodeError):
            continue

    # Trier du plus récent au plus ancien, supprimer au-delà du max
    fichiers.sort(key=lambda x: x[0], reverse=True)
    for _, fichier in fichiers[MAX_CONVERSATIONS_PAR_UTILISATEUR:]:
        if fichier.stem != garder_id:
            try:
                fichier.unlink()
                logger.info(f"🗑️  Purge conversation ancienne : {fichier.name}")
            except OSError:
                pass


def lister_conversations(
    user_id: str,
    dossier: Path | None = None,
    max_nb: int = MAX_CONVERSATIONS_PAR_UTILISATEUR,
) -> list[dict]:
    """Retourne la liste des conversations de l'utilisateur, du plus récent au plus ancien."""
    dossier = dossier or DOSSIER_CONVERSATIONS_DEFAUT
    if not dossier.exists():
        return []

    resultats = []
    for fichier in dossier.glob("*.json"):
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("user_id") != user_id:
                continue
            nb_echanges = len(data.get("echanges", []))
            resultats.append({
                "conversation_id": data.get("conversation_id", fichier.stem),
                "titre": data.get("titre") or "Nouvelle conversation",
                "nb_echanges": nb_echanges,
                "cree_le": data.get("cree_le"),
                "mis_a_jour_le": data.get("mis_a_jour_le"),
                "derniere_formation_code": data.get("derniere_formation_code"),
            })
        except (OSError, json.JSONDecodeError):
            continue

    resultats.sort(key=lambda x: x.get("mis_a_jour_le") or 0, reverse=True)
    return resultats[:max_nb]


def supprimer_conversation(
    conversation_id: str,
    user_id: str,
    dossier: Path | None = None,
) -> bool:
    """Supprime une conversation si elle appartient à l'utilisateur. Retourne True si supprimée."""
    chemin = _chemin(conversation_id, dossier)
    if not chemin.exists():
        return False
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("user_id") != user_id:
            return False
        chemin.unlink()
        return True
    except (OSError, json.JSONDecodeError):
        return False


def purger_conversations_expirees(
    dossier: Path | None = None,
    ttl_jours: int = TTL_CONVERSATIONS_JOURS,
) -> int:
    """Supprime les fichiers de conversation non modifiés depuis ttl_jours."""
    dossier = dossier or DOSSIER_CONVERSATIONS_DEFAUT
    if not dossier.exists():
        return 0

    limite = time.time() - ttl_jours * 86400
    supprimes = 0
    for fichier in dossier.glob("*.json"):
        try:
            if fichier.stat().st_mtime < limite:
                fichier.unlink()
                supprimes += 1
        except OSError as exc:
            logger.warning(f"⚠️ Purge conversation échouée ({fichier.name}) : {exc}")

    if supprimes:
        logger.info(f"🗑️  Purge conversations : {supprimes} fichier(s) > {ttl_jours}j supprimé(s)")
    return supprimes


def ajouter_echange(
    conversation: Conversation, role: str, texte: str,
    formation_code: str | None = None,
    type_reponse: str | None = None,
) -> Conversation:
    """Ajoute un échange, ne garde que les NB_ECHANGES_MEMORISES derniers."""
    conversation.echanges.append(Echange(role=role, texte=texte, type_reponse=type_reponse))
    conversation.echanges = conversation.echanges[-NB_ECHANGES_MEMORISES:]
    if formation_code:
        conversation.derniere_formation_code = formation_code
    return conversation


def noter_echange(
    conversation_id: str,
    index_echange: int,
    feedback: str,
    dossier: Path | None = None,
) -> bool:
    """Enregistre un feedback ('positif'|'negatif') sur un échange assistant.
    Retourne True si l'opération a réussi."""
    conv = charger_conversation(conversation_id, dossier)
    if index_echange < 0 or index_echange >= len(conv.echanges):
        return False
    echange = conv.echanges[index_echange]
    if echange.role != "assistant":
        return False
    echange.feedback = feedback
    sauvegarder_conversation(conv, dossier)
    return True
