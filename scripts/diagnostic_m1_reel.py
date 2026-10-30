"""Essai réel borné M1, indépendant du SSE démo, sans sync Backend.

Depuis la racine : python -m scripts.diagnostic_m1_reel --query "formation web Madagascar"
Consomme le quota réel Tavily et un nombre borné d'analyses Groq.
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="appel d'offres formation informatique Madagascar")
    parser.add_argument("--max-batches", type=int, choices=range(1, 4), default=1,
                        help="Nombre maximal de lots Groq (défaut : 1). Arrêt sur quota.")
    parser.add_argument("--batch-size", type=int, choices=range(1, 6), default=3,
                        help="Sources par lot, alternées par domaine (défaut : 3).")
    parser.add_argument("--budget-seconds", type=int, choices=range(1, 121), metavar="1..120", default=60,
                        help="Budget total du diagnostic, attente entre lots incluse (défaut : 60).")
    parser.add_argument("--source-group", default="institutionnel",
                        help="Famille du registre YAML, ou all pour toutes (défaut : institutionnel).")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    logging.basicConfig(level=logging.WARNING)
    from app.orchestrator import veille_orchestrator as module
    from app.services.veille.source_registry import SEARCH_GROUP, load_registry
    registry = load_registry()
    groups = [g for g in registry.groups if any(s.enabled for s in g.sources)] if args.source_group == "all" else [registry.group(args.source_group)]
    if args.source_group == "all":
        private = next((g for g in groups if g.id == "missions_privees"), None)
        if private:
            groups.remove(private)
            groups.insert(1, private)

    # Une requête ; les limites explicites protègent les quotas.
    # Pas de changement du .env, du scheduler ou du mode de démonstration.
    module.MAX_FALLBACK_BATCHES = args.max_batches
    module.MAX_RESULTS_AI = args.batch_size
    orch = module.VeilleOrchestrator()
    async def execute():
        token = SEARCH_GROUP.set(groups[0].id)
        try:
            async with asyncio.timeout(args.budget_seconds):
                if args.source_group == "all":
                    return await orch.detecter_automatiquement(
                        [args.query] * len(groups), sync_backend=False,
                        source_groups=[g.id for g in groups], budget_seconds=args.budget_seconds - 0.5,
                        categorie="manuel", collect_first=True)
                return await orch.analyser_opportunites(args.query, sync_backend=False)
        except TimeoutError:
            return {"status": "technical_error", "total": 0,
                    "notes": f"Budget total du diagnostic ({args.budget_seconds} secondes) dépassé."}
        finally:
            SEARCH_GROUP.reset(token)
    result = asyncio.run(execute())
    result["source_plan"] = {"family": args.source_group, "domains": [d for g in groups for d in registry.domains(g.id)],
                             "method": "index Tavily ; lectures directes éventuelles détaillées dans collection_diagnostics"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
