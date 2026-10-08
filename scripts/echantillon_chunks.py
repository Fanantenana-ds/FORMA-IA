# scripts/echantillon_chunks.py
# ============================================================
# ÉCHANTILLON DE CHUNKS — pour jugement humain de la qualité (RAG, Étape C §2)
# ============================================================
# N'ajuste RIEN automatiquement : affiche seulement 5 chunks au hasard par
# format (PDF/DOCX/PPTX/XLSX), avec leur taille et leur page/diapositive,
# pour que vous en jugiez la qualité.
#
# Exécution : python scripts/echantillon_chunks.py <dossier_a_scanner>
# ============================================================

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag import (
    detect_file_type, extract_segments, clean_text, chunk_segments,
    chunk_pptx_slides, Segment,
)

FORMATS = ("pdf", "docx", "pptx", "xlsx")
N_PAR_FORMAT = 5


def echantillonner(dossier: str) -> None:
    dossier_path = Path(dossier)
    if not dossier_path.is_dir():
        print(f"❌ Dossier introuvable : {dossier}")
        sys.exit(1)

    chunks_par_format = {f: [] for f in FORMATS}

    for fichier in sorted(dossier_path.rglob("*")):
        if not fichier.is_file():
            continue

        type_fichier = detect_file_type(str(fichier))
        if type_fichier not in FORMATS:
            continue

        try:
            segments = extract_segments(str(fichier), type_fichier)
            segments_propres = [
                Segment(numero=s.numero, texte=clean_text(s.texte)) for s in segments
            ]
            chunks = (
                chunk_pptx_slides(segments_propres)
                if type_fichier == "pptx"
                else chunk_segments(segments_propres)
            )
        except Exception as exc:
            print(f"⚠️ {fichier.name} : échec extraction/découpage ({exc})")
            continue

        chunks_par_format[type_fichier].extend((fichier.name, c) for c in chunks)

    print("=" * 70)
    print(f"📊 ÉCHANTILLON DE CHUNKS — {dossier}")
    print("=" * 70)

    for type_fichier in FORMATS:
        entrees = chunks_par_format[type_fichier]
        print(f"\n### {type_fichier.upper()} — {len(entrees)} chunk(s) au total ###")

        if not entrees:
            print("   (aucun fichier de ce format trouvé)")
            continue

        echantillon = random.sample(entrees, min(N_PAR_FORMAT, len(entrees)))
        for nom_fichier, chunk in echantillon:
            unite = "diapositive(s)" if type_fichier == "pptx" else "page(s)"
            print(f"\n--- {nom_fichier} | {unite} {chunk.page_debut}-{chunk.page_fin} "
                  f"| {len(chunk.texte)} caractères ---")
            print(chunk.texte[:600])

    print("\n" + "=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python scripts/echantillon_chunks.py <dossier_a_scanner>")
        sys.exit(1)
    echantillonner(sys.argv[1])
