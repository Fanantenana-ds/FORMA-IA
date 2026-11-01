export type UserRole = 'Dir.' | 'Form.' | 'Assis.' | 'Compt.';
export const canAccessSection = (role: UserRole, section: MenuSection): boolean => {
  if (section === 'gestion_utilisateurs') return role === 'Dir.';
  if (role === 'Form.') return ['sessions_groupes', 'suivi_presences', 'espace_ia'].includes(section);
  if (role === 'Assis.') return section !== 'tableau_de_bord' && section !== 'veille_marche';
  return true;
};

/** Libellés d'affichage des rôles. */
export const ROLE_LABELS: Record<UserRole, string> = {
  'Dir.': 'Directeur',
  'Form.': 'Formateur',
  'Assis.': 'Assistant / Secrétaire',
  'Compt.': 'Comptable'
};

export interface AuthUser {
  id: string;
  nom: string;
  email: string;
  role: UserRole;
}

export interface KPIStats {
  sessionsRealisees: number;
  participantsFormes: number;
  tauxPresenceMoyen: number; // percentage e.g. 91
  opportunitesDetectees: number;
  // Indicateurs complémentaires (undefined = non disponible)
  tdrGeneres?: number;
  offresGenerees?: number;
  attestationsGenerees?: number;
  chiffreAffairesFacture?: number; // Ar HT, toutes factures
  chiffreAffairesEncaisse?: number; // Ar, paiements reçus
  facturesEnRetard?: number;
  montantImpaye?: number; // Ar TTC restant dû
  relancesEnvoyees?: number;
  /** Vrai si participants et taux de présence ne sont pas disponibles (réservés à la Direction). */
  presenceIndisponible?: boolean;
}

export interface DomainOpportunity {
  domaine: string;
  nombre: number;
  valeurEstimee: number; // en Ariary (somme des budgets renseignés)
  croissance?: number; // percentage
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
  type: 'session' | 'presence' | 'opportunite' | 'facture' | 'veille' | 'document';
  statutTag?: string;
  utilisateur?: string;
}

export interface Session {
  id: string;
  code: string;
  intitule: string;
    formationCode?: string;
  domaine: string;
  formateur: string;
  formateurId?: string;
  dates: string;
  dateDebut?: string;
  participantsInscrits: number;
  capacityMax?: number;
  tauxPresence: number;
  statut: 'En cours' | 'Planifiée' | 'Terminée' | 'Annulée';
    lieu?: string;
  prixUnitaire?: number;
  client?: string;
  dateFin?: string;
  opportuniteId?: string;
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

export type StatutFormateur = 'Disponible' | 'En session' | 'Indisponible';

/** Formateur externe (backend : /api/v1/rh/formateurs). */
export interface Formateur {
  id: string;
  nom: string;
  prenom?: string;
  email?: string;
  telephone?: string;
  adresse?: string;
  /** Spécialités en texte libre, séparées par des virgules. */
  specialite?: string;
  tarifJournalier?: number;
  statut: StatutFormateur;
  /** Score global sur 100, calculé par l'évaluation IA post-session. */
  scoreMoyen?: number;
  nbSessions?: number;
  /** « Oui », « Conditionnel » ou « Non » (évaluation IA). */
  recommandation?: string;
  notesInternes?: string;
  dateCreation?: string;
}

export interface PresenceRecord {
  id: string;
  participantId?: string;
  sessionId: string;
  sessionTitle: string;
  apprenantNom: string;
  nom?: string;
  prenom?: string;
  entreprise: string;
  poste?: string;
  niveauInitial?: string;
  niveauFinal?: string;
  scorePositionnement?: number;
  scoreTestFinal?: number;
  scoreSatisfaction?: number;
  date: string;
  statut: 'Présent' | 'Absent' | 'Retard' | 'Excusé';
  heureEmargement?: string;
}

export interface DevisFacture {
  id: string;
  numero: string;
  type: 'Devis' | 'Facture';
  client: string;
  clientAdresse?: string;
  clientSiret?: string;
  clientRcs?: string;
  clientTva?: string;
  montantHT: number;
  montantTTC: number;
    tvaTaux?: number;
  dateEmission: string;
  dateEcheance: string;
  statut: 'Payé' | 'Partiellement payé' | 'En attente' | 'Envoyé' | 'En retard' | 'Brouillon' | 'Annulée';
  montantPaye?: number;
  montantRestantDu?: number;
  paiements?: Array<{ id: string; montant: number; date: string; mode?: string | null }>;
  sessionId?: string;
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
  /** Lien vers la source de l'annonce (résultats de la recherche IA). */
  url?: string;
  /** Score de pertinence 0-100 calculé par le backend. */
  score?: number;
  /** Niveau de confiance 0-1. */
  confiance?: number;
  /** « validated » : fiable ; « to_review » : à vérifier par un humain. */
  validation?: 'validated' | 'to_review';
  /** Date limite telle que fournie par la source. */
  echeance?: string;
  /** Site d'origine de l'annonce. */
  sourceSite?: string;
  /** « Madagascar » ou « International ». */
  portee?: string;
  /** Justification du score fournie par le backend. */
  raison?: string;
  /** Requête qui a permis de détecter ce marché (détection automatique). */
  requeteDetection?: string;
}

export type MenuSection = 
  | 'tableau_de_bord'
  | 'veille_marche'
  | 'opportunites_crm'
  | 'formateurs_staff'
  | 'evaluation_competences'
  | 'sessions_groupes'
  | 'suivi_presences'
  | 'facturation_devis'
  | 'espace_ia'
  | 'gestion_utilisateurs';

export interface ApiConfig {
  baseUrl: string;
  isConnected: boolean;
  isMockFallback?: boolean;
  lastPingTime?: string;
  errorCount: number;
}
