import { API_BASE_URL, API_PREFIX, API_REQUEST_BASE } from '../config/env';
import type {
  ApiConfig, AuthUser, DevisFacture, Formateur,
  OpportuniteCRM, PresenceRecord, Session, UserRole, VeilleMarche
} from '../types';
import { buildDashboard, type BackendStats } from './dashboardMapping';
import { formateurFullName, toFormateur, type BackendFormateur } from './formateurMapping';
import type { DetectionResult, DetectionStatus, TavilyQuota } from './veilleMapping';
import { addDaysToDate, addMonthsToDate } from './sessionDates';
import { reportFrontendError } from './frontendErrorReporter';

const IA_TOKEN = import.meta.env.VITE_IA_TOKEN as string | undefined;
const roleFromApi: Record<string, UserRole> = {
  DIRECTION: 'Dir.', ADMIN: 'Dir.', FORMATEUR: 'Form.', ASSISTANT: 'Assis.', COMPTABLE: 'Compt.'
};
const roleToApi: Record<UserRole, string> = {
  'Dir.': 'DIRECTION', 'Form.': 'FORMATEUR', 'Assis.': 'ASSISTANT', 'Compt.': 'COMPTABLE'
};

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly detail?: unknown) {
    super(message); this.name = 'ApiError';
  }
}

export type SessionTrainerOption = Formateur;

export const tokenStore = {
  get: () => { try { return localStorage.getItem('token'); } catch { return null; } },
  set: (token: string) => { try { localStorage.setItem('token', token); } catch { /* stockage indisponible */ } },
  clear: () => { try { localStorage.removeItem('token'); } catch { /* stockage indisponible */ } }
};

const dateOnly = (value: string | undefined): string | undefined => {
  if (!value) return undefined;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().slice(0, 10);
};
const fromRole = (value: unknown): UserRole => roleFromApi[String(value ?? '').toUpperCase()] ?? 'Assis.';
const arr = <T,>(data: unknown, key?: string): T[] => {
  const list = key && data && typeof data === 'object' ? (data as Record<string, unknown>)[key] : data;
  return Array.isArray(list) ? list as T[] : [];
};
const currency = (n: unknown) => Number(n ?? 0);
const normalizeBudget = (value: unknown): number | undefined => {
  if (typeof value === 'number') return Number.isFinite(value) && value >= 0 ? value : undefined;
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const millionMultiplier = /millions?|(?:^|\d)\s*m\s*(?:ar|mga|$)/i.test(value) ? 1_000_000 : 1;
  let numeric = value.replace(/[\s\u00a0]/g, '').replace(/[^\d,.-]/g, '');
  if (!numeric) return undefined;
  if (numeric.includes(',') && numeric.includes('.')) {
    numeric = numeric.lastIndexOf(',') > numeric.lastIndexOf('.')
      ? numeric.replace(/\./g, '').replace(',', '.')
      : numeric.replace(/,/g, '');
  } else if ((numeric.match(/,/g) ?? []).length > 1) {
    numeric = numeric.replace(/,/g, '');
  } else {
    numeric = numeric.replace(',', '.');
  }
  const amount = Number(numeric) * millionMultiplier;
  return Number.isFinite(amount) && amount >= 0 ? amount : undefined;
};
const mapOpportunity = (o: any): OpportuniteCRM => ({
  id: String(o.id), entreprise: o.objet || 'Opportunité', contactName: '', contactEmail: '',
  domaineIA: o.domaine || 'AUTRE', besoinFormation: o.contenu || '', participantsEstimes: 0,
  montantEstime: currency(o.budget), etape: o.statut === 'ANALYSEE' ? 'Contact qualifié' : o.statut === 'ARCHIVEE' ? 'Perdue' : 'Détectée par IA',
  probabilite: currency(o.score_pertinence), dateDetection: o.date_creation ? new Date(o.date_creation).toLocaleDateString('fr-FR') : ''
});
let veilleClientId = 0;
const mapVeilleMarket = (m: any): VeilleMarche => ({
  id: String(m.id ?? m.review_id ?? globalThis.crypto?.randomUUID?.() ?? `veille-${Date.now()}-${++veilleClientId}`), titre: m.titre ?? m.title ?? m.objet ?? 'Résultat de veille',
  categorie: m.domaine ?? m.domain ?? 'AUTRE', description: m.contenu ?? m.description ?? m.summary ?? '', impactOrganisme: 'Opportunité émergente',
  demandeClient: m.contenu ?? m.description ?? m.summary ?? '', dateAnalyse: m.date_creation ?? new Date().toLocaleDateString('fr-FR'),
  motsCles: [], statut: 'Trouvé', url: m.url ?? m.source_url, score: m.score_pertinence ?? m.score, budgetEstimeAr: normalizeBudget(m.budget),
  echeance: m.echeance ?? m.deadline, clientCible: m.organizer ?? m.organization ?? m.objet, sourceSite: m.source ?? m.source_name, validation: m.validation
});
const mapSession = (s: any, formateurNom?: string): Session => {
  const dateDebut = s.date_debut ? String(s.date_debut).slice(0, 10) : '';
  const dateFin = s.date_fin ? String(s.date_fin).slice(0, 10) : '';
  const start = dateDebut ? new Date(`${dateDebut}T12:00:00`) : null;
  const end = dateFin ? new Date(`${dateFin}T12:00:00`) : null;
  const now = Date.now();
  const status: Session['statut'] = end && end.getTime() < now ? 'Terminée' : start && start.getTime() <= now ? 'En cours' : 'Planifiée';
  return { id: String(s.id), code: String(s.id).slice(0, 8).toUpperCase(), intitule: s.titre, formationCode: s.formation_code ?? undefined, domaine: s.domaine ?? s.formation_code ?? 'À définir',
    formateur: formateurNom ?? (s.formateur ? formateurFullName({ nom: s.formateur.nom ?? '', prenom: s.formateur.prenom }) : undefined) ?? s.formateur_nom ?? 'À définir', formateurId: s.formateur_id ?? s.formateur?.id ?? undefined,
    dates: [start, end].filter(Boolean).map(d => d!.toLocaleDateString('fr-FR')).join(' – '), dateDebut: dateDebut || undefined,
    participantsInscrits: Number(s.nombre_participants ?? s.participants?.length ?? 0), capacityMax: s.nb_participants_max == null ? undefined : Number(s.nb_participants_max),
    tauxPresence: Number(s.taux_presence ?? 0), statut: status, lieu: s.lieu ?? 'À définir', prixUnitaire: s.prix_unitaire == null ? undefined : Number(s.prix_unitaire),
    client: s.client ?? undefined, dateFin: dateFin || undefined, opportuniteId: s.opportunite_id ?? undefined };
};
const mapInvoice = (f: any): DevisFacture => ({
  id: String(f.id), numero: f.numero ?? String(f.id).slice(0, 8), type: 'Facture', client: f.client,
  clientAdresse: f.client_adresse ?? undefined, clientSiret: f.client_siret ?? undefined,
  clientRcs: f.client_rcs ?? undefined, clientTva: f.client_tva ?? undefined,
  montantHT: currency(f.montant), montantTTC: currency(f.montant_ttc ?? f.montant), tvaTaux: currency(f.tva_taux ?? 20),
  dateEmission: f.date_emission ? new Date(f.date_emission).toLocaleDateString('fr-FR') : '',
  dateEcheance: f.date_echeance ? String(f.date_echeance).slice(0, 10) : '',
  statut: f.statut === 'BROUILLON' ? 'Brouillon' : f.statut === 'PAYEE' ? 'Payé' : f.statut === 'PARTIELLEMENT_PAYEE' ? 'Partiellement payé' : f.statut === 'EN_RETARD' ? 'En retard' : f.statut === 'ANNULEE' ? 'Annulée' : 'Envoyé',
  paiements: Array.isArray(f.paiements) ? f.paiements.map((payment: any) => ({ id: String(payment.id), montant: currency(payment.montant), date: payment.date, mode: payment.mode })) : [],
  montantPaye: Array.isArray(f.paiements) ? f.paiements.reduce((sum: number, payment: any) => sum + currency(payment.montant), 0) : 0,
  montantRestantDu: Math.max(0, currency(f.montant_ttc ?? f.montant) - (Array.isArray(f.paiements) ? f.paiements.reduce((sum: number, payment: any) => sum + currency(payment.montant), 0) : 0)),
  sessionId: f.session_id ? String(f.session_id) : undefined
});

class ApiService {
  private connected = false;
  private fallback = false;
  private errors = 0;
  private ping = '';
  private listeners = new Set<(config: ApiConfig) => void>();
  private unauthorized = new Set<() => void>();
  getConfig = (): ApiConfig => ({ baseUrl: API_BASE_URL, isConnected: this.connected, isMockFallback: this.fallback, errorCount: this.errors, lastPingTime: this.ping });
  subscribe = (fn: (config: ApiConfig) => void) => { this.listeners.add(fn); fn(this.getConfig()); return () => this.listeners.delete(fn); };
  onUnauthorized = (fn: () => void) => { this.unauthorized.add(fn); return () => this.unauthorized.delete(fn); };
  private notify() { this.ping = new Date().toLocaleTimeString('fr-FR'); this.listeners.forEach(fn => fn(this.getConfig())); }
  private async request<T>(path: string, init: RequestInit = {}, opts: { ia?: boolean; jwtForIA?: boolean; timeout?: number; auth?: boolean } = {}): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), opts.timeout ?? (opts.ia ? 120000 : 20000));
    const headers = new Headers(init.headers);
    if (init.body != null && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    headers.set('Accept', 'application/json');
    // Pour les appels IA, préférer la session JWT déjà ouverte dans le front.
    // La clé interne reste un recours pour les intégrations sans session.
    const userToken = tokenStore.get();
    const token = opts.ia && !opts.jwtForIA ? (userToken || IA_TOKEN) : userToken;
    const usingUserToken = !!userToken && token === userToken;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    try {
      const response = await fetch(`${API_REQUEST_BASE}${API_PREFIX}${path}`, { ...init, headers, signal: controller.signal });
      clearTimeout(timeout);
      if (response.status === 401 && opts.auth !== false && (!opts.ia || opts.jwtForIA || usingUserToken)) this.unauthorized.forEach(fn => fn());
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = (body as any)?.detail ?? (body as any)?.message;
        const message = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : `Erreur API ${response.status}`;
        this.connected = response.status !== 0; this.fallback = false; this.errors++; this.notify();
        reportFrontendError('api', { route: path.split('?')[0], status: response.status });
        throw new ApiError(message, response.status, detail);
      }
      this.connected = true; this.fallback = false; this.notify();
      if (response.status === 204) return undefined as T;
      const type = response.headers.get('content-type') ?? '';
      return (type.includes('application/json') ? await response.json() : await response.blob()) as T;
    } catch (error) {
      clearTimeout(timeout);
      if (error instanceof ApiError) throw error;
      this.connected = false; this.fallback = true; this.errors++; this.notify();
      reportFrontendError('network', { route: path.split('?')[0], status: 0 });
      throw new ApiError(error instanceof Error && error.name === 'AbortError' ? 'Le service met plus de temps que prévu. Réessayez dans un instant.' : 'La connexion au service est momentanément indisponible. Vérifiez que le serveur est démarré, puis actualisez la page.', 0, error);
    }
  }
  private json(method: string, body?: unknown): RequestInit { return { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }; }
  async checkHealth() {
    try {
      const response = await fetch(`${API_REQUEST_BASE}/health`, { signal: AbortSignal.timeout(5000) });
      this.connected = response.ok; this.fallback = !response.ok; this.notify(); return response.ok;
    } catch { this.connected = false; this.fallback = true; this.notify(); return false; }
  }
  async login(email: string, password: string): Promise<AuthUser> {
    const token = await this.request<any>('/auth/login', this.json('POST', { email, password }), { auth: false });
    tokenStore.set(token.access_token);
    return this.fetchCurrentUser();
  }
  async register(user: { nom: string; email: string; password: string; role: UserRole }) {
    return this.request('/auth/register', this.json('POST', { ...user, role: roleToApi[user.role] }), { auth: false });
  }
  async fetchCurrentUser(): Promise<AuthUser> { const u = await this.request<any>('/auth/me'); return { id: String(u.id), nom: u.nom, email: u.email, role: fromRole(u.role) }; }
  async getManagedUsers() { return this.request<any[]>('/auth/users'); }
  async createManagedUser(data: { nom: string; email: string; password: string; role: 'ASSISTANT' | 'COMPTABLE' }) {
    return this.request<any>('/auth/users', this.json('POST', data));
  }
  async updateManagedUser(id: string, payload: { actif?: boolean; nom?: string; email?: string }) {
    return this.request<any>('/auth/users/' + encodeURIComponent(id), this.json('PATCH', payload));
  }
  async deleteManagedUser(id: string) { return this.request('/auth/users/' + encodeURIComponent(id), this.json('DELETE')); }
  async logout() { try { if (tokenStore.get()) await this.request('/auth/logout', this.json('POST')); } finally { tokenStore.clear(); } }
  async getDashboard(role: UserRole) {
    const results = await Promise.allSettled([
      this.request<BackendStats>('/dashboard/statistiques'), this.request<any>('/opportunites?skip=0&limit=100'),
      this.request<any[]>('/sessions?skip=0&limit=100'), this.request<any[]>('/factures?skip=0&limit=100'), this.request<any[]>('/documents?skip=0&limit=100')
    ]);
    const val = <T,>(i: number): T | null => results[i].status === 'fulfilled' ? (results[i] as PromiseFulfilledResult<T>).value : null;
    const op = val<any>(1); const dashboard = buildDashboard({ stats: val<BackendStats>(0), opportunites: arr(op, 'opportunites'), sessions: val<any[]>(2), factures: val<any[]>(3), documents: val<any[]>(4) }, results.some((result, index) => result.status === 'rejected' && (index !== 0 || role === 'Dir.')));
    if (role !== 'Dir.') { dashboard.kpis.presenceIndisponible = true; }
    return dashboard;
  }
  async getFormateurs(): Promise<Formateur[]> { return arr<BackendFormateur>(await this.request('/rh/formateurs')).map(toFormateur); }
  async getSessionTrainerOptions(): Promise<SessionTrainerOption[]> {
    const trainers = await this.getFormateurs();
    // Session.formateur_id référence directement formateurs.id dans ce backend.
    return trainers.filter((trainer) => trainer.statut !== 'Indisponible').sort((a, b) =>
      Number(b.recommandation === 'Oui') - Number(a.recommandation === 'Oui') ||
      (b.scoreMoyen ?? -1) - (a.scoreMoyen ?? -1)
    );
  }
  async createFormateur(payload: Record<string, unknown>) { return toFormateur(await this.request<BackendFormateur>('/rh/formateurs', this.json('POST', payload))); }
  async updateFormateur(id: string, payload: Record<string, unknown>) { return toFormateur(await this.request<BackendFormateur>(`/rh/formateurs/${id}`, this.json('PATCH', payload))); }
  async deleteFormateur(id: string) { return this.request(`/rh/formateurs/${id}`, this.json('DELETE')); }
  async getVeilles(): Promise<VeilleMarche[]> { const data = await this.request<any>('/opportunites?skip=0&limit=100'); return arr<any>(data, 'opportunites').map(mapVeilleMarket); }
  async getOpportunites(): Promise<OpportuniteCRM[]> { const data = await this.request<any>('/opportunites?skip=0&limit=100'); return arr<any>(data, 'opportunites').map(mapOpportunity); }
  async createOpportunite(form: Partial<OpportuniteCRM>) {
    const raw = await this.request<any>('/opportunites', this.json('POST', { source: 'TEXTE', contenu: form.besoinFormation || form.entreprise || 'Opportunité saisie depuis le CRM', objet: form.entreprise || 'Nouvelle opportunité', budget: normalizeBudget(form.montantEstime), domaine: normalizeDomain(form.domaineIA) }));
    return mapOpportunity(raw);
  }
  async searchMarkets(query: string) {
    const data = await this.request<any>('/ia/veille/rechercher', this.json('POST', { query, domains: [], min_score: 0, limit: 20 }), { ia: true, jwtForIA: true });
    const payload = data.data ?? data;
    const results = arr<any>(payload, 'opportunities').concat(arr<any>(payload, 'opportunites'), arr<any>(payload, 'results'), arr<any>(payload, 'markets'));
    const markets = results.map(mapVeilleMarket);
    return { markets, status: payload.status === 'degraded' ? 'degraded' as const : 'ok' as const, notes: payload.notes ?? payload.message };
  }
  async acceptMarket(market: VeilleMarche): Promise<{ opportunity: OpportuniteCRM; session?: Session; sessionError?: string }> {
    const opportunity = await this.createOpportunite({ entreprise: market.titre, domaineIA: market.categorie, besoinFormation: market.description || market.titre, montantEstime: market.budgetEstimeAr });
    const acceptanceDate = new Date();
    const acceptedOn = `${acceptanceDate.getFullYear()}-${String(acceptanceDate.getMonth() + 1).padStart(2, '0')}-${String(acceptanceDate.getDate()).padStart(2, '0')}`;
    const dateDebut = addDaysToDate(acceptedOn, 7);
    const dateFin = addMonthsToDate(dateDebut, 1);
    try {
      const session = await this.createSession({
        intitule: market.titre,
        client: market.clientCible || market.sourceSite,
        dates: dateDebut,
        dateFin,
        opportuniteId: opportunity.id
      });
      return { opportunity, session };
    } catch (error) {
      return { opportunity, sessionError: error instanceof Error ? error.message : 'La session automatique n’a pas pu être créée.' };
    }
  }
  async getDetectionStatus(): Promise<DetectionStatus> {
    const response = await this.request<any>('/ia/veille/detecter/statut', {}, { ia: true, jwtForIA: true });
    return response.data;
  }
  async getTavilyQuota(): Promise<TavilyQuota> {
    const response = await this.request<any>('/ia/veille/quota', {}, { ia: true, jwtForIA: true });
    return response.data;
  }
  async runDetection(options: { syncBackend?: boolean } = {}): Promise<DetectionResult> {
    const data = await this.request<any>('/ia/veille/detecter', this.json('POST', { sync_backend: !!options.syncBackend }), { ia: true, jwtForIA: true, timeout: 120000 });
    const payload = data.data ?? data;
    return {
      markets: arr<any>(payload, 'opportunities').concat(arr<any>(payload, 'opportunites'), arr<any>(payload, 'results')).map(mapVeilleMarket),
      total: Number(payload.total ?? 0), status: payload.status ?? 'success',
      demoMode: payload.demo_mode === true,
      quotaReached: payload.status === 'quota_atteint' || data.status === 'quota_atteint',
      reason: payload.reason ?? payload.notes ?? data.error,
      statistics: payload.statistics ?? {}, queries: arr<any>(payload, 'queries')
    };
  }
  async streamDetection(onEvent: (event: string, data: any) => void, options: { syncBackend?: boolean } = {}): Promise<DetectionResult> {
    const token = tokenStore.get();
    if (!token) throw new ApiError('Reconnectez-vous pour lancer la détection.', 401);
    const params = new URLSearchParams({ sync_backend: String(!!options.syncBackend) });
    const response = await fetch(`${API_REQUEST_BASE}${API_PREFIX}/ia/veille/detecter/stream?${params}`, {
      headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) {
      reportFrontendError('api', { route: '/ia/veille/detecter/stream', status: response.status });
      throw new ApiError(`Le flux de détection a échoué (HTTP ${response.status}).`, response.status);
    }
    if (!response.body) throw new ApiError('Le serveur n’a pas ouvert le flux de détection.', 502);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let final: any = null;
    let streamError = '';
    const dispatch = (flush = false) => {
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = flush ? '' : frames.pop() ?? '';
      for (const frame of frames) {
        const event = frame.match(/^event:\s*(.+)$/m)?.[1]?.trim();
        const dataText = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
        if (!event || !dataText) continue;
        let data: any;
        try { data = JSON.parse(dataText); } catch { continue; }
        onEvent(event, data);
        if (event === 'erreur') streamError = String(data.message ?? 'Erreur de détection.');
        if (event === 'fin') final = data;
      }
    };
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      dispatch();
    }
    buffer += decoder.decode();
    dispatch(true);
    if (!final) throw new ApiError(streamError || 'Flux interrompu avant la fin de la détection.', 502);
    if (['technical_error', 'error', 'quota_atteint', 'in_progress'].includes(final.status)) {
      throw new ApiError(streamError || 'La détection n’a pas abouti.', final.status === 'in_progress' ? 409 : 503);
    }
    const opportunities = arr<any>(final, 'opportunites');
    const demoMode = opportunities.some((item) => item.demo_data_type === 'archive_reelle' || item.demo_data_type === 'synthetic_fallback');
    return {
      markets: opportunities.map(mapVeilleMarket), total: Number(final.total ?? opportunities.length),
      status: String(final.status ?? 'success'), demoMode, quotaReached: false,
      statistics: final.statistics ?? { queries_run: final['requêtes'], backend_sync: { enabled: false } },
      queries: arr<any>(final, 'queries'),
    };
  }
  async getSessions(): Promise<Session[]> {
    const rawSessions = arr<any>(await this.request('/sessions?skip=0&limit=100'));
    const trainers = await this.getFormateurs().catch(() => []);
    return rawSessions.map((raw) => {
      const trainer = trainers.find((item) => String(item.id) === String(raw.formateur_id ?? ''));
      return mapSession(raw, trainer ? formateurFullName(trainer) : undefined);
    });
  }
  async createSession(form: Partial<Session>) {
    const trainers = form.formateurId || form.formateur ? await this.getFormateurs().catch(() => []) : [];
    const trainer = trainers.find(t => t.id === form.formateurId || `${t.prenom ?? ''} ${t.nom}`.trim() === form.formateur || t.nom === form.formateur);
    const formateurId = trainer?.id;
    const start = dateOnly(form.dates);
    const raw = await this.request<any>('/sessions', this.json('POST', { titre: form.intitule?.trim().slice(0, 50), client: form.client?.trim().slice(0, 50) || undefined, formation_code: (form as any).formationCode || undefined, opportunite_id: form.opportuniteId || undefined, lieu: form.lieu || undefined, nb_participants_max: form.capacityMax || undefined, date_debut: start, date_fin: dateOnly(form.dateFin), ...(formateurId ? { formateur_id: formateurId } : {}) }));
    return mapSession(raw, trainer ? formateurFullName(trainer) : form.formateur);
  }
  async getFactures(): Promise<DevisFacture[]> { return arr<any>(await this.request('/factures?skip=0&limit=100')).map(mapInvoice); }
  async getOffersByOpportunity(opportunityId: string) {
    return this.request<any>(`/offres${queryString({ opportunite_id: opportunityId, skip: '0', limit: '100' })}`);
  }
  async createFacture(form: Partial<DevisFacture>) {
    const raw = await this.request<any>('/factures', this.json('POST', {
      client: form.client?.trim() || undefined,
      client_adresse: form.clientAdresse?.trim() || undefined,
      client_siret: form.clientSiret?.trim() || undefined,
      client_rcs: form.clientRcs?.trim() || undefined,
      client_tva: form.clientTva?.trim() || undefined,
      montant: form.montantHT ?? 0,
      tva_taux: form.tvaTaux ?? 20,
      date_echeance: form.dateEcheance || new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
      session_id: form.sessionId || undefined
    }));
    return mapInvoice(raw);
  }
  async updateFactureStatus(id: string, statut: string) {
    const status = statut === 'Brouillon' || statut === 'Annulée' ? 'ANNULEE' : 'EMISE';
    return mapInvoice(await this.request<any>(`/factures/${id}`, this.json('PATCH', { statut: status })));
  }
  async addPayment(id: string, montant: number, mode?: string) {
    return this.request(`/factures/${id}/paiements`, this.json('POST', { montant, date: new Date().toISOString().slice(0, 10), mode }));
  }
  async generateInvoiceReminder(id: string) { return this.request<any>('/ia/facturation/relances/generer', this.json('POST', { facture_id: id }), { ia: true, timeout: 120000 }); }
  async syncInvoiceReminder(reviewId: string) { return this.request<any>('/ia/facturation/relances/synchroniser', this.json('POST', { review_id: reviewId }), { ia: true, timeout: 120000 }); }
  async evaluateTrainer(body: unknown) { return this.request<any>('/ia/rh/formateur/evaluer', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async syncTrainerEvaluation(reviewId: string, trainerId: string) { return this.request<any>('/ia/rh/synchroniser/evaluation', this.json('POST', { review_id: reviewId, formateur_id: trainerId }), { ia: true, timeout: 120000 }); }
  async analyzeTrainerCv(file: File, criteria: Record<string, unknown>) {
    const form = new FormData(); form.append('fichier', file); form.append('criteres_poste', JSON.stringify(criteria));
    return this.request<any>('/ia/rh/cv/analyser', { method: 'POST', body: form }, { ia: true, timeout: 120000 });
  }
  async generateTrainerContract(body: unknown) { return this.request<any>('/ia/rh/contrat-formateur', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async draftTrainerEmail(body: { type_email: string; destinataire: string; contexte?: Record<string, unknown> }) { return this.request<any>('/ia/rh/email/brouillon', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async updateTrainerEmailDraft(reviewId: string, body: { objet: string; corps: string }) { return this.request<any>(`/ia/rh/email/brouillon/${encodeURIComponent(reviewId)}`, this.json('PATCH', body), { ia: true }); }
  async sendTrainerEmail(reviewId: string, email: string) { return this.request<any>('/ia/rh/email/envoyer', this.json('POST', { review_id: reviewId, email_destinataire: email }), { ia: true, timeout: 30000 }); }
  async getApprovedTrainerContracts() { return this.getReviewHistory('approved', 'agent_m4_contrat'); }
  async downloadTrainerContract(reviewId: string) { return this.request<Blob>(`/ia/rh/contrat-formateur/download/${encodeURIComponent(reviewId)}`, {}, { ia: true, timeout: 30000 }); }
  async analyzeTrainerEvaluation(body: unknown) { return this.request<any>('/ia/rh/formateur/evaluer', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async sendVoiceCommand(body: { texte: string; ecran_actuel?: string; formations_disponibles?: string[]; contexte_action?: string[]; sessions_disponibles?: Array<{ id: string; titre: string; code: string; date_debut?: string; dates: string; formation_code?: string }> }) {
    return this.request<any>('/ia/vocal/commande', this.json('POST', body), { ia: true, timeout: 60000 });
  }
  async executeVoiceAction(action: string, session_info: Record<string, unknown>, payload: Record<string, unknown> = {}) {
    return this.request<any>('/ia/vocal/executer', this.json('POST', { action, confirmer: true, session_info, payload }), { ia: true, timeout: 120000 });
  }
  async getInvoiceReminders(id: string) { return this.request<any[]>(`/factures/${id}/relances`); }
  async saveInvoicePayment(id: string, payload: { montant: number; date: string; mode?: string }) { return mapInvoice(await this.request<any>(`/factures/${id}/paiements`, this.json('POST', payload))); }
  async createManualReminder(id: string) { return this.request(`/factures/${id}/relance`, this.json('POST', {})); }
  async exportAccounting(format: 'csv' | 'excel' | 'pdf') { return this.request<Blob>(`/exports/comptable?format=${format}`); }
  async downloadInvoicePdf(id: string) { return this.request<Blob>(`/factures/${encodeURIComponent(id)}/pdf`); }
  async getPresences(): Promise<PresenceRecord[]> { return []; }
  async getPresenceForSession(id: string) { return this.request<any[]>(`/sessions/seances/${id}/presences`); }
  async createSeance(sessionId: string, body: unknown) { return this.request(`/sessions/${sessionId}/seances`, this.json('POST', body)); }
  async createPresence(seanceId: string, participantId: string, statut: string, extras: { heure_arrivee?: string; motif_absence?: string } = {}) { return this.request(`/sessions/seances/${seanceId}/presences`, this.json('POST', { participant_id: participantId, statut, ...extras })); }
  async updatePresence(id: string, statut: string, extras: { heure_arrivee?: string; motif_absence?: string } = {}) { return this.request(`/sessions/seances/presences/${id}`, this.json('PATCH', { statut, ...extras })); }
  async getSeances(sessionId: string) { return this.request<any[]>(`/sessions/${sessionId}/seances`); }
  async createParticipant(data: { nom: string; prenom?: string; email?: string; entreprise?: string }) { return this.request<any>('/participants', this.json('POST', data)); }
  async getParticipants(sessionId?: string) { return this.request<any[]>(sessionId ? `/sessions/${sessionId}/participants` : '/participants?skip=0&limit=500'); }
  async enrollParticipant(sessionId: string, participantId: string) { return this.request(`/sessions/${sessionId}/inscrire`, this.json('POST', { participant_id: participantId })); }
  async removeParticipant(sessionId: string, participantId: string) { return this.request(`/sessions/${sessionId}/inscrire/${participantId}`, this.json('DELETE')); }
  async updateSession(id: string, payload: Record<string, unknown>) { return mapSession(await this.request<any>(`/sessions/${id}`, this.json('PATCH', payload))); }
  async deleteSession(id: string) { return this.request(`/sessions/${id}`, this.json('DELETE')); }
  async deleteOpportunity(id: string) { return this.request(`/opportunites/${encodeURIComponent(id)}`, this.json('DELETE')); }
  async createPublicRegistrationLink(kind: 'participant' | 'formateur' | 'post_formation', session_id?: string) { return this.request<{token:string;path:string;kind:string;assessment_question_count?:number}>('/public/links', this.json('POST', { kind, ...(session_id ? {session_id} : {}) })); }
  async getSessionPublicLinks(sessionId: string) { return this.request<{participant?:{token:string;path:string};formateur?:{token:string;path:string};post_formation?:{token:string;path:string}}>(`/public/links/session/${encodeURIComponent(sessionId)}`); }
  async revokePublicRegistrationLink(token: string) { return this.request<any>(`/public/links/${encodeURIComponent(token)}`, { method: 'DELETE' }); }
  async getPublicRegistration(token: string) { return this.request<any>(`/public/links/${encodeURIComponent(token)}`, {}, {auth:false}); }
  async submitPublicParticipant(token: string, data: {nom:string;prenom:string;email:string;organisation?:string;poste?:string;assessment_attempt_id?:string;answers?:Array<{question_id:string;answer:string}>}) { return this.request<any>(`/public/links/${encodeURIComponent(token)}/participant`, this.json('POST', data), {auth:false}); }
  async submitPostFormation(token: string, data: {email:string;assessment_attempt_id:string;answers:Array<{question_id:string;answer:string}>;satisfaction_answers:Array<{question_id:string;answer:string}>}) { return this.request<any>(`/public/links/${encodeURIComponent(token)}/post-formation`, this.json('POST', data), {auth:false}); }
  async getTrainerSatisfactionResponses() { return this.request<any[]>('/sessions/evaluations/satisfaction'); }
  async submitPublicTrainer(token: string, data: {nom:string;prenom:string;email:string;telephone?:string;specialite:string;fichier:File}) {
    const form = new FormData(); Object.entries(data).forEach(([key, value]) => form.append(key, value as string | Blob));
    return this.request<any>(`/public/links/${encodeURIComponent(token)}/formateur`, {method:'POST',body:form}, {auth:false});
  }
  async getCandidates() { return this.request<any[]>('/rh/candidats'); }
  async getRecentCandidatures(heures = 48) { return this.request<any>(`/ia/rh/candidatures/recentes?heures=${heures}`, {}, { ia: true }); }
  async updateCandidate(id: string, payload: Record<string, unknown>) { return this.request<any>(`/rh/candidats/${encodeURIComponent(id)}`, this.json('PATCH', payload)); }
  async preselectTrainerCv(body: { cv_texte: string; criteres_poste: Record<string, unknown> }) { return this.request<any>('/ia/rh/preselection', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async getCandidateCv(id:string) { return this.request<any>(`/rh/candidats/${encodeURIComponent(id)}/cv`); }
  async downloadCandidateCv(id:string) { return this.request<Blob>(`/rh/candidats/${encodeURIComponent(id)}/cv-fichier`); }
  async decideCandidate(id:string, decision:'ACCEPTER'|'REFUSER') { return this.request<any>(`/rh/candidats/${encodeURIComponent(id)}/decision?decision=${decision}`, this.json('POST', {})); }
  async createOpportunityFromReview(path: string, body: unknown) { return this.request(`/ia/${path}`, this.json('POST', body), { ia: true, timeout: 120000 }); }
  async getTdrBriefFromOpportunity(id: string) { return this.request<any>(`/ia/tdr/from-opportunite/${encodeURIComponent(id)}`, {}, { ia: true }); }
  async searchRagDocuments(requete: string) { return this.request<any>('/ia/rag/rechercher', this.json('POST', { requete, top_k: 5, collection: 'support' }), { ia: true, timeout: 60000 }); }
  async generateTdr(body: unknown) { return this.request<any>('/ia/tdr/generer', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async rectifyTdr(body: unknown) { return this.request<any>('/ia/tdr/rectifier', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async generateOfferTechnique(body: unknown) { return this.request<any>('/ia/offres/generer-technique', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async generateOfferFinanciere(body: unknown) { return this.request<any>('/ia/offres/generer-financiere', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async rectifyOfferTechnique(body: unknown) { return this.request<any>('/ia/offres/rectifier-technique', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async rectifyOfferFinanciere(body: unknown) { return this.request<any>('/ia/offres/rectifier-financiere', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async getOfferReviews() { return this.request<any>('/ia/offres/reviews', {}, { ia: true, timeout: 30000 }); }
  async getOfferReview(id: string) { return this.request<any>(`/ia/offres/reviews/${id}`, {}, { ia: true }); }
  async deleteOfferReview(id: string) { return this.request<any>(`/ia/offres/reviews/${id}`, { method: 'DELETE' }, { ia: true }); }
  async approveOfferReview(id: string, reviewer_note = 'OK') { return this.request(`/ia/offres/reviews/${id}/approve`, this.json('POST', { reviewer_note }), { ia: true }); }
  async rejectOfferReview(id: string, reason: string) { return this.request(`/ia/offres/reviews/${id}/reject`, this.json('POST', { reason }), { ia: true }); }
  async approveTdr(id: string, reviewer_note: string) { return this.request(`/ia/tdr/reviews/${id}/approve`, this.json('POST', { reviewer_note }), { ia: true }); }
  async rejectTdr(id: string, reviewer_note: string) { return this.request(`/ia/tdr/reviews/${id}/reject`, this.json('POST', { reviewer_note }), { ia: true }); }
  async syncTdr(id: string, opportunite_id?: string) { return this.request('/ia/tdr/synchroniser', this.json('POST', { review_id: id, opportunite_id }), { ia: true, timeout: 120000 }); }
  async syncOffer(id: string, opportunite_id?: string) { return this.request('/ia/offres/synchroniser', this.json('POST', { review_id: id, opportunite_id }), { ia: true, timeout: 120000 }); }
  async createOffer(body: unknown) { return this.request<any>('/offres', this.json('POST', body)); }
  async downloadTdr(filename: string) {
    if (!tokenStore.get()) throw new ApiError('Votre session frontend est affichée comme ouverte, mais son jeton est absent. Reconnectez-vous puis réessayez.', 401);
    return this.request<Blob>(`/ia/tdr/download/${encodeURIComponent(filename)}`, { credentials: 'include' }, { ia: true, jwtForIA: true });
  }
  async getPendingReviews() { return this.request<any>('/ia/formations/pending-reviews', {}, { ia: true, timeout: 30000 }); }
  async getReviewHistory(status: 'approved' | 'rejected', agentId?: string) { const params = new URLSearchParams({ status }); if (agentId) params.set('agent_id', agentId); return this.request<any>(`/ia/formations/reviews?${params}`, {}, { ia: true, timeout: 30000 }); }
  async generateFormationForms(body: unknown) { return this.request<any>('/ia/formations/generate-forms', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async getM6Eligibility(sessionId: string) { return this.request<any>(`/ia/formations/sessions/${encodeURIComponent(sessionId)}/attestations/eligibilite`, {}, { ia: true, timeout: 30000 }); }
  async generateSessionAttestations(sessionId: string) { return this.request<any>(`/ia/formations/sessions/${encodeURIComponent(sessionId)}/attestations/generer`, this.json('POST', {}), { ia: true, timeout: 120000 }); }
  async generateFormationReport(sessionData: unknown) { return this.request<any>('/ia/formations/generate-report', this.json('POST', { session_data: sessionData }), { ia: true, timeout: 120000 }); }
  async previewAttestation(reviewId: string, numero: string) { return this.request<Blob>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations/${encodeURIComponent(numero)}/preview`, {}, { ia: true }); }
  async downloadAttestation(reviewId: string, numero: string) { return this.request<Blob>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations/${encodeURIComponent(numero)}/download`, {}, { ia: true }); }
  async downloadAttestationsZip(reviewId: string) { return this.request<Blob>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations.zip`, {}, { ia: true }); }
  async approveAttestationInBatch(reviewId: string, numero: string, reviewer_note?: string) { return this.request<any>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations/${encodeURIComponent(numero)}/approve`, this.json('POST', { reviewer_note }), { ia: true }); }
  async editPendingAttestation(reviewId: string, numero: string, content: unknown, expected_updated_at: string) { return this.request<any>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations/${encodeURIComponent(numero)}`, this.json('PUT', { content, expected_updated_at }), { ia: true, timeout: 30000 }); }
  async deletePendingAttestation(reviewId: string, numero: string, expected_updated_at: string) { return this.request<any>(`/ia/formations/reviews/${encodeURIComponent(reviewId)}/attestations/${encodeURIComponent(numero)}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_updated_at }) }, { ia: true, timeout: 30000 }); }
  async analyzeFormationLevels(body: unknown) { return this.request<any>('/ia/formations/analyze-levels', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async analyzeFormationSatisfaction(body: unknown) { return this.request<any>('/ia/formations/analyze-satisfaction', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async analyserNiveauxDb(sessionId: string) { return this.request<any>(`/ia/formations/${sessionId}/analyser-niveaux-db`, this.json('POST', {}), { ia: true, timeout: 120000 }); }
  async analyserSatisfactionDb(sessionId: string) { return this.request<any>(`/ia/formations/${sessionId}/analyser-satisfaction-db`, this.json('POST', {}), { ia: true, timeout: 120000 }); }
  async publishFormationForms(reviewId: string, session_titre: string) { return this.request<any>(`/ia/formations/reviews/${reviewId}/publish-forms`, this.json('POST', { session_titre }), { ia: true, timeout: 120000 }); }
  private isM3ReviewId(id: string) { return /(?:^|-)AM3(?:-|$)/i.test(id); }
  async getReview(id: string) {
    const path = this.isM3ReviewId(id) ? `/ia/offres/reviews/${id}` : `/ia/formations/reviews/${id}`;
    return this.request<any>(path, {}, { ia: true });
  }
  async updateReviewDocument(id: string, content: Record<string, unknown>, expectedUpdatedAt: string) {
    return this.request<any>(`/ia/formations/reviews/${encodeURIComponent(id)}/document`, this.json('PATCH', { content, expected_updated_at: expectedUpdatedAt }), { ia: true, timeout: 120000 });
  }
  async approveReview(id: string, reviewer_note?: string) {
    if (this.isM3ReviewId(id)) return this.approveOfferReview(id, reviewer_note || 'OK');
    return this.request(`/ia/formations/reviews/${id}/approve`, this.json('POST', { reviewer_note }), { ia: true });
  }
  async rejectReview(id: string, reason: string) {
    if (this.isM3ReviewId(id)) return this.rejectOfferReview(id, reason);
    return this.request(`/ia/formations/reviews/${id}/reject`, this.json('POST', { reason }), { ia: true });
  }
  async getRagReviews() { return this.request<any>('/ia/rag/reviews', {}, { ia: true, timeout: 30000 }); }
  async getRagReview(id: string) { return this.request<any>(`/ia/rag/reviews/${id}`, {}, { ia: true }); }
  async deleteReview(id: string) { return this.request<any>(`/ia/formations/reviews/${id}`, { method: 'DELETE' }, { ia: true }); }
  async deleteHistoryReview(id: string) { return this.request<any>(`/ia/formations/history/${id}`, { method: 'DELETE' }, { ia: true }); }
  async deleteRagReview(id: string) { return this.request<any>(`/ia/rag/reviews/${id}`, { method: 'DELETE' }, { ia: true }); }
  async approveRagReview(id: string, reviewer_note: string) { return this.request(`/ia/rag/reviews/${id}/approve`, this.json('POST', { reviewer_note }), { ia: true }); }
  async rejectRagReview(id: string, reviewer_note: string) { return this.request(`/ia/rag/reviews/${id}/reject`, this.json('POST', { reviewer_note }), { ia: true }); }
  async uploadSupport(file: File, formation_code: string, session_id: string, collection?: string, module?: string) {
    const form = new FormData(); form.append('fichier', file); form.append('formation_code', formation_code);
    form.append('session_id', session_id);
    if (collection) form.append('collection', collection); if (module) form.append('module', module);
    return this.request('/documents/upload', { method: 'POST', body: form });
  }
  async getSupports(params: Record<string, string> = {}) { return this.request<any>(`/documents/rag/supports${queryString(params)}`); }
  async deleteSupport(docHash: string) { return this.request<any>(`/documents/rag/supports/${encodeURIComponent(docHash)}`, { method: 'DELETE' }); }
  async getRagSessions() { return this.request<any>('/ia/rag/sessions', {}, { ia: true }); }
  async getRagIndexStatus(hash: string) { return this.request<any>(`/ia/rag/statut/${encodeURIComponent(hash)}`, {}, { ia: true }); }
  async indexSupport(chemin_fichier: string, formation_code: string, session_id: string, module?: string) { return this.request('/ia/rag/indexer-document', this.json('POST', { chemin_fichier, formation_code, session_id, module }), { ia: true }); }
  async archiveSupport(docHash: string) { return this.request<any>(`/ia/rag/documents/${docHash}/archiver`, this.json('PATCH', {}), { ia: true }); }
  async restoreSupport(docHash: string) { return this.request<any>(`/ia/rag/documents/${docHash}/restaurer`, this.json('PATCH', {}), { ia: true }); }
  async chatRag(body: { message: string; conversation_id?: string | null; formation_code?: string | null; session_id?: string | null; module?: string | null }) { return this.request<any>('/ia/rag/chat', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async chatRagStream(
    body: { message: string; conversation_id?: string | null; formation_code?: string | null; session_id?: string | null; module?: string | null },
    onEvent: (event: any) => void,
  ) {
    const headers = new Headers({ Accept: 'text/event-stream', 'Content-Type': 'application/json' });
    const userToken = tokenStore.get();
    const token = userToken || IA_TOKEN;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(`${API_REQUEST_BASE}${API_PREFIX}/ia/rag/chat/stream`, {
      method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const detail = (payload as any)?.detail ?? (payload as any)?.message;
      throw new ApiError(typeof detail === 'string' ? detail : `Erreur API ${response.status}`, response.status, detail);
    }
    if (!response.body) throw new ApiError('Le serveur n’a pas ouvert le flux de réponse.', 500);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const dispatchFrames = (final = false) => {
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = final ? '' : frames.pop() ?? '';
      for (const frame of frames) {
        const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
        if (!data) continue;
        try { onEvent(JSON.parse(data)); } catch { /* ignore malformed server event */ }
      }
    };
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      dispatchFrames();
    }
    buffer += decoder.decode();
    dispatchFrames(true);
  }
  async getRagHealth() { return this.request<any>('/ia/rag/health', {}, { ia: true }); }
  async getRagFormations() { return this.request<any>('/ia/rag/formations', {}, { ia: true }); }
  async getRagConversations() { return this.request<any>('/ia/rag/conversations', {}, { ia: true }); }
  async getRagConversation(id: string) { return this.request<any>(`/ia/rag/conversations/${id}`, {}, { ia: true }); }
  async deleteRagConversation(id: string) { return this.request<any>(`/ia/rag/conversations/${id}`, { method: 'DELETE' }, { ia: true }); }
  async renameRagConversation(id: string, titre: string) { return this.request<any>(`/ia/rag/conversations/${id}/rename`, { method: 'PATCH', body: JSON.stringify({ titre }) }, { ia: true }); }
  async feedbackRagMessage(conversationId: string, indexEchange: number, feedback: 'positif' | 'negatif') { return this.request<any>(`/ia/rag/conversations/${conversationId}/feedback`, { method: 'POST', body: JSON.stringify({ index_echange: indexEchange, feedback }) }, { ia: true }); }
  async getProjects() { return this.request<any[]>('/projets?skip=0&limit=100'); }
  async createProject(body: unknown) { return this.request<any>('/projets', this.json('POST', body)); }
  async getRooms() { return this.request<any[]>('/salles?skip=0&limit=100'); }
  async createRoom(body: unknown) { return this.request<any>('/salles', this.json('POST', body)); }
  async createCandidate(body: unknown) { return this.request<any>('/rh/candidats', this.json('POST', body)); }
  async generateSyllabus(body: unknown) { return this.request<any>('/ia/rag/syllabus', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async generatePortfolio(body: unknown) { return this.request<any>('/ia/rag/portfolio', this.json('POST', body), { ia: true, timeout: 120000 }); }
  async getBlob(path: string, params: Record<string, string> = {}) { return this.request<Blob>(`${path}${queryString(params)}`); }
}
const normalizeDomain = (value?: string): string => {
  const text = (value ?? '').toUpperCase();
  if (text.includes('DATA')) return 'DATA'; if (text.includes('DEVOPS')) return 'DEVOPS';
  if (text.includes('DEVELOP')) return 'DEVELOPPEMENT'; if (text.includes('BUREAUT')) return 'BUREAUTIQUE';
  if (text.includes('IA')) return 'IA'; return 'AUTRE';
};
const queryString = (params: Record<string, string>) => { const q = new URLSearchParams(params); const value = q.toString(); return value ? `?${value}` : ''; };
export const apiService = new ApiService();
