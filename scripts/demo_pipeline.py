# scripts/demo_pipeline.py
# ============================================================
# DÉMO END-TO-END — FORMA-IA (Préparation soutenance)
# ============================================================
# Démontre le pipeline métier complet :
#   M1 (Veille) → M2 (TDR) → M3 (Offres) → Préparation (Budget + EDT)
#
# AUCUN appel Groq n'est effectué sans confirmation interactive.
# AUCUNE synchronisation Backend (sync_backend=False partout).
# AUCUNE lecture/écriture DB.
#
# Usage :
#   python scripts/demo_pipeline.py --dry-run        # estimation seule
#   python scripts/demo_pipeline.py                  # démo complète
#   python scripts/demo_pipeline.py --etapes M1,M2   # étapes sélectionnées
#
# Étapes disponibles : M1, M2, M3, PREP
# ============================================================

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv
load_dotenv(RACINE / ".env")

# ============================================================
# DONNÉES D'ENTRÉE SYNTHÉTIQUES — scénario de démonstration
# ============================================================
# Opportunité fictive réaliste (formation IA pour fonctionnaires)

TEXTE_OPPORTUNITE = """
APPEL À MANIFESTATION D'INTÉRÊT — PRESTATION DE FORMATION
Ministère de l'Économie Numérique et de la Communication (MENC)
Antananarivo, Madagascar — Octobre 2026

Le MENC lance un appel à candidatures pour la sélection d'un prestataire
de formation en intelligence artificielle et analyse de données à destination
de ses cadres techniques.

Objet : Formation « IA et Data pour décideurs publics »
Durée : 3 jours (24 heures)
Participants : 20 cadres et ingénieurs du Ministère
Lieu : Salle de conférence MENC, Antananarivo
Date prévue : 10-12 novembre 2026
Budget estimé : 15 000 000 MGA (tout compris)

Contenu attendu :
- Introduction à l'intelligence artificielle et aux outils LLM
- Analyse de données avec Python et Power BI
- Cas pratiques sur des données publiques malgaches

Les candidatures sont à envoyer avant le 30 septembre 2026 à :
formation@menc.gov.mg
"""

BRIEF_DEMO = {
    "client": "Ministère de l'Économie Numérique et de la Communication (MENC)",
    "titre": "Formation IA et Data pour décideurs publics",
    "objectifs": [
        "Comprendre les bases de l'intelligence artificielle et des LLM",
        "Savoir analyser des données avec Python et Power BI",
        "Appliquer ces compétences sur des données publiques malgaches",
    ],
    "public_cible": "Cadres et ingénieurs du MENC",
    "duree_jours": 3,
    "nb_participants": 20,
    "lieu": "Salle de conférence MENC, Antananarivo",
    "budget_client": 15_000_000,
    "contexte": "Formation commandée suite à l'appel à manifestation d'intérêt du MENC.",
    "contact": "formation@menc.gov.mg",
}

SESSION_INFO_DEMO = {
    "client": "MENC",
    "formateur": "Dr. Rakoto Jean",
    "nb_participants": 20,
    "lieu": "Salle de conférence MENC, Antananarivo",
    "date_debut": "2026-11-10",
    "date_fin": "2026-11-12",
}

RESSOURCES_DEMO = {
    "formateur": {
        "nom": "Dr. Rakoto Jean",
        "tarif_journalier": 500_000,
        "specialite": "IA et Data Science",
    },
    "salle": {
        "nom": "Salle MENC",
        "capacite": 30,
        "tarif_journalier": 150_000,
        "equipee": True,
    },
}

PROJET_INFO_DEMO = {
    "client": "MENC",
    "titre": "Formation IA et Data pour décideurs publics",
    "nb_participants": 20,
    "lieu": "Antananarivo",
}

ESTIMATION_APPELS_GROQ = {
    "M1": 1,   # analyser_texte → 1 appel LLM
    "M2": 1,   # generate → 1 appel LLM
    "M3": 2,   # offre_technique + offre_financiere → 2 appels LLM
    "PREP": 1, # generer_edt → 1 appel LLM (budget = Python pur, 0 appel)
}

COULEURS = {
    "titre":  "\033[1;36m",  # cyan gras
    "ok":     "\033[0;32m",  # vert
    "warn":   "\033[0;33m",  # jaune
    "err":    "\033[0;31m",  # rouge
    "dim":    "\033[0;37m",  # gris
    "reset":  "\033[0m",
}


def c(texte: str, style: str) -> str:
    return f"{COULEURS.get(style, '')}{texte}{COULEURS['reset']}"


def titre_etape(num: int, nom: str, total: int) -> None:
    print()
    print(c("=" * 70, "titre"))
    print(c(f"  ÉTAPE {num}/{total} — {nom}", "titre"))
    print(c("=" * 70, "titre"))


def afficher_json(data: Any, max_chars: int = 800) -> None:
    txt = json.dumps(data, ensure_ascii=False, indent=2)
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n  ... (tronqué)"
    print(c(txt, "dim"))


# ============================================================
# ÉTAPE M1 — VEILLE
# ============================================================

async def etape_m1(dry_run: bool) -> Optional[Dict[str, Any]]:
    """M1 : analyser_texte sur l'opportunité synthétique."""
    print(c("  Texte analysé :", "dim"))
    print(c(TEXTE_OPPORTUNITE[:300] + "...", "dim"))
    print()

    if dry_run:
        print(c("  [DRY-RUN] 1 appel Groq simulé — résultat fictif.", "warn"))
        return {
            "opportunities": [{
                "titre": "Formation IA et Data pour décideurs publics — MENC",
                "client": "Ministère de l'Économie Numérique (MENC)",
                "domaine": "ia",
                "budget": "15 000 000 MGA",
                "deadline": "2026-09-30",
                "score": 0.95,
                "is_opportunity": True,
            }]
        }

    from app.orchestrator.veille_orchestrator import VeilleOrchestrator
    orch = VeilleOrchestrator()
    t0 = time.perf_counter()
    result = await orch.analyser_texte(
        texte=TEXTE_OPPORTUNITE,
        source="demo_pipeline",
        sync_backend=False,
        date_reference=datetime(2026, 9, 27),
    )
    elapsed = time.perf_counter() - t0

    nb = len(result.get("opportunities", []))
    print(c(f"  ✅ {nb} opportunité(s) détectée(s) en {elapsed:.1f}s", "ok"))
    afficher_json(result.get("opportunities", []))
    return result


# ============================================================
# ÉTAPE M2 — TDR
# ============================================================

async def etape_m2(dry_run: bool, m1_result: Optional[Dict]) -> Optional[Dict[str, Any]]:
    """M2 : generate TDR à partir du brief."""
    print(c(f"  Brief client : {BRIEF_DEMO['client']}", "dim"))
    print(c(f"  Titre        : {BRIEF_DEMO['titre']}", "dim"))
    print()

    if dry_run:
        print(c("  [DRY-RUN] 1 appel Groq simulé — TDR fictif.", "warn"))
        return {
            "titre": BRIEF_DEMO["titre"],
            "client": BRIEF_DEMO["client"],
            "duree_jours": 3,
            "modules": [
                {"titre": "Introduction à l'IA", "duree_heures": 8},
                {"titre": "Analyse de données", "duree_heures": 8},
                {"titre": "Cas pratiques", "duree_heures": 8},
            ],
        }

    from app.orchestrator.tdr_orchestrator import TdrOrchestrator
    orch = TdrOrchestrator()
    t0 = time.perf_counter()
    result = await orch.generate(brief=BRIEF_DEMO)
    elapsed = time.perf_counter() - t0

    success = result.get("success", False)
    if success:
        data = result.get("data", {})
        print(c(f"  ✅ TDR généré en {elapsed:.1f}s", "ok"))
        print(c(f"  Titre  : {data.get('titre', '?')}", "dim"))
        print(c(f"  Review : {result.get('_review_id', '?')}", "dim"))
        afficher_json(data)
        return data
    else:
        print(c(f"  ❌ Échec TDR : {result.get('error', '?')}", "err"))
        return None


# ============================================================
# ÉTAPE M3 — OFFRES
# ============================================================

async def etape_m3(
    dry_run: bool, tdr_data: Optional[Dict]
) -> Optional[Dict[str, Any]]:
    """M3 : generate_complete offre technique + financière."""
    tdr = tdr_data or {
        "titre": BRIEF_DEMO["titre"],
        "client": BRIEF_DEMO["client"],
        "duree_jours": 3,
        "modules": [
            {"titre": "Introduction à l'IA", "duree_heures": 8},
            {"titre": "Analyse de données", "duree_heures": 8},
            {"titre": "Cas pratiques", "duree_heures": 8},
        ],
    }
    print(c(f"  TDR en entrée : {tdr.get('titre', '?')}", "dim"))
    print()

    if dry_run:
        print(c("  [DRY-RUN] 2 appels Groq simulés — offres fictives.", "warn"))
        return {
            "reference": "ALTIORA-MENC-2026-001",
            "duree_jours": 3,
            "offre_technique": {"titre": tdr["titre"], "approche": "..."},
            "offre_financiere": {"montant_total": 14_500_000, "devise": "MGA"},
        }

    from app.orchestrator.offre_orchestrator import OffreOrchestrator
    orch = OffreOrchestrator()
    t0 = time.perf_counter()
    result = await orch.generate_complete(
        tdr_data=tdr,
        session_info=SESSION_INFO_DEMO,
        options={"nb_participants": 20},
    )
    elapsed = time.perf_counter() - t0

    success = result.get("success", False)
    if success:
        data = result.get("data", {})
        print(c(f"  ✅ Offres générées en {elapsed:.1f}s", "ok"))
        mt = data.get("offre_financiere", {}).get("montant_total")
        if mt:
            print(c(f"  Montant total : {mt:,} MGA", "ok"))
        print(c(f"  Review : {result.get('_review_id', '?')}", "dim"))
        afficher_json(data)
        return data
    else:
        print(c(f"  ❌ Échec M3 : {result.get('error', '?')}", "err"))
        return None


# ============================================================
# ÉTAPE PREP — PRÉPARATION (Budget + EDT)
# ============================================================

async def etape_prep(
    dry_run: bool, offre_data: Optional[Dict]
) -> Optional[Dict[str, Any]]:
    """Préparation : calculer_budget (Python pur) + generer_edt (LLM)."""
    offre = offre_data or {
        "reference": "ALTIORA-MENC-2026-001",
        "duree_jours": 3,
        "modules": [
            {"titre": "Introduction à l'IA", "duree_heures": 8},
            {"titre": "Analyse de données", "duree_heures": 8},
            {"titre": "Cas pratiques", "duree_heures": 8},
        ],
    }
    print(c(f"  Offre en entrée : {offre.get('reference', '?')}", "dim"))
    print(c(f"  Durée : {offre.get('duree_jours', '?')} jours", "dim"))
    print()

    if dry_run:
        print(c("  [DRY-RUN] Budget Python pur (0 appel) + 1 appel Groq EDT simulé.", "warn"))
        return {
            "budget": {"cout_total": 2_050_000},
            "edt": {"jours": 3},
        }

    from app.orchestrator.preparation_orchestrator import PreparationOrchestrator
    orch = PreparationOrchestrator()
    t0 = time.perf_counter()
    result = await orch.generate_complete(
        offre_data=offre,
        projet_info=PROJET_INFO_DEMO,
        ressources=RESSOURCES_DEMO,
        options={
            "date_debut": "2026-11-10",
            "date_fin": "2026-11-12",
            "inclure_logistique": True,
            "inclure_administration": True,
        },
    )
    elapsed = time.perf_counter() - t0

    success = result.get("success", False)
    if success:
        budget = result.get("budget", {})
        edt = result.get("edt", {})
        print(c(f"  ✅ Préparation complète en {elapsed:.1f}s", "ok"))
        cout = budget.get("cout_total")
        if cout:
            print(c(f"  Coût total budget : {cout:,} MGA", "ok"))
        nb_jours_edt = len(edt.get("jours", []))
        print(c(f"  Jours EDT générés : {nb_jours_edt}", "ok"))
        print(c(f"  Review : {result.get('_review_id', '?')}", "dim"))
        afficher_json({"budget_cout_total": cout, "edt_jours": nb_jours_edt})
        return result
    else:
        print(c(f"  ❌ Échec Préparation : {result.get('error', '?')}", "err"))
        return None


# ============================================================
# MAIN
# ============================================================

async def main(dry_run: bool, etapes: list) -> bool:
    print()
    print(c("=" * 70, "titre"))
    print(c("  FORMA-IA — DÉMO PIPELINE END-TO-END", "titre"))
    print(c(f"  Scénario : Formation MENC — {datetime.now().strftime('%Y-%m-%d %H:%M')}", "titre"))
    print(c("=" * 70, "titre"))

    etapes_actives = [e.upper() for e in etapes]
    nb_appels = sum(v for k, v in ESTIMATION_APPELS_GROQ.items() if k in etapes_actives)

    print()
    print(c("  ESTIMATION AVANT TOUT APPEL", "warn"))
    print(c(f"  Étapes sélectionnées  : {', '.join(etapes_actives)}", "dim"))
    print(c(f"  Appels Groq estimés   : ~{nb_appels}", "dim"))
    print(c(f"  Latence estimée       : ~{nb_appels * 10}s (10s/appel moyen)", "dim"))
    print(c("  Sync Backend          : NON (sync_backend=False partout)", "dim"))
    print(c("  Lecture/écriture DB   : AUCUNE", "dim"))
    print()

    if dry_run:
        print(c("  MODE --dry-run : aucun appel Groq. Les résultats sont fictifs.", "warn"))
        print()
    else:
        try:
            rep = input(c(
                f"  Lancer la démo réelle ({nb_appels} appels Groq, ~{nb_appels * 10}s) ? [o/N] ",
                "warn"
            )).strip().lower()
        except EOFError:
            print(c("  Entrée non interactive — démo annulée.", "err"))
            return False
        if rep not in ("o", "oui", "y", "yes"):
            print(c("  Démo annulée.", "dim"))
            return False
        print()

    resultats: Dict[str, Any] = {}
    nb = len(etapes_actives)

    t_global = time.perf_counter()

    # --- M1 ---
    if "M1" in etapes_actives:
        titre_etape(etapes_actives.index("M1") + 1, "M1 — VEILLE MARCHÉ (analyser_texte)", nb)
        resultats["m1"] = await etape_m1(dry_run)

    # --- M2 ---
    if "M2" in etapes_actives:
        titre_etape(etapes_actives.index("M2") + 1, "M2 — GÉNÉRATION TDR", nb)
        resultats["m2"] = await etape_m2(dry_run, resultats.get("m1"))

    # --- M3 ---
    if "M3" in etapes_actives:
        titre_etape(etapes_actives.index("M3") + 1, "M3 — OFFRES TECHNIQUE & FINANCIÈRE", nb)
        resultats["m3"] = await etape_m3(dry_run, resultats.get("m2"))

    # --- PREP ---
    if "PREP" in etapes_actives:
        titre_etape(etapes_actives.index("PREP") + 1, "PRÉPARATION — BUDGET & EDT", nb)
        resultats["prep"] = await etape_prep(dry_run, resultats.get("m3"))

    elapsed_global = time.perf_counter() - t_global

    # --- BILAN ---
    print()
    print(c("=" * 70, "titre"))
    print(c("  BILAN DE LA DÉMO", "titre"))
    print(c("=" * 70, "titre"))
    for etape in etapes_actives:
        key = etape.lower()
        val = resultats.get(key)
        # None = échec réel ; {} ou dict non vide = succès (y compris fallback template)
        etat = c("✅ OK", "ok") if val is not None else c("❌ ECHEC", "err")
        print(f"  {etape:6s} : {etat}")
    print()
    print(c(f"  Durée totale : {elapsed_global:.1f}s", "dim"))
    if dry_run:
        print(c("  (aucun appel Groq réel — relancer sans --dry-run pour la démo complète)", "warn"))
    print()

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Démo pipeline end-to-end FORMA-IA")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimation et simulation — aucun appel Groq ni Tavily",
    )
    parser.add_argument(
        "--etapes",
        type=str,
        default="M1,M2,M3,PREP",
        help="Étapes à exécuter parmi M1,M2,M3,PREP (défaut : toutes)",
    )
    args = parser.parse_args()
    etapes = [e.strip() for e in args.etapes.split(",") if e.strip()]

    etapes_connues = {"M1", "M2", "M3", "PREP"}
    inconnues = set(etapes) - etapes_connues
    if inconnues:
        print(f"Étapes inconnues : {inconnues}. Disponibles : {etapes_connues}")
        sys.exit(1)

    ok = asyncio.run(main(dry_run=args.dry_run, etapes=etapes))
    sys.exit(0 if ok else 1)
