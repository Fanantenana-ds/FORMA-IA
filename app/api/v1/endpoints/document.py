# app/api/v1/endpoints/document.py
# ============================================================
# ROUTES BACKEND — Documents (TDR, Offres, Attestations, Supports RAG)
# ============================================================
# Blocs historiques : TDR (POST /tdr), Offres (POST /offre),
#   Attestations (POST /attestations/{session_id}), Export, Validation.
# Bloc J (2026-09-28) : upload multipart supports RAG, liste, suppression.
#   Flow : Frontend → POST /upload → sauvegarde dans data/rag/fichiers/
#   → retourne chemin_fichier → Frontend appelle POST /ia/rag/indexer-document.
# ============================================================

import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.document import Document, FormatExport, TypeDocument
from app.schemas.document import (
    TDRRequest,
    DocumentResponse,
    ValidationRequest,
    OffreRequest,
)
from app.services.document_service import DocumentService
from app.services.document_export_service import DocumentExportService
from app.services.rag import registry_service as registre
from app.services.rag.registry_service import initialiser_entree
from app.services.storage import get_storage, calculer_hash, TAILLE_MAX_OCTETS, EXTENSIONS_AUTORISEES

logger = logging.getLogger(__name__)

# Chemin local des fichiers RAG (utilisé pour vérifier l'existence côté filesystem)
DOSSIER_FICHIERS_RAG = Path(__file__).resolve().parents[4] / "data" / "rag" / "fichiers"

router = APIRouter(prefix="/documents", tags=["Documents"])


# ─────────────────────────────────────────────────────────────
# Dépendances
# ─────────────────────────────────────────────────────────────
def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db)


def get_document_export_service() -> DocumentExportService:
    return DocumentExportService()

# ─────────────────────────────────────────────────────────────
# CRÉATION — TDR (M2)
# ─────────────────────────────────────────────────────────────
@router.post("/tdr", response_model=DocumentResponse, status_code=201)
def generer_tdr(
    data: TDRRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.generer_tdr(data)


# ─────────────────────────────────────────────────────────────
# CRÉATION — OFFRE (M3)
# ─────────────────────────────────────────────────────────────
@router.post("/offre", response_model=DocumentResponse, status_code=201)
def generer_offre(
    data: OffreRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    return service.generer_offre(data)


# ─────────────────────────────────────────────────────────────
# CRÉATION — ATTESTATIONS (M6)
# ─────────────────────────────────────────────────────────────
@router.post(
    "/attestations/{session_id}",
    response_model=List[DocumentResponse],
    status_code=201,
)
def generer_attestations(
    session_id: UUID,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.generer_attestations(session_id)


# ─────────────────────────────────────────────────────────────
# ✅ NOUVEAU — LISTER tous les documents (avec filtres)
# ─────────────────────────────────────────────────────────────
@router.get("", response_model=List[DocumentResponse])
def lister_documents(
    type: Optional[TypeDocument] = Query(
        None, description="Filtrer par type : TDR, OFFRE, ATTESTATION"
    ),
    statut_validation: Optional[str] = Query(
        None, description="Filtrer par statut : EN_ATTENTE, VALIDE, REJETE"
    ),
    skip: int = Query(0, ge=0, description="Pagination — offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination — limite"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste tous les documents, avec filtres optionnels par type
    et par statut de validation.
    """
    query = db.query(Document)

    if type:
        query = query.filter(Document.type == type)
    if statut_validation:
        query = query.filter(Document.statut_validation == statut_validation)

    return (
        query.order_by(Document.date_generation.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────────────────────
# LECTURE — Un document
# ─────────────────────────────────────────────────────────────
@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return document


# ─────────────────────────────────────────────────────────────
# VALIDATION HITL
# ─────────────────────────────────────────────────────────────
@router.post("/{document_id}/valider", response_model=DocumentResponse)
def valider_document(
    document_id: UUID,
    data: ValidationRequest,
    service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.valider(document_id, current_user.id, data.approuve)


# ─────────────────────────────────────────────────────────────
# EXPORT Word / PDF
# ─────────────────────────────────────────────────────────────
@router.get("/{document_id}/export")
def exporter_document(
    document_id: UUID,
    format: FormatExport,
    db: Session = Depends(get_db),
    export_service: DocumentExportService = Depends(get_document_export_service),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    contenu, nom_fichier, media_type = export_service.exporter(document, format)

    document.format_export = format
    db.commit()

    return Response(
        content=contenu,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={nom_fichier}"},
    )


# ─────────────────────────────────────────────────────────────
# ✅ NOUVEAU — SUPPRESSION (admin uniquement)
# ─────────────────────────────────────────────────────────────
@router.delete("/{document_id}", status_code=204)
def supprimer_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("DIRECTION")),
):
    return service.generer_offre(data)


# ============================================================
# BLOC J — Supports RAG : upload, liste, suppression
# ============================================================

@router.post(
    "/upload",
    status_code=201,
    summary="Uploader un support RAG (PDF, DOCX, PPTX, XLSX…)",
    description=(
        "Sauvegarde le fichier dans `data/rag/fichiers/` et l'enregistre dans le registre "
        "d'indexation avec le statut `en_attente`. Le champ `chemin_fichier` retourné permet "
        "d'appeler ensuite `POST /ia/rag/indexer-document` pour lancer l'indexation vectorielle. "
        "Idempotent : si le même fichier (même SHA-256) a déjà été uploadé, le chemin existant "
        "est retourné sans réécriture. Rôles autorisés : DIRECTION, ASSISTANT, FORMATEUR."
    ),
)
async def uploader_support(
    fichier: UploadFile = File(..., description="Fichier à indexer (PDF, DOCX, PPTX, XLSX, TXT, MD)"),
    formation_code: Optional[str] = Form(default=None, description="Code de la formation associée (catalogue RAG)"),
    collection: str = Form(default="support", description="Collection RAG : support | aide_plateforme"),
    module: Optional[str] = Form(default=None, description="Module pédagogique (ex: 'Module 1 — Introduction'). Optionnel — utilisé pour grouper les supports dans le résumé téléchargeable."),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT", "FORMATEUR")),
):
    # Vérification extension
    nom = fichier.filename or "fichier_inconnu"
    ext = Path(nom).suffix.lower()
    if ext not in EXTENSIONS_AUTORISEES:
        raise HTTPException(
            status_code=422,
            detail=f"Extension '{ext}' non supportée. Formats acceptés : {', '.join(sorted(EXTENSIONS_AUTORISEES))}",
        )

    # Lecture et vérification taille
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {TAILLE_MAX_OCTETS // (1024*1024)} Mo).")
    if len(contenu) == 0:
        raise HTTPException(status_code=422, detail="Le fichier est vide.")

    doc_hash = calculer_hash(contenu)

    # Sauvegarde via le backend configuré (local ou GCS selon STORAGE_BACKEND dans .env)
    try:
        storage = get_storage()
        chemin_fichier, deja_present = storage.sauvegarder(contenu, doc_hash, ext)
    except IOError as e:
        raise HTTPException(status_code=507, detail=str(e))

    # Enregistrement dans le registre RAG (crée ou retourne l'entrée existante)
    entree = initialiser_entree(
        hash_fichier=doc_hash,
        fichier=nom,
        formation_code=formation_code,
        collection=collection,
        module=module,
    )

    return {
        "success": True,
        "hash": doc_hash,
        "fichier": nom,
        "chemin_fichier": chemin_fichier,
        "formation_code": formation_code,
        "module": module,
        "collection": collection,
        "statut": entree.statut,
        "deja_present": deja_present,
        "taille_octets": len(contenu),
    }


@router.get(
    "/rag/supports",
    summary="Lister les supports RAG uploadés (avec statut d'indexation)",
    description=(
        "Retourne tous les documents présents dans le registre d'indexation RAG. "
        "Filtre optionnel par `formation_code` ou `statut` (en_attente, en_cours, indexe, erreur). "
        "Rôles autorisés : tous les utilisateurs authentifiés."
    ),
)
def lister_supports(
    formation_code: Optional[str] = Query(default=None, description="Filtrer par code de formation"),
    statut: Optional[str] = Query(default=None, description="en_attente | en_cours | indexe | erreur"),
    current_user: User = Depends(get_current_user),
):
    registre_complet = registre.charger_registre()
    entrees = list(registre_complet.values())

    if formation_code:
        entrees = [e for e in entrees if e.formation_code == formation_code]
    if statut:
        entrees = [e for e in entrees if e.statut == statut]

    data = []
    for e in entrees:
        chemin = DOSSIER_FICHIERS_RAG / f"{e.hash}{Path(e.fichier).suffix.lower()}"
        data.append({
            "hash": e.hash,
            "fichier": e.fichier,
            "formation_code": e.formation_code,
            "module": e.module,
            "collection": e.collection,
            "statut": e.statut,
            "nb_chunks": e.nb_chunks,
            "date_debut": e.date_debut,
            "date_fin": e.date_fin,
            "message": e.message,
            "fichier_disponible": chemin.exists(),
            "chemin_fichier": str(chemin),
        })

    return {"success": True, "total": len(data), "data": data}


@router.get(
    "/rag/supports/resume-formation",
    summary="Télécharger le résumé de tous les supports d'une formation (DOCX)",
    description=(
        "Génère et retourne un document DOCX contenant le résumé de tous les supports "
        "indexés d'une formation, groupés par module pédagogique. "
        "Chaque support contribue : titre, résumé, mots-clés, plan. "
        "Supports sans résumé encore généré sont signalés ('indexation en cours'). "
        "Rôles autorisés : tous les utilisateurs authentifiés."
    ),
)
def telecharger_resume_formation(
    formation_code: str = Query(..., description="Code de la formation (ex: PYTHON-2026)"),
    current_user: User = Depends(get_current_user),
):
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor
    from io import BytesIO
    from collections import defaultdict

    entrees = registre.charger_registre()
    supports = [e for e in entrees.values() if e.formation_code == formation_code]

    if not supports:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun support trouvé pour la formation '{formation_code}'.",
        )

    # Grouper par module (None → "Supports généraux")
    par_module: dict = defaultdict(list)
    for e in supports:
        cle = e.module or "Supports généraux"
        par_module[cle].append(e)

    # Trier les modules (Module 1 avant Module 2, etc.)
    modules_tries = sorted(par_module.keys(), key=lambda m: (
        0 if m == "Supports généraux" else 1,
        m,
    ))

    doc = DocxDocument()

    # Page de garde
    titre = doc.add_heading(f"Résumé de formation", level=0)
    titre.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    doc.add_paragraph(f"Formation : {formation_code}")
    doc.add_paragraph(f"Nombre de supports : {len(supports)}")
    doc.add_paragraph(f"Modules : {len(par_module)}")
    doc.add_paragraph("")

    total_sans_resume = 0

    for module_nom in modules_tries:
        doc.add_heading(module_nom, level=1)
        for e in par_module[module_nom]:
            doc.add_heading(f"📄 {e.fichier}", level=2)

            if e.resume:
                doc.add_paragraph(e.resume)
            else:
                p = doc.add_paragraph("⏳ Résumé pas encore généré (indexation en attente ou en cours).")
                p.runs[0].italic = True
                total_sans_resume += 1

            if e.mots_cles:
                doc.add_paragraph(f"Mots-clés : {', '.join(e.mots_cles)}")

            if e.plan:
                doc.add_paragraph("Plan :")
                for item in e.plan:
                    titre_item = item.get("titre") or item.get("title") or str(item)
                    doc.add_paragraph(f"  • {titre_item}", style="List Bullet")

            doc.add_paragraph("")

    if total_sans_resume:
        doc.add_paragraph(
            f"ℹ️  {total_sans_resume} support(s) sans résumé. "
            "Lancez POST /ia/rag/indexer-document pour les supports concernés.",
        ).italic = True

    # Sérialisation en mémoire
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    nom_fichier = f"resume_{formation_code}.docx".replace(" ", "_")
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )


@router.get(
    "/rag/supports/bilan-formations",
    summary="Télécharger le bilan de toutes les formations sur une période (DOCX)",
    description=(
        "Génère un document DOCX récapitulatif de toutes les formations ayant des supports "
        "indexés, avec filtre optionnel par période (date_debut / date_fin au format YYYY-MM-DD). "
        "Pour chaque formation : code, nombre de supports, modules, thèmes couverts (mots-clés). "
        "Rôles autorisés : DIRECTION, ASSISTANT."
    ),
)
def telecharger_bilan_formations(
    date_debut: Optional[str] = Query(default=None, description="Période début YYYY-MM-DD (optionnel)"),
    date_fin: Optional[str] = Query(default=None, description="Période fin YYYY-MM-DD (optionnel)"),
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    from docx import Document as DocxDocument
    from docx.shared import RGBColor
    from io import BytesIO
    from collections import defaultdict

    entrees = registre.charger_registre()
    tous_supports = list(entrees.values())

    # Filtre par période si fourni
    if date_debut or date_fin:
        filtres = []
        for e in tous_supports:
            d = (e.date_debut or "")[:10]
            if date_debut and d < date_debut:
                continue
            if date_fin and d > date_fin:
                continue
            filtres.append(e)
        tous_supports = filtres

    if not tous_supports:
        raise HTTPException(
            status_code=404,
            detail="Aucun support trouvé pour la période demandée.",
        )

    # Regrouper par formation_code
    par_formation: dict = defaultdict(list)
    for e in tous_supports:
        par_formation[e.formation_code or "Sans formation"].append(e)

    doc = DocxDocument()

    # En-tête
    titre = doc.add_heading("Bilan des formations", level=0)
    titre.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    periode = ""
    if date_debut and date_fin:
        periode = f"{date_debut} → {date_fin}"
    elif date_debut:
        periode = f"depuis {date_debut}"
    elif date_fin:
        periode = f"jusqu'au {date_fin}"
    if periode:
        doc.add_paragraph(f"Période : {periode}")
    doc.add_paragraph(f"Formations : {len(par_formation)}  |  Supports total : {len(tous_supports)}")
    doc.add_paragraph("")

    for formation_code in sorted(par_formation.keys()):
        supports_f = par_formation[formation_code]
        modules = sorted({e.module for e in supports_f if e.module})
        tous_mots_cles = []
        for e in supports_f:
            tous_mots_cles.extend(e.mots_cles or [])
        mots_cles_uniques = sorted(set(tous_mots_cles))[:20]

        doc.add_heading(formation_code, level=1)
        doc.add_paragraph(f"Supports : {len(supports_f)}")
        if modules:
            doc.add_paragraph(f"Modules : {', '.join(modules)}")
        if mots_cles_uniques:
            doc.add_paragraph(f"Thèmes couverts : {', '.join(mots_cles_uniques)}")

        doc.add_paragraph("Supports :")
        for e in supports_f:
            statut_label = "✅" if e.statut == "indexe" else "⏳"
            module_label = f" [{e.module}]" if e.module else ""
            doc.add_paragraph(
                f"  {statut_label} {e.fichier}{module_label}",
                style="List Bullet",
            )
        doc.add_paragraph("")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    label = f"bilan_{date_debut or 'tout'}_{date_fin or 'tout'}.docx".replace(" ", "_")
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{label}"'},
    )


@router.delete(
    "/rag/supports/{doc_hash}",
    status_code=200,
    summary="Supprimer un support RAG (registre + disque + vecteurs)",
    description=(
        "Supprime complètement un support RAG : retire l'entrée du registre d'indexation, "
        "supprime le fichier physique de `data/rag/fichiers/` et efface tous les chunks "
        "vectorisés de la table `knowledge_base` (pgvector). "
        "Irréversible. Rôles autorisés : DIRECTION, ASSISTANT."
    ),
)
def supprimer_support(
    doc_hash: str,
    current_user: User = Depends(require_role("DIRECTION", "ASSISTANT")),
):
    # Validation format hash (64 hex)
    if not doc_hash.isalnum() or len(doc_hash) != 64:
        raise HTTPException(status_code=422, detail="Hash invalide (SHA-256 attendu, 64 caractères hexadécimaux).")

    entree = registre.obtenir_entree(doc_hash)
    if entree is None:
        raise HTTPException(status_code=404, detail="Support RAG introuvable dans le registre.")

    nb_chunks_supprimes = 0
    fichier_supprime = False

    # 1. Suppression des vecteurs en base
    try:
        from app.services.rag.knowledge_repository import KnowledgeRepository
        repo = KnowledgeRepository()
        nb_chunks_supprimes = repo.supprimer_par_hash(doc_hash)
        logger.info(f"RAG suppression : {nb_chunks_supprimes} chunks supprimés pour hash={doc_hash}")
    except Exception as exc:
        logger.warning(f"Impossible de supprimer les chunks knowledge_base : {exc}")

    # 2. Suppression du fichier physique
    ext = Path(entree.fichier).suffix.lower()
    chemin = DOSSIER_FICHIERS_RAG / f"{doc_hash}{ext}"
    if chemin.exists():
        chemin.unlink()
        fichier_supprime = True
        logger.info(f"RAG suppression : fichier supprimé {chemin}")

    # 3. Suppression du registre
    registre.supprimer_entree(doc_hash)

    return {
        "success": True,
        "hash": doc_hash,
        "fichier": entree.fichier,
        "nb_chunks_supprimes": nb_chunks_supprimes,
        "fichier_supprime": fichier_supprime,
        "message": f"Support '{entree.fichier}' supprimé avec succès.",
    }

    """
    Supprime un document. Réservé à la Direction.
    Refuse la suppression d'un document déjà validé.
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    # Sécurité : on ne supprime pas un document validé
    if document.statut_validation and document.statut_validation.value == "VALIDE":
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer un document validé",
        )

    db.delete(document)
    db.commit()
    return None
