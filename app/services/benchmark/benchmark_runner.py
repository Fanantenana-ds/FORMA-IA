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
#
# Correction 1c (2026-09-25, mission "Étape 1") : analyser_texte() est
# appelé avec sync_backend=False — AVANT cette correction, ce paramètre
# n'existait pas et chaque exécution du benchmark synchronisait réellement
# les "opportunités" du corpus de test avec le Backend (POST /opportunites),
# polluant la base formaia à chaque lancement.
# ============================================================

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.orchestrator.veille_orchestrator import VeilleOrchestrator

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = BASE_DIR / "data" / "corpus_veille" / "corpus_v1.jsonl"
CORPUS_PATH = Path(os.getenv("CORPUS_VEILLE_PATH", str(DEFAULT_CORPUS_PATH)))

VALEURS_VIDES = (None, "", "Non précisé")


# ============================================================
# COMPARAISON DES VALEURS EXTRAITES (correction 1d)
# ============================================================
# AVANT : un champ (budget, deadline) était compté "correct" dès qu'il
# était non vide, sans jamais être comparé à la valeur attendue (gold).
# Une valeur totalement fausse était donc comptée comme une réussite.

def _est_valeur_inventee(valeur: Any) -> bool:
    """True si le LLM a rempli ce champ alors qu'aucune valeur n'était
    attendue par le gold (hallucination)."""
    return valeur not in VALEURS_VIDES


def _dates_concordent(predite: Any, attendue: Any) -> Optional[bool]:
    """Compare deux dates si les deux sont parseables en ISO 8601.
    Retourne None si l'une des deux n'est pas parseable (comparaison
    textuelle en repli, la date pouvant être en langage naturel)."""
    try:
        d1 = datetime.fromisoformat(str(predite).strip())
        d2 = datetime.fromisoformat(str(attendue).strip())
        return d1.date() == d2.date()
    except (TypeError, ValueError):
        return None


def _valeur_correcte(predite: Any, attendue: Any, est_date: bool = False) -> bool:
    """Compare RÉELLEMENT la valeur extraite à la valeur attendue (gold) —
    une valeur non vide mais différente n'est jamais comptée correcte.

    Comparaison EXACTE (après normalisation espaces/casse) uniquement —
    PAS de similarité floue (difflib) ici : pour un budget ou une date,
    une différence d'un seul chiffre ('50M Ar' vs '5M Ar') est une erreur
    totale, pas une variante mineure. Une comparaison floue masquerait
    exactement le genre d'erreur que cette correction doit détecter."""
    if predite in VALEURS_VIDES or attendue in VALEURS_VIDES:
        return False

    if est_date:
        resultat_date = _dates_concordent(predite, attendue)
        if resultat_date is not None:
            return resultat_date

    p = str(predite).strip().lower()
    a = str(attendue).strip().lower()
    return p == a


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
        organizer_correct = 0
        extraction_total = 0
        hallucinations = {"budget": 0, "deadline": 0, "organizer": 0}

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
                sync_backend=False,  # correction 1c : jamais de pollution de formaia
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
            predicted_organizer = None

            # --- Classification / extraction, uniquement sur les vrais
            # positifs détectés (comparer l'extraction n'a de sens que
            # si le pipeline a effectivement trouvé l'opportunité) ---
            if expected_is_opportunity and predicted_is_opportunity:
                top = predicted_opportunities[0]
                predicted_domain = top.get("domain")
                predicted_budget = top.get("budget")
                predicted_deadline = top.get("deadline")
                predicted_organizer = top.get("organizer")

                if gold.get("domain") is not None:
                    domain_total += 1
                    if predicted_domain == gold.get("domain"):
                        domain_correct += 1

                # Correction 1d : comparaison RÉELLE à la valeur gold
                # (budget/deadline/organisateur), plus une simple
                # vérification de non-vacuité ; les valeurs inventées par
                # le LLM (champ non vide alors que gold n'attend rien)
                # sont comptabilisées séparément, jamais comme une réussite.
                budget_attendu = gold.get("budget_expected")
                if budget_attendu is not None:
                    extraction_total += 1
                    if _valeur_correcte(predicted_budget, budget_attendu):
                        budget_correct += 1
                elif _est_valeur_inventee(predicted_budget):
                    hallucinations["budget"] += 1

                deadline_attendue = gold.get("deadline_expected")
                if deadline_attendue is not None:
                    extraction_total += 1
                    if _valeur_correcte(predicted_deadline, deadline_attendue, est_date=True):
                        deadline_correct += 1
                elif _est_valeur_inventee(predicted_deadline):
                    hallucinations["deadline"] += 1

                organizer_attendu = gold.get("organizer_expected")
                if organizer_attendu is not None:
                    extraction_total += 1
                    if _valeur_correcte(predicted_organizer, organizer_attendu):
                        organizer_correct += 1
                elif _est_valeur_inventee(predicted_organizer):
                    hallucinations["organizer"] += 1

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
            (budget_correct + deadline_correct + organizer_correct) / extraction_total
            if extraction_total > 0 else None
        )
        hallucinations["total"] = sum(hallucinations.values())
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
            "hallucinated_values": hallucinations,
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