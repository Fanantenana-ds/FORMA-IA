# app/services/rag/__init__.py
# ============================================================
# RAG Package — Services
# ============================================================

from app.services.rag.document_loader_service import (
    Segment,
    detect_file_type,
    extract_text,
    extract_segments,
    pdf_necessite_ocr,
    compter_pages_pdf,
    FORMATS_INDEXABLES,
    FORMATS_IMAGE,
)
from app.services.rag.text_cleaner_service import clean_text
from app.services.rag.chunking_service import (
    Chunk,
    chunk_text,
    chunk_segments,
    chunk_pptx_slides,
)
from app.services.rag.embedding_service import embed_texts, embed_query

__all__ = [
    "Segment",
    "detect_file_type",
    "extract_text",
    "extract_segments",
    "pdf_necessite_ocr",
    "compter_pages_pdf",
    "FORMATS_INDEXABLES",
    "FORMATS_IMAGE",
    "clean_text",
    "Chunk",
    "chunk_text",
    "chunk_segments",
    "chunk_pptx_slides",
    "embed_texts",
    "embed_query",
    "get_package_status",
]

__version__ = "1.0.0"
__module_code__ = "C3"
__module_name__ = "RAG — Base de connaissances et Assistant documentaire"


# ============================================================
# ÉTAT DU PACKAGE (Étape H — entrée « Agent 7 » de ia_health.py)
# ============================================================
# Imports en DIFFÉRÉ (dans la fonction, pas en tête de fichier) : certains
# de ces modules importent eux-mêmes depuis app.services.rag — un import
# au niveau module créerait un cycle (ce package n'est pas encore
# entièrement initialisé pendant son propre chargement).

def get_package_status() -> dict:
    """État d'implémentation du package RAG (C3) — même format que
    app.services.facturation.get_package_status() (M7)."""
    services = {}

    def _verifier(nom: str, chemin_module: str, attribut: str) -> None:
        try:
            module = __import__(chemin_module, fromlist=[attribut])
            services[nom] = hasattr(module, attribut)
        except ImportError:
            services[nom] = False

    _verifier("Embeddings (Voyage AI)", "app.services.rag.embedding_provider", "get_embedding_provider")
    _verifier("Dépôt base de connaissances", "app.services.rag.knowledge_repository", "KnowledgeRepository")
    _verifier("Catalogue formations", "app.services.rag.catalogue_service", "charger_catalogue")
    _verifier("Recherche vectorielle", "app.services.rag.recherche_service", "rechercher")
    _verifier("Orchestrateur d'ingestion", "app.orchestrator.rag_orchestrator", "RagOrchestrator")
    # PAS de préfixe "Agent 7" ici : app/services/formations/__init__.py (M5)
    # utilise déjà ce préfixe pour un placeholder SANS RAPPORT ("RAG V2",
    # jamais implémenté), qu'ia_health.py exempte volontairement via
    # OPTIONNELS — un même préfixe rendrait CETTE entrée optionnelle aussi,
    # ce qui n'est pas voulu : le module C3 est livré et doit être REQUIS.
    _verifier("Assistant documentaire (chat RAG)", "app.orchestrator.chat_orchestrator", "ChatOrchestrator")
    _verifier("Portfolio / syllabus / questions", "app.services.rag.portfolio_service", "generer_fiche_reference")

    return {
        "module": __module_code__,
        "module_name": __module_name__,
        "version": __version__,
        "services": services,
        "implemented_count": sum(1 for v in services.values() if v),
        "total_services": len(services),
    }
