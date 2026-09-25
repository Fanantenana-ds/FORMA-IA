# app/services/rag/zip_securite.py
# ============================================================
# SÉCURITÉ ZIP — extraction sûre pour l'ingestion RAG (Étape C)
# ============================================================
# Protège contre : bombe ZIP (ratio de compression extrême), Zip Slip
# (chemins ".." ou absolus), ZIP imbriqué, trop de fichiers.
# ============================================================

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import List

logger = logging.getLogger(__name__)

MAX_COMPRESSE_OCTETS = 200 * 1024 * 1024   # 200 Mo
MAX_DECOMPRESSE_OCTETS = 500 * 1024 * 1024  # 500 Mo
MAX_FICHIERS = 200


class ZipSecuriteError(Exception):
    """Erreur de sécurité ZIP — message déjà en français, à afficher tel quel."""


@dataclass
class MembreZip:
    nom: str
    taille_decompressee: int


def _chemin_est_sur(nom: str) -> bool:
    """Refuse tout chemin absolu ou contenant '..' (Zip Slip)."""
    if not nom or nom.startswith("/") or nom.startswith("\\"):
        return False
    if ".." in PurePosixPath(nom).parts:
        return False
    # Chemin Windows avec lettre de lecteur (ex: C:\...)
    if len(nom) >= 2 and nom[1] == ":":
        return False
    return True


def verifier_et_lister(chemin_zip: str) -> List[MembreZip]:
    """
    Vérifie un fichier ZIP AVANT toute extraction et retourne la liste de
    ses membres sûrs à extraire.

    Lève ZipSecuriteError (message en français) si :
      - le fichier compressé dépasse 200 Mo ;
      - le contenu décompressé dépasserait 500 Mo ;
      - plus de 200 fichiers ;
      - un chemin contient '..' ou est absolu (Zip Slip) ;
      - un membre est lui-même un fichier .zip (ZIP imbriqué, refusé).
    """
    taille_compressee = Path(chemin_zip).stat().st_size
    if taille_compressee > MAX_COMPRESSE_OCTETS:
        raise ZipSecuriteError(
            f"Archive ZIP trop volumineuse : {taille_compressee / (1024*1024):.1f} Mo "
            f"(maximum {MAX_COMPRESSE_OCTETS / (1024*1024):.0f} Mo compressé)."
        )

    try:
        zf = zipfile.ZipFile(chemin_zip)
    except zipfile.BadZipFile:
        raise ZipSecuriteError("Archive ZIP invalide ou corrompue.")

    with zf:
        infos = zf.infolist()

        if len(infos) > MAX_FICHIERS:
            raise ZipSecuriteError(
                f"Archive ZIP refusée : {len(infos)} fichiers "
                f"(maximum {MAX_FICHIERS})."
            )

        total_decompresse = 0
        membres: List[MembreZip] = []

        for info in infos:
            if info.is_dir():
                continue

            if not _chemin_est_sur(info.filename):
                raise ZipSecuriteError(
                    f"Archive ZIP refusée : chemin non sûr détecté "
                    f"('{info.filename}')."
                )

            if info.filename.lower().endswith(".zip"):
                raise ZipSecuriteError(
                    f"Archive ZIP refusée : ZIP imbriqué détecté "
                    f"('{info.filename}'). Décompressez-le manuellement avant import."
                )

            total_decompresse += info.file_size
            if total_decompresse > MAX_DECOMPRESSE_OCTETS:
                raise ZipSecuriteError(
                    f"Archive ZIP refusée : contenu décompressé dépasse "
                    f"{MAX_DECOMPRESSE_OCTETS / (1024*1024):.0f} Mo (bombe ZIP suspectée)."
                )

            membres.append(MembreZip(nom=info.filename, taille_decompressee=info.file_size))

    logger.info(
        f"📦 ZIP vérifié : {len(membres)} fichier(s), "
        f"{total_decompresse / (1024*1024):.1f} Mo décompressés"
    )
    return membres


def extraire_membre(chemin_zip: str, nom_membre: str, dossier_destination: Path) -> Path:
    """
    Extrait UN membre déjà validé par verifier_et_lister() vers
    dossier_destination. Revérifie le chemin par sécurité (défense en
    profondeur) avant d'écrire sur disque.
    """
    if not _chemin_est_sur(nom_membre):
        raise ZipSecuriteError(f"Chemin non sûr, extraction refusée : '{nom_membre}'.")

    dossier_destination.mkdir(parents=True, exist_ok=True)
    destination = (dossier_destination / nom_membre).resolve()

    if not str(destination).startswith(str(dossier_destination.resolve())):
        raise ZipSecuriteError(f"Chemin hors du dossier de destination : '{nom_membre}'.")

    with zipfile.ZipFile(chemin_zip) as zf:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(nom_membre) as source, open(destination, "wb") as cible:
            cible.write(source.read())

    return destination
