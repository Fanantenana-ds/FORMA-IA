// Ce fichier gère la transformation des données entre le backend (Python/FastAPI) et le frontend (React)

import type { VeilleMarche } from '../types';

export interface BackendOpportunite {
  id: string;
  source: 'TEXTE' | 'PDF' | 'URL';
  contenu: string;
  objet?: string | null;
  budget?: number | null;
  echeance?: string | null;
  domaine?: string | null;
  statut: 'EN_ATTENTE' | 'ANALYSEE' | 'ARCHIVEE';
  score_pertinence?: number | null;
  date_creation?: string;
}

export interface DetectionStatus {
  en_cours: boolean;
  configuration: {
    planification_activee: boolean;
    intervalle_heures: number;
    requetes: string[];
    score_minimum: number;
    limite: number;
  };
  derniere_execution?: {
    derniere_execution?: string;
    declenchement?: string;
    statut?: string;
    total?: number;
    envoyees?: number;
    deja_presentes?: number;
    echecs_envoi?: number;
    erreur?: string;
  } | null;
}

export interface TavilyQuota {
  total_appels: number;
  pourcentage_utilise: number;
  runs_auto_aujourd_hui: number;
  avertissement?: string | null;
  configuration: { quota_mensuel: number; max_runs_par_jour: number };
}

export interface DetectionResult {
  markets: VeilleMarche[];
  total: number;
  status: string;
  demoMode: boolean;
  quotaReached: boolean;
  reason?: string;
  statistics: {
    queries_run?: number;
    processing_time_seconds?: number;
    backend_sync?: { enabled?: boolean; sent?: number; already_present?: number; failed?: number };
  };
  queries: Array<{ status: string }>;
}

/** Reconnaît une opportunité déjà sauvegardée, même si la recherche lui donne un autre ID. */
export const isAlreadyAccepted = (market: VeilleMarche, accepted: VeilleMarche[]): boolean =>
  accepted.some((item) => item.id === market.id || (
    item.titre.trim().toLocaleLowerCase() === market.titre.trim().toLocaleLowerCase() &&
    item.description.trim().slice(0, 120).toLocaleLowerCase() === market.description.trim().slice(0, 120).toLocaleLowerCase()
  ));

export const mapVeilleBackendToFrontend = (backendData: any) => {
  return {
    id: backendData.id || backendData._id,
    title: backendData.titre || backendData.title || 'Sans titre',
    description: backendData.description || '',
    score: backendData.score || 0,
    status: backendData.statut || backendData.status || 'pending',
    date: backendData.created_at || backendData.date,
    source: backendData.source || 'Inconnue',
    // Ajoutez ici d'autres champs spécifiques au design existant sans le modifier
    raw_data: backendData
  };
};

export const mapVeilleFrontendToBackend = (frontendData: any) => {
  return {
    titre: frontendData.title,
    description: frontendData.description,
    // Paramètres requis par le nouveau backend
    parametres_recherche: frontendData.searchParams || {}
  };
};
