export type UserRole = 'Dir.' | 'Form.' | 'Assis.';

export interface AuthUser {
  id: string;
  nom: string;
  prenom: string;
  email: string;
  role: UserRole;
  organisation?: string;
  avatarUrl?: string;
}

export interface KPIStats {
  sessionsRealisees: number;
  participantsFormes: number;
  tauxPresenceMoyen: number; // percentage e.g. 91
  opportunitesDetectees: number;
}

export interface DomainOpportunity {
  domaine: string;
  nombre: number;
  valeurEstimee: number; // in Euros
  croissance: number; // percentage
  couleur?: string;
}

export interface FacturationStatut {
  statut: 'Payé' | 'En attente' | 'En retard' | 'Devis envoyé';
  montant: number;
  nombreFactures: number;
  pourcentage: number;
  couleur: string;
}

export interface ActiviteRecente {
  id: string;
  titre: string;
  description: string;
  horodateur: string;
  type: 'session' | 'presence' | 'opportunite' | 'facture' | 'veille';
  statutTag?: string;
  utilisateur?: string;
}

export interface Session {
  id: string;
  code: string;
  intitule: string;
  domaine: string;
  formateur: string;
  dates: string;
  participantsInscrits: number;
  capacityMax: number;
  tauxPresence: number;
  statut: 'En cours' | 'Planifiée' | 'Terminée' | 'Annulée';
  lieu: 'Présentiel' | 'Distanciel' | 'Hybride';
  prixUnitaire: number;
}

export interface OpportuniteCRM {
  id: string;
  entreprise: string;
  contactName: string;
  contactEmail: string;
  domaineIA: string;
  besoinFormation: string;
  participantsEstimes: number;
  montantEstime: number;
  etape: 'Détectée par IA' | 'Contact qualifié' | 'Devis transmis' | 'Gagnée' | 'Perdue';
  probabilite: number; // 0-100%
  dateDetection: string;
}

export interface EvaluationFormateur {
  id: string;
  formateurId: string;
  apprenantNom: string;
  entreprise: string;
  date: string;
  notePedagogie: number; // 1-5
  noteMaitriseTech: number; // 1-5
  noteSupports: number; // 1-5
  notePonctualite: number; // 1-5
  noteMoyenne: number; // 1-5
  commentaire: string;
  recommande: boolean;
}

export interface Formateur {
  id: string;
  nom: string;
  specialites: string[];
  statut: 'Disponible' | 'En session' | 'Indisponible';
  tauxSatisfaction: number; // e.g. 4.9
  tarifJournalier: number;
  email: string;
  telephone: string;
  sessionsCompteur: number;
  avatarUrl?: string;
  evaluations?: EvaluationFormateur[];
}

export interface PresenceRecord {
  id: string;
  sessionId: string;
  sessionTitle: string;
  apprenantNom: string;
  entreprise: string;
  date: string;
  statut: 'Présent' | 'Absent' | 'Retard' | 'Excusé';
  heureEmargement?: string;
}

export interface DevisFacture {
  id: string;
  numero: string;
  type: 'Devis' | 'Facture';
  client: string;
  montantHT: number;
  montantTTC: number;
  dateEmission: string;
  dateEcheance: string;
  statut: 'Payé' | 'En attente' | 'En retard' | 'Envoyé' | 'Brouillon';
}

export interface VeilleMarche {
  id: string;
  titre: string;
  categorie: string;
  description: string;
  impactOrganisme: 'Majeur' | 'Moyen' | 'Opportunité émergente';
  demandeClient: string;
  dateAnalyse: string;
  motsCles: string[];
  statut?: 'Trouvé' | 'Accepté';
  clientCible?: string;
  budgetEstimeAr?: number;
  tdrSummary?: string;
  otSummary?: string;
}

export type MenuSection = 
  | 'tableau_de_bord'
  | 'veille_marche'
  | 'opportunites_crm'
  | 'formateurs_staff'
  | 'evaluation_competences'
  | 'sessions_groupes'
  | 'suivi_presences'
  | 'facturation_devis';

export interface ApiConfig {
  baseUrl: string;
  isConnected: boolean;
  isMockFallback: boolean;
  lastPingTime?: string;
  errorCount: number;
}
