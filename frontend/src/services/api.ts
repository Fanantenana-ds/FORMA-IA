import {
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente,
  Session,
  OpportuniteCRM,
  Formateur,
  PresenceRecord,
  DevisFacture,
  VeilleMarche,
  ApiConfig
} from '../types';

import {
  initialKPIs,
  initialDomainOpportunities,
  initialFacturationStatuts,
  initialActivites,
  initialSessions,
  initialOpportunites,
  initialFormateurs,
  initialPresences,
  initialFactures,
  initialVeilles
} from '../data/mockData';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

class ApiService {
  private baseUrl: string = DEFAULT_BASE_URL;
  private isConnected: boolean = false;
  private isMockFallback: boolean = true;
  private errorCount: number = 0;
  private listeners: Array<(config: ApiConfig) => void> = [];

  constructor() {
    // Check saved base URL in localStorage if available
    const savedUrl = typeof window !== 'undefined' ? localStorage.getItem('forma_ia_api_url') : null;
    if (savedUrl) {
      this.baseUrl = savedUrl;
    }
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url.replace(/\/$/, '');
    if (typeof window !== 'undefined') {
      localStorage.setItem('forma_ia_api_url', this.baseUrl);
    }
    this.checkHealth();
  }

  public subscribe(listener: (config: ApiConfig) => void) {
    this.listeners.push(listener);
    // Send initial status
    listener(this.getConfig());
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify() {
    const config = this.getConfig();
    this.listeners.forEach(listener => listener(config));
  }

  public getConfig(): ApiConfig {
    return {
      baseUrl: this.baseUrl,
      isConnected: this.isConnected,
      isMockFallback: this.isMockFallback,
      errorCount: this.errorCount,
      lastPingTime: new Date().toLocaleTimeString('fr-FR')
    };
  }

  public async checkHealth(): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);

      const res = await fetch(`${this.baseUrl}/api/health`, {
        method: 'GET',
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        this.isConnected = true;
        this.isMockFallback = false;
        this.errorCount = 0;
        this.notify();
        return true;
      } else {
        throw new Error(`HTTP Error ${res.status}`);
      }
    } catch (err) {
      this.isConnected = false;
      this.isMockFallback = true;
      this.errorCount++;
      this.notify();
      return false;
    }
  }

  private async request<T>(endpoint: string, fallbackData: T, options?: RequestInit): Promise<T> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...(options?.headers || {})
        },
        signal: controller.signal,
        ...options
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Erreur API ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.isConnected = true;
      this.isMockFallback = false;
      this.notify();
      return data as T;
    } catch (error) {
      console.warn(`[FORMA-IA API Client] Impossible de contacter ${this.baseUrl}${endpoint}. Bascule sur le fallback local REST simulation.`, error);
      this.isConnected = false;
      this.isMockFallback = true;
      this.errorCount++;
      this.notify();
      return fallbackData;
    }
  }

  // API Methods
  public async getKPIs(): Promise<KPIStats> {
    return this.request<KPIStats>('/api/dashboard/kpis', initialKPIs);
  }

  public async getDomainOpportunities(): Promise<DomainOpportunity[]> {
    return this.request<DomainOpportunity[]>('/api/dashboard/opportunities-by-domain', initialDomainOpportunities);
  }

  public async getFacturationStatuts(): Promise<FacturationStatut[]> {
    return this.request<FacturationStatut[]>('/api/dashboard/invoicing-status', initialFacturationStatuts);
  }

  public async getRecentActivities(): Promise<ActiviteRecente[]> {
    return this.request<ActiviteRecente[]>('/api/dashboard/recent-activities', initialActivites);
  }

  public async getSessions(): Promise<Session[]> {
    return this.request<Session[]>('/api/sessions', initialSessions);
  }

  public async createSession(session: Partial<Session>): Promise<Session> {
    const newSession: Session = {
      id: `sess-${Date.now()}`,
      code: `FORMA-IA-${new Date().getFullYear()}-${Math.floor(Math.random() * 90 + 10)}`,
      intitule: session.intitule || 'Nouvelle Session IA',
      domaine: session.domaine || 'IA Générative',
      formateur: session.formateur || 'Formateur Assigné',
      dates: session.dates || 'À déterminer',
      participantsInscrits: session.participantsInscrits || 0,
      capacityMax: session.capacityMax || 20,
      tauxPresence: 0,
      statut: 'Planifiée',
      lieu: session.lieu || 'Distanciel',
      prixUnitaire: session.prixUnitaire || 1200
    };

    return this.request<Session>('/api/sessions', newSession, {
      method: 'POST',
      body: JSON.stringify(newSession)
    });
  }

  public async getOpportunites(): Promise<OpportuniteCRM[]> {
    return this.request<OpportuniteCRM[]>('/api/opportunities', initialOpportunites);
  }

  public async createOpportunite(opp: Partial<OpportuniteCRM>): Promise<OpportuniteCRM> {
    const newOpp: OpportuniteCRM = {
      id: `opp-${Date.now()}`,
      entreprise: opp.entreprise || 'Nouvelle Entreprise',
      contactName: opp.contactName || 'Contact Prospect',
      contactEmail: opp.contactEmail || 'contact@entreprise.com',
      domaineIA: opp.domaineIA || 'IA Générative',
      besoinFormation: opp.besoinFormation || 'Acculturation et pratique des outils IA',
      participantsEstimes: opp.participantsEstimes || 10,
      montantEstime: opp.montantEstime || 15000,
      etape: 'Détectée par IA',
      probabilite: 40,
      dateDetection: new Date().toLocaleDateString('fr-FR')
    };

    return this.request<OpportuniteCRM>('/api/opportunities', newOpp, {
      method: 'POST',
      body: JSON.stringify(newOpp)
    });
  }

  public async getFormateurs(): Promise<Formateur[]> {
    return this.request<Formateur[]>('/api/trainers', initialFormateurs);
  }

  public async getPresences(): Promise<PresenceRecord[]> {
    return this.request<PresenceRecord[]>('/api/attendance', initialPresences);
  }

  public async getFactures(): Promise<DevisFacture[]> {
    return this.request<DevisFacture[]>('/api/invoices', initialFactures);
  }

  public async createFacture(fac: Partial<DevisFacture>): Promise<DevisFacture> {
    const newFacture: DevisFacture = {
      id: `fac-${Date.now()}`,
      numero: fac.type === 'Devis' ? `DEV-2026-${Math.floor(Math.random() * 900 + 100)}` : `FAC-2026-${Math.floor(Math.random() * 900 + 100)}`,
      type: fac.type || 'Devis',
      client: fac.client || 'Nouveau Client',
      montantHT: fac.montantHT || 10000,
      montantTTC: Math.round((fac.montantHT || 10000) * 1.2),
      dateEmission: new Date().toLocaleDateString('fr-FR'),
      dateEcheance: new Date(Date.now() + 30 * 24 * 3600 * 1000).toLocaleDateString('fr-FR'),
      statut: fac.type === 'Devis' ? 'Envoyé' : 'En attente'
    };

    return this.request<DevisFacture>('/api/invoices', newFacture, {
      method: 'POST',
      body: JSON.stringify(newFacture)
    });
  }

  public async getVeilles(): Promise<VeilleMarche[]> {
    return this.request<VeilleMarche[]>('/api/market-watch', initialVeilles);
  }
}

export const apiService = new ApiService();
