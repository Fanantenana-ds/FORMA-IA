# app/services/storage/storage_service.py
# ============================================================
# Couche d'abstraction du stockage de fichiers (supports RAG)
# ============================================================
# COMMENT CHANGER DE BACKEND DE STOCKAGE :
#   Dans le fichier .env, changer UNE SEULE ligne :
#
#   STORAGE_BACKEND=local   → fichiers sur le disque du serveur (défaut)
#   STORAGE_BACKEND=gcs     → Google Cloud Storage (bucket GCP)
#
#   Aucun autre fichier à modifier. Le reste du code utilise
#   get_storage() et ne connaît pas le backend réel.
# ============================================================

import hashlib
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# ── Constantes globales ──────────────────────────────────────
TAILLE_MAX_OCTETS = int(os.getenv("STORAGE_MAX_FILE_MB", "100")) * 1024 * 1024
EXTENSIONS_AUTORISEES = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md"}

# Seuils d'alerte disque (uniquement pour LocalStorage)
_SEUIL_WARNING_OCTETS  = 2 * 1024 ** 3   # 2 Go libres → warning dans les logs
_SEUIL_CRITIQUE_OCTETS = 500 * 1024 ** 2  # 500 Mo libres → upload bloqué (HTTP 507)


# ── Interface commune ────────────────────────────────────────
class AbstractStorageService(ABC):

    @abstractmethod
    def sauvegarder(self, contenu: bytes, doc_hash: str, ext: str) -> Tuple[str, bool]:
        """
        Sauvegarde le fichier.
        Retourne (chemin_ou_uri, deja_present).
        Idempotent : si le même hash existe déjà, retourne le chemin existant.
        """

    @abstractmethod
    def supprimer(self, doc_hash: str, ext: str) -> bool:
        """Supprime le fichier. Retourne True si supprimé, False si introuvable."""

    @abstractmethod
    def existe(self, doc_hash: str, ext: str) -> bool:
        """Vérifie si le fichier existe déjà."""


# ── Implémentation 1 : Filesystem local ─────────────────────
class LocalStorageService(AbstractStorageService):
    """
    Stocke les fichiers dans data/rag/fichiers/ sur le disque du serveur.
    Actif quand STORAGE_BACKEND=local (défaut).
    """

    def __init__(self) -> None:
        self._dossier = Path(__file__).resolve().parents[4] / "data" / "rag" / "fichiers"
        self._dossier.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Storage] LOCAL — dossier : {self._dossier}")

    def _chemin(self, doc_hash: str, ext: str) -> Path:
        return self._dossier / f"{doc_hash}{ext}"

    def _verifier_espace_disque(self) -> None:
        """Bloque l'upload si le disque est presque plein."""
        try:
            libre = shutil.disk_usage(self._dossier).free
            if libre < _SEUIL_CRITIQUE_OCTETS:
                raise IOError(
                    f"Espace disque critique : {libre // (1024**2)} Mo libres. "
                    "Upload impossible. Contactez l'administrateur."
                )
            if libre < _SEUIL_WARNING_OCTETS:
                logger.warning(
                    f"⚠️  [Storage] Espace disque faible : {libre // (1024**2)} Mo libres "
                    f"dans {self._dossier}. Pensez à nettoyer ou migrer vers GCS."
                )
        except OSError:
            pass  # Si le chemin n'existe pas encore, pas d'alerte

    def sauvegarder(self, contenu: bytes, doc_hash: str, ext: str) -> Tuple[str, bool]:
        chemin = self._chemin(doc_hash, ext)
        if chemin.exists():
            return str(chemin), True
        self._verifier_espace_disque()
        chemin.write_bytes(contenu)
        logger.info(f"[Storage] Fichier sauvegardé : {chemin}")
        return str(chemin), False

    def supprimer(self, doc_hash: str, ext: str) -> bool:
        chemin = self._chemin(doc_hash, ext)
        if chemin.exists():
            chemin.unlink()
            return True
        return False

    def existe(self, doc_hash: str, ext: str) -> bool:
        return self._chemin(doc_hash, ext).exists()


# ── Implémentation 2 : Google Cloud Storage ─────────────────
class GCSStorageService(AbstractStorageService):
    """
    Stocke les fichiers dans un bucket Google Cloud Storage.
    Actif quand STORAGE_BACKEND=gcs.

    Variables .env requises :
      GCS_BUCKET_NAME        : nom du bucket (ex: forma-ia-bucket)
      GOOGLE_CREDENTIALS_PATH: chemin vers secrets/google_credentials.json
                               (même fichier que pour Google Forms)
    """

    def __init__(self) -> None:
        bucket_name = os.getenv("GCS_BUCKET_NAME", "")
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
        if not bucket_name:
            raise ValueError(
                "GCS_BUCKET_NAME manquant dans .env. "
                "Définissez le nom du bucket GCS (ex: forma-ia-bucket)."
            )
        if not credentials_path or not Path(credentials_path).exists():
            raise FileNotFoundError(
                f"GOOGLE_CREDENTIALS_PATH introuvable : '{credentials_path}'. "
                "Même fichier que pour Google Forms."
            )
        from google.cloud import storage
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
        )
        client = storage.Client(credentials=creds)
        self._bucket = client.bucket(bucket_name)
        self._prefix = "rag/fichiers"
        logger.info(f"[Storage] GCS — bucket : gs://{bucket_name}/{self._prefix}/")

    def _blob_name(self, doc_hash: str, ext: str) -> str:
        return f"{self._prefix}/{doc_hash}{ext}"

    def _uri(self, doc_hash: str, ext: str) -> str:
        return f"gs://{self._bucket.name}/{self._blob_name(doc_hash, ext)}"

    def sauvegarder(self, contenu: bytes, doc_hash: str, ext: str) -> Tuple[str, bool]:
        blob = self._bucket.blob(self._blob_name(doc_hash, ext))
        if blob.exists():
            return self._uri(doc_hash, ext), True
        blob.upload_from_string(contenu)
        logger.info(f"[Storage] Fichier GCS sauvegardé : {self._uri(doc_hash, ext)}")
        return self._uri(doc_hash, ext), False

    def supprimer(self, doc_hash: str, ext: str) -> bool:
        blob = self._bucket.blob(self._blob_name(doc_hash, ext))
        if blob.exists():
            blob.delete()
            return True
        return False

    def existe(self, doc_hash: str, ext: str) -> bool:
        return self._bucket.blob(self._blob_name(doc_hash, ext)).exists()


# ── Factory : retourne le bon backend selon .env ─────────────
def get_storage() -> AbstractStorageService:
    """
    Retourne l'implémentation active selon STORAGE_BACKEND dans .env.
    Appelé une fois au démarrage — résultat mis en cache par FastAPI (Depends).
    """
    backend = os.getenv("STORAGE_BACKEND", "local").lower().strip()
    if backend == "gcs":
        return GCSStorageService()
    return LocalStorageService()


def calculer_hash(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()
