"""
scripts/reimporter_aide_plateforme.py
=============================================================
Réindexe les guides utilisateur de la collection aide_plateforme.

Ce script :
  1. Supprime les anciens chunks aide_plateforme de la base vectorielle
  2. Supprime les entrées correspondantes dans l'index_registry.json
  3. Indexe les nouveaux fichiers depuis data/rag/aide_plateforme/

Exécution :
    cd C:\\PROJET_FANA\\FORMA_IA\\backend
    python scripts/reimporter_aide_plateforme.py

Prérequis :
    - Le serveur FastAPI doit être ARRÊTÉ (pas de conflits DB)
    - Les clés VOYAGE_API_KEY et DATABASE_URL doivent être dans .env
=============================================================
"""

import asyncio
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv
load_dotenv(RACINE / ".env")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from app.database import SessionLocal
    from app.models.knowledge_base import KnowledgeBase
    from app.services.rag import registry_service as registre
    from app.orchestrator.rag_orchestrator import RagOrchestrator

    dossier_guides = RACINE / "docs" / "guides_plateforme"
    fichiers = sorted(dossier_guides.glob("*.md"))

    if not fichiers:
        logger.error(f"Aucun fichier .md trouvé dans {dossier_guides}")
        sys.exit(1)

    logger.info(f"📂 {len(fichiers)} guide(s) trouvé(s) dans docs/guides_plateforme/")

    # ── Étape 1 : supprimer les anciens chunks aide_plateforme ──
    logger.info("🗑️  Suppression des anciens chunks aide_plateforme...")
    db = SessionLocal()
    try:
        supprimes = db.query(KnowledgeBase).filter(
            KnowledgeBase.collection == "aide_plateforme"
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"   → {supprimes} chunk(s) supprimé(s) de la base vectorielle")
    finally:
        db.close()

    # ── Étape 2 : nettoyer le registre ──
    logger.info("🗑️  Nettoyage du registre...")
    registre_data = registre.charger_registre()
    anciens_hashs = [
        h for h, e in registre_data.items()
        if e.collection == "aide_plateforme"
    ]
    for h in anciens_hashs:
        del registre_data[h]
    # Sauvegarder le registre nettoyé
    import json
    from dataclasses import asdict
    chemin_registre = RACINE / "data" / "rag" / "index_registry.json"
    with open(chemin_registre, "w", encoding="utf-8") as f:
        json.dump(
            {h: asdict(e) for h, e in registre_data.items()},
            f, ensure_ascii=False, indent=2,
        )
    logger.info(f"   → {len(anciens_hashs)} entrée(s) supprimée(s) du registre")

    # ── Étape 3 : indexer les nouveaux guides ──
    orch = RagOrchestrator()
    logger.info("📥 Indexation des nouveaux guides utilisateur...")
    for fichier in fichiers:
        logger.info(f"   → {fichier.name}")
        try:
            info = orch.preparer_indexation(
                str(fichier), formation_code=None, collection="aide_plateforme"
            )
            if info.get("deja_indexe"):
                logger.info(f"      ✅ Déjà indexé (hash inchangé)")
            else:
                await orch.ingerer_fichier(
                    str(fichier), None, "aide_plateforme", fichier.name
                )
                logger.info(f"      ✅ Indexé")
        except Exception as exc:
            logger.error(f"      ❌ Erreur : {exc}")

    logger.info("")
    logger.info("✅ Réindexation aide_plateforme terminée.")
    logger.info("   Relancez le serveur FastAPI pour utiliser les nouveaux guides.")


if __name__ == "__main__":
    asyncio.run(main())
