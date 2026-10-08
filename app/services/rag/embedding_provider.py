# app/services/rag/embedding_provider.py
# ============================================================
# PROVIDER ABSTRACTION — EMBEDDINGS (RAG / C3)
# ============================================================
# Interface EmbeddingProvider + implémentation Voyage AI (httpx, PAS le
# SDK voyageai) + fabrique selon EMBEDDING_PROVIDER, pour qu'un autre
# fournisseur puisse être ajouté un jour sans toucher à la logique métier
# (ingestion, recherche, chat).
#
# RÈGLE ABSOLUE : ne jamais afficher, journaliser ni écrire la valeur
# d'une clé API. Seule la PRÉSENCE des variables est vérifiée.
# ============================================================

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.services.rag.rate_limiter import LimiteurDebit

logger = logging.getLogger(__name__)

# ============================================================
# FAMILLES DE MODÈLES COMPATIBLES ENTRE ELLES (même espace vectoriel)
# ============================================================
# Décision argumentée (voir mission) : NE PAS modifier sans revalider la
# justification donnée (recherche asymétrique, mémoire de Master).

FAMILLES_MODELES = {
    "voyage-4": ("voyage-4-large", "voyage-4", "voyage-4-lite"),
}

MODELES_CONNUS = {m for famille in FAMILLES_MODELES.values() for m in famille}


def famille_de(modele: str) -> Optional[str]:
    """Nom de la famille d'un modèle, ou None si le modèle est inconnu."""
    for nom_famille, modeles in FAMILLES_MODELES.items():
        if modele in modeles:
            return nom_famille
    return None


def verifier_compatibilite_famille(modele_a: str, modele_b: str) -> None:
    """
    Lève ValueError (message en français) si modele_a et modele_b
    n'appartiennent pas à la même famille Voyage (même espace vectoriel).
    """
    famille_a = famille_de(modele_a)
    famille_b = famille_de(modele_b)

    if famille_a is None:
        raise ValueError(
            f"Modèle d'embedding inconnu : '{modele_a}'. "
            f"Modèles autorisés : {sorted(MODELES_CONNUS)}."
        )
    if famille_b is None:
        raise ValueError(
            f"Modèle d'embedding inconnu : '{modele_b}'. "
            f"Modèles autorisés : {sorted(MODELES_CONNUS)}."
        )
    if famille_a != famille_b:
        raise ValueError(
            f"Modèles d'embedding incompatibles : '{modele_a}' (famille "
            f"{famille_a}) et '{modele_b}' (famille {famille_b}) n'utilisent "
            f"pas le même espace vectoriel. Une ré-indexation complète est "
            f"nécessaire pour changer de famille."
        )


# ============================================================
# ESTIMATION DE TOKENS (PAS de tiktoken/regex — voir contrainte du poste)
# ============================================================

CARACTERES_PAR_TOKEN_ESTIME = 4  # estimation documentée, pas un comptage exact


def estimer_tokens(texte: str) -> int:
    """Estimation grossière (≈ 4 caractères/token en français), documentée
    comme telle. Ne remplace pas un vrai tokenizer."""
    return max(1, (len(texte) + CARACTERES_PAR_TOKEN_ESTIME - 1) // CARACTERES_PAR_TOKEN_ESTIME)


# ============================================================
# ERREURS — TRADUITES EN FRANÇAIS, JAMAIS LA CLÉ
# ============================================================

class EmbeddingProviderError(Exception):
    """Erreur du fournisseur d'embeddings, message déjà en français."""


def traduire_erreur_voyage(status_code: Optional[int], detail: str = "") -> str:
    if status_code == 401:
        return "Clé Voyage invalide. Vérifier VOYAGE_API_KEY dans .env."
    if status_code == 402:
        return "Moyen de paiement requis pour dépasser le palier gratuit Voyage."
    if status_code == 429:
        return "Limite de débit Voyage atteinte (VOYAGE_RPM / VOYAGE_TPM)."
    if status_code is not None and 500 <= status_code < 600:
        return f"API Voyage indisponible (erreur serveur {status_code})."
    return "API Voyage injoignable. Vérifier la connexion."


# ============================================================
# INTERFACE — pour qu'un autre fournisseur soit ajoutable sans tout casser
# ============================================================

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_documents(self, textes: List[str]) -> List[List[float]]:
        """Vectorise des textes en mode DOCUMENT (indexation)."""

    @abstractmethod
    async def embed_query(
        self, texte: str, *, attente_max_s: Optional[float] = 5.0
    ) -> List[float]:
        """Vectorise une requête en mode QUERY (recherche/chat)."""

    @property
    @abstractmethod
    def modele_document(self) -> str:
        ...

    @property
    @abstractmethod
    def modele_requete(self) -> str:
        ...


# ============================================================
# CONFIGURATION — lue depuis .env, clé jamais journalisée
# ============================================================

@dataclass
class ConfigurationVoyage:
    cle_api: str
    modele_document: str
    modele_requete: str
    rpm: int
    tpm: int
    opt_out: bool
    dimension: int = 1024
    timeout_s: float = 30.0
    url: str = "https://api.voyageai.com/v1/embeddings"

    @classmethod
    def depuis_env(cls) -> "ConfigurationVoyage":
        profil = os.getenv("VOYAGE_KEY_PROFILE", "dev").strip().lower()

        if profil == "soutenance":
            nom_variable = "VOYAGE_API_KEY_SOUTENANCE"
        else:
            nom_variable = "VOYAGE_API_KEY"

        cle_api = os.getenv(nom_variable, "").strip()
        if not cle_api:
            raise EmbeddingProviderError(
                f"Clé Voyage absente : la variable '{nom_variable}' "
                f"(profil VOYAGE_KEY_PROFILE='{profil}') est vide ou "
                f"absente de .env."
            )

        modele_document = os.getenv("VOYAGE_MODEL_DOCUMENT", "voyage-4-large").strip()
        modele_requete = os.getenv("VOYAGE_MODEL_QUERY", "voyage-4-large").strip()
        verifier_compatibilite_famille(modele_document, modele_requete)

        return cls(
            cle_api=cle_api,
            modele_document=modele_document,
            modele_requete=modele_requete,
            rpm=int(os.getenv("VOYAGE_RPM", "3")),
            tpm=int(os.getenv("VOYAGE_TPM", "10000")),
            opt_out=os.getenv("VOYAGE_OPT_OUT", "false").strip().lower() == "true",
        )


# ============================================================
# LIMITEUR PARTAGÉ — une seule instance pour tout le module
# ============================================================

_limiteur_partage: Optional[LimiteurDebit] = None


def get_limiteur_partage(rpm: Optional[int] = None, tpm: Optional[int] = None) -> LimiteurDebit:
    """Retourne le limiteur unique partagé par tout le module RAG."""
    global _limiteur_partage
    if _limiteur_partage is None:
        _limiteur_partage = LimiteurDebit(
            rpm=rpm or int(os.getenv("VOYAGE_RPM", "3")),
            tpm=tpm or int(os.getenv("VOYAGE_TPM", "10000")),
        )
    return _limiteur_partage


def reinitialiser_limiteur_partage() -> None:
    """Pour les tests uniquement : force la recréation du limiteur partagé."""
    global _limiteur_partage
    _limiteur_partage = None


# ============================================================
# CONSTRUCTION DES LOTS — par nombre de tokens, jamais un nombre fixe de chunks
# ============================================================

MAX_TEXTES_PAR_LOT = 1000


def decouper_indices_par_lots(
    textes: List[str], tpm: int, pourcentage_max: float = 0.8
) -> List[List[int]]:
    """
    Découpe `textes` en lots (listes d'INDICES, pas de textes — pour
    pouvoir retrouver l'objet d'origine de chaque texte après l'appel
    Voyage, ex. le Chunk avec sa page). Un lot ne dépasse jamais
    `pourcentage_max` * tpm tokens estimés, ni MAX_TEXTES_PAR_LOT textes.
    """
    if not textes:
        return []

    budget_tokens = max(1, int(tpm * pourcentage_max))
    lots: List[List[int]] = []
    lot_courant: List[int] = []
    tokens_lot_courant = 0

    for i, texte in enumerate(textes):
        tokens_texte = estimer_tokens(texte)

        depasse_budget = lot_courant and (tokens_lot_courant + tokens_texte > budget_tokens)
        depasse_taille = len(lot_courant) >= MAX_TEXTES_PAR_LOT

        if depasse_budget or depasse_taille:
            lots.append(lot_courant)
            lot_courant = []
            tokens_lot_courant = 0

        lot_courant.append(i)
        tokens_lot_courant += tokens_texte

    if lot_courant:
        lots.append(lot_courant)

    return lots


def construire_lots(
    textes: List[str], tpm: int, pourcentage_max: float = 0.8
) -> List[List[str]]:
    """Comme decouper_indices_par_lots(), mais retourne directement les
    textes (pratique quand on n'a pas besoin de retrouver l'origine)."""
    indices_par_lot = decouper_indices_par_lots(textes, tpm, pourcentage_max)
    return [[textes[i] for i in indices] for indices in indices_par_lot]


# ============================================================
# IMPLÉMENTATION VOYAGE AI (httpx direct, PAS le SDK voyageai)
# ============================================================

MAX_TENTATIVES = 3
DELAI_BASE_S = 1.0
STATUTS_RETRYABLES = {429, 500, 502, 503, 504}


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: Optional[ConfigurationVoyage] = None,
        limiteur: Optional[LimiteurDebit] = None,
        client: Optional[httpx.AsyncClient] = None,
        dormir: "Optional[callable]" = None,
    ):
        self.config = config or ConfigurationVoyage.depuis_env()
        self.limiteur = limiteur or get_limiteur_partage(self.config.rpm, self.config.tpm)
        self._client = client
        self._dormir = dormir or asyncio.sleep

    @property
    def modele_document(self) -> str:
        return self.config.modele_document

    @property
    def modele_requete(self) -> str:
        return self.config.modele_requete

    async def _appeler_api(
        self, textes: List[str], modele: str, input_type: str
    ) -> List[List[float]]:
        headers = {
            "Authorization": f"Bearer {self.config.cle_api}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": textes,
            "model": modele,
            "input_type": input_type,
            "output_dimension": self.config.dimension,
        }

        derniere_erreur: Optional[str] = None

        for tentative in range(1, MAX_TENTATIVES + 1):
            client_local = self._client or httpx.AsyncClient(timeout=self.config.timeout_s)
            try:
                try:
                    reponse = await client_local.post(
                        self.config.url, headers=headers, json=payload
                    )
                except httpx.RequestError:
                    raise EmbeddingProviderError(traduire_erreur_voyage(None))

                if reponse.status_code == 200:
                    corps = reponse.json()
                    return [item["embedding"] for item in corps["data"]]

                if reponse.status_code not in STATUTS_RETRYABLES:
                    raise EmbeddingProviderError(
                        traduire_erreur_voyage(reponse.status_code)
                    )

                derniere_erreur = traduire_erreur_voyage(reponse.status_code)

            finally:
                if self._client is None:
                    await client_local.aclose()

            if tentative < MAX_TENTATIVES:
                await self._dormir(DELAI_BASE_S * (2 ** (tentative - 1)))

        raise EmbeddingProviderError(derniere_erreur or traduire_erreur_voyage(None))

    async def embed_documents(self, textes: List[str]) -> List[List[float]]:
        if not textes:
            return []

        resultats: List[List[float]] = []
        lots = construire_lots(textes, self.config.tpm)

        for lot in lots:
            tokens_lot = sum(estimer_tokens(t) for t in lot)
            await self.limiteur.attendre_puis_consommer(
                tokens_lot, attente_max_s=None,
                sur_attente=lambda s: logger.info(
                    "⏳ Limite Voyage : attente de %.0f s avant le prochain lot...", s
                ),
            )
            resultats.extend(
                await self._appeler_api(lot, self.config.modele_document, "document")
            )

        return resultats

    async def embed_query(
        self, texte: str, *, attente_max_s: Optional[float] = 5.0
    ) -> List[float]:
        tokens = estimer_tokens(texte)
        await self.limiteur.attendre_puis_consommer(tokens, attente_max_s=attente_max_s)
        resultats = await self._appeler_api([texte], self.config.modele_requete, "query")
        return resultats[0]


# ============================================================
# FABRIQUE — selon EMBEDDING_PROVIDER
# ============================================================

def get_embedding_provider() -> EmbeddingProvider:
    """
    Sélectionne le fournisseur d'embeddings selon EMBEDDING_PROVIDER.
    Aujourd'hui : uniquement 'voyage'. Prévu pour en accueillir d'autres
    sans toucher à la logique métier (ingestion, recherche, chat).
    """
    fournisseur = os.getenv("EMBEDDING_PROVIDER", "voyage").strip().lower()

    if fournisseur == "voyage":
        return VoyageEmbeddingProvider()

    raise EmbeddingProviderError(
        f"EMBEDDING_PROVIDER='{fournisseur}' inconnu. Seul 'voyage' est "
        f"disponible actuellement."
    )
