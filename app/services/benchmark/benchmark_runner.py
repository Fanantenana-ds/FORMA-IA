# app/services/benchmark/benchmark_runner.py
import json
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Any
from difflib import SequenceMatcher

from app.orchestrator.veille_orchestrator import VeilleOrchestrator

logger = logging.getLogger(__name__)

class BenchmarkRunner:
    def __init__(self, test_file: str = "data/benchmark/test_dataset.json"):
        self.orchestrator = VeilleOrchestrator()
        self.test_file = Path(test_file)
        self.results_dir = Path("data/benchmark/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _normalize(self, text: str) -> str:
        """Normalise le texte pour la comparaison (supprime les variations)."""
        if not text:
            return ""
        text = text.lower().strip()
        # Supprime les suffixes courants (.mg, .com, .org, .net, .io, .fr, .dev)
        text = re.sub(r'\.(mg|com|org|net|io|fr|dev)$', '', text)
        # Supprime les pluriels simples
        if text.endswith('s') and not text.endswith('ss'):
            text = text[:-1]
        # Supprime certains mots génériques inutiles
        text = re.sub(r'\b(entreprise|société|group|hiring|sarl|sa|sas)\b', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _fuzzy_equal(self, a: str, b: str, threshold: int = 85) -> bool:
        """Compare deux chaînes avec tolérance (fuzzy matching)."""
        if not a and not b:
            return True
        if not a or not b:
            return False
        a_norm = self._normalize(a)
        b_norm = self._normalize(b)
        # Si identiques après normalisation, match direct
        if a_norm == b_norm:
            return True
        # Sinon, on utilise le ratio de similarité
        ratio = SequenceMatcher(None, a_norm, b_norm).ratio() * 100
        return ratio >= threshold

    async def run(self, limit: int = 20) -> Dict[str, Any]:
        """Exécute le benchmark sur les N premiers cas de test."""
        if not self.test_file.exists():
            logger.error(f"❌ Fichier de test non trouvé: {self.test_file}")
            return {"error": "Fichier de test introuvable"}

        with open(self.test_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
        test_cases = test_cases[:limit]

        results = []
        for case in test_cases:
            query = case.get("query", "")
            expected = case.get("expected", {}).get("opportunities", [])
            start = time.perf_counter()
            response = await self.orchestrator.analyser_opportunites(query)
            elapsed = time.perf_counter() - start

            actual = response.get("opportunities", [])
            true_positives = 0
            matched = set()
            for exp in expected:
                for idx, act in enumerate(actual):
                    if idx in matched:
                        continue
                    if self._fuzzy_equal(act.get("title"), exp.get("title")) and \
                       self._fuzzy_equal(act.get("organizer"), exp.get("organizer")):
                        true_positives += 1
                        matched.add(idx)
                        break

            precision = true_positives / len(actual) if actual else 0
            recall = true_positives / len(expected) if expected else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            results.append({
                "id": case.get("id"),
                "query": query,
                "expected_count": len(expected),
                "actual_count": len(actual),
                "true_positives": true_positives,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "elapsed": elapsed
            })

        total = len(results)
        if total == 0:
            return {"error": "Aucun test exécuté"}

        avg_precision = sum(r["precision"] for r in results) / total
        avg_recall = sum(r["recall"] for r in results) / total
        avg_f1 = sum(r["f1"] for r in results) / total
        avg_latency = sum(r["elapsed"] for r in results) / total

        report = {
            "total_requests": total,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_f1": avg_f1,
            "avg_latency_seconds": avg_latency,
            "details": results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        out_file = self.results_dir / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Benchmark sauvegardé dans {out_file}")
        return report