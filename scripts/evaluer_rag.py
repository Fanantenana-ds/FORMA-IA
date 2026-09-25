# scripts/evaluer_rag.py
# ============================================================
# ÉVALUATION RAG — Recall@5 + proposition de seuil (Étape D)
# ============================================================
# Lit data/rag/eval_questions.yaml. Respecte le limiteur et le cache
# (script interactif : attend si besoin, pas de limite à 5 s). N'APPLIQUE
# PAS de seuil : le propose seulement, la décision finale revient à
# l'utilisateur.
#
# Exécution :
#   python scripts/evaluer_rag.py
#   python scripts/evaluer_rag.py --modeles-requete voyage-4-large,voyage-4
# ============================================================

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import yaml

from app.services.rag import recherche_service

CHEMIN_QUESTIONS_DEFAUT = Path(__file__).resolve().parents[1] / "data" / "rag" / "eval_questions.yaml"


def charger_questions(chemin: Path):
    with open(chemin, "r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("questions") or []


async def evaluer_pour_modele(questions, modele_requete: str, top_k: int = 5):
    """Évalue toutes les questions avec un modèle de requête donné (même
    index, aucune ré-indexation — recherche asymétrique)."""
    ancien = os.environ.get("VOYAGE_MODEL_QUERY")
    os.environ["VOYAGE_MODEL_QUERY"] = modele_requete

    try:
        trouvees = 0
        pertinentes_total = 0
        scores_corrects = []
        scores_hors_sujet = []
        latences = []

        for q in questions:
            debut = time.perf_counter()
            resultats = await recherche_service.rechercher(
                q["texte"], top_k=top_k, seuil_min=0.0, attente_max_s=None,
            )
            latences.append((time.perf_counter() - debut) * 1000)

            meilleur_score = resultats[0].score if resultats else 0.0

            if q.get("pertinente"):
                pertinentes_total += 1
                trouve = any(r.formation_code == q.get("formation_code") for r in resultats)
                if trouve:
                    trouvees += 1
                    scores_corrects.append(meilleur_score)
            else:
                scores_hors_sujet.append(meilleur_score)

        recall_5 = trouvees / pertinentes_total if pertinentes_total else 0.0
        score_moyen_correct = sum(scores_corrects) / len(scores_corrects) if scores_corrects else 0.0
        score_max_hors_sujet = max(scores_hors_sujet) if scores_hors_sujet else 0.0
        seuil_propose = (
            (score_moyen_correct + score_max_hors_sujet) / 2
            if scores_corrects and scores_hors_sujet else None
        )
        latence_moyenne = sum(latences) / len(latences) if latences else 0.0

        return {
            "modele": modele_requete,
            "recall@5": round(recall_5, 3),
            "score_moyen_bonnes_reponses": round(score_moyen_correct, 4),
            "score_max_hors_sujet": round(score_max_hors_sujet, 4),
            "seuil_propose": round(seuil_propose, 4) if seuil_propose is not None else None,
            "latence_moyenne_ms": round(latence_moyenne, 1),
        }
    finally:
        if ancien is not None:
            os.environ["VOYAGE_MODEL_QUERY"] = ancien
        else:
            os.environ.pop("VOYAGE_MODEL_QUERY", None)


async def main(chemin_questions: Path, modeles_requete):
    print("=" * 70)
    print("📊 ÉVALUATION RAG — FORMA-IA")
    print("=" * 70)

    if not chemin_questions.exists():
        print(f"\n❌ Fichier introuvable : {chemin_questions}")
        return False

    questions = charger_questions(chemin_questions)
    if not questions:
        print(f"\n❌ Aucune question dans {chemin_questions}.")
        return False

    nb_pertinentes = sum(1 for q in questions if q.get("pertinente"))
    nb_hors_sujet = len(questions) - nb_pertinentes
    print(f"\n📋 {len(questions)} question(s) : {nb_pertinentes} pertinente(s), {nb_hors_sujet} hors sujet.")

    resultats = []
    for modele in modeles_requete:
        print(f"\n🔍 Évaluation avec le modèle de requête : {modele}...")
        resultats.append(await evaluer_pour_modele(questions, modele))

    print("\n" + "=" * 70)
    print("📊 RÉSULTATS")
    print("=" * 70)
    print(f"{'Modèle':<20} {'Recall@5':<10} {'Score moy.':<12} {'Max hors-sujet':<16} {'Seuil proposé':<15} {'Latence (ms)'}")
    for r in resultats:
        print(
            f"{r['modele']:<20} {r['recall@5']:<10} {r['score_moyen_bonnes_reponses']:<12} "
            f"{r['score_max_hors_sujet']:<16} {str(r['seuil_propose']):<15} {r['latence_moyenne_ms']}"
        )

    print("\nℹ️ Le seuil proposé n'est PAS appliqué automatiquement. Choisissez-le")
    print("   vous-même (RAG_MIN_SCORE dans .env) à partir de ce tableau.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=CHEMIN_QUESTIONS_DEFAUT)
    parser.add_argument("--modeles-requete", type=str, default=None,
                         help="Liste séparée par des virgules, ex: voyage-4-large,voyage-4")
    args = parser.parse_args()

    if args.modeles_requete:
        modeles = [m.strip() for m in args.modeles_requete.split(",") if m.strip()]
    else:
        modeles = [os.getenv("VOYAGE_MODEL_QUERY", "voyage-4-large")]

    succes = asyncio.run(main(args.questions, modeles))
    sys.exit(0 if succes else 1)
