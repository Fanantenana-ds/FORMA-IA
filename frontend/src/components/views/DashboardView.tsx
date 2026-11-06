import React, { useState } from 'react';
import {
  Calendar,
  Users,
  Percent,
  Zap,
  TrendingUp,
  ArrowUpRight,
  Filter,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  Search,
  Sparkles,
  ChevronRight,
  Plus
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  Legend
} from 'recharts';
import {
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente,
  UserRole,
  MenuSection,
  canAccessSection
} from '../../types';

interface DashboardViewProps {
  kpis: KPIStats;
  domainOpportunities: DomainOpportunity[];
  facturationStatuts: FacturationStatut[];
  activites: ActiviteRecente[];
  currentRole: UserRole;
  isLoading?: boolean;
  notice?: string | null;
  onRefresh: () => void;
  onNavigateTo: (section: MenuSection) => void;
  onOpenNewOpportunity: () => void;
  onOpenNewSession: () => void;
}

const DASHBOARD_VIEW_LABELS: Record<UserRole, string> = {
  'Dir.': 'Direction Générale',
  'Form.': 'Pédagogique',
  'Assis.': 'Assistant',
  'Compt.': 'Comptabilité'
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  kpis,
  domainOpportunities,
  facturationStatuts,
  activites,
  currentRole,
  isLoading = false,
  notice,
  onRefresh,
  onNavigateTo,
  onOpenNewOpportunity,
  onOpenNewSession
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const totalFacturation = facturationStatuts.reduce((acc, curr) => acc + curr.montant, 0);
  const presenceProgress = Math.max(0, Math.min(kpis.tauxPresenceMoyen, 100));
  const presenceStatus = kpis.presenceIndisponible ? 'Réservé' : kpis.tauxPresenceMoyen >= 85 ? 'Conforme' : 'À surveiller';

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-300">
      {/* Top Title Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#1B8F6E]/10 text-[#1B8F6E]">
              Vue {DASHBOARD_VIEW_LABELS[currentRole]}
            </span>
            <span className="text-xs text-slate-500">• Données synchronisées depuis le Backend</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-[#11162A] tracking-tight">
            Tableau de bord
          </h1>
          <p className="text-slate-600 text-sm mt-1 max-w-2xl font-normal leading-relaxed">
            Vue consolidée de l'activité de formation : sessions, présences, opportunités et facturation.
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2.5 self-start md:self-center">
          {currentRole === 'Dir.' && <>
            <button
              type="button"
              onClick={onOpenNewSession}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#16785c] px-3 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-[#125f49] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] focus-visible:ring-offset-2"
            >
              <Plus size={14} /> Nouvelle session
            </button>
            <button
              type="button"
              onClick={onOpenNewOpportunity}
              className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs font-bold text-[#17694f] transition hover:bg-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] focus-visible:ring-offset-2"
            >
              <Plus size={14} /> Nouvelle opportunité
            </button>
          </>}
          <button
            type="button"
            onClick={handleRefreshClick}
            disabled={isRefreshing}
            aria-label={isRefreshing ? 'Actualisation des données' : 'Actualiser les données du tableau de bord'}
            aria-busy={isRefreshing}
            className="p-2.5 text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-xs active:scale-95"
            title="Rafraîchir les données"
          >
            <RefreshCw size={16} className={isRefreshing ? 'animate-spin text-[#1B8F6E]' : ''} />
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold flex items-center gap-2">
          <RefreshCw size={14} className="animate-spin shrink-0" />
          Chargement des indicateurs…
        </div>
      )}

      {notice && !isLoading && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold flex items-start gap-2">
          <AlertCircle size={14} className="shrink-0 mt-0.5" />
          <span>{notice}</span>
        </div>
      )}

      {kpis.presenceIndisponible && !isLoading && (
        <div className="p-3 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 text-xs font-medium">
          Le nombre de participants et le taux de présence global sont réservés à la Direction.
        </div>
      )}

      {/* GROS AFFICHAGE - 4 KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* KPI 1: Sessions Réalisées */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-[#1B8F6E]/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Sessions enregistrées
            </span>
            <div className="w-10 h-10 rounded-xl bg-[#1B8F6E]/10 text-[#1B8F6E] flex items-center justify-center font-bold group-hover:bg-[#1B8F6E] group-hover:text-white transition-colors">
              <Calendar size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.sessionsRealisees}
            </div>
          </div>
        </div>

        {/* KPI 2: Participants Formés */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-blue-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Participants formés
            </span>
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold group-hover:bg-blue-600 group-hover:text-white transition-colors">
              <Users size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.presenceIndisponible ? '—' : kpis.participantsFormes}
            </div>
          </div>
        </div>

        {/* KPI 3: Taux de présence moyen */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-amber-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Taux de présence moyen
            </span>
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold group-hover:bg-amber-600 group-hover:text-white transition-colors">
              <Percent size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.presenceIndisponible ? '—' : `${kpis.tauxPresenceMoyen}%`}
            </div>
            <div className={`flex items-center rounded-full px-2 py-0.5 text-xs font-bold ${kpis.presenceIndisponible ? 'bg-slate-100 text-slate-600' : presenceProgress >= 85 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
              {kpis.presenceIndisponible ? <AlertCircle size={12} className="mr-1" /> : <CheckCircle2 size={12} className="mr-1" />}
              {presenceStatus}
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 flex items-center justify-between">
            <span>Seuil d'alerte : &lt;85%</span>
            <span className={`font-semibold ${kpis.presenceIndisponible ? 'text-slate-500' : presenceProgress >= 85 ? 'text-emerald-600' : 'text-amber-600'}`}>
              {kpis.presenceIndisponible ? 'Réservé' : presenceProgress >= 85 ? 'Seuil atteint' : `${Math.round(85 - presenceProgress)} pt avant le seuil`}
            </span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className={`h-full rounded-full transition-[width] ${presenceProgress >= 85 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${presenceProgress}%` }}></div>
          </div>
        </div>

        {/* KPI 4: Opportunités détectées */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-purple-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Opportunités suivies
            </span>
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Zap size={20} />
            </div>
          </div>
            <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.opportunitesDetectees}
            </div>
            <div className="flex items-center text-xs font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
              Enregistrées
            </div>
          </div>
        </div>
      </div>

      {/* INDICATEURS FINANCIERS & DOCUMENTS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'CA facturé (HT)', value: kpis.chiffreAffairesFacture, unit: ' Ar', accent: 'text-[#11162A]' },
          { label: 'CA encaissé', value: kpis.chiffreAffairesEncaisse, unit: ' Ar', accent: 'text-emerald-700' },
          { label: 'Montant impayé (TTC)', value: kpis.montantImpaye, unit: ' Ar', accent: 'text-amber-700' },
          { label: 'Factures en retard', value: kpis.facturesEnRetard, unit: '', accent: (kpis.facturesEnRetard ?? 0) > 0 ? 'text-red-600' : 'text-[#11162A]' }
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{card.label}</span>
            <div className={`text-2xl font-extrabold mt-2 ${card.accent}`}>
              {card.value === undefined ? '—' : `${card.value.toLocaleString()}${card.unit}`}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2 mb-4">
          <FileText size={18} className="text-[#1B8F6E]" />
          <h3 className="text-lg font-bold text-[#11162A]">Documents générés</h3>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-center">
          {[
            { label: 'TDR', value: kpis.tdrGeneres },
            { label: 'Offres', value: kpis.offresGenerees },
            { label: 'Attestations', value: kpis.attestationsGenerees },
            { label: 'Relances de facture', value: kpis.relancesEnvoyees }
          ].map((doc) => (
            <div key={doc.label} className="bg-[#F4F5F3] rounded-xl p-3 border border-slate-200/60">
              <div className="text-2xl font-extrabold text-[#11162A]">
                {doc.value === undefined ? '—' : doc.value.toLocaleString()}
              </div>
              <div className="text-[11px] font-bold text-slate-500 uppercase mt-0.5">{doc.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* SECTION 1 & SECTION 2: Opportunités par domaine & Facturation Statut */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Opportunités détectées par domaine (Bar Chart & Visual Breakdown) */}
        <div className="lg:col-span-7 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-[#11162A] flex items-center gap-2">
                  <Zap size={18} className="text-[#1B8F6E]" />
                  Opportunités suivies par domaine
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Analyse automatisée du marché de la formation par l'IA FORMA-IA
                </p>
              </div>
              <button
                onClick={() => onNavigateTo('opportunites_crm')}
                className="text-xs text-[#1B8F6E] hover:underline font-semibold flex items-center gap-1"
              >
                <span>Voir le CRM</span>
                <ArrowUpRight size={14} />
              </button>
            </div>

            {/* Recharts Bar Chart */}
            {domainOpportunities.length === 0 && (
              <p className="text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200/80 mt-2">
                Aucune opportunité enregistrée pour le moment.
              </p>
            )}
            {domainOpportunities.length > 0 && (
            <div className="h-64 w-full mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={domainOpportunities}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
                >
                  <XAxis type="number" stroke="#94A3B8" fontSize={12} />
                  <YAxis
                    dataKey="domaine"
                    type="category"
                    stroke="#475569"
                    fontSize={11}
                    width={140}
                    tickFormatter={(val) => val.length > 20 ? `${val.substring(0, 18)}...` : val}
                  />
                  <Tooltip
                    formatter={(value: any, name: any, props: any) => [
                      `${value} opportunités (${props.payload.valeurEstimee.toLocaleString()} Ar)`,
                      'Domaine'
                    ]}
                    contentStyle={{
                      backgroundColor: '#11162A',
                      borderColor: '#334155',
                      borderRadius: '12px',
                      color: '#fff',
                      fontSize: '12px'
                    }}
                  />
                  <Bar dataKey="nombre" radius={[0, 8, 8, 0]}>
                    {domainOpportunities.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.couleur || '#1B8F6E'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            )}
          </div>

          {/* Quick Domain Metrics Grid */}
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {domainOpportunities.slice(0, 3).map((item, idx) => (
              <div key={idx} className="bg-[#F4F5F3] p-2.5 rounded-xl border border-slate-200/60">
                <div className="text-[11px] font-bold text-slate-600 truncate">{item.domaine}</div>
                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-sm font-extrabold text-[#11162A]">{item.nombre} opp.</span>
                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-100/60 px-1.5 py-0.2 rounded">
                    {item.valeurEstimee > 0 ? `${item.valeurEstimee.toLocaleString()} Ar` : 'Budget n.c.'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Facturation - statut */}
        <div className="lg:col-span-5 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-[#11162A] flex items-center gap-2">
                  <FileText size={18} className="text-[#1B8F6E]" />
                  Facturation - statut
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Total engagé : <span className="font-extrabold text-[#11162A]">{totalFacturation.toLocaleString()} Ar HT</span>
                </p>
              </div>
              <button
                onClick={() => onNavigateTo('facturation_devis')}
                className="text-xs text-[#1B8F6E] hover:underline font-semibold flex items-center gap-1"
              >
                <span>Détails</span>
                <ArrowUpRight size={14} />
              </button>
            </div>

            {facturationStatuts.length === 0 && (
              <p className="text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
                Aucune facture enregistrée pour le moment.
              </p>
            )}

            {/* Donut Chart */}
            {facturationStatuts.length > 0 && (
            <div className="h-52 w-full flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={facturationStatuts}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={4}
                    dataKey="montant"
                  >
                    {facturationStatuts.map((entry, index) => (
                      <Cell key={`cell-pie-${index}`} fill={entry.couleur} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: any) => [`${Number(value).toLocaleString()} Ar`, 'Montant']}
                    contentStyle={{
                      backgroundColor: '#11162A',
                      borderColor: '#334155',
                      borderRadius: '12px',
                      color: '#fff',
                      fontSize: '12px'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            )}
          </div>

          {/* Status breakdown list */}
          <div className="space-y-2 mt-2 pt-3 border-t border-slate-100">
            {facturationStatuts.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.couleur }}></span>
                  <span className="font-medium text-slate-700">{item.statut}</span>
                  <span className="text-slate-400">({item.nombreFactures})</span>
                </div>
                <div className="font-bold text-[#11162A]">
                  {item.montant.toLocaleString()} Ar <span className="text-slate-400 font-normal">({item.pourcentage}%)</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SECTION 3: Activité récente */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h3 className="text-lg font-bold text-[#11162A] flex items-center gap-2">
              <Clock size={18} className="text-[#1B8F6E]" />
              Activité récente
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Dernières créations : opportunités, sessions, factures et documents
            </p>
          </div>
        </div>

        {/* Timeline List */}
        <div className="space-y-4">
          {activites.length === 0 && (
            <p className="text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
              Aucune activité enregistrée pour le moment.
            </p>
          )}
          {activites.map((item) => {
            const getIcon = () => {
              switch (item.type) {
                case 'session':
                  return <Calendar className="text-[#1B8F6E]" size={16} />;
                case 'presence':
                  return <Users className="text-blue-600" size={16} />;
                case 'opportunite':
                  return <Zap className="text-purple-600" size={16} />;
                case 'facture':
                  return <FileText className="text-emerald-600" size={16} />;
                case 'document':
                  return <FileText className="text-amber-600" size={16} />;
                default:
                  return <Sparkles className="text-amber-600" size={16} />;
              }
            };

            const activityDestination: Partial<Record<ActiviteRecente['type'], MenuSection>> = {
              session: 'sessions_groupes',
              presence: 'suivi_presences',
              opportunite: 'opportunites_crm',
              facture: 'facturation_devis',
              veille: 'veille_marche',
              document: 'espace_ia'
            };
            const destination = activityDestination[item.type];
            const canOpenActivity = destination ? canAccessSection(currentRole, destination) : false;

            return (
              <button
                type="button"
                key={item.id}
                onClick={() => { if (destination && canOpenActivity) onNavigateTo(destination); }}
                disabled={!canOpenActivity}
                aria-label={canOpenActivity ? `${item.titre} — ouvrir la rubrique correspondante` : item.titre}
                className="flex w-full items-start gap-4 rounded-xl border border-slate-200/70 bg-[#F4F5F3]/80 p-3.5 text-left transition-all hover:bg-[#F4F5F3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16785c] disabled:cursor-default"
              >
                <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center shrink-0 shadow-2xs mt-0.5">
                  {getIcon()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-[#11162A] truncate">
                      {item.titre}
                    </h4>
                    <span className="text-[11px] font-medium text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-200">
                      {item.horodateur}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                    {item.description}
                  </p>
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-500">
                    {item.utilisateur && (
                      <span className="font-semibold text-slate-700">
                        Par : {item.utilisateur}
                      </span>
                    )}
                    {item.statutTag && (
                      <span className="bg-[#1B8F6E]/10 text-[#1B8F6E] font-bold px-2 py-0.5 rounded">
                        {item.statutTag}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
