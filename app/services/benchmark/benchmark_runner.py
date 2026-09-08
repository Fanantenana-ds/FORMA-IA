# app/services/benchmark/benchmark_runner.py
# ============================================================
# BENCHMARK M1 — mesure de précision / extraction / latence
# ============================================================
# Compare la sortie du pipeline (VeilleOrchestrator.analyser_texte)
# au corpus annoté (data/corpus_veille/corpus_v1.jsonl), conformément
# aux exigences du CDC §4 :
#   - précision de classification > 85 % sur jeu de test ≥ 100 docs
#   - exactitude d'extraction des champs > 90 %
#   - latence moyenne < 3 secondes
#
# Aucun accès SQLAlchemy ici : lecture d'un fichier JSONL local et
# appel de l'orchestrateur existant, conformément à la séparation
# des rôles (persistance = responsabilité du module Backend).
# ============================================================

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.orchestrator.veille_orchestrator import VeilleOrchestrator

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = BASE_DIR / "data" / "corpus_veille" / "corpus_v1.jsonl"
CORPUS_PATH = Path(os.getenv("CORPUS_VEILLE_PATH", str(DEFAULT_CORPUS_PATH)))


class BenchmarkRunner:
    """
    Rejoue le corpus annoté à travers le pipeline M1 (analyser_texte)
    et calcule les indicateurs de précision/extraction/latence exigés
    par le CDC.
    """

    def __init__(self, corpus_path: Optional[Path] = None):
        self.corpus_path = Path(corpus_path) if corpus_path else CORPUS_PATH
        self.orchestrator = VeilleOrchestrator()

    # --------------------------------------------------------
    # CHARGEMENT DU CORPUS
    # --------------------------------------------------------

    def _load_corpus(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus introuvable : {self.corpus_path}. "
                "Vérifie data/corpus_veille/corpus_v1.jsonl."
            )

        entries: List[Dict[str, Any]] = []
        with open(self.corpus_path, "r", encoding="utf-8") as file:
            for line_number, raw_line in enumerate(file, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "⚠️ Ligne %d du corpus invalide (ignorée) : %s",
                        line_number, exc,
                    )

        if not entries:
            raise ValueError(f"Corpus vide ou illisible : {self.corpus_path}")

        if limit:
            entries = entries[:limit]

        return entries

    # --------------------------------------------------------
    # EXÉCUTION DU BENCHMARK
    # --------------------------------------------------------

    async def run(self, limit: int = 20) -> Dict[str, Any]:
        entries = self._load_corpus(limit=limit)
        total = len(entries)

        logger.info("📊 BENCHMARK M1 — DÉBUT (%d document(s) du corpus)", total)

        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0

        domain_correct = 0
        domain_total = 0

        budget_correct = 0
        deadline_correct = 0
        extraction_total = 0

        latencies: List[float] = []
        details: List[Dict[str, Any]] = []

        for entry in entries:
            gold = entry.get("gold", {}) or {}
            expected_is_opportunity = bool(gold.get("is_opportunity", False))
            entry_id = entry.get("id", "corpus-inconnu")

            start = time.perf_counter()
            result = await self.orchestrator.analyser_texte(
                texte=entry.get("raw_text", ""),
                source=entry_id,
            )
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

            predicted_opportunities = result.get("opportunities", []) or []
            predicted_is_opportunity = len(predicted_opportunities) > 0

            # --- Matrice de confusion sur la DÉTECTION ---
            if expected_is_opportunity and predicted_is_opportunity:
                true_positives += 1
            elif expected_is_opportunity and not predicted_is_opportunity:
                false_negatives += 1
            elif not expected_is_opportunity and predicted_is_opportunity:
                false_positives += 1
            else:
                true_negatives += 1

            predicted_domain = None
            predicted_budget = None
            predicted_deadline = None

            # --- Classification / extraction, uniquement sur les vrais
            # positifs détectés (comparer l'extraction n'a de sens que
            # si le pipeline a effectivement trouvé l'opportunité) ---
            if expected_is_opportunity and predicted_is_opportunity:
                top = predicted_opportunities[0]
                predicted_domain = top.get("domain")
                predicted_budget = top.get("budget")
                predicted_deadline = top.get("deadline")

                if gold.get("domain") is not None:
                    domain_total += 1
                    if predicted_domain == gold.get("domain"):
                        domain_correct += 1

                if gold.get("budget_expected") is not None:
                    extraction_total += 1
                    if predicted_budget not in (None, "", "Non précisé"):
                        budget_correct += 1

                if gold.get("deadline_expected") is not None:
                    extraction_total += 1
                    if predicted_deadline not in (None, "", "Non précisé"):
                        deadline_correct += 1

            details.append({
                "id": entry_id,
                "expected_is_opportunity": expected_is_opportunity,
                "predicted_is_opportunity": predicted_is_opportunity,
                "correct_detection": (
                    expected_is_opportunity == predicted_is_opportunity
                ),
                "expected_domain": gold.get("domain"),
                "predicted_domain": predicted_domain,
                "latency_seconds": round(elapsed, 3),
            })

        # --------------------------------------------------------
        # CALCUL DES INDICATEURS
        # --------------------------------------------------------

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0 else None
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0 else None
        )
        accuracy_globale = (
            (true_positives + true_negatives) / total if total > 0 else None
        )
        domain_accuracy = (
            domain_correct / domain_total if domain_total > 0 else None
        )
        extraction_accuracy = (
            (budget_correct + deadline_correct) / extraction_total
            if extraction_total > 0 else None
        )
        avg_latency = (
            sum(latencies) / len(latencies) if latencies else None
        )

        cdc_targets = {
            "precision_target": 0.85,
            "extraction_target": 0.90,
            "latency_target_seconds": 3.0,
        }

        report = {
            "corpus_path": str(self.corpus_path),
            "corpus_size_tested": total,
            "confusion_matrix": {
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "true_negatives": true_negatives,
            },
            "precision_detection": round(precision, 3) if precision is not None else None,
            "recall_detection": round(recall, 3) if recall is not None else None,
            "accuracy_globale": round(accuracy_globale, 3) if accuracy_globale is not None else None,
            "domain_classification_accuracy": round(domain_accuracy, 3) if domain_accuracy is not None else None,
            "extraction_accuracy": round(extraction_accuracy, 3) if extraction_accuracy is not None else None,
            "average_latency_seconds": round(avg_latency, 3) if avg_latency is not None else None,
            "cdc_targets": cdc_targets,
            "meets_cdc_precision": (
                precision is not None and precision >= cdc_targets["precision_target"]
            ),
            "meets_cdc_extraction": (
                extraction_accuracy is not None
                and extraction_accuracy >= cdc_targets["extraction_target"]
            ),
            "meets_cdc_latency": (
                avg_latency is not None
                and avg_latency <= cdc_targets["latency_target_seconds"]
            ),
            "details": details,
        }

        logger.info(
            "📊 BENCHMARK M1 — FIN : précision=%s | rappel=%s | "
            "extraction=%s | latence_moy=%ss",
            report["precision_detection"],
            report["recall_detection"],
            report["extraction_accuracy"],
            report["average_latency_seconds"],
        )

        if total < 100:
            logger.warning(
                "⚠️ Corpus testé sur %d document(s) seulement — le CDC "
                "exige ≥100 documents annotés pour valider officiellement "
                "la précision >85%%. Ce rapport est indicatif, pas la "
                "mesure de recette.",
                total,
            )

        return report