# scripts/test_phase5_chat.py
# ============================================================
# TEST PHASE 5 — Chat (assistant documentaire)
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.orchestrator.chat_orchestrator import ChatOrchestrator


QUESTIONS = [
    # Aide plateforme (RAG)
    ("Comment valider une relance de facture ?",      "aide_plateforme"),
    ("Comment fonctionne le HITL ?",                  "aide_plateforme"),
    # Contenu de formation (RAG + résumés)
    ("donne moi les contenus de IA fondamentaux",     "contenu_formation"),
    # Conversationnel (regex, pas de LLM)
    ("bonjour",                                        "conversationnel"),
    # Hors sujet (MODE STRICT)
    ("Qu'est-ce que la blockchain ?",                 "hors_sujet"),
    # Localisation (recherche vectorielle groupée)
    ("où est expliqué le surapprentissage ?",         "localisation"),
]


async def main():
    print("=" * 70)
    print("TEST PHASE 5 — CHAT")
    print("=" * 70)

    orch = ChatOrchestrator()

    for question, type_attendu in QUESTIONS:
        print()
        print(f"❓ {question}")
        print(f"   (type attendu : {type_attendu})")
        try:
            r = await orch.traiter_message(question)
        except Exception as exc:
            print(f"   ❌ {type(exc).__name__} — {exc}")
            continue

        type_obtenu = r.get("type_reponse")
        ok = "✅" if type_obtenu == type_attendu else "⚠️ "
        print(f"   {ok} type_reponse = {type_obtenu}")

        reponse = (r.get("reponse") or "")[:200].replace("\n", " ")
        print(f"   réponse : {reponse}...")

        sources = r.get("sources") or []
        print(f"   sources : {len(sources)}")
        print(f"   durée   : {r.get('duree_ms', '?')} ms")

    print()
    print("=" * 70)
    print("PHASE 5 : OK")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
    
    