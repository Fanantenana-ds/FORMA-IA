# app/services/rag/conversation_service.py
# ============================================================
# MÉMOIRE DE CONVERSATION — data/rag/conversations/{id}.json (Étape E §5)
# ============================================================
# 6 derniers échanges + dernière formation résolue (pour les relances du
# type "et le module 2 ?", "où est-ce expliqué ?").
# ============================================================

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DOSSIER_CONVERSATIONS_DEFAUT = Path(__file__).resolve().parents[3] / "data" / "rag" / "conversations"
NB_ECHANGES_MEMORISES = 6


@dataclass
class Echange:
    role: str  # "utilisateur" | "assistant"
    texte: str


@dataclass
class Conversation:
    conversation_id: str
    echanges: List[Echange] = field(default_factory=list)
    derniere_formation_code: Optional[str] = None


def nouveau_id() -> str:
    return str(uuid.uuid4())


def _chemin(conversation_id: str, dossier: Optional[Path] = None) -> Path:
    dossier = dossier or DOSSIER_CONVERSATIONS_DEFAUT
    return dossier / f"{conversation_id}.json"


def charger_conversation(conversation_id: str, dossier: Optional[Path] = None) -> Conversation:
    chemin = _chemin(conversation_id, dossier)
    if not chemin.exists():
        return Conversation(conversation_id=conversation_id)

    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Conversation(
            conversation_id=conversation_id,
            echanges=[Echange(**e) for e in data.get("echanges", [])],
            derniere_formation_code=data.get("derniere_formation_code"),
        )
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"❌ Conversation illisible ({conversation_id}) : {exc}")
        return Conversation(conversation_id=conversation_id)


def sauvegarder_conversation(conversation: Conversation, dossier: Optional[Path] = None) -> None:
    chemin = _chemin(conversation.conversation_id, dossier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(conversation), f, ensure_ascii=False)
    os.replace(tmp, chemin)


def ajouter_echange(
    conversation: Conversation, role: str, texte: str,
    formation_code: Optional[str] = None,
) -> Conversation:
    """Ajoute un échange, ne garde que les NB_ECHANGES_MEMORISES derniers,
    met à jour la dernière formation résolue SI une nouvelle est fournie
    (sinon la mémoire précédente est conservée, pour les relances)."""
    conversation.echanges.append(Echange(role=role, texte=texte))
    conversation.echanges = conversation.echanges[-NB_ECHANGES_MEMORISES:]
    if formation_code:
        conversation.derniere_formation_code = formation_code
    return conversation
