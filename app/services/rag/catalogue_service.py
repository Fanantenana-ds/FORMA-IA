# app/services/rag/catalogue_service.py
# ============================================================
# SERVICE — Catalogue des formations (data/rag/catalogue_formations.yaml)
# ============================================================
# Lecture seule. La résolution floue par nom (difflib, synonymes, accents)
# est ajoutée à l'Étape E (assistant documentaire) — ce module se limite à
# charger le catalogue et à répondre aux besoins de l'Étape C (ingestion) :
# retrouver une formation par son code, savoir si elle est confidentielle.
# ============================================================

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

CHEMIN_CATALOGUE_DEFAUT = (
    Path(__file__).resolve().parents[3] / "data" / "rag" / "catalogue_formations.yaml"
)


@dataclass
class Realisation:
    client: Optional[str] = None
    client_confidentiel: bool = False
    secteur_public: Optional[str] = None
    annee: Optional[int] = None
    lieu: Optional[str] = None
    participants: Optional[int] = None
    session_id: Optional[int] = None
    attestation_bonne_execution: bool = False

    def affichage_client(self) -> str:
        """Nom du client, ou son secteur si client_confidentiel=true."""
        if self.client_confidentiel:
            return self.secteur_public or "Client confidentiel"
        return self.client or "Client non renseigné"


@dataclass
class Formation:
    code: str
    titre: str
    domaine: Optional[str] = None
    niveau: Optional[str] = None
    duree_jours: Optional[int] = None
    confidentiel: bool = False
    synonymes: List[str] = field(default_factory=list)
    realisations: List[Realisation] = field(default_factory=list)

    def annee_la_plus_recente(self) -> Optional[int]:
        annees = [r.annee for r in self.realisations if r.annee]
        return max(annees) if annees else None


class CatalogueFormationsError(Exception):
    """Erreur de lecture du catalogue, message déjà en français."""


def charger_catalogue(chemin: Optional[Path] = None) -> List[Formation]:
    """Charge et valide data/rag/catalogue_formations.yaml."""
    chemin = chemin or CHEMIN_CATALOGUE_DEFAUT

    if not chemin.exists():
        raise CatalogueFormationsError(
            f"Catalogue des formations introuvable : {chemin}. "
            f"Créez-le à partir de l'exemple fourni."
        )

    with open(chemin, "r", encoding="utf-8") as f:
        donnees = yaml.safe_load(f) or {}

    formations_brutes = donnees.get("formations") or []
    formations = []

    for item in formations_brutes:
        if "code" not in item or "titre" not in item:
            raise CatalogueFormationsError(
                f"Entrée du catalogue invalide (code/titre requis) : {item}"
            )
        realisations = [
            Realisation(**r) for r in (item.get("realisations") or [])
        ]
        formations.append(Formation(
            code=item["code"],
            titre=item["titre"],
            domaine=item.get("domaine"),
            niveau=item.get("niveau"),
            duree_jours=item.get("duree_jours"),
            confidentiel=bool(item.get("confidentiel", False)),
            synonymes=item.get("synonymes") or [],
            realisations=realisations,
        ))

    codes = [f.code for f in formations]
    if len(codes) != len(set(codes)):
        raise CatalogueFormationsError("Codes de formation en double dans le catalogue.")

    logger.info(f"📚 Catalogue chargé : {len(formations)} formation(s)")
    return formations


def obtenir_formation(code: str, chemin: Optional[Path] = None) -> Optional[Formation]:
    """Retrouve une formation par son code exact (insensible à la casse)."""
    for formation in charger_catalogue(chemin):
        if formation.code.lower() == code.lower():
            return formation
    return None


def opt_out_actif() -> bool:
    """VOYAGE_OPT_OUT dans .env : tant que ce n'est pas 'true', les
    documents marqués confidentiels ne doivent PAS être indexés (Voyage
    peut utiliser le contenu envoyé pour entraîner ses modèles sans
    moyen de paiement, voir mission C3)."""
    return os.getenv("VOYAGE_OPT_OUT", "false").strip().lower() == "true"


def formation_indexable(formation: Formation) -> bool:
    """False si la formation est confidentielle ET que VOYAGE_OPT_OUT
    n'est pas actif."""
    if formation.confidentiel and not opt_out_actif():
        return False
    return True
