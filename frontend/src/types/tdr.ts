export interface TdrDocModel {
  projetCode: string;
  projetTitre: string;
  clientOrganisme: string;
  partenaireAcademic: string;
  anneeAcademique: string;
  dureePrestation: string;
  datesDebutFin: string;
  etudiantAssign: string;
  encadreurPro: string;
  encadreurAcademic: string;
  versionDate: string;
  
  // Section 1: Contexte
  presentationClient: string;
  positionnementProjet: string;
  justificationBesoin: string;
  
  // Section 2: Objectifs
  problematique: string;
  objectifGeneral: string;
  objectifsSMART: string[];
  resultatsAttendus: string[];
  
  // Section 3: Planning
  planningPhases: { phase: string; semaines: string; activites: string; livrable: string }[];
  
  // Section 4: Profil
  niveauRequis: string;
  competencesTech: string[];
  competencesComportement: string[];
  
  // Section 5: Conditions
  cadreGeneral: string;
  encadrementRythme: string;
  conditionsMaterielles: string;
  
  // Section 6: Livrables
  livrablesTable: { id: number; livrable: string; echeance: string; destinataire: string; validation: string }[];
  
  // Section 7: Grille d'évaluation
  grilleEvaluation: { critere: string; poids: string; evaluateur: string }[];
}

export interface OtDocModel {
  referenceOt: string;
  clientOrganisme: string;
  intituleFormation: string;
  formateurRef: string;
  dureeAtelier: string;
  methodologiePedago: string;
  programmeModules: { module: string; duree: string; description: string }[];
  budgetDetails: { designation: string; quantite: number; prixUnitaireAr: number; totalAr: number }[];
  budgetTotalAr: number;
  garantiesEtPropretie: string;
}

export interface AcceptedMarket {
  id: string;
  titre: string;
  client: string;
  domaine: string;
  budgetAr: number;
  duree: string;
  date: string;
  statut: string;
}

/** Marchés acceptés : alimentés par le backend (aucun exemple embarqué). */
export const DEFAULT_ACCEPTED_MARKETS: AcceptedMarket[] = [];

/** Modèle de TDR vierge : tous les champs sont à renseigner. */
export const EMPTY_TDR_DATA: TdrDocModel = {
  projetCode: '',
  projetTitre: '',
  clientOrganisme: '',
  partenaireAcademic: '',
  anneeAcademique: '',
  dureePrestation: '',
  datesDebutFin: '',
  etudiantAssign: '',
  encadreurPro: '',
  encadreurAcademic: '',
  versionDate: '',

  presentationClient: '',
  positionnementProjet: '',
  justificationBesoin: '',

  problematique: '',
  objectifGeneral: '',
  objectifsSMART: [],
  resultatsAttendus: [],

  planningPhases: [],

  niveauRequis: '',
  competencesTech: [],
  competencesComportement: [],

  cadreGeneral: '',
  encadrementRythme: '',
  conditionsMaterielles: '',

  livrablesTable: [],

  grilleEvaluation: []
};

/** Modèle d'offre technique vierge. */
export const EMPTY_OT_DATA: OtDocModel = {
  referenceOt: '',
  clientOrganisme: '',
  intituleFormation: '',
  formateurRef: '',
  dureeAtelier: '',
  methodologiePedago: '',
  programmeModules: [],
  budgetDetails: [],
  budgetTotalAr: 0,
  garantiesEtPropretie: ''
};
