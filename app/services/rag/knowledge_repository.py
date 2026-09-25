# app/services/rag/knowledge_repository.py
# ============================================================
# ACCÈS DONNÉES — knowledge_base (RAG, Étape C)
# ============================================================
# Isole rag_orchestrator.py de SQLAlchemy : permet de le tester "sans
# base" (mission C3) en injectant un faux dépôt en mémoire dans les tests,
# sans avoir à interpréter des constructions SQLAlchemy Core dans les faux.
# ============================================================

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """Implémentation réelle (PostgreSQL, via SessionLocal)."""

    def modeles_presents(self, collection: Optional[str] = None) -> List[str]:
        db = SessionLocal()
        try:
            requete = select(KnowledgeBase.modele_embed).distinct()
            if collection:
                requete = requete.where(KnowledgeBase.collection == collection)
            return [m for (m,) in db.execute(requete).all() if m]
        finally:
            db.close()

    def rechercher_par_similarite(
        self,
        vecteur: List[float],
        collection: str,
        top_k: int,
        formation_code: Optional[str] = None,
        domaine: Optional[str] = None,
        annee: Optional[int] = None,
        type_support: Optional[str] = None,
    ) -> List[Tuple[KnowledgeBase, float]]:
        """Retourne [(ligne, distance_cosinus)], triées par distance
        croissante (les plus similaires d'abord)."""
        db = SessionLocal()
        try:
            distance = KnowledgeBase.embedding.cosine_distance(vecteur)
            stmt = select(KnowledgeBase, distance.label("distance")).where(
                KnowledgeBase.collection == collection
            )
            if formation_code:
                stmt = stmt.where(KnowledgeBase.formation_code == formation_code)
            if domaine:
                stmt = stmt.where(KnowledgeBase.domaine == domaine)
            if annee:
                stmt = stmt.where(KnowledgeBase.annee == annee)
            if type_support:
                stmt = stmt.where(KnowledgeBase.type_support == type_support)

            stmt = stmt.order_by(distance).limit(top_k)
            return [(ligne, float(dist)) for ligne, dist in db.execute(stmt).all()]
        finally:
            db.close()

    def inserer_chunks(self, lignes: List[KnowledgeBase]) -> None:
        if not lignes:
            return
        db = SessionLocal()
        try:
            db.add_all(lignes)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def supprimer_par_hash(self, doc_hash: str) -> int:
        db = SessionLocal()
        try:
            resultat = db.execute(delete(KnowledgeBase).where(KnowledgeBase.doc_hash == doc_hash))
            db.commit()
            return resultat.rowcount
        finally:
            db.close()

    def remplacer_resume_formation(self, formation_code: str, ligne: KnowledgeBase) -> None:
        db = SessionLocal()
        try:
            db.execute(delete(KnowledgeBase).where(
                KnowledgeBase.collection == "resume_formation",
                KnowledgeBase.formation_code == formation_code,
            ))
            db.add(ligne)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
