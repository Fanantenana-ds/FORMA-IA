import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

from app.services.llm import (
    get_llm_provider,
    get_provider_info,
    LLMProvider,
)


async def main():
    print("=" * 70)
    print("🧪 TEST PROVIDER ABSTRACTION — FORMA-IA")
    print("=" * 70)

    # ────────────────────────────────────────────────────────────
    # TEST 1 — Info provider
    # ────────────────────────────────────────────────────────────
    print("\n🔍 [1/4] Informations sur le provider actif...")
    info = get_provider_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))

    # ────────────────────────────────────────────────────────────
    # TEST 2 — Instanciation
    # ────────────────────────────────────────────────────────────
    print("\n🔧 [2/4] Instanciation du provider...")
    try:
        llm = get_llm_provider()
        print(f"   ✅ Provider : {llm.get_provider_name()}")
        print(f"   ✅ Modèle   : {llm.get_model_name()}")
        print(f"   ✅ Dispo    : {llm.is_available()}")
    except Exception as e:
        print(f"   ❌ Échec : {type(e).__name__} — {e}")
        return

    # ────────────────────────────────────────────────────────────
    # TEST 3 — Génération simple (texte)
    # ────────────────────────────────────────────────────────────
    print("\n🚀 [3/4] Génération simple (texte)...")
    try:
        response = await llm.generate(
            system_prompt=(
                "Tu es un assistant. Réponds en une phrase courte."
            ),
            user_prompt="Dis bonjour en malgache.",
            temperature=0.3,
            max_tokens=100,
            json_mode=False,
        )
        print(f"   ✅ Réponse : {response['content'][:200]}")
        print(f"   ✅ Finish  : {response['finish_reason']}")
        print(f"   ✅ Tokens  : {response['usage']['total_tokens']}")
    except Exception as e:
        print(f"   ❌ Échec : {type(e).__name__} — {e}")

    # ────────────────────────────────────────────────────────────
    # TEST 4 — Génération JSON + retry
    # ────────────────────────────────────────────────────────────
    print("\n🚀 [4/4] Génération JSON avec retry...")
    try:
        response = await llm.generate_with_retry(
            system_prompt=(
                "Tu es un assistant. Réponds UNIQUEMENT en JSON valide."
            ),
            user_prompt=(
                'Retourne {"status": "ok", "message": "Bonjour"} '
                'sans texte autour.'
            ),
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
            max_retries=2,
        )
        content = response["content"]

        # Extraire le JSON
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end + 1])
            print(f"   ✅ JSON parsé : {parsed}")
        else:
            print(f"   ⚠️  Pas de JSON détecté : {content[:200]}")
    except Exception as e:
        print(f"   ❌ Échec : {type(e).__name__} — {e}")

    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())