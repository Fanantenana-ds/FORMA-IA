# app/models/knowledge_base.py
# ============================================================
# MODÈLE — Knowledge Base (pgvector) — RAG / C3
# ============================================================
# Schéma finalisé à l'Étape C de la mission RAG (2026-09-24), après
# validation : découplé du cycle de vie Backend (formation_code, un code
# métier du catalogue, plutôt qu'une FK vers sessions.id) pour pouvoir
# indexer un corpus de démonstration sans session Backend réelle.
# ============================================================

import uuid
from sqlalchemy import (
    Column, String, Text, TIMESTAMP, Integer, JSON,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.database import Base

# JSONB en PostgreSQL (prod/dev) ; JSON générique en SQLite (tests unitaires
# en mémoire) — SQLite n'a pas de type JSONB.
_JSON_PORTABLE = JSONB(astext_type=Text()).with_variant(JSON(), "sqlite")


class KnowledgeBase(Base):
    """
    Table de stockage des chunks vectorisés du module RAG (C3).

    collection distingue 3 natures de contenu partageant le même espace
    vectoriel Voyage 4 :
      - "support"          : chunk d'un support de formation (PDF/DOCX/PPTX/XLSX)
      - "resume_formation"  : résumé thématique d'une formation entière
      - "aide_plateforme"   : guide utilisateur FORMA-IA (Étape F)
    """
    __tablename__ = "knowledge_base"

    # ═══ IDENTIFIANT ═══
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ═══ CLASSEMENT ═══
    collection = Column(String(30), nullable=False, index=True)
    doc_hash = Column(String(64), nullable=True, index=True)  # SHA-256 du fichier source (idempotence)
    fichier = Column(String(500), nullable=True)
    formation_code = Column(String(100), nullable=True, index=True)
    formation_titre = Column(String(255), nullable=True)
    domaine = Column(String(100), nullable=True)
    annee = Column(Integer, nullable=True)
    type_support = Column(String(20), nullable=True)  # pdf, docx, pptx, xlsx

    # ═══ POSITION DANS LE DOCUMENT ═══
    # PDF/DOCX/XLSX : page_debut peut différer de page_fin si le chunk
    # chevauche une limite de page. PPTX : plage de diapositives groupées
    # (3 à 5 par chunk, voir chunking_service.chunk_pptx_slides).
    page_debut = Column(Integer, nullable=True)
    page_fin = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=True)

    # ═══ CONTENU ═══
    contenu = Column(Text, nullable=False)
    # 1024 = dimension Voyage AI (voyage-4-large/voyage-4/voyage-4-lite).
    embedding = Column(Vector(1024), nullable=False)
    modele_embed = Column(String(50), nullable=False)

    # ═══ MÉTADONNÉES LIBRES ═══
    # Ex. chemin dans un ZIP, plage de diapositives détaillée, etc.
    meta = Column(_JSON_PORTABLE, default=dict)

    # ═══ AUDIT ═══
    created_at = Column(TIMESTAMP, server_default=func.now())

    def __repr__(self):
        return f"<KnowledgeBase {self.id} | {self.collection} | {self.fichier}>"
