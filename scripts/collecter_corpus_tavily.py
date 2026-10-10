# scripts/collecter_corpus_tavily.py
# ============================================================
# COLLECTE TAVILY — Corpus benchmark M1 (Étape E, "Préparation soutenance")
# ============================================================
# Recherche des annonces réelles via Tavily pour alimenter le corpus d'annotation.
# AUCUN appel réseau n'est effectué sans confirmation interactive explicite.
# Catégorie Tavily : 'collecte' (comptabilisée séparément dans le quota mensuel).
#
# Ce script produit uniquement des entrées SANS champ 'gold' — l'annotation
# (is_opportunity, domain, budget_expected, etc.) doit être faite manuellement
# par l'annotateur humain conformément au protocole :
#   docs/protocole_annotation_corpus_m1.md
#
# Les résultats sont dédupliqués par URL et sauvegardés dans :
#   data/corpus_veille/collecte_tavily_{YYYYMMDD}.jsonl
#
# Usage : python scripts/collecter_corpus_tavily.py [--dry-run] [--limit N]
#   --dry-run   Affiche l'estimation et les requêtes sans rien appeler
#   --limit N   Limite le nombre de requêtes (défaut : toutes)
# ============================================================

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv
load_dotenv(RACINE / ".env")

from app.services.veille.tavily_service import TavilyService
from app.services.veille import tavily_quota_service

# ============================================================
# LISTE DE REQUÊTES — domaines ALTIORA
# ============================================================
# 30 requêtes ciblées (≈ 60 appels HTTP max avec fallback).
# Objectif : mélanger positifs attendus (opportunités réelles) et
# documents neutres (bruit naturel des moteurs) pour diversifier le corpus.
# ============================================================

REQUETES = [
    # --- Intelligence artificielle ---
    {"query": "formation intelligence artificielle Madagascar 2026", "domaine_attendu": "ia"},
    {"query": "prestataire formation IA Antananarivo appel offres", "domaine_attendu": "ia"},
    {"query": "formation machine learning data science Madagascar", "domaine_attendu": "ia"},
    {"query": "formation prompt engineering IA générative Madagascar", "domaine_attendu": "ia"},
    {"query": "consultant formateur IA Madagascar recrutement", "domaine_attendu": "ia"},
    {"query": "appel offres renforcement capacités numériques IA Madagascar", "domaine_attendu": "ia"},

    # --- Data / analyse de données ---
    {"query": "formation analyse données Excel Madagascar 2026", "domaine_attendu": "data"},
    {"query": "formation Power BI tableaux de bord Antananarivo", "domaine_attendu": "data"},
    {"query": "formation data analyst Madagascar entreprise", "domaine_attendu": "data"},
    {"query": "appel offres formation traitement données Madagascar", "domaine_attendu": "data"},

    # --- Bureautique ---
    {"query": "formation bureautique Word Excel Madagascar fonctionnaires", "domaine_attendu": "bureautique"},
    {"query": "appel offres formation outils bureautiques administration publique Madagascar", "domaine_attendu": "bureautique"},
    {"query": "formation Microsoft Office Antananarivo prestataire", "domaine_attendu": "bureautique"},
    {"query": "formation automatisation tâches bureau Madagascar", "domaine_attendu": "bureautique"},

    # --- DevOps ---
    {"query": "formation DevOps Docker Kubernetes Madagascar", "domaine_attendu": "devops"},
    {"query": "mission freelance DevOps CI CD Madagascar", "domaine_attendu": "devops"},
    {"query": "recrutement formateur DevOps Antananarivo", "domaine_attendu": "devops"},

    # --- Développement web / mobile ---
    {"query": "formation développement web JavaScript React Madagascar", "domaine_attendu": "developpement"},
    {"query": "formation développeur mobile Flutter Android Madagascar", "domaine_attendu": "developpement"},
    {"query": "appel offres formation programmation Madagascar 2026", "domaine_attendu": "developpement"},
    {"query": "recrutement formateur développement web Antananarivo", "domaine_attendu": "developpement"},

    # --- Requêtes transverses (mélange positifs + bruit attendu) ---
    {"query": "appel offres formation professionnelle numérique Madagascar", "domaine_attendu": None},
    {"query": "renforcement compétences numériques ONG Madagascar 2026", "domaine_attendu": None},
    {"query": "offre emploi formateur informatique Madagascar", "domaine_attendu": None},
    {"query": "marché public formation informatique Madagascar", "domaine_attendu": None},

    # --- Requêtes susceptibles de générer du bruit (négatifs utiles) ---
    {"query": "actualités technologie Madagascar 2026", "domaine_attendu": None},
    {"query": "startup tech Madagascar investissement", "domaine_attendu": None},
    {"query": "Madagascar numérique développement économique", "domaine_attendu": None},
    {"query": "emploi Madagascar Antananarivo offres diverses", "domaine_attendu": None},
    {"query": "conférence IA Afrique Madagascar événement", "domaine_attendu": None},
]

CORPUS_DIR = RACINE / "data" / "corpus_veille"
APPELS_HTTP_PAR_REQUETE = 2  # primary + fallback possible


def _formater_entree(resultat: Dict[str, Any], query: str, index_global: int) -> Optional[Dict[str, Any]]:
    """Convertit un résultat Tavily en entrée corpus (sans 'gold')."""
    url = resultat.get("url", "")
    titre = (resultat.get("title") or "").strip()
    contenu = (resultat.get("content") or "").strip()

    # raw_text = titre + contenu (max 500 chars pour garder les textes denses)
    parties = []
    if titre:
        parties.append(titre)
    if contenu:
        parties.append(contenu[:400])
    raw_text = " — ".join(parties).strip()

    if len(raw_text) < 30:
        return None

    return {
        "id": f"tavily-{date.today().strftime('%Y%m%d')}-{index_global:04d}",
        "source_type": "site_web",
        "date_collected": date.today().isoformat(),
        "url": url,
        "query_used": query,
        "raw_text": raw_text,
        # Pas de champ 'gold' — à annoter manuellement
        "annotator": None,
        "notes": f"Collecté via Tavily (requête: '{query}'). À annoter.",
    }


async def main(dry_run: bool = False, limit: Optional[int] = None) -> bool:
    print("=" * 70)
    print("🌐 COLLECTE CORPUS TAVILY — FORMA-IA M1")
    print("=" * 70)

    # Vérification présence clé API (nom seulement, jamais la valeur)
    import os
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ TAVILY_API_KEY absente du .env — collecte impossible.")
        return False

    requetes = REQUETES[:limit] if limit else REQUETES
    nb_requetes = len(requetes)
    nb_appels_max = nb_requetes * APPELS_HTTP_PAR_REQUETE

    etat = tavily_quota_service.etat_pour_route()
    restant = etat["restant"]
    plafond_dur = etat["configuration"]["plafond_dur"]
    total_consomme = etat["total_appels"]

    print(f"\n📊 ESTIMATION AVANT TOUT APPEL RÉEL")
    print(f"   Requêtes planifiées    : {nb_requetes}")
    print(f"   Appels HTTP max        : ~{nb_appels_max} (× 2 avec fallback Tavily)")
    print(f"   Quota mensuel restant  : {restant}/1000 (consommé : {total_consomme})")
    print(f"   Après collecte         : ~{total_consomme + nb_appels_max}/{plafond_dur} (plafond dur)")
    print(f"   Résultats attendus     : ~{nb_requetes * 5} à {nb_requetes * 10} entrées brutes")
    print(f"   (dédup. par URL → moins d'entrées uniques)")
    print(f"   Fichier de sortie      : data/corpus_veille/collecte_tavily_{date.today().strftime('%Y%m%d')}.jsonl")

    if total_consomme + nb_appels_max > plafond_dur:
        print(f"\n⚠️  ATTENTION : le plafond dur ({plafond_dur}) pourrait être atteint.")
        print(f"   Réduire avec --limit N si nécessaire.")

    if dry_run:
        print(f"\n🔍 MODE --dry-run : aucun appel effectué.")
        print(f"\n   Requêtes prévues :")
        for i, r in enumerate(requetes, 1):
            print(f"   {i:2d}. {r['query']}")
        return True

    print("=" * 70)
    try:
        reponse = input(f"\n❓ Lancer la collecte réelle ({nb_requetes} requêtes, ~{nb_appels_max} appels HTTP) ? [o/N] ").strip().lower()
    except EOFError:
        print("\n❌ Entrée non interactive — collecte annulée.")
        return False

    if reponse not in ("o", "oui", "y", "yes"):
        print("❌ Collecte annulée par l'utilisateur.")
        return False

    service = TavilyService()
    urls_vus: set = set()
    entrees: List[Dict[str, Any]] = []
    index_global = 0
    erreurs = 0

    print(f"\n⏳ Collecte en cours ({nb_requetes} requêtes)...\n")

    for i, item in enumerate(requetes, 1):
        q = item["query"]
        print(f"  [{i:2d}/{nb_requetes}] {q[:60]}...", end=" ", flush=True)
        try:
            resultats = await service.search(q, categorie="collecte")
            nb_nouveaux = 0
            for res in resultats:
                url = res.get("url", "")
                if url and url in urls_vus:
                    continue
                entree = _formater_entree(res, q, index_global)
                if entree:
                    entrees.append(entree)
                    if url:
                        urls_vus.add(url)
                    index_global += 1
                    nb_nouveaux += 1
            print(f"→ {nb_nouveaux} entrée(s) nouvelle(s)")
        except Exception as exc:
            print(f"→ ERREUR : {exc}")
            erreurs += 1

    # Sauvegarde
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_sortie = CORPUS_DIR / f"collecte_tavily_{horodatage}.jsonl"
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        for e in entrees:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 70}")
    print(f"✅ Collecte terminée.")
    print(f"   Entrées uniques sauvegardées : {len(entrees)}")
    print(f"   Erreurs de requête           : {erreurs}/{nb_requetes}")
    print(f"   Fichier                      : {chemin_sortie}")
    print(f"\n⚠️  Ces entrées sont SANS annotation 'gold'.")
    print(f"   Ouvrez le fichier et annotez chaque ligne manuellement")
    print(f"   selon docs/protocole_annotation_corpus_m1.md avant")
    print(f"   d'ajouter les lignes dans data/corpus_veille/corpus_v1.jsonl.")
    print(f"\n   Validez la structure avec :")
    print(f"   python scripts/valider_corpus.py data/corpus_veille/corpus_v1.jsonl")
    print(f"{'=' * 70}")

    return erreurs < nb_requetes  # succès partiel accepté


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collecte Tavily — corpus benchmark M1")
    parser.add_argument("--dry-run", action="store_true", help="Estimation seule, aucun appel")
    parser.add_argument("--limit", type=int, default=None, help="Nombre max de requêtes")
    args = parser.parse_args()

    ok = asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
    sys.exit(0 if ok else 1)
