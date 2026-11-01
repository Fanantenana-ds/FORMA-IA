import {
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente
} from '../types';
import type { BackendOpportunite } from './veilleMapping';

/* -------------------------------------------------------------------------- */
/* Formes renvoyées par le backend                                             */
/* -------------------------------------------------------------------------- */

/** GET /api/v1/dashboard/statistiques (Direction uniquement). */
export interface BackendStats {
  session_realisees: number;
  participant: number;
  taux_presence: number;
  opportunite_total: number;
  opportunite_par_domaine: Record<string, number>;
  opportunite_par_statut: Record<string, number>;
  tdr_generes: number;
  offres_generees: number;
  attestations_generees: number;
  chiffre_affaires_facture: number;
  chiffre_affaires_encaisse: number;
  factures_en_retard: number;
  montant_impaye: number;
  relances_envoyees: number;
}

export interface BackendSession {
  id: string;
  titre: string;
  client: string | null;
  date_debut: string;
  date_fin: string | null;
  date_creation: string;
}

export interface BackendFacture {
  id: string;
  numero: string;
  client: string;
  montant: number;
  montant_ttc: number;
  statut: 'EMISE' | 'PARTIELLEMENT_PAYEE' | 'PAYEE' | 'EN_RETARD' | 'ANNULEE';
  date_emission: string;
  paiements?: { montant: number }[];
}

export interface BackendDocument {
  id: string;
  type: 'TDR' | 'OFFRE' | 'ATTESTATION';
  client: string | null;
  numero_unique: string | null;
  statut_validation: string;
  date_generation: string;
}

export interface DashboardInput {
  stats: BackendStats | null;
  opportunites: BackendOpportunite[] | null;
  sessions: BackendSession[] | null;
  factures: BackendFacture[] | null;
  documents: BackendDocument[] | null;
}

export interface DashboardData {
  kpis: KPIStats;
  domainOpportunities: DomainOpportunity[];
  facturationStatuts: FacturationStatut[];
  activites: ActiviteRecente[];
  /** Vrai si une partie des données n'a pas pu être chargée. */
  partial: boolean;
}

/* -------------------------------------------------------------------------- */
/* Constantes d'affichage                                                      */
/* -------------------------------------------------------------------------- */

const DOMAIN_META: Record<string, { label: string; color: string }> = {
  IA: { label: 'IA', color: '#1B8F6E' },
  DATA: { label: 'Data', color: '#3B82F6' },
  DEVOPS: { label: 'DevOps', color: '#8B5CF6' },
  DEVELOPPEMENT: { label: 'Développement', color: '#F59E0B' },
  BUREAUTIQUE: { label: 'Bureautique', color: '#EC4899' },
  AUTRE: { label: 'Autre', color: '#64748B' }
};
const UNCLASSIFIED = { label: 'Non classé', color: '#94A3B8' };

const OPPORTUNITE_STATUT_LABELS: Record<string, string> = {
  EN_ATTENTE: 'En attente',
  ANALYSEE: 'Analysée',
  ARCHIVEE: 'Archivée'
};

const FACTURE_STATUT_LABELS: Record<string, string> = {
  EMISE: 'Émise',
  PARTIELLEMENT_PAYEE: 'Partiellement payée',
  PAYEE: 'Payée',
  EN_RETARD: 'En retard',
  ANNULEE: 'Annulée'
};

const DOCUMENT_LABELS: Record<string, string> = {
  TDR: 'TDR généré',
  OFFRE: 'Offre générée',
  ATTESTATION: 'Attestation émise'
};

const BILLING_GROUPS: Array<{
  statut: FacturationStatut['statut'];
  couleur: string;
  backend: BackendFacture['statut'][];
}> = [
  { statut: 'Payé', couleur: '#1B8F6E', backend: ['PAYEE'] },
  { statut: 'En attente', couleur: '#F59E0B', backend: ['EMISE', 'PARTIELLEMENT_PAYEE'] },
  { statut: 'En retard', couleur: '#EF4444', backend: ['EN_RETARD'] }
];

/* -------------------------------------------------------------------------- */
/* Utilitaires                                                                 */
/* -------------------------------------------------------------------------- */

const round = (value: number): number => Math.round(value);

const toTime = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const time = new Date(iso).getTime();
  return Number.isNaN(time) ? null : time;
};

/** « À l'instant », « Il y a 3 h », « Hier », puis la date. */
export const formatRelative = (time: number, now: number = Date.now()): string => {
  const diffMin = Math.floor((now - time) / 60000);
  if (diffMin < 1) return "À l'instant";
  if (diffMin < 60) return `Il y a ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `Il y a ${diffH} h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return 'Hier';
  if (diffD < 7) return `Il y a ${diffD} j`;
  return new Date(time).toLocaleDateString('fr-FR');
};

const formatDay = (iso: string | null | undefined): string => {
  const time = toTime(iso);
  return time === null ? '' : new Date(time).toLocaleDateString('fr-FR');
};

const sessionStatus = (s: BackendSession, now: number): string => {
  const start = toTime(s.date_debut);
  const end = toTime(s.date_fin) ?? start;
  if (start === null || end === null) return 'Planifiée';
  const endOfDay = end + 24 * 3600 * 1000;
  if (now >= endOfDay) return 'Terminée';
  if (now >= start) return 'En cours';
  return 'Planifiée';
};

const paid = (f: BackendFacture): number =>
  (f.paiements ?? []).reduce((acc, p) => acc + p.montant, 0);

/* -------------------------------------------------------------------------- */
/* Construction du tableau de bord                                             */
/* -------------------------------------------------------------------------- */

export const buildDashboard = (input: DashboardInput, partial: boolean): DashboardData => {
  const { stats, opportunites, sessions, factures, documents } = input;
  const now = Date.now();

  /* ---- Indicateurs ---- */
  const countDocs = (type: BackendDocument['type']): number | undefined =>
    documents ? documents.filter((d) => d.type === type).length : undefined;

  let kpis: KPIStats;
  if (stats) {
    kpis = {
      sessionsRealisees: stats.session_realisees,
      participantsFormes: stats.participant,
      tauxPresenceMoyen: Math.round(stats.taux_presence * 10) / 10,
      opportunitesDetectees: stats.opportunite_total,
      tdrGeneres: stats.tdr_generes,
      offresGenerees: stats.offres_generees,
      attestationsGenerees: stats.attestations_generees,
      chiffreAffairesFacture: round(stats.chiffre_affaires_facture),
      chiffreAffairesEncaisse: round(stats.chiffre_affaires_encaisse),
      facturesEnRetard: stats.factures_en_retard,
      montantImpaye: round(stats.montant_impaye),
      relancesEnvoyees: stats.relances_envoyees
    };
  } else {
    // Repli : calcul à partir des listes accessibles à tous les rôles.
    // Mêmes définitions que le backend (voir DashboardService).
    kpis = {
      sessionsRealisees: sessions?.length ?? 0,
      participantsFormes: 0,
      tauxPresenceMoyen: 0,
      presenceIndisponible: true,
      opportunitesDetectees: opportunites?.length ?? 0,
      tdrGeneres: countDocs('TDR'),
      offresGenerees: countDocs('OFFRE'),
      attestationsGenerees: countDocs('ATTESTATION'),
      chiffreAffairesFacture: factures
        ? round(factures.reduce((acc, f) => acc + f.montant, 0))
        : undefined,
      chiffreAffairesEncaisse: factures
        ? round(factures.reduce((acc, f) => acc + paid(f), 0))
        : undefined,
      facturesEnRetard: factures ? factures.filter((f) => f.statut === 'EN_RETARD').length : undefined,
      montantImpaye: factures
        ? round(
            factures
              .filter((f) => f.statut !== 'PAYEE')
              .reduce((acc, f) => acc + Math.max(f.montant_ttc - paid(f), 0), 0)
          )
        : undefined
    };
  }

  /* ---- Opportunités par domaine ---- */
  const byDomain = new Map<string, { nombre: number; valeur: number }>();
  (opportunites ?? []).forEach((o) => {
    const key = o.domaine ?? '';
    const entry = byDomain.get(key) ?? { nombre: 0, valeur: 0 };
    entry.nombre += 1;
    entry.valeur += o.budget ?? 0;
    byDomain.set(key, entry);
  });
  const domainOpportunities: DomainOpportunity[] = Array.from(byDomain.entries())
    .map(([key, v]) => {
      const meta = DOMAIN_META[key] ?? UNCLASSIFIED;
      return {
        domaine: meta.label,
        nombre: v.nombre,
        valeurEstimee: round(v.valeur),
        couleur: meta.color
      };
    })
    .sort((a, b) => b.nombre - a.nombre);

  /* ---- Facturation par statut (factures annulées exclues) ---- */
  const billing = BILLING_GROUPS.map((group) => {
    const items = (factures ?? []).filter((f) => group.backend.includes(f.statut));
    return {
      statut: group.statut,
      couleur: group.couleur,
      nombreFactures: items.length,
      montant: round(items.reduce((acc, f) => acc + f.montant, 0))
    };
  }).filter((g) => g.nombreFactures > 0);
  const billingTotal = billing.reduce((acc, g) => acc + g.montant, 0);
  const facturationStatuts: FacturationStatut[] = billing.map((g) => ({
    ...g,
    pourcentage: billingTotal > 0 ? round((g.montant / billingTotal) * 100) : 0
  }));

  /* ---- Activité récente : dernières créations toutes catégories confondues ---- */
  const events: Array<{ time: number; item: Omit<ActiviteRecente, 'horodateur'> }> = [];

  (opportunites ?? []).forEach((o) => {
    const time = toTime(o.date_creation);
    if (time === null) return;
    const domain = o.domaine ? (DOMAIN_META[o.domaine]?.label ?? o.domaine) : 'Domaine non classé';
    events.push({
      time,
      item: {
        id: `opp-${o.id}`,
        titre: `Opportunité : ${o.objet?.trim() || o.contenu.slice(0, 70)}`,
        description: `${domain}${o.budget ? ` — budget ${o.budget.toLocaleString()} Ar` : ''}`,
        type: 'opportunite',
        statutTag: OPPORTUNITE_STATUT_LABELS[o.statut] ?? o.statut
      }
    });
  });

  (sessions ?? []).forEach((s) => {
    const time = toTime(s.date_creation);
    if (time === null) return;
    const period = [formatDay(s.date_debut), formatDay(s.date_fin)].filter(Boolean).join(' → ');
    events.push({
      time,
      item: {
        id: `ses-${s.id}`,
        titre: `Session créée : ${s.titre}`,
        description: [s.client, period].filter(Boolean).join(' — '),
        type: 'session',
        statutTag: sessionStatus(s, now)
      }
    });
  });

  (factures ?? []).forEach((f) => {
    const time = toTime(f.date_emission);
    if (time === null) return;
    events.push({
      time,
      item: {
        id: `fac-${f.id}`,
        titre: `Facture ${f.numero} émise`,
        description: `${f.client} — ${round(f.montant_ttc).toLocaleString()} Ar TTC`,
        type: 'facture',
        statutTag: FACTURE_STATUT_LABELS[f.statut] ?? f.statut
      }
    });
  });

  (documents ?? []).forEach((d) => {
    const time = toTime(d.date_generation);
    if (time === null) return;
    events.push({
      time,
      item: {
        id: `doc-${d.id}`,
        titre: DOCUMENT_LABELS[d.type] ?? 'Document généré',
        description: [d.client, d.numero_unique].filter(Boolean).join(' — '),
        type: 'document',
        statutTag: d.statut_validation === 'VALIDE' ? 'Validé' : d.statut_validation === 'REJETE' ? 'Rejeté' : 'En attente de validation'
      }
    });
  });

  const activites: ActiviteRecente[] = events
    .sort((a, b) => b.time - a.time)
    .slice(0, 10)
    .map((e) => ({ ...e.item, horodateur: formatRelative(e.time, now) }));

  return { kpis, domainOpportunities, facturationStatuts, activites, partial };
};
