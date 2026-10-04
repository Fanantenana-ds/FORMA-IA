# app/services/formations/knowledge_base_service.py
# ============================================================
# AGENT 7 — KnowledgeBaseService (RAG V2)
# ============================================================
# Pont entre le module M5 (formations) et le moteur RAG C3.
#
# Rôle : permettre aux agents M5 (LevelAnalyzer, SatisfactionAnalyzer,
# FormGenerator) de chercher du contenu pertinent dans les supports
# de formation déjà indexés, afin de personnaliser les formulaires
# et les analyses au contenu réel de chaque formation.
#
# Utilise les services RAG existants (embedding_service, recherche_service,
# knowledge_repository) sans les dupliquer.
# ============================================================

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VERBOSE = True

_MAX_CHUNKS_PAR_RECHERCHE = 5
_SCORE_MIN = 0.45


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class KnowledgeBaseService:
    """
    Agent 7 — Accès RAG pour les agents M5.

    Méthodes principales :
      - search(query, formation_code?)  : cherche des chunks pertinents
      - get_formation_context(...)      : résumé du contenu pour un agent
      - is_available()                  : vérifie si des données sont indexées
    """

    # ----------------------------------------------------------
    # DISPONIBILITÉ
    # ----------------------------------------------------------
    @staticmethod
    def is_available() -> bool:
        """Retourne True si la base RAG contient des supports de formation."""
        try:
            from sqlalchemy import select, func as sqlfunc
            from app.database import SessionLocal
            from app.models.knowledge_base import KnowledgeBase

            db = SessionLocal()
            try:
                total = db.execute(
                    select(sqlfunc.count()).select_from(KnowledgeBase)
                ).scalar() or 0
                vlog(f"🔍 [KnowledgeBaseService] Base RAG : {total} chunk(s) indexé(s)")
                return total > 0
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"⚠️ [KnowledgeBaseService] Impossible de vérifier la base RAG : {e}")
            return False

    # ----------------------------------------------------------
    # RECHERCHE PRINCIPALE
    # ----------------------------------------------------------
    async def search(
        self,
        query: str,
        formation_code: Optional[str] = None,
        collection: Optional[str] = None,
        top_k: int = _MAX_CHUNKS_PAR_RECHERCHE,
        score_min: float = _SCORE_MIN,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des chunks pertinents dans la base RAG.

        Args:
            query         : question ou thème à rechercher
            formation_code: filtre sur un code de formation précis
            collection    : filtre sur la collection ("support", "resume_formation", etc.)
            top_k         : nombre max de résultats
            score_min     : score de similarité minimum (0-1)

        Returns:
            Liste de dicts {contenu, score, fichier, formation_code, formation_titre}
        """
        try:
            from app.services.rag.recherche_service import rechercher
            from app.services.rag.knowledge_repository import KnowledgeRepository

            repo = KnowledgeRepository()

            resultats = await rechercher(
                requete=query,
                top_k=top_k,
                collection=collection or "support",
                formation_code=formation_code,
                seuil_min=score_min,
                repository=repo,
            )

            chunks = [
                {
                    "contenu": r.contenu,
                    "score": round(r.score, 3),
                    "fichier": r.fichier,
                    "formation_code": r.formation_code,
                    "formation_titre": r.formation_titre,
                }
                for r in resultats
            ]

            vlog(
                f"✅ [KnowledgeBaseService] '{query[:60]}' → "
                f"{len(chunks)} chunk(s) (formation_code={formation_code})"
            )
            return chunks

        except Exception as e:
            logger.warning(f"⚠️ [KnowledgeBaseService] Recherche échouée : {e}")
            return []

    # ----------------------------------------------------------
    # CONTEXTE FORMATÉ POUR LES AGENTS M5
    # ----------------------------------------------------------
    async def get_formation_context(
        self,
        formation_titre: str,
        domaine: str,
        formation_code: Optional[str] = None,
        max_chars: int = 3000,
    ) -> str:
        """
        Retourne un résumé textuel du contenu d'une formation,
        utilisable directement dans un prompt LLM.

        Cherche des chunks sur le titre + le domaine, les concatène
        et tronque à max_chars pour rester dans le contexte LLM.

        Returns:
            Texte formaté prêt à injecter dans un prompt, ou chaîne vide
            si aucun contenu trouvé.
        """
        query = f"{formation_titre} {domaine} objectifs contenu programme"

        chunks = await self.search(
            query=query,
            formation_code=formation_code,
            top_k=6,
            score_min=0.4,
        )

        if not chunks:
            vlog(
                f"⚠️ [KnowledgeBaseService] Aucun contenu trouvé pour "
                f"'{formation_titre}' — les agents utiliseront leur connaissance générale"
            )
            return ""

        parties = []
        total = 0
        for i, chunk in enumerate(chunks, 1):
            texte = chunk["contenu"].strip()
            if total + len(texte) > max_chars:
                texte = texte[: max_chars - total]
                parties.append(f"[Extrait {i}] {texte}")
                break
            parties.append(f"[Extrait {i}] {texte}")
            total += len(texte)

        contexte = "\n\n".join(parties)
        vlog(
            f"✅ [KnowledgeBaseService] Contexte formation : "
            f"{len(parties)} extrait(s), {len(contexte)} caractères"
        )
        return contexte

    # ----------------------------------------------------------
    # STATS
    # ----------------------------------------------------------
    async def get_stats(
        self,
        formation_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retourne des statistiques sur les supports indexés.
        Utile pour le health check et le dashboard.
        """
        try:
            from sqlalchemy import select, func as sqlfunc
            from app.database import SessionLocal
            from app.models.knowledge_base import KnowledgeBase

            db = SessionLocal()
            try:
                rows = db.execute(
                    select(KnowledgeBase.collection, sqlfunc.count().label("n"))
                    .group_by(KnowledgeBase.collection)
                ).all()
                par_collection = {r.collection: r.n for r in rows}
                total = sum(par_collection.values())

                result: Dict[str, Any] = {
                    "total_chunks": total,
                    "par_collection": par_collection,
                    "disponible": total > 0,
                }

                if formation_code:
                    chunks_fc = db.execute(
                        select(sqlfunc.count()).select_from(KnowledgeBase)
                        .where(KnowledgeBase.formation_code == formation_code)
                    ).scalar() or 0
                    result["formation_code"] = formation_code
                    result["chunks_formation"] = chunks_fc

                return result
            finally:
                db.close()

        except Exception as e:
            logger.warning(f"⚠️ [KnowledgeBaseService] Stats échouées : {e}")
            return {"total_chunks": 0, "disponible": False, "erreur": str(e)}
