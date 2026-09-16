from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field



class PresentationStructure(BaseModel):
    """Section 1 : Présentation de la structure."""
    nom: str = Field("ALTIORA Prest", description="Nom de l'entreprise")
    description: str = Field(..., description="Présentation en 2-3 phrases")
    domaines_expertise: List[str] = Field(
        default_factory=list,
        description="Domaines d'expertise",
    )


class ComprehensionBesoin(BaseModel):
    """Section 2 : Compréhension du besoin client."""
    objectifs_client: List[str] = Field(
        default_factory=list,
        description="Objectifs reformulés du client",
    )
    enjeux: List[str] = Field(
        default_factory=list,
        description="Enjeux identifiés",
    )
    public_cible: str = Field(..., description="Description du public cible")
    contraintes: List[str] = Field(
        default_factory=list,
        description="Contraintes identifiées",
    )


class ApprocheMethodologique(BaseModel):
    """Section 3 : Approche méthodologique."""
    pedagogie: str = Field(..., description="Pédagogie retenue")
    modalites: str = Field(..., description="Présentiel / distanciel / hybride")
    outils_supports: List[str] = Field(
        default_factory=list,
        description="Outils et supports",
    )
    innovations: List[str] = Field(
        default_factory=list,
        description="Innovations pédagogiques",
    )


class ArchitectureStack(BaseModel):
    """Sous-section : Stack technique."""
    frontend: Optional[str] = None
    backend: Optional[str] = None
    base_donnees: Optional[str] = Field(None, alias="base_donnees")
    ia_ml: Optional[str] = Field(None, alias="ia_ml")

    class Config:
        populate_by_name = True


class ArchitectureComposant(BaseModel):
    """Sous-section : Composant d'architecture."""
    nom: str = Field(..., description="Nom du composant")
    role: str = Field(..., description="Rôle du composant")


class ArchitectureTechnique(BaseModel):
    """Section 4 : Architecture technique (si applicable)."""
    stack: Optional[ArchitectureStack] = None
    composants: List[ArchitectureComposant] = Field(default_factory=list)
    securite: List[str] = Field(default_factory=list)
    conformite: List[str] = Field(default_factory=list)


class ProgrammeModule(BaseModel):
    """Un module du programme."""
    numero: int = Field(..., ge=1, description="Numéro du module")
    titre: str = Field(..., description="Titre du module")
    duree: str = Field(..., description="Durée (ex: '3h')")
    objectifs: List[str] = Field(default_factory=list)
    contenu: List[str] = Field(default_factory=list)
    methode: str = Field(..., description="Méthode pédagogique")


class Programme(BaseModel):
    """Section 5 : Programme détaillé."""
    duree_totale: str = Field(..., description="Durée totale (ex: '2 jours')")
    modules: List[ProgrammeModule] = Field(default_factory=list)


class RessourcesFormateur(BaseModel):
    """Sous-section : Formateur."""
    nom: str = Field(..., description="Nom du formateur")
    profil: str = Field(..., description="Profil / titre")
    expertise: List[str] = Field(default_factory=list)


class Ressources(BaseModel):
    """Section 6 : Ressources mobilisées."""
    formateur: RessourcesFormateur
    support_technique: Optional[str] = None
    materiel: List[str] = Field(default_factory=list)


class PlanningJalon(BaseModel):
    """Un jalon du planning."""
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    livrable: str = Field(..., description="Livrable attendu")


class Planning(BaseModel):
    """Section 7 : Planning prévisionnel."""
    dates_proposees: List[str] = Field(default_factory=list)
    jalons: List[PlanningJalon] = Field(default_factory=list)
    livrables: List[str] = Field(default_factory=list)


class Garanties(BaseModel):
    """Section 8 : Garanties et engagements."""
    qualite: str = Field(..., description="Engagement qualité")
    suivi: Optional[str] = Field(None, description="Suivi post-formation")
    confidentialite: Optional[str] = None


class Annexes(BaseModel):
    """Section 9 : Annexes."""
    cv_formateur: Optional[str] = None
    references: List[str] = Field(default_factory=list)


class OffreTechniqueResponse(BaseModel):
    """
    Réponse complète de l'Agent M3-1 (OffreTechniqueGeneratorService).

    Contient la trame technique complète d'une offre de formation.
    """
    success: bool = True
    titre_offre: str = Field(..., description="Titre de l'offre")
    reference: str = Field(..., description="Référence ALT-OFF-TECH-YYYY-NNNN")
    date_emission: str = Field(..., description="Date d'émission (YYYY-MM-DD)")

    presentation_structure: PresentationStructure
    comprehension_besoin: ComprehensionBesoin
    approche_methodologique: ApprocheMethodologique
    architecture_technique: Optional[ArchitectureTechnique] = None
    programme: Programme
    ressources: Ressources
    planning: Planning
    garanties: Garanties
    annexes: Optional[Annexes] = None

    points_forts: List[str] = Field(default_factory=list)
    conclusion: str = Field(..., description="Conclusion de l'offre")

    # Métadonnées
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True



class DetailCout(BaseModel):
    """Un poste de coût (générique)."""
    description: Optional[str] = None
    tarif_journalier: Optional[int] = None
    nb_jours: Optional[int] = None
    forfait_participant: Optional[int] = None
    nb_participants: Optional[int] = None
    pourcentage: Optional[float] = None
    base: Optional[int] = None
    montant: Optional[int] = None
    sous_total: Optional[int] = None


class Remise(BaseModel):
    """Une remise appliquée."""
    type: str = Field(..., description="Type de remise (quantitative, fidélité)")
    description: str = Field(..., description="Description de la remise")
    pourcentage: float = Field(..., ge=0, le=100, description="Pourcentage de remise")
    montant: int = Field(..., ge=0, description="Montant de la remise en MGA")


class TVA(BaseModel):
    """TVA."""
    taux: float = Field(20.0, ge=0, le=100, description="Taux de TVA (%)")
    montant: int = Field(..., ge=0, description="Montant de la TVA")
    applicable: bool = Field(True, description="TVA applicable ou non")


class Recapitulatif(BaseModel):
    """Récapitulatif financier."""
    sous_total_ht: int = Field(..., ge=0, description="Sous-total HT")
    tva: TVA
    total_ttc: int = Field(..., ge=0, description="Total TTC")
    remises: List[Remise] = Field(default_factory=list)
    net_a_payer: int = Field(..., ge=0, description="Net à payer")


class Echeance(BaseModel):
    """Une échéance de paiement."""
    ordre: int = Field(..., ge=1, description="Ordre de l'échéance")
    libelle: str = Field(..., description="Libellé de l'échéance")
    pourcentage: float = Field(..., ge=0, le=100, description="Pourcentage du net")
    montant: int = Field(..., ge=0, description="Montant en MGA")
    delai: str = Field(..., description="Délai (ex: 'À la signature')")


class ConditionsFinancieres(BaseModel):
    """Conditions financières de l'offre."""
    validite_offre: str = Field(..., description="Durée de validité (ex: '60 jours')")
    modalites_paiement: str = Field(..., description="Modalités (virement, chèque)")
    penalites_retard: Optional[str] = Field(None, description="Pénalités de retard")
    monnaie: str = Field("MGA", description="Devise")
    autres: List[str] = Field(default_factory=list, description="Autres conditions")


class OffreFinanciereResponse(BaseModel):
    """
    Réponse complète de l'Agent M3-2 (OffreFinanciereGeneratorService).

    Contient la trame financière complète d'une offre.
    """
    success: bool = True
    titre_offre: str = Field(..., description="Titre de l'offre")
    reference: str = Field(..., description="Référence ALT-OFF-FIN-YYYY-NNNN")
    date_emission: str = Field(..., description="Date d'émission (YYYY-MM-DD)")
    devise: str = Field("MGA", description="Devise utilisée")

    details_couts: Dict[str, DetailCout] = Field(
        ...,
        description="Détail des coûts par poste",
    )
    recapitulatif: Recapitulatif
    echeancier: List[Echeance] = Field(default_factory=list)
    conditions_financieres: ConditionsFinancieres
    notes: List[str] = Field(default_factory=list)
    conclusion: str = Field(..., description="Conclusion de l'offre")

    # Métadonnées
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True



class OffreCompleteResponse(BaseModel):
    """
    Réponse complète de l'orchestrateur M3.

    Combine l'offre technique et l'offre financière + HITL.
    """
    success: bool = True
    session_id: Optional[int] = None
    tdr_id: Optional[int] = None
    client_id: Optional[int] = None

    # Résultats des agents
    offre_technique: Optional[Dict[str, Any]] = None
    offre_financiere: Optional[Dict[str, Any]] = None

    # HITL
    review_id: Optional[str] = Field(None, alias="_review_id")
    review_status: Optional[str] = Field(None, alias="_review_status")

    # Chemins de fichiers
    docx_path: Optional[str] = None
    pdf_path: Optional[str] = None

    # Métadonnées
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True



class GenerateOffreTechniqueRequest(BaseModel):
    """Corps de la requête pour générer une offre technique."""
    tdr_data: Dict[str, Any] = Field(..., description="Données du TDR (issu du M2)")
    session_info: Dict[str, Any] = Field(..., description="Informations de session")


class GenerateOffreFinanciereRequest(BaseModel):
    """Corps de la requête pour générer une offre financière."""
    tdr_data: Dict[str, Any] = Field(..., description="Données du TDR")
    session_info: Dict[str, Any] = Field(..., description="Informations de session")
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Options (type_formateur, type_salle, tva_applicable, etc.)",
    )


class GenerateOffreCompleteRequest(BaseModel):
    """Corps de la requête pour générer une offre complète."""
    tdr_data: Dict[str, Any] = Field(..., description="Données du TDR")
    session_info: Dict[str, Any] = Field(..., description="Informations de session")
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Options : "
            "type_formateur (senior/junior), "
            "type_salle (standard/premium), "
            "tva_applicable (bool), "
            "inclure_logistique (bool), "
            "inclure_administration (bool)"
        ),
    )


class RegenerateOffreRequest(BaseModel):
    """Corps de la requête pour régénérer une offre."""
    review_id: str = Field(..., description="ID du review à régénérer")
    feedback: str = Field(
        ...,
        min_length=10,
        description="Feedback humain détaillé",
    )