import React, { useMemo } from 'react';
import {
  ArrowUpRight,
  RefreshCw,
  AlertCircle,
  FileText,
  Plus,
  WalletCards,
  BadgeCheck,
  CalendarCheck,
  BrainCircuit,
  Workflow,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Zap,
  Users,
  Calendar,
  Percent,
  CheckCircle2,
  Clock,
  ChevronRight,
  BarChart2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  RadialBarChart,
  RadialBar,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import {
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente,
  UserRole,
  MenuSection,
  canAccessSection,
  AuthUser,
} from '../../types';

interface DashboardViewProps {
  kpis: KPIStats;
  domainOpportunities: DomainOpportunity[];
  facturationStatuts: FacturationStatut[];
  activites: ActiviteRecente[];
  currentRole: UserRole;
  isLoading?: boolean;
  notice?: string | null;
  pendingReviewCount?: number;
  onRefresh: () => void;
  onNavigateTo: (section: MenuSection) => void;
  onOpenNewOpportunity: () => void;
  onOpenNewSession: () => void;
  authUser?: AuthUser | null;
}

const NAVY   = '#0A1628';
const GOLD   = '#C9A440';
const GOLD_L = '#F0D87C';

const formatAr = (v: number) =>
  v >= 1_000_000
    ? `${(v / 1_000_000).toFixed(1)}M Ar`
    : v >= 1_000
    ? `${(v / 1_000).toFixed(0)}k Ar`
    : `${v.toLocaleString('fr-FR')} Ar`;

const GREETINGS = ['Bonne journée', 'Bienvenue', 'Bon retour'];
function greeting(nom: string) {
  const h = new Date().getHours();
  let prefix: string;
  if (h >= 0 && h < 5)       prefix = 'Bonne nuit';
  else if (h < 12)            prefix = 'Bonjour';
  else if (h < 18)            prefix = 'Bon après-midi';
  else                        prefix = 'Bonsoir';
  const first = (nom || '').split(' ')[0] || nom;
  return `${prefix}, ${first}`;
}

function motivationLine(kpis: KPIStats): string {
  const retard = kpis.facturesEnRetard ?? 0;
  const taux   = kpis.tauxPresenceMoyen ?? 0;
  const opp    = kpis.opportunitesDetectees ?? 0;
  if (retard > 0) return `⚠ ${retard} facture${retard > 1 ? 's' : ''} en retard pensez à relancer vos clients.`;
  if (taux >= 90) return `✓ Excellent taux de présence (${taux}%)  votre formation attire et fidélise.`;
  if (taux > 0 && taux < 85) return ` Taux de présence à ${taux}% l'objectif est 85%, encore un effort !`;
  if (opp >= 10) return `${opp} opportunités en cours le pipeline commercial est actif.`;
  return '✓ Tous les indicateurs sont sous contrôle.';
}

// Mock sparkline data (12 pts)
const sparkBase = [4.2, 5.1, 4.8, 6.3, 5.9, 7.2, 6.8, 8.1, 7.5, 9.0, 8.4, 10.1];

// Pipeline M1→M7 mock (sera remplacé par données réelles)
const PIPELINE_LABELS: Record<string, string> = {
  M1: 'Veille & détection',
  M2: 'TDR & Offre',
  M3: 'Contractualisation',
  M4: 'Logistique',
  M5: 'Attestations',
  M6: 'Évaluation',
  M7: 'Clôture',
};

const CustomSparkTooltip = ({ active, payload }: any) =>
  active && payload?.length ? (
    <div className="rounded-lg bg-white/90 border border-slate-200 px-2 py-1 text-[10px] font-bold text-slate-700 shadow-lg">
      {formatAr(payload[0].value * 1_000_000)}
    </div>
  ) : null;

const CustomBarTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const descs: Record<string, string> = {
    M1: 'Veille & appels d\'offres repérés',
    M2: 'TDR rédigé, offre déposée',
    M3: 'Formation confirmée et planifiée',
    M4: 'Formateur, salle, convocations',
    M5: 'Présences, évaluation & attestations',
    M6: 'Satisfaction des participants',
    M7: 'Dossier archivé, facture émise',
  };
  return (
    <div className="rounded-xl bg-white border border-slate-200 px-3 py-2.5 text-xs shadow-xl max-w-[180px]">
      <div className="font-extrabold text-slate-800 mb-0.5">{label}</div>
      <div className="text-slate-500 text-[10px] leading-tight mb-1">{descs[label] ?? ''}</div>
      <div className="font-bold text-brand-navy">{payload[0].value} dossier{payload[0].value > 1 ? 's' : ''} actif{payload[0].value > 1 ? 's' : ''}</div>
    </div>
  );
};

const CustomPieTooltip = ({ active, payload }: any) =>
  active && payload?.length ? (
    <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 text-xs font-bold text-slate-800 shadow-xl">
      {payload[0].name} : {formatAr(payload[0].value)}
    </div>
  ) : null;

const CustomAreaTooltip = ({ active, payload, label }: any) =>
  active && payload?.length ? (
    <div className="rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-xs shadow-xl space-y-1">
      <div className="font-extrabold text-white mb-1">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color }} className="font-bold">
          {p.name === 'facture' ? 'Facturé' : 'Encaissé'} : {formatAr(p.value * 100_000)}
        </div>
      ))}
    </div>
  ) : null;

export const DashboardView: React.FC<DashboardViewProps> = ({
  kpis,
  domainOpportunities,
  facturationStatuts,
  activites,
  currentRole,
  isLoading = false,
  notice,
  pendingReviewCount = 0,
  onRefresh,
  onNavigateTo,
  onOpenNewOpportunity,
  onOpenNewSession,
  authUser,
}) => {
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const presenceGauge = useMemo(() => [
    { name: 'Présence', value: Math.min(kpis.tauxPresenceMoyen, 100), fill: kpis.tauxPresenceMoyen >= 85 ? '#10B981' : '#F59E0B' },
    { name: 'Reste', value: Math.max(0, 100 - kpis.tauxPresenceMoyen), fill: '#E2E8F0' },
  ], [kpis.tauxPresenceMoyen]);

  // Pipeline data (mock counts par étape — idéalement from API)
  const pipelineData = useMemo(() => {
    const sess = kpis.sessionsRealisees ?? 0;
    return [
      { etape: 'M1', label: 'Détection marché', desc: 'Veille & appels d\'offres repérés', count: Math.max(1, Math.round(sess * 0.9)), fill: '#0A1628' },
      { etape: 'M2', label: 'Dossier de candidature', desc: 'TDR rédigé, offre déposée', count: Math.max(1, Math.round(sess * 0.7)), fill: '#0C2050' },
      { etape: 'M3', label: 'Contrat signé', desc: 'Formation confirmée et planifiée', count: Math.max(0, Math.round(sess * 0.5)), fill: GOLD },
      { etape: 'M4', label: 'Logistique', desc: 'Formateur, salle, convocations', count: Math.max(0, Math.round(sess * 0.4)), fill: '#0C2050' },
      { etape: 'M5', label: 'Formation réalisée', desc: 'Présences, évaluation & attestations', count: Math.max(0, Math.round(sess * 0.25)), fill: '#0A1628' },
      { etape: 'M6', label: 'Évaluation qualité', desc: 'Satisfaction des participants', count: Math.max(0, Math.round(sess * 0.1)), fill: '#0A1628' },
      { etape: 'M7', label: 'Clôture & facturation', desc: 'Dossier archivé, facture émise', count: Math.max(0, Math.round(sess * 0.05)), fill: '#10B981' },
    ];
  }, [kpis.sessionsRealisees]);

  // Sparkline data for each KPI card
  const sparkCA   = sparkBase.map((v, i) => ({ i, v: v * ((kpis.chiffreAffairesFacture ?? 1_000_000) / 10_100_000) }));
  const sparkPart = sparkBase.map((v, i) => ({ i, v: Math.round(v * (kpis.participantsFormes ?? 30) / 10.1) }));
  const sparkOpp  = sparkBase.map((v, i) => ({ i, v: Math.round(v * (kpis.opportunitesDetectees ?? 47) / 10.1) }));
  const sparkSess = sparkBase.map((v, i) => ({ i, v: Math.round(v * (kpis.sessionsRealisees ?? 18) / 10.1) }));

  // Area chart CA mensuel (mock 12 mois)
  const months = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Juil', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'];
  const areaData = months.map((m, i) => ({
    mois: m,
    facture: Math.round((0.4 + Math.random() * 0.6) * sparkBase[i] * 10),
    encaisse: Math.round((0.3 + Math.random() * 0.5) * sparkBase[i] * 8),
  }));

  // Donut facturation
  const donutData = facturationStatuts.length > 0 ? facturationStatuts.map(f => ({
    name: f.statut,
    value: f.montant,
    fill: f.couleur,
  })) : [
    { name: 'Encaissé', value: kpis.chiffreAffairesEncaisse ?? 0, fill: '#10B981' },
    { name: 'Impayé', value: kpis.montantImpaye ?? 0, fill: '#F59E0B' },
    { name: 'En retard', value: (kpis.facturesEnRetard ?? 0) * 500_000, fill: '#EF4444' },
  ].filter(d => d.value > 0);

  const totalFacture = kpis.chiffreAffairesFacture ?? 0;
  const totalEncaisse = kpis.chiffreAffairesEncaisse ?? 0;
  const totalImpaye = kpis.montantImpaye ?? 0;

  const documentOverviewSection: MenuSection = canAccessSection(currentRole, 'dossiers_formation') ? 'dossiers_formation' : 'espace_ia';

  // Urgency actions
  const urgentActions = [
    pendingReviewCount > 0 && {
      icon: BrainCircuit, label: `${pendingReviewCount} validation${pendingReviewCount > 1 ? 's' : ''} IA`, color: 'red',
      action: () => onNavigateTo('espace_ia'),
    },
    (kpis.facturesEnRetard ?? 0) > 0 && {
      icon: WalletCards, label: `${kpis.facturesEnRetard} facture${(kpis.facturesEnRetard ?? 0) > 1 ? 's' : ''} en retard`, color: 'amber',
      action: () => onNavigateTo('facturation_devis'),
    },
    (kpis.attestationsGenerees ?? 0) === 0 && kpis.sessionsRealisees > 0 && {
      icon: CalendarCheck, label: 'Attestations à générer', color: 'blue',
      action: () => onNavigateTo('sessions_groupes'),
    },
  ].filter(Boolean) as Array<{ icon: any; label: string; color: string; action: () => void }>;

  const colorMap: Record<string, string> = {
    red: 'bg-red-50 border-red-200 text-red-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
  };
  const iconColorMap: Record<string, string> = {
    red: 'bg-red-100 text-red-600',
    amber: 'bg-amber-100 text-amber-600',
    blue: 'bg-blue-100 text-blue-600',
  };

  const userName = authUser?.nom ?? 'vous';
  const greet = greeting(userName);
  const motiv = motivationLine(kpis);

  return (
    <div className="space-y-6 pb-14 animate-in fade-in duration-300">

      {/* ── HERO HEADER ───────────────────────────────────────────────── */}
      <div
        className="relative overflow-hidden rounded-2xl px-6 py-5 shadow-lg"
        style={{ background: `linear-gradient(135deg, ${NAVY} 0%, #0C2050 60%, #142566 100%)` }}
      >
        {/* Orb déco */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full opacity-10"
          style={{ background: `radial-gradient(circle, ${GOLD} 0%, transparent 70%)` }} />
        <div className="pointer-events-none absolute right-32 bottom-0 h-32 w-32 rounded-full opacity-5"
          style={{ background: `radial-gradient(circle, ${GOLD_L} 0%, transparent 70%)` }} />

        <div className="relative flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest mb-1" style={{ color: GOLD }}>
              {currentRole === 'Dir.' ? 'Direction Générale' : currentRole === 'Form.' ? 'Vue Pédagogique' : currentRole === 'Assis.' ? 'Vue Assistant' : 'Vue Comptabilité'}
            </p>
            <h1 className="text-2xl font-extrabold text-white leading-tight">{greet}</h1>
            <p className="mt-1.5 text-sm text-white/65">{motiv}</p>
          </div>
          <button onClick={handleRefresh} disabled={isRefreshing}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-white hover:bg-white/20 transition">
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Alertes inline */}
        {urgentActions.length > 0 && (
          <div className="relative mt-4 flex flex-wrap gap-2">
            {urgentActions.map((a, i) => {
              const Icon = a.icon;
              const dot = a.color === 'red' ? '#EF4444' : a.color === 'amber' ? '#F59E0B' : '#3B82F6';
              return (
                <button key={i} onClick={a.action}
                  className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-bold text-white hover:bg-white/20 transition">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: dot }} />
                  <Icon size={12} />
                  {a.label}
                  <ArrowUpRight size={11} className="opacity-60" />
                </button>
              );
            })}
            {urgentActions.length === 0 && (
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1.5 text-xs font-bold text-emerald-300">
                <CheckCircle2 size={12} /> Aucune action urgente
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── NOTICES ───────────────────────────────────────────────────── */}
      {isLoading && (
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold flex items-center gap-2">
          <RefreshCw size={14} className="animate-spin shrink-0" /> Chargement des indicateurs…
        </div>
      )}
      {notice && !isLoading && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-start gap-2">
          <AlertCircle size={14} className="shrink-0 mt-0.5" /><span>{notice}</span>
        </div>
      )}

      {/* ── KPI ROW avec sparklines ────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">

        {/* KPI 1 — CA Facturé */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group" onClick={() => onNavigateTo('facturation_devis')}>
          <div className="p-5 pb-2">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-semibold text-slate-500">Chiffre d'affaires</span>
              <div className="h-8 w-8 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform" style={{ background: `${NAVY}12`, color: NAVY }}>
                <TrendingUp size={15} />
              </div>
            </div>
            <div className="text-3xl font-black tracking-tight" style={{ color: NAVY }}>
              {totalFacture > 0 ? formatAr(totalFacture) : <span className="text-slate-300 text-xl font-semibold">Aucune facture</span>}
            </div>
            <div className="mt-2 flex items-center gap-2">
              {totalEncaisse > 0
                ? <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">✓ {formatAr(totalEncaisse)} encaissé</span>
                : <span className="text-xs text-slate-400">Total facturé HT</span>
              }
            </div>
          </div>
          <div className="h-14">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkCA} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gCA" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={NAVY} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={NAVY} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke={NAVY} strokeWidth={2} fill="url(#gCA)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* KPI 2 — Participants */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group" onClick={() => onNavigateTo('sessions_groupes')}>
          <div className="p-5 pb-2">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-semibold text-slate-500">Participants formés</span>
              <div className="h-8 w-8 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform" style={{ background: `${GOLD}18`, color: '#7A5C10' }}>
                <Users size={15} />
              </div>
            </div>
            <div className="text-3xl font-black tracking-tight" style={{ color: NAVY }}>
              {kpis.presenceIndisponible ? <span className="text-slate-300 text-xl font-semibold">Réservé</span> : kpis.participantsFormes}
            </div>
            <div className="mt-2">
              <span className="text-xs text-slate-400">
                {kpis.sessionsRealisees} session{kpis.sessionsRealisees !== 1 ? 's' : ''} réalisée{kpis.sessionsRealisees !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <div className="h-14">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkPart} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gPart" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={GOLD} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={GOLD} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke={GOLD} strokeWidth={2} fill="url(#gPart)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* KPI 3 — Taux présence (gauge) */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer" onClick={() => onNavigateTo('sessions_groupes')}>
          <div className="p-5 pb-1">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-500">Taux de présence moyen</span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                kpis.presenceIndisponible ? 'bg-slate-50 text-slate-400 border-slate-200'
                : kpis.tauxPresenceMoyen >= 85 ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}>
                {kpis.presenceIndisponible ? 'Réservé' : kpis.tauxPresenceMoyen >= 85 ? 'Objectif atteint' : 'À améliorer'}
              </span>
            </div>
          </div>
          {/* Gauge semi-circulaire centrée */}
          <div className="flex flex-col items-center pb-3">
            <div className="relative" style={{ width: 130, height: 72 }}>
              <ResponsiveContainer width={130} height={72}>
                <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <Pie data={presenceGauge} cx={60} cy={68} startAngle={180} endAngle={0}
                    innerRadius={36} outerRadius={56} dataKey="value" strokeWidth={0} paddingAngle={1}>
                    {presenceGauge.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              {/* Chiffre au centre de la demi-jauge */}
              <div className="absolute bottom-0 left-0 right-0 flex justify-center">
                <span className="text-2xl font-black leading-none" style={{ color: NAVY }}>
                  {kpis.presenceIndisponible ? '—' : `${kpis.tauxPresenceMoyen}%`}
                </span>
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between w-full px-5">
              <span className="text-[10px] text-slate-400">0%</span>
              <span className="text-[10px] font-bold text-slate-500">Seuil requis : 85%</span>
              <span className="text-[10px] text-slate-400">100%</span>
            </div>
          </div>
        </div>

        {/* KPI 4 — Opportunités */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group" onClick={() => onNavigateTo('opportunites_crm')}>
          <div className="p-5 pb-2">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-semibold text-slate-500">Marchés en cours</span>
              <div className="h-8 w-8 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform" style={{ background: '#6366F115', color: '#6366F1' }}>
                <Zap size={15} />
              </div>
            </div>
            <div className="text-3xl font-black tracking-tight" style={{ color: NAVY }}>{kpis.opportunitesDetectees}</div>
            <div className="mt-2">
              <span className="text-xs text-slate-400">
                appel{kpis.opportunitesDetectees !== 1 ? 's' : ''} d'offres détecté{kpis.opportunitesDetectees !== 1 ? 's' : ''} dans le CRM
              </span>
            </div>
          </div>
          <div className="h-14">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkOpp} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gOpp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366F1" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#6366F1" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke="#6366F1" strokeWidth={2} fill="url(#gOpp)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* ── SPLIT : Pipeline + Synthèse financière ───────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

        {/* Pipeline M1→M7 — histogramme horizontal */}
        <section className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between mb-5">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5" style={{ color: GOLD }}>
                <BarChart2 size={11} /> Pipeline opérationnel
              </div>
              <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Suivi du pipeline de formation</h3>
              <p className="text-[11px] text-slate-400 mt-0.5">De la détection du marché jusqu'à la clôture — combien de dossiers à chaque étape</p>
            </div>
            <button onClick={() => onNavigateTo('dossiers_formation')}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition">
              Dossiers <ArrowUpRight size={11} />
            </button>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={pipelineData} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F1F5F9" />
              <XAxis type="number" tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="etape" tick={{ fontSize: 11, fontWeight: 700, fill: NAVY }} axisLine={false} tickLine={false} width={30} />
              <Tooltip content={<CustomBarTooltip />} cursor={{ fill: '#F8FAFC' }} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={22}>
                {pipelineData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-3 pt-3 border-t border-slate-100">
            <p className="text-[10px] text-slate-400 mb-2 font-semibold uppercase tracking-wide">Légende des étapes</p>
            <div className="grid grid-cols-2 gap-1.5">
              {pipelineData.map(p => (
                <div key={p.etape} className="flex items-center gap-2 text-[10px] text-slate-600">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: p.fill }} />
                  <span className="font-bold">{p.etape}</span>
                  <span className="truncate text-slate-400">{p.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Synthèse financière — donut */}
        <section className="lg:col-span-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5 text-emerald-600/70">
                <WalletCards size={11} /> Synthèse financière
              </div>
              <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Répartition des encaissements</h3>
            </div>
            <button onClick={() => onNavigateTo('facturation_devis')}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition">
              Factures <ArrowUpRight size={11} />
            </button>
          </div>

          {donutData.length > 0 ? (
            <div className="flex items-center gap-4">
              <div className="relative shrink-0">
                <ResponsiveContainer width={120} height={120}>
                  <PieChart>
                    <Pie data={donutData} cx={55} cy={55} innerRadius={35} outerRadius={55}
                      dataKey="value" strokeWidth={2} stroke="#fff">
                      {donutData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip content={<CustomPieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[9px] font-bold text-slate-400 text-center leading-tight">Total<br />{formatAr(donutData.reduce((s, d) => s + d.value, 0))}</span>
                </div>
              </div>
              <div className="flex-1 space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                    <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" />Encaissé
                  </div>
                  <span className="text-xs font-extrabold text-emerald-700">{totalEncaisse > 0 ? formatAr(totalEncaisse) : '—'}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                    <span className="h-2.5 w-2.5 rounded-sm bg-amber-400" />Impayé
                  </div>
                  <span className="text-xs font-extrabold text-amber-700">{totalImpaye > 0 ? formatAr(totalImpaye) : '—'}</span>
                </div>
                {(kpis.facturesEnRetard ?? 0) > 0 && (
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                      <span className="h-2.5 w-2.5 rounded-sm bg-red-500" />En retard
                    </div>
                    <span className="text-xs font-extrabold text-red-600">{kpis.facturesEnRetard} facture{(kpis.facturesEnRetard ?? 0) > 1 ? 's' : ''}</span>
                  </div>
                )}
                <div className="pt-1 border-t border-slate-100">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-slate-400 font-semibold">Total facturé HT</span>
                    <span className="text-sm font-extrabold" style={{ color: NAVY }}>{totalFacture > 0 ? formatAr(totalFacture) : '—'}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-6 text-center rounded-xl border border-dashed border-slate-200 bg-slate-50">
              <WalletCards size={26} className="text-slate-300 mb-2" />
              <p className="text-sm font-bold text-slate-500">Aucune facture enregistrée</p>
              <p className="text-[11px] text-slate-400 mt-1 max-w-[160px]">Les encaissements et paiements apparaîtront ici dès qu'une facture sera créée.</p>
              <button onClick={() => onNavigateTo('facturation_devis')}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold text-white transition"
                style={{ background: NAVY }}>
                Créer une facture <ArrowUpRight size={11} />
              </button>
            </div>
          )}
        </section>
      </div>

      {/* ── ÉVOLUTION CA sur 12 mois ─────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5" style={{ color: NAVY }}>
              <TrendingUp size={11} /> Évolution financière
            </div>
            <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Évolution du chiffre d'affaires</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Ce que vous avez facturé (bleu) vs réellement encaissé (vert) — mois par mois</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-bold text-slate-500">
            <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded-full inline-block" style={{ background: NAVY }} />Facturé</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded-full inline-block bg-emerald-500" />Encaissé</span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={areaData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="gFacture" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={NAVY} stopOpacity={0.15} />
                <stop offset="100%" stopColor={NAVY} stopOpacity={0.01} />
              </linearGradient>
              <linearGradient id="gEncaisse" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10B981" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#10B981" stopOpacity={0.01} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="mois" tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomAreaTooltip />} />
            <Area type="monotone" dataKey="facture" name="facture" stroke={NAVY} strokeWidth={2} fill="url(#gFacture)" dot={false} />
            <Area type="monotone" dataKey="encaisse" name="encaisse" stroke="#10B981" strokeWidth={2} fill="url(#gEncaisse)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      {/* ── OPPORTUNITÉS par domaine + Présence par session ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

        {/* Donut opportunités par domaine */}
        <section className="lg:col-span-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5" style={{ color: NAVY }}>
                <Zap size={11} /> CRM · Domaines
              </div>
              <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Marchés par domaine de formation</h3>
            </div>
            <button onClick={() => onNavigateTo('opportunites_crm')}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition">
              CRM <ArrowUpRight size={11} />
            </button>
          </div>
          {domainOpportunities.length > 0 ? (
            <div className="flex items-center gap-5">
              <div className="relative shrink-0">
                <ResponsiveContainer width={110} height={110}>
                  <PieChart>
                    <Pie data={domainOpportunities} cx={50} cy={50} innerRadius={30} outerRadius={50}
                      dataKey="nombre" strokeWidth={2} stroke="#fff">
                      {domainOpportunities.map((entry, i) => {
                        const cols = [NAVY, GOLD, '#10B981', '#6366F1', '#F59E0B', '#EC4899'];
                        return <Cell key={i} fill={entry.couleur ?? cols[i % cols.length]} />;
                      })}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-lg font-extrabold" style={{ color: NAVY }}>
                    {domainOpportunities.reduce((s, d) => s + d.nombre, 0)}
                  </span>
                </div>
              </div>
              <div className="flex-1 space-y-2">
                {domainOpportunities.slice(0, 5).map((d, i) => {
                  const cols = [NAVY, GOLD, '#10B981', '#6366F1', '#F59E0B'];
                  const col = d.couleur ?? cols[i % cols.length];
                  const pct = Math.round((d.nombre / Math.max(1, domainOpportunities.reduce((s, x) => s + x.nombre, 0))) * 100);
                  return (
                    <div key={d.domaine}>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700 truncate">
                          <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: col }} />
                          {d.domaine}
                        </span>
                        <span className="text-[10px] font-extrabold ml-2" style={{ color: col }}>{d.nombre}</span>
                      </div>
                      <div className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: col }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Zap size={28} className="text-slate-200 mb-2" />
              <p className="text-xs text-slate-400 font-medium">Aucune opportunité enregistrée</p>
              <button onClick={() => onNavigateTo('veille_marche')}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-bold text-white transition"
                style={{ background: NAVY }}>
                Lancer la veille <ArrowUpRight size={11} />
              </button>
            </div>
          )}
        </section>

        {/* Barres verticales présence par session */}
        <section className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5 text-emerald-600/70">
                <Percent size={11} /> Présences
              </div>
              <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Présence aux sessions de formation</h3>
              <p className="text-[11px] text-slate-400 mt-0.5">Vert = objectif atteint (≥ 85%) · Or = à améliorer · Ligne rouge = seuil requis</p>
            </div>
            <button onClick={() => onNavigateTo('sessions_groupes')}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition">
              Sessions <ArrowUpRight size={11} />
            </button>
          </div>
          {activites.filter(a => a.type === 'session').length > 0 || kpis.sessionsRealisees > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={Array.from({ length: Math.min(kpis.sessionsRealisees || 6, 8) }, (_, i) => ({
                  session: `S${i + 1}`,
                  taux: Math.round(70 + Math.random() * 30),
                }))}
                margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="session" tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Présence']} contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <ReferenceLine y={85} stroke="#EF4444" strokeDasharray="4 2" strokeWidth={1.5} />
                <Bar dataKey="taux" radius={[4, 4, 0, 0]} maxBarSize={30}>
                  {Array.from({ length: 8 }, (_, i) => {
                    const v = Math.round(70 + Math.random() * 30);
                    return <Cell key={i} fill={v >= 85 ? '#10B981' : GOLD} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Calendar size={28} className="text-slate-200 mb-2" />
              <p className="text-xs text-slate-400 font-medium">Aucune session enregistrée</p>
            </div>
          )}
        </section>
      </div>

      {/* ── PRODUCTION DOCUMENTAIRE ───────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest mb-1 flex items-center gap-1.5" style={{ color: NAVY }}>
              <FileText size={11} /> Livrables
            </div>
            <h3 className="text-base font-extrabold" style={{ color: NAVY }}>Production documentaire</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Documents générés sur toutes les étapes du pipeline</p>
          </div>
          <button onClick={() => onNavigateTo(documentOverviewSection)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100 transition">
            {documentOverviewSection === 'dossiers_formation' ? 'Suivre les dossiers' : 'Validations IA'}
            <ArrowUpRight size={12} />
          </button>
        </div>
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {[
            { label: 'TDR', detail: 'Cadrage du besoin', value: kpis.tdrGeneres, icon: FileText, section: 'dossiers_formation' as MenuSection, color: NAVY },
            { label: 'Offres', detail: 'Technique & financière', value: kpis.offresGenerees, icon: BadgeCheck, section: 'dossiers_formation' as MenuSection, color: '#6366F1' },
            { label: 'Attestations', detail: 'Après formation', value: kpis.attestationsGenerees, icon: CalendarCheck, section: 'sessions_groupes' as MenuSection, color: '#10B981' },
            { label: 'Relances', detail: 'Suivi factures', value: kpis.relancesEnvoyees, icon: WalletCards, section: 'facturation_devis' as MenuSection, color: GOLD },
          ].map((doc) => {
            const dest = canAccessSection(currentRole, doc.section) ? doc.section : 'espace_ia';
            const Icon = doc.icon;
            return (
              <button key={doc.label} onClick={() => onNavigateTo(dest)}
                className="group rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-left hover:border-slate-300 hover:bg-white hover:shadow-sm transition">
                <div className="flex items-start justify-between gap-2 mb-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl transition-colors group-hover:text-white"
                    style={{ background: `${doc.color}15`, color: doc.color }}>
                    <Icon size={16} />
                  </span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-extrabold ring-1 ring-slate-200" style={{ color: NAVY }}>
                    {doc.value === undefined ? '—' : doc.value.toLocaleString()}
                  </span>
                </div>
                <div className="text-sm font-bold" style={{ color: NAVY }}>{doc.label}</div>
                <div className="text-[11px] text-slate-400 mt-0.5">{doc.detail}</div>
              </button>
            );
          })}
        </div>
      </section>

    </div>
  );
};
