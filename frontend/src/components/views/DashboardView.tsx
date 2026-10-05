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
  UserRole
} from '../../types';

interface DashboardViewProps {
  kpis: KPIStats;
  domainOpportunities: DomainOpportunity[];
  facturationStatuts: FacturationStatut[];
  activites: ActiviteRecente[];
  currentRole: UserRole;
  onRefresh: () => void;
  onNavigateTo: (section: any) => void;
  onOpenNewOpportunity: () => void;
  onOpenNewSession: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  kpis,
  domainOpportunities,
  facturationStatuts,
  activites,
  currentRole,
  onRefresh,
  onNavigateTo,
  onOpenNewOpportunity,
  onOpenNewSession
}) => {
  const [timeframe, setTimeframe] = useState<'mois' | 'trimestre' | 'annee'>('mois');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    await onRefresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const totalFacturation = facturationStatuts.reduce((acc, curr) => acc + curr.montant, 0);

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-300">
      {/* Top Title Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#1B8F6E]/10 text-[#1B8F6E]">
              Vue {currentRole === 'Dir.' ? 'Direction Générale' : currentRole === 'Form.' ? 'Pédagogique' : 'Assistant'}
            </span>
            <span className="text-xs text-slate-400">• Temps réel (REST)</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-[#11162A] tracking-tight">
            Tableau de bord
          </h1>
          <p className="text-slate-600 text-sm mt-1 max-w-2xl font-normal leading-relaxed">
            Vue consolidée de l'activité de formation : sessions, présences, opportunités et facturation.
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2.5 shrink-0 self-start md:self-center">
          <div className="flex items-center bg-[#F4F5F3] p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setTimeframe('mois')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                timeframe === 'mois'
                  ? 'bg-white text-[#11162A] shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Mois
            </button>
            <button
              onClick={() => setTimeframe('trimestre')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                timeframe === 'trimestre'
                  ? 'bg-white text-[#11162A] shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Trimestre
            </button>
            <button
              onClick={() => setTimeframe('annee')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                timeframe === 'annee'
                  ? 'bg-white text-[#11162A] shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Année 2026
            </button>
          </div>

          <button
            onClick={handleRefreshClick}
            disabled={isRefreshing}
            className="p-2.5 text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-xs active:scale-95"
            title="Rafraîchir les données depuis l'API REST"
          >
            <RefreshCw size={16} className={isRefreshing ? 'animate-spin text-[#1B8F6E]' : ''} />
          </button>
        </div>
      </div>

      {/* GROS AFFICHAGE - 4 KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* KPI 1: Sessions Réalisées */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-[#1B8F6E]/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Sessions réalisées
            </span>
            <div className="w-10 h-10 rounded-xl bg-[#1B8F6E]/10 text-[#1B8F6E] flex items-center justify-center font-bold group-hover:bg-[#1B8F6E] group-hover:text-white transition-colors">
              <Calendar size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.sessionsRealisees}
            </div>
            <div className="flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
              <TrendingUp size={12} className="mr-1" />
              +12%
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 flex items-center justify-between">
            <span>Objectif mensuel : 40</span>
            <span className="font-semibold text-slate-700">92.5% atteint</span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className="bg-[#1B8F6E] h-full rounded-full" style={{ width: '92.5%' }}></div>
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
              {kpis.participantsFormes}
            </div>
            <div className="flex items-center text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
              <TrendingUp size={12} className="mr-1" />
              +18%
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 flex items-center justify-between">
            <span>Moyenne/session : 11.1</span>
            <span className="font-semibold text-slate-700">Qualiopi Conforme</span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className="bg-blue-600 h-full rounded-full" style={{ width: '84%' }}></div>
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
              {kpis.tauxPresenceMoyen}%
            </div>
            <div className="flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
              <CheckCircle2 size={12} className="mr-1" />
              Émargé
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 flex items-center justify-between">
            <span>Seuil d'alerte : &lt;85%</span>
            <span className="font-semibold text-emerald-600">Excellence</span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className="bg-amber-500 h-full rounded-full" style={{ width: `${kpis.tauxPresenceMoyen}%` }}></div>
          </div>
        </div>

        {/* KPI 4: Opportunités détectées */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-purple-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Opportunités détectées
            </span>
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold group-hover:bg-purple-600 group-hover:text-white transition-colors">
              <Zap size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.opportunitesDetectees}
            </div>
            <div className="flex items-center text-xs font-bold text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
              <Sparkles size={12} className="mr-1" />
              IA Active
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2 flex items-center justify-between">
            <span>Valeur estimée pipeline :</span>
            <span className="font-extrabold text-[#11162A]">300 000 Ar</span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className="bg-purple-600 h-full rounded-full" style={{ width: '78%' }}></div>
          </div>
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
                  Opportunités détectées par domaine
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
          </div>

          {/* Quick Domain Metrics Grid */}
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {domainOpportunities.slice(0, 3).map((item, idx) => (
              <div key={idx} className="bg-[#F4F5F3] p-2.5 rounded-xl border border-slate-200/60">
                <div className="text-[11px] font-bold text-slate-600 truncate">{item.domaine}</div>
                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-sm font-extrabold text-[#11162A]">{item.nombre} opp.</span>
                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-100/60 px-1.5 py-0.2 rounded">
                    +{item.croissance}%
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

            {/* Donut Chart */}
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
              Historique des événements clés, signatures et émargements
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenNewOpportunity}
              className="px-3 py-1.5 bg-[#1B8F6E]/10 text-[#1B8F6E] hover:bg-[#1B8F6E]/20 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1"
            >
              <Plus size={14} />
              <span>Saisir événement</span>
            </button>
          </div>
        </div>

        {/* Timeline List */}
        <div className="space-y-4">
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
                default:
                  return <Sparkles className="text-amber-600" size={16} />;
              }
            };

            return (
              <div
                key={item.id}
                className="flex items-start gap-4 p-3.5 rounded-xl bg-[#F4F5F3]/80 hover:bg-[#F4F5F3] border border-slate-200/70 transition-all"
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
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
