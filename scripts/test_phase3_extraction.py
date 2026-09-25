# scripts/test_phase3_extraction.py
# ============================================================
# TEST PHASE 3 — Extraction + Nettoyage + Chunking
# ============================================================

import sys
from pathlib import Path

# Permet d'importer le package `app` depuis la racine du projet
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag.document_loader_service import (
    extract_segments, extract_text, detect_file_type, Segment,
)
from app.services.rag.text_cleaner_service import clean_text
from app.services.rag.chunking_service import chunk_segments

# ... (le reste du script est inchangé)

FICHIER = "app/templates/tdr/template_tdr_formation.docx"

print("=" * 70)
print("TEST PHASE 3 — EXTRACTION / NETTOYAGE / CHUNKING")
print("=" * 70)

# --- 1. Extraction ------------------------------------------------------
print()
print(f"Fichier : {FICHIER}")
print(f"Type    : {detect_file_type(FICHIER)}")

segments = extract_segments(FICHIER)
print(f"Segments extraits : {len(segments)}")

if not segments:
    print("ECHEC : aucun segment extrait")
    raise SystemExit(1)

s0 = segments[0]
print(f"  Segment[0] : numero={s0.numero}  longueur={len(s0.texte)}")
print(f"  Extrait    : {s0.texte[:150]!r}")

total_brut = sum(len(s.texte) for s in segments)
print(f"  Chars bruts total : {total_brut}")

# --- 2. Nettoyage -------------------------------------------------------
segments_propres = [
    Segment(numero=s.numero, texte=clean_text(s.texte))
    for s in segments
]
total_propre = sum(len(s.texte) for s in segments_propres)
print()
print(f"Chars propres     : {total_propre}")
print(f"Reduction         : {total_brut - total_propre} chars")

# --- 3. Chunking --------------------------------------------------------
chunks = chunk_segments(segments_propres)
print()
print(f"Chunks produits : {len(chunks)}")

if not chunks:
    print("ATTENTION : 0 chunk (fichier probablement trop court)")
    raise SystemExit(0)

c = chunks[0]
print(f"  Premier chunk :")
print(f"    page_debut = {c.page_debut}")
print(f"    page_fin   = {c.page_fin}")
print(f"    taille     = {len(c.texte)} chars")
print(f"    texte      = {c.texte[:200]!r}...")

if len(chunks) > 1:
    c_last = chunks[-1]
    print(f"  Dernier chunk : page_debut={c_last.page_debut} "
          f"page_fin={c_last.page_fin} taille={len(c_last.texte)}")

print()
print("=" * 70)
print("PIPELINE EXTRACTION -> NETTOYAGE -> CHUNKING : OK")
print("=" * 70)