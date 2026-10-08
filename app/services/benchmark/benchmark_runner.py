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

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.orchestrator.veille_orchestrator import VeilleOrchestrator
from app.services.veille.classification_service import ClassificationService

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = BASE_DIR / "data" / "corpus_veille" / "corpus_v1.jsonl"
CORPUS_PATH = Path(os.getenv("CORPUS_VEILLE_PATH", str(DEFAULT_CORPUS_PATH)))
PROMPTS_M1_DIR = BASE_DIR / "app" / "prompts" / "m1"

VALEURS_VIDES = (None, "", "Non précisé")


# ============================================================
# INDICATEURS SUPPLÉMENTAIRES (Étape C, mission "Préparation soutenance")
# ============================================================

def _f1(precision: Optional[float], rappel: Optional[float]) -> Optional[float]:
    if precision is None or rappel is None or (precision + rappel) == 0:
        return None
    return 2 * precision * rappel / (precision + rappel)


def _percentile(valeurs: List[float], p: float) -> Optional[float]:
    """Percentile par interpolation linéaire (méthode usuelle) — sans
    dépendance externe (numpy)."""
    if not valeurs:
        return None
    valeurs_triees = sorted(valeurs)
    if len(valeurs_triees) == 1:
        return valeurs_triees[0]
    k = (len(valeurs_triees) - 1) * p
    f = int(k)
    c = min(f + 1, len(valeurs_triees) - 1)
    if f == c:
        return valeurs_triees[f]
    return valeurs_triees[f] + (valeurs_triees[c] - valeurs_triees[f]) * (k - f)


def _f1_macro_domaine(matrice: Dict[str, Dict[str, int]], domaines: List[str]) -> Optional[float]:
    """F1 macro (one-vs-rest) sur la matrice de confusion des domaines.
    matrice[domaine_attendu][domaine_predit] = nombre de cas."""
    scores = []
    for d in domaines:
        vrais_positifs = matrice.get(d, {}).get(d, 0)
        faux_positifs = sum(
            matrice.get(autre, {}).get(d, 0) for autre in domaines if autre != d
        )
        faux_negatifs = sum(
            matrice.get(d, {}).get(autre, 0) for autre in domaines if autre != d
        )
        if vrais_positifs + faux_positifs == 0 and vrais_positifs + faux_negatifs == 0:
            continue  # classe absente du gold ET jamais prédite : ignorée (pas de signal)
        p = vrais_positifs / (vrais_positifs + faux_positifs) if (vrais_positifs + faux_positifs) > 0 else 0.0
        r = vrais_positifs / (vrais_positifs + faux_negatifs) if (vrais_positifs + faux_negatifs) > 0 else 0.0
        scores.append(2 * p * r / (p + r) if (p + r) > 0 else 0.0)
    return sum(scores) / len(scores) if scores else None


def _parser_date_collectee(valeur: Any) -> Optional[datetime]:
    """Parse le champ date_collected du corpus (ISO AAAA-MM-JJ). None si
    absent/invalide — analyser_texte() retombe alors sur "maintenant"
    (comportement inchangé, voir ScoringService.score)."""
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(str(valeur).strip())
    except (TypeError, ValueError):
        return None


def _empreinte_prompts() -> str:
    """Empreinte (SHA-256, tronquée) du contenu des prompts M1 — détecte
    si les prompts ont changé entre deux exécutions du benchmark."""
    hachage = hashlib.sha256()
    if PROMPTS_M1_DIR.exists():
        for chemin in sorted(PROMPTS_M1_DIR.glob("*.yaml")):
            hachage.update(chemin.read_bytes())
    return hachage.hexdigest()[:16]


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


def fusionner_rapports(rapports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fusionne plusieurs rapports de BenchmarkRunner.run() (ex. après une
    reprise --reprendre : un rapport par tranche traitée) en un seul
    rapport ÉQUIVALENT à un run() unique sur l'union des documents.

    Recalcule tous les ratios depuis les compteurs BRUTS déjà présents
    dans chaque rapport (confusion_matrix, domain_confusion_matrix,
    extraction_par_champ, hallucinated_values, latency_seconds par
    entrée dans "details") — aucune perte de précision par arrondi
    successif (round() n'est appliqué qu'une fois, à la fin).
    """
    if not rapports:
        raise ValueError("Aucun rapport à fusionner.")
    if len(rapports) == 1:
        return rapports[0]

    tp = sum(r["confusion_matrix"]["true_positives"] for r in rapports)
    fp = sum(r["confusion_matrix"]["false_positives"] for r in rapports)
    fn = sum(r["confusion_matrix"]["false_negatives"] for r in rapports)
    tn = sum(r["confusion_matrix"]["true_negatives"] for r in rapports)
    total = tp + fp + fn + tn

    domain_matrix: Dict[str, Dict[str, int]] = {}
    for r in rapports:
        for attendu, predictions in r["domain_confusion_matrix"].items():
            domain_matrix.setdefault(attendu, {})
            for predit, n in predictions.items():
                domain_matrix[attendu][predit] = domain_matrix[attendu].get(predit, 0) + n
    domain_total = sum(sum(p.values()) for p in domain_matrix.values())
    domain_correct = sum(domain_matrix.get(d, {}).get(d, 0) for d in domain_matrix)

    extraction_par_champ: Dict[str, Dict[str, Any]] = {}
    for champ in ("budget", "deadline", "organizer"):
        correct = sum(r["extraction_par_champ"][champ]["correct"] for r in rapports)
        total_champ = sum(r["extraction_par_champ"][champ]["total"] for r in rapports)
        extraction_par_champ[champ] = {
            "correct": correct, "total": total_champ,
            "accuracy": round(correct / total_champ, 3) if total_champ > 0 else None,
        }
    extraction_total = sum(v["total"] for v in extraction_par_champ.values())
    extraction_correct = sum(v["correct"] for v in extraction_par_champ.values())

    hallucinations = {"budget": 0, "deadline": 0, "organizer": 0}
    for r in rapports:
        for cle in ("budget", "deadline", "organizer"):
            hallucinations[cle] += r["hallucinated_values"].get(cle, 0)
    hallucinations["total"] = sum(hallucinations[c] for c in ("budget", "deadline", "organizer"))

    details = [d for r in rapports for d in r["details"]]
    latencies = [d["latency_seconds"] for d in details if "latency_seconds" in d]

    llm_fallback_count = sum(r.get("llm_fallback_count", 0) for r in rapports)
    model_error_count = sum(r.get("model_error_count", 0) for r in rapports)

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    accuracy_globale = (tp + tn) / total if total > 0 else None
    domain_accuracy = domain_correct / domain_total if domain_total > 0 else None
    extraction_accuracy = extraction_correct / extraction_total if extraction_total > 0 else None
    f1_detection = _f1(precision, recall)
    domaines_observes = sorted({
        *domain_matrix.keys(),
        *(p for ligne in domain_matrix.values() for p in ligne.keys() if p),
    })
    f1_macro_domain = _f1_macro_domaine(domain_matrix, domaines_observes)
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    latency_median = _percentile(latencies, 0.5)
    latency_p95 = _percentile(latencies, 0.95)

    cdc_targets = rapports[-1]["cdc_targets"]

    return {
        "corpus_path": rapports[-1]["corpus_path"],
        "corpus_size_tested": sum(r["corpus_size_tested"] for r in rapports),
        "confusion_matrix": {
            "true_positives": tp, "false_positives": fp,
            "false_negatives": fn, "true_negatives": tn,
        },
        "precision_detection": round(precision, 3) if precision is not None else None,
        "recall_detection": round(recall, 3) if recall is not None else None,
        "accuracy_globale": round(accuracy_globale, 3) if accuracy_globale is not None else None,
        "domain_classification_accuracy": round(domain_accuracy, 3) if domain_accuracy is not None else None,
        "extraction_accuracy": round(extraction_accuracy, 3) if extraction_accuracy is not None else None,
        "hallucinated_values": hallucinations,
        "average_latency_seconds": round(avg_latency, 3) if avg_latency is not None else None,
        "f1_detection": round(f1_detection, 3) if f1_detection is not None else None,
        "domain_confusion_matrix": domain_matrix,
        "f1_macro_domain": round(f1_macro_domain, 3) if f1_macro_domain is not None else None,
        "extraction_par_champ": extraction_par_champ,
        "latency_median_seconds": round(latency_median, 3) if latency_median is not None else None,
        "latency_p95_seconds": round(latency_p95, 3) if latency_p95 is not None else None,
        "llm_fallback_count": llm_fallback_count,
        "model_error_count": model_error_count,
        "configuration_snapshot": rapports[-1]["configuration_snapshot"],
        "cdc_targets": cdc_targets,
        "meets_cdc_precision": (
            precision is not None and precision >= cdc_targets["precision_target"]
        ),
        "meets_cdc_extraction": (
            extraction_accuracy is not None
            and extraction_accuracy >= cdc_targets["extraction_target"]
        ),
        "meets_cdc_latency": (
            avg_latency is not None and avg_latency <= cdc_targets["latency_target_seconds"]
        ),
        "details": details,
    }


class BenchmarkRunner:
    """
    Rejoue le corpus annoté à travers le pipeline M1 (analyser_texte)
    et calcule les indicateurs de précision/extraction/latence exigés
    par le CDC.
    """

    def __init__(self, corpus_path: Path | None = None):
        self.corpus_path = Path(corpus_path) if corpus_path else CORPUS_PATH
        self.orchestrator = VeilleOrchestrator()

    # --------------------------------------------------------
    # CHARGEMENT DU CORPUS
    # --------------------------------------------------------

    def _load_corpus(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus introuvable : {self.corpus_path}. "
                "Vérifie data/corpus_veille/corpus_v1.jsonl."
            )

        entries: list[dict[str, Any]] = []
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
    # MESURE DÉTERMINISTE SÉPARÉE (Étape C point 4) — AUCUN LLM
    # --------------------------------------------------------

    def mesurer_classification_deterministe(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        ClassificationService SEUL sur les textes gold (règles de
        mots-clés, Python pur — aucun appel réseau, aucun LLM). Isole la
        contribution de la classification déterministe dans la précision
        globale de M1 : un écart avec les métriques du pipeline complet
        (run()) révèle si les erreurs viennent du LLM (extraction/détection)
        ou des règles de classification elles-mêmes. Résultat 100%
        reproductible (pas de dépendance à l'heure ni au réseau).
        """
        entries = self._load_corpus(limit=limit)
        classifier = ClassificationService()

        domain_total = 0
        domain_correct = 0
        domain_confusion_matrix: Dict[str, Dict[str, int]] = {}
        details: List[Dict[str, Any]] = []

        for entry in entries:
            gold = entry.get("gold", {}) or {}
            gold_domain = gold.get("domain")
            if gold_domain is None:
                continue

            resultat = classifier.classify({"title": "", "summary": entry.get("raw_text", "")})
            predicted_domain = resultat.get("domain")

            domain_total += 1
            if predicted_domain == gold_domain:
                domain_correct += 1
            domain_confusion_matrix.setdefault(gold_domain, {})
            domain_confusion_matrix[gold_domain][predicted_domain] = (
                domain_confusion_matrix[gold_domain].get(predicted_domain, 0) + 1
            )
            details.append({
                "id": entry.get("id", "corpus-inconnu"),
                "expected_domain": gold_domain,
                "predicted_domain": predicted_domain,
                "correct": predicted_domain == gold_domain,
            })

        domaines_observes = sorted({
            *domain_confusion_matrix.keys(),
            *(p for ligne in domain_confusion_matrix.values() for p in ligne.keys() if p),
        })

        return {
            "corpus_path": str(self.corpus_path),
            "corpus_size_tested": domain_total,
            "domain_total": domain_total,
            "domain_correct": domain_correct,
            "domain_accuracy": (
                round(domain_correct / domain_total, 3) if domain_total > 0 else None
            ),
            "domain_confusion_matrix": domain_confusion_matrix,
            "f1_macro_domain": (
                round(f1, 3) if (f1 := _f1_macro_domaine(domain_confusion_matrix, domaines_observes)) is not None else None
            ),
            "details": details,
        }

    # --------------------------------------------------------
    # INSTANTANÉ DE CONFIGURATION (Étape C point 2)
    # --------------------------------------------------------

    def _instantane_configuration(self) -> Dict[str, Any]:
        """Fournisseur/modèle LLM actifs, empreinte des prompts M1, date
        d'exécution — pour pouvoir expliquer un écart entre deux rapports
        de benchmark (prompt modifié ? fournisseur changé ? etc.)."""
        llm = getattr(self.orchestrator.llm_service, "llm", None)
        return {
            "fournisseur_llm": llm.get_provider_name() if llm else None,
            "modele_llm": llm.get_model_name() if llm else None,
            "empreinte_prompts_m1": _empreinte_prompts(),
            "date_execution": datetime.now(timezone.utc).isoformat(),
        }

    # --------------------------------------------------------
    # EXÉCUTION DU BENCHMARK
    # --------------------------------------------------------

    async def run(self, limit: int = 20) -> dict[str, Any]:
        entries = self._load_corpus(limit=limit)
        total = len(entries)

        logger.info("📊 BENCHMARK M1 — DÉBUT (%d document(s) du corpus)", total)

        true_positives = 0
        false_positives = 0
        false_negatives = 0
        true_negatives = 0

        domain_correct = 0
        domain_total = 0
        domain_confusion_matrix: Dict[str, Dict[str, int]] = {}

        budget_correct = budget_total = 0
        deadline_correct = deadline_total = 0
        organizer_correct = organizer_total = 0
        extraction_total = 0
        hallucinations = {"budget": 0, "deadline": 0, "organizer": 0}

        llm_fallback_count = 0
        model_error_count = 0

        latencies: list[float] = []
        details: list[dict[str, Any]] = []

        for entry in entries:
            gold = entry.get("gold", {}) or {}
            expected_is_opportunity = bool(gold.get("is_opportunity", False))
            entry_id = entry.get("id", "corpus-inconnu")
            date_reference = _parser_date_collectee(entry.get("date_collected"))

            start = time.perf_counter()
            try:
                result = await self.orchestrator.analyser_texte(
                    texte=entry.get("raw_text", ""),
                    source=entry_id,
                    sync_backend=False,  # correction 1c : jamais de pollution de formaia
                    date_reference=date_reference,  # correction Étape C point 1 : reproductibilité
                )
            except Exception as exc:
                # AVANT cette correction : une exception ici faisait planter
                # TOUT le benchmark (aucun try/except par document). Comptée
                # séparément d'un repli LLM gracieux (ai_provider="fallback").
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)
                model_error_count += 1
                logger.error("❌ Benchmark — erreur sur %s : %s", entry_id, exc)
                details.append({
                    "id": entry_id,
                    "expected_is_opportunity": expected_is_opportunity,
                    "predicted_is_opportunity": False,
                    "correct_detection": not expected_is_opportunity,
                    "erreur": f"{type(exc).__name__} : {exc}",
                    "latency_seconds": round(elapsed, 3),
                })
                if expected_is_opportunity:
                    false_negatives += 1
                else:
                    true_negatives += 1
                if pause_secondes:
                    await asyncio.sleep(pause_secondes)
                continue

            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

            if result.get("ai_provider") == "fallback":
                llm_fallback_count += 1

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

                gold_domain = gold.get("domain")
                if gold_domain is not None:
                    domain_total += 1
                    if predicted_domain == gold_domain:
                        domain_correct += 1
                    domain_confusion_matrix.setdefault(gold_domain, {})
                    domain_confusion_matrix[gold_domain][predicted_domain] = (
                        domain_confusion_matrix[gold_domain].get(predicted_domain, 0) + 1
                    )

                # Correction 1d : comparaison RÉELLE à la valeur gold
                # (budget/deadline/organisateur), plus une simple
                # vérification de non-vacuité ; les valeurs inventées par
                # le LLM (champ non vide alors que gold n'attend rien)
                # sont comptabilisées séparément, jamais comme une réussite.
                # Étape C point 2 : chaque champ a aussi son propre total
                # (extraction_total reste la somme combinée, inchangée).
                budget_attendu = gold.get("budget_expected")
                if budget_attendu is not None:
                    extraction_total += 1
                    budget_total += 1
                    if _valeur_correcte(predicted_budget, budget_attendu):
                        budget_correct += 1
                elif _est_valeur_inventee(predicted_budget):
                    hallucinations["budget"] += 1

                deadline_attendue = gold.get("deadline_expected")
                if deadline_attendue is not None:
                    extraction_total += 1
                    deadline_total += 1
                    if _valeur_correcte(predicted_deadline, deadline_attendue, est_date=True):
                        deadline_correct += 1
                elif _est_valeur_inventee(predicted_deadline):
                    hallucinations["deadline"] += 1

                organizer_attendu = gold.get("organizer_expected")
                if organizer_attendu is not None:
                    extraction_total += 1
                    organizer_total += 1
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

            if pause_secondes:
                await asyncio.sleep(pause_secondes)

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

        # ── Étape C point 2 : indicateurs supplémentaires du rapport complet ──
        f1_detection = _f1(precision, recall)
        domaines_observes = sorted({
            *domain_confusion_matrix.keys(),
            *(p for ligne in domain_confusion_matrix.values() for p in ligne.keys() if p),
        })
        f1_macro_domain = _f1_macro_domaine(domain_confusion_matrix, domaines_observes)

        def _stat_champ(correct: int, total_champ: int) -> Dict[str, Any]:
            return {
                "correct": correct, "total": total_champ,
                "accuracy": round(correct / total_champ, 3) if total_champ > 0 else None,
            }

        extraction_par_champ = {
            "budget": _stat_champ(budget_correct, budget_total),
            "deadline": _stat_champ(deadline_correct, deadline_total),
            "organizer": _stat_champ(organizer_correct, organizer_total),
        }

        latency_median = _percentile(latencies, 0.5)
        latency_p95 = _percentile(latencies, 0.95)

        configuration_snapshot = self._instantane_configuration()

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
            # Étape C point 2 — rapport complet (ajouts, tout ce qui précède est conservé) :
            "f1_detection": round(f1_detection, 3) if f1_detection is not None else None,
            "domain_confusion_matrix": domain_confusion_matrix,
            "f1_macro_domain": round(f1_macro_domain, 3) if f1_macro_domain is not None else None,
            "extraction_par_champ": extraction_par_champ,
            "latency_median_seconds": round(latency_median, 3) if latency_median is not None else None,
            "latency_p95_seconds": round(latency_p95, 3) if latency_p95 is not None else None,
            "llm_fallback_count": llm_fallback_count,
            "model_error_count": model_error_count,
            "configuration_snapshot": configuration_snapshot,
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