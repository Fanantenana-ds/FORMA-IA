# scripts/diagnostic_rag.py
# ============================================================
# DIAGNOSTIC — Module RAG (C3, Étape H)
# ============================================================
# Vérifie, DANS L'ORDRE, que le module RAG est opérationnel de bout en
# bout : PostgreSQL -> pgvector -> schéma -> .env -> clé Voyage (UN SEUL
# appel réel, minimal) -> modèles -> limites/confidentialité -> Groq ->
# contenu indexé -> cache -> résolution de formation -> route /chat.
#
# Le palier gratuit Voyage (3 RPM / 10 000 TPM par défaut) n'est PAS une
# erreur : affiché comme information, avec la capacité réelle.
#
# Arrêt à la première erreur BLOQUANTE (infrastructure : DB, extension,
# schéma, clé Voyage invalide). Les autres points signalent ATTENTION et
# le diagnostic continue (ex. catalogue vide avant l'Étape I).
#
# RÈGLE ABSOLUE : aucune valeur de clé secrète n'est jamais affichée ni
# journalisée — seule la PRÉSENCE des variables .env est vérifiée.
#
# Sortie : affichage console + journal JSON horodaté dans logs/.
#
# Exécution : python scripts/diagnostic_rag.py
# ============================================================

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parents[1]
load_dotenv(RACINE / ".env")

from sqlalchemy import text

OK, ATTENTION, ECHEC = "OK", "ATTENTION", "ÉCHEC"

VARIABLES_ENV = [
    ("VOYAGE_API_KEY", True),
    ("VOYAGE_API_KEY_SOUTENANCE", False),
    ("VOYAGE_KEY_PROFILE", False),
    ("VOYAGE_MODEL_DOCUMENT", False),
    ("VOYAGE_MODEL_QUERY", False),
    ("VOYAGE_RPM", False),
    ("VOYAGE_TPM", False),
    ("VOYAGE_OPT_OUT", False),
    ("GROQ_API_KEY", True),
    ("GROQ_MODEL", False),
    ("LLM_PROVIDER", False),
]


def _afficher(nom_etape: str, statut: str, message: str, cause: str = "", solution: str = "") -> None:
    symbole = {"OK": "✅", "ATTENTION": "⚠️ ", "ÉCHEC": "❌"}[statut]
    print(f"[ÉTAPE] Vérification {nom_etape} ..... {statut} {symbole}")
    print(f"        {message}")
    if cause:
        print(f"        Cause probable : {cause}")
    if solution:
        print(f"        Solution probable : {solution}")


def _resultat(nom: str, statut: str, message: str, cause: str = "", solution: str = "", bloquant: bool = False) -> dict:
    _afficher(nom, statut, message, cause, solution)
    return {
        "etape": nom, "statut": statut, "message": message,
        "cause": cause, "solution": solution, "bloquant": bloquant,
    }


# ============================================================
# 1. PostgreSQL
# ============================================================

def verifier_postgresql() -> dict:
    from app.database import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return _resultat("PostgreSQL", OK, "Connexion établie.")
    except Exception as exc:
        return _resultat(
            "PostgreSQL", ECHEC, f"Connexion impossible : {type(exc).__name__} — {exc}",
            cause="PostgreSQL non démarré, ou DATABASE_URL incorrecte dans .env.",
            solution="Démarrer PostgreSQL localement et vérifier DATABASE_URL.",
            bloquant=True,
        )


# ============================================================
# 2. Extension pgvector
# ============================================================

def verifier_extension_vector() -> dict:
    from app.database import engine
    try:
        with engine.connect() as conn:
            ligne = conn.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )).fetchone()
        if ligne is None:
            return _resultat(
                "extension pgvector", ECHEC, "Extension 'vector' non installée sur cette base.",
                cause="CREATE EXTENSION vector n'a jamais été exécuté.",
                solution="Exécuter scripts/setup_pgvector.py.",
                bloquant=True,
            )
        return _resultat("extension pgvector", OK, f"pgvector {ligne[0]} actif.")
    except Exception as exc:
        return _resultat(
            "extension pgvector", ECHEC, f"Vérification impossible : {exc}",
            solution="Vérifier la connexion PostgreSQL (étape précédente).", bloquant=True,
        )


# ============================================================
# 3. Table knowledge_base + dimension 1024
# ============================================================

def verifier_table_et_dimension() -> dict:
    from app.database import engine
    try:
        with engine.connect() as conn:
            existe = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = 'knowledge_base')"
            )).scalar()
            if not existe:
                return _resultat(
                    "table knowledge_base", ECHEC, "Table 'knowledge_base' absente.",
                    cause="Schéma jamais créé (Alembic ne suit pas cette table, hors périmètre).",
                    solution="Exécuter scripts/finaliser_schema_knowledge_base.py.",
                    bloquant=True,
                )
            type_colonne = conn.execute(text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'knowledge_base'::regclass AND attname = 'embedding'"
            )).scalar()
        if type_colonne is None:
            return _resultat(
                "table knowledge_base", ECHEC, "Colonne 'embedding' absente de knowledge_base.",
                solution="Exécuter scripts/finaliser_schema_knowledge_base.py.", bloquant=True,
            )
        if "1024" not in type_colonne:
            return _resultat(
                "table knowledge_base", ECHEC, f"Dimension inattendue : '{type_colonne}' (1024 attendu).",
                cause="Schéma créé avec une ancienne dimension (avant migration v1024).",
                solution="Exécuter scripts/migrer_knowledge_base_v1024.py.", bloquant=True,
            )
        return _resultat("table knowledge_base", OK, f"Table présente, embedding {type_colonne}.")
    except Exception as exc:
        return _resultat("table knowledge_base", ECHEC, f"Vérification impossible : {exc}", bloquant=True)


# ============================================================
# 4. Variables .env (présence uniquement — jamais la valeur)
# ============================================================

def verifier_variables_env() -> dict:
    manquantes_bloquantes, manquantes_optionnelles = [], []
    for nom, requise in VARIABLES_ENV:
        if not os.getenv(nom, "").strip():
            (manquantes_bloquantes if requise else manquantes_optionnelles).append(nom)

    if manquantes_bloquantes:
        return _resultat(
            "variables .env", ECHEC,
            f"Variable(s) requise(s) absente(s) : {', '.join(manquantes_bloquantes)}.",
            cause="Le fichier .env n'a pas été renseigné (modifié uniquement par l'utilisateur).",
            solution="Demander à l'utilisateur de renseigner ces variables dans .env.",
            bloquant=True,
        )
    if manquantes_optionnelles:
        return _resultat(
            "variables .env", ATTENTION,
            f"Variable(s) optionnelle(s) absente(s) (valeurs par défaut utilisées) : "
            f"{', '.join(manquantes_optionnelles)}.",
        )
    return _resultat("variables .env", OK, "Toutes les variables attendues sont présentes.")


# ============================================================
# 5. Clé Voyage valide — UN SEUL appel réel, minimal
# ============================================================

async def verifier_cle_voyage() -> dict:
    from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError
    try:
        provider = get_embedding_provider()
    except EmbeddingProviderError as exc:
        return _resultat(
            "clé Voyage", ECHEC, str(exc),
            solution="Vérifier VOYAGE_API_KEY / VOYAGE_KEY_PROFILE dans .env.", bloquant=True,
        )

    try:
        vecteur = await provider.embed_query("test de connexion", attente_max_s=None)
        return _resultat(
            "clé Voyage", OK,
            f"Appel réel réussi (1 requête), vecteur de dimension {len(vecteur)} reçu.",
        )
    except EmbeddingProviderError as exc:
        return _resultat(
            "clé Voyage", ECHEC, str(exc),
            cause="Clé invalide, quota dépassé, ou API Voyage injoignable.",
            solution="Vérifier VOYAGE_API_KEY et la connexion réseau.", bloquant=True,
        )


# ============================================================
# 6. Modèles configurés + compatibilité avec la base
# ============================================================

def verifier_modeles() -> dict:
    from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError
    from app.services.rag.recherche_service import verifier_compatibilite_avec_base, IncompatibiliteModeleError

    try:
        provider = get_embedding_provider()
    except EmbeddingProviderError as exc:
        return _resultat("modèles Voyage", ECHEC, str(exc))

    message = f"Document='{provider.modele_document}', Requête='{provider.modele_requete}'."
    try:
        verifier_compatibilite_avec_base(provider.modele_document, None)
        verifier_compatibilite_avec_base(provider.modele_requete, None)
        return _resultat("modèles Voyage", OK, message + " Compatibles avec le contenu déjà indexé.")
    except IncompatibiliteModeleError as exc:
        return _resultat(
            "modèles Voyage", ECHEC, f"{message} INCOMPATIBLE avec la base : {exc}",
            solution="Aligner VOYAGE_MODEL_DOCUMENT/QUERY avec la famille déjà indexée, ou réindexer.",
        )


# ============================================================
# 7. Limites (RPM/TPM) et confidentialité (VOYAGE_OPT_OUT)
# ============================================================

def verifier_limites_et_confidentialite() -> dict:
    from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError
    try:
        provider = get_embedding_provider()
    except EmbeddingProviderError as exc:
        return _resultat("limites & confidentialité", ECHEC, str(exc))

    cfg = provider.config
    message = (
        f"Palier configuré : {cfg.rpm} RPM / {cfg.tpm} TPM (le palier gratuit n'est PAS une "
        f"erreur — capacité réelle ≈ {cfg.rpm} recherche(s)/minute). "
        f"VOYAGE_OPT_OUT={'true (confidentiel autorisé)' if cfg.opt_out else 'false (formations confidentielles non indexées)'}."
    )
    return _resultat("limites & confidentialité", OK, message)


# ============================================================
# 8. Groq (Provider Abstraction LLM) — configuration, pas d'appel réel
# ============================================================

def verifier_groq() -> dict:
    from app.services.llm import get_llm_provider, LLMNotAvailableError
    try:
        get_llm_provider()
        return _resultat("Groq (LLM)", OK, "Fournisseur LLM initialisé (aucun appel réel effectué ici).")
    except LLMNotAvailableError as exc:
        return _resultat(
            "Groq (LLM)", ATTENTION, f"Fournisseur LLM indisponible : {exc}",
            cause="GROQ_API_KEY absente ou LLM_PROVIDER mal configuré.",
            solution="Vérifier GROQ_API_KEY et LLM_PROVIDER dans .env. Résumés/chat en mode dégradé sans ceci.",
        )


# ============================================================
# 9. Nombre de chunks par collection
# ============================================================

def verifier_chunks_par_collection() -> dict:
    from app.database import engine
    with engine.connect() as conn:
        lignes = conn.execute(text(
            "SELECT collection, COUNT(*) FROM knowledge_base GROUP BY collection ORDER BY collection"
        )).all()
    if not lignes:
        return _resultat(
            "contenu indexé", ATTENTION, "Aucun chunk en base (normal avant l'Étape I — import du corpus).",
        )
    detail = ", ".join(f"{collection}={nb}" for collection, nb in lignes)
    return _resultat("contenu indexé", OK, f"Chunks par collection : {detail}.")


# ============================================================
# 10. Documents sans résumé
# ============================================================

def verifier_resumes_manquants() -> dict:
    from app.services.rag import registry_service as registre
    entrees = registre.entrees_sans_resume()
    if not entrees:
        return _resultat("résumés", OK, "Tous les documents indexés ont un résumé (ou aucun document indexé).")
    noms = ", ".join(e.fichier for e in entrees[:5])
    suffixe = f" (+{len(entrees) - 5} autre(s))" if len(entrees) > 5 else ""
    return _resultat(
        "résumés", ATTENTION, f"{len(entrees)} document(s) sans résumé : {noms}{suffixe}.",
        solution="Exécuter scripts/generer_resumes.py.",
    )


# ============================================================
# 11. Cache de requêtes + couverture des questions de démo
# ============================================================

def verifier_cache_et_demo() -> dict:
    from app.services.rag import query_cache_service as cache
    from app.services.rag.embedding_provider import get_embedding_provider, EmbeddingProviderError

    taille = cache.taille_cache()

    chemin_demo = RACINE / "data" / "rag" / "questions_demo.yaml"
    if not chemin_demo.exists():
        return _resultat("cache & questions de démo", ATTENTION, f"Cache : {taille} entrée(s). questions_demo.yaml absent.")

    import yaml
    with open(chemin_demo, "r", encoding="utf-8") as f:
        questions = (yaml.safe_load(f) or {}).get("questions", [])

    try:
        modele_requete = get_embedding_provider().modele_requete
    except EmbeddingProviderError:
        return _resultat("cache & questions de démo", ATTENTION, f"Cache : {taille} entrée(s). Modèle de requête indisponible pour vérifier la couverture.")

    couvertes = sum(1 for q in questions if cache.depuis_cache(q, modele_requete) is not None)
    message = f"Cache : {taille} entrée(s). Questions de démo couvertes : {couvertes}/{len(questions)}."
    if questions and couvertes < len(questions):
        return _resultat(
            "cache & questions de démo", ATTENTION, message,
            solution="Exécuter scripts/prechauffer_cache.py avant une démo/soutenance.",
        )
    return _resultat("cache & questions de démo", OK, message)


# ============================================================
# 12. Résolution d'une formation test (catalogue, pur Python)
# ============================================================

def verifier_resolution_formation() -> dict:
    from app.services.rag.catalogue_service import charger_catalogue
    from app.services.rag.formation_resolver_service import resoudre_formation

    formations = charger_catalogue()
    if not formations:
        return _resultat(
            "résolution de formation", ATTENTION,
            "Catalogue vide (normal avant l'Étape I) : test non exécuté.",
        )
    premiere = formations[0]
    resolution = resoudre_formation(premiere.titre)
    if resolution.statut == "trouvee" and resolution.formation and resolution.formation.code == premiere.code:
        return _resultat(
            "résolution de formation", OK,
            f"'{premiere.titre}' résolu correctement vers '{premiere.code}'.",
        )
    return _resultat(
        "résolution de formation", ATTENTION,
        f"'{premiere.titre}' résolu en statut '{resolution.statut}' (attendu 'trouvee').",
    )


# ============================================================
# 13. Route /ia/rag/chat joignable (montage + dépendances, sans appel LLM)
# ============================================================

def verifier_route_chat() -> dict:
    try:
        from app.api.v1.router import api_router
        chemins = {route.path for route in api_router.routes}
        if "/ia/rag/chat" not in chemins:
            return _resultat(
                "route /ia/rag/chat", ECHEC, "Route absente du routeur applicatif.",
                cause="rag_ia.router non monté dans app/api/v1/router.py.",
                solution="Vérifier l'include_router(rag_ia.router) dans router.py.",
            )
        from app.orchestrator.chat_orchestrator import get_chat_orchestrator
        get_chat_orchestrator()
        return _resultat(
            "route /ia/rag/chat", OK,
            "Route montée et ChatOrchestrator s'instancie sans erreur (aucun appel LLM effectué ici).",
        )
    except Exception as exc:
        return _resultat(
            "route /ia/rag/chat", ECHEC, f"Erreur : {type(exc).__name__} — {exc}",
            solution="Consulter la trace complète (logs/) et l'import de chat_orchestrator.py.",
        )


# ============================================================
# ORCHESTRATION
# ============================================================

async def main() -> bool:
    print("=" * 70)
    print("🩺 DIAGNOSTIC RAG — FORMA-IA (module C3)")
    print("=" * 70)

    resultats = []

    # Étapes synchrones, dans l'ordre du CDC
    for verification in (
        verifier_postgresql,
        verifier_extension_vector,
        verifier_table_et_dimension,
        verifier_variables_env,
    ):
        r = verification()
        resultats.append(r)
        if r["bloquant"] and r["statut"] == ECHEC:
            return _terminer(resultats, succes=False)

    r = await verifier_cle_voyage()
    resultats.append(r)
    if r["bloquant"] and r["statut"] == ECHEC:
        return _terminer(resultats, succes=False)

    for verification in (
        verifier_modeles,
        verifier_limites_et_confidentialite,
        verifier_groq,
        verifier_chunks_par_collection,
        verifier_resumes_manquants,
        verifier_cache_et_demo,
        verifier_resolution_formation,
        verifier_route_chat,
    ):
        resultats.append(verification())

    echecs = [r for r in resultats if r["statut"] == ECHEC]
    return _terminer(resultats, succes=not echecs)


def _terminer(resultats: list, succes: bool) -> bool:
    print("\n" + "=" * 70)
    nb_ok = sum(1 for r in resultats if r["statut"] == OK)
    nb_attention = sum(1 for r in resultats if r["statut"] == ATTENTION)
    nb_echec = sum(1 for r in resultats if r["statut"] == ECHEC)
    print(f"📊 Résumé : {nb_ok} OK, {nb_attention} ATTENTION, {nb_echec} ÉCHEC.")
    print("✅ DIAGNOSTIC TERMINÉ." if succes else "❌ DIAGNOSTIC INTERROMPU (erreur bloquante).")
    print("=" * 70)

    dossier_logs = RACINE / "logs"
    dossier_logs.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_journal = dossier_logs / f"diagnostic_rag_{horodatage}.json"
    with open(chemin_journal, "w", encoding="utf-8") as f:
        json.dump(
            {"horodatage": datetime.now().isoformat(), "succes": succes, "resultats": resultats},
            f, ensure_ascii=False, indent=2,
        )
    print(f"📝 Journal : {chemin_journal}")

    return succes


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
