import React, { useState } from 'react';
import {
  Calendar,
  Users,
  Percent,
  Zap,
  ArrowUpRight,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  FileText,
  Sparkles,
  Plus,
  WalletCards,
  BadgeCheck,
  CalendarCheck
} from 'lucide-react';
import {
  ResponsiveContainer,
  Tooltip,
  Cell,
  PieChart,
  Pie
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

const formatAriary = (amount: number): string =>
  `${amount.toLocaleString('fr-FR')} Ar`;

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
  const invoiceCount = facturationStatuts.reduce((acc, curr) => acc + curr.nombreFactures, 0);
  const totalDomainOpportunities = domainOpportunities.reduce((acc, item) => acc + item.nombre, 0);
  const totalEstimatedBudget = domainOpportunities.reduce((acc, item) => acc + item.valeurEstimee, 0);
  const maxDomainCount = Math.max(1, ...domainOpportunities.map(item => item.nombre));
  const documentOverviewSection: MenuSection = canAccessSection(currentRole, 'dossiers_formation') ? 'dossiers_formation' : 'espace_ia';
  const presenceProgress = Math.max(0, Math.min(kpis.tauxPresenceMoyen, 100));
  const presenceStatus = kpis.presenceIndisponible ? 'Réservé' : kpis.tauxPresenceMoyen >= 85 ? 'Conforme' : 'À surveiller';

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-300">
      {/* Top Title Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-gold/15 text-brand-navy">
              Vue {DASHBOARD_VIEW_LABELS[currentRole]}
            </span>
            <span className="text-xs text-slate-500">• Vue de pilotage consolidée</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-[#11162A] tracking-tight">
            Tableau de bord
          </h1>
          <p className="text-slate-600 text-sm mt-1 max-w-2xl font-normal leading-relaxed">
            Suivez l’activité de formation, les opportunités commerciales et les principaux indicateurs financiers.
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2.5 self-start md:self-center">
          {currentRole === 'Dir.' && <>
            <button
              type="button"
              onClick={onOpenNewSession}
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-navy px-3 py-2.5 text-xs font-bold text-white shadow-sm transition hover:bg-brand-darkNavy focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
            >
              <Plus size={14} /> Nouvelle session
            </button>
            <button
              type="button"
              onClick={onOpenNewOpportunity}
              className="inline-flex items-center gap-1.5 rounded-xl border border-brand-gold/50 bg-brand-gold/10 px-3 py-2.5 text-xs font-bold text-brand-navy transition hover:bg-brand-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2"
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
            <RefreshCw size={16} className={isRefreshing ? 'animate-spin text-brand-goldDark' : ''} />
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

      {/* Indicateurs opérationnels */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Sessions comptées par le Backend */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-[#0B1F4D]/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Sessions recensées
            </span>
            <div className="w-10 h-10 rounded-xl bg-[#0B1F4D]/10 text-[#0B1F4D] flex items-center justify-center font-bold group-hover:bg-[#0B1F4D] group-hover:text-white transition-colors">
              <Calendar size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.sessionsRealisees}
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">Nombre total de sessions enregistrées dans la plateforme.</p>
        </div>

        {/* KPI 2: Participants Formés */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-blue-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Participants recensés
            </span>
            <div className="w-10 h-10 rounded-xl bg-brand-gold/15 text-brand-navy flex items-center justify-center font-bold group-hover:bg-brand-navy group-hover:text-white transition-colors">
              <Users size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.presenceIndisponible ? '—' : kpis.participantsFormes}
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">Personnes distinctes relevées dans les feuilles de présence.</p>
        </div>

        {/* KPI 3: Taux de présence moyen */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-amber-500/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Taux de présence
            </span>
            <div className="w-10 h-10 rounded-xl bg-brand-gold/15 text-brand-goldDark flex items-center justify-center font-bold group-hover:bg-brand-gold group-hover:text-brand-darkNavy transition-colors">
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
            <span>Repère de suivi : 85 %</span>
            <span className={`font-semibold ${kpis.presenceIndisponible ? 'text-slate-500' : presenceProgress >= 85 ? 'text-emerald-600' : 'text-amber-600'}`}>
              {kpis.presenceIndisponible ? 'Réservé' : presenceProgress >= 85 ? 'Seuil atteint' : `${Math.round(85 - presenceProgress)} pt avant le seuil`}
            </span>
          </p>
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div className={`h-full rounded-full transition-[width] ${presenceProgress >= 85 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${presenceProgress}%` }}></div>
          </div>
        </div>

        {/* KPI 4: Opportunités détectées */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:border-[#0B1F4D]/40 transition-all group">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Opportunités au CRM
            </span>
            <div className="w-10 h-10 rounded-xl bg-[#0B1F4D]/10 text-[#0B1F4D] flex items-center justify-center font-bold group-hover:bg-[#0B1F4D] group-hover:text-white transition-colors">
              <Zap size={20} />
            </div>
          </div>
          <div className="flex items-baseline justify-between">
            <div className="text-3xl font-extrabold text-[#11162A]">
              {kpis.opportunitesDetectees}
            </div>
            <div className="flex items-center text-xs font-bold text-brand-navy bg-brand-gold/15 px-2 py-0.5 rounded-full">
              Enregistrées
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">Opportunités enregistrées, toutes étapes confondues.</p>
        </div>
      </div>

      {/* Synthèse financière */}
      <section aria-labelledby="dashboard-finance-title" className="space-y-3">
        <div>
          <h2 id="dashboard-finance-title" className="text-base font-extrabold text-[#11162A]">Synthèse financière</h2>
          <p className="mt-1 text-xs text-slate-500">Montants consolidés à partir des factures et paiements enregistrés.</p>
        </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {[
          { label: 'Total facturé · HT', value: kpis.chiffreAffairesFacture, accent: 'text-brand-navy' },
          { label: 'Total encaissé', value: kpis.chiffreAffairesEncaisse, accent: 'text-emerald-700' },
          { label: 'Solde à recouvrer · TTC', value: kpis.montantImpaye, accent: 'text-amber-700' },
          { label: 'Factures en retard', value: kpis.facturesEnRetard, unit: '', accent: (kpis.facturesEnRetard ?? 0) > 0 ? 'text-red-600' : 'text-[#11162A]' }
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{card.label}</span>
            <div className={`text-2xl font-extrabold mt-2 ${card.accent}`}>
              {card.value === undefined ? '—' : card.label === 'Factures en retard' ? card.value.toLocaleString('fr-FR') : formatAriary(card.value)}
            </div>
          </div>
        ))}
      </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:p-6">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-brand-navy">
              <FileText size={15} /> Production documentaire
            </div>
            <h3 className="text-lg font-bold text-[#11162A]">Documents générés et suivi</h3>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-600">
              Les TDR et les offres se consultent dans le dossier de leur opportunité ; les autres livrables restent accessibles dans leur module.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTo(documentOverviewSection)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs font-bold text-[#0B1F4D] transition hover:bg-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F] focus-visible:ring-offset-2"
          >
            {documentOverviewSection === 'dossiers_formation' ? 'Suivre les dossiers' : 'Voir les validations IA'}
            <ArrowUpRight size={14} />
          </button>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: 'TDR', detail: 'Cadrage du besoin', value: kpis.tdrGeneres, icon: FileText, section: 'dossiers_formation' as const },
            { label: 'Offres', detail: 'Technique et financière', value: kpis.offresGenerees, icon: BadgeCheck, section: 'dossiers_formation' as const },
            { label: 'Attestations', detail: 'Après la formation', value: kpis.attestationsGenerees, icon: CalendarCheck, section: 'sessions_groupes' as const },
            { label: 'Relances', detail: 'Suivi des factures', value: kpis.relancesEnvoyees, icon: WalletCards, section: 'facturation_devis' as const }
          ].map((doc) => {
            const destination = canAccessSection(currentRole, doc.section) ? doc.section : 'espace_ia';
            const Icon = doc.icon;
            const countLabel = doc.value === undefined ? 'Indicateur indisponible' : doc.value === 0 ? 'Aucun résultat enregistré' : `${doc.value.toLocaleString()} résultat${doc.value === 1 ? '' : 's'}`;
            return (
              <button
                type="button"
                key={doc.label}
                onClick={() => onNavigateTo(destination)}
                className="group rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-left transition hover:border-emerald-300 hover:bg-emerald-50/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F] focus-visible:ring-offset-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-[#0B1F4D] transition group-hover:bg-[#06132F] group-hover:text-white">
                    <Icon size={18} />
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-xs font-extrabold text-[#11162A] ring-1 ring-slate-200">
                    {doc.value === undefined ? '—' : doc.value.toLocaleString()}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-bold text-[#11162A]">{doc.label}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500">{doc.detail}</div>
                  </div>
                  <ArrowUpRight size={15} className="shrink-0 text-slate-400 transition group-hover:text-[#0B1F4D]" />
                </div>
                <p className="mt-2 text-[11px] font-medium text-slate-600">{countLabel}</p>
              </button>
            );
          })}
        </div>
        <p className="mt-4 rounded-xl border border-blue-100 bg-blue-50/70 px-3.5 py-3 text-xs leading-relaxed text-blue-900">
          <strong>Traçabilité :</strong> un TDR ou une offre est relié à une opportunité par son identifiant. Ouvrez le dossier pour retrouver le contenu et son statut de validation.
        </p>
      </section>

      {/* SECTION 1 & SECTION 2: Opportunités par domaine & Facturation Statut */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Opportunités détectées par domaine (Bar Chart & Visual Breakdown) */}
        <section className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:p-6">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-brand-navy">
                <Zap size={15} /> Veille marché · M1
              </div>
              <h3 className="text-lg font-bold text-[#11162A]">Opportunités par domaine</h3>
              <p className="mt-1 text-xs text-slate-600">Répartition des opportunités enregistrées dans le CRM.</p>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTo('opportunites_crm')}
              className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-lg px-2 py-1.5 text-xs font-bold text-[#0B1F4D] transition hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F]"
            >
              Voir le CRM <ArrowUpRight size={14} />
            </button>
          </div>

          {domainOpportunities.length === 0 ? (
            <div className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-5 py-6 text-center">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-brand-navy shadow-sm ring-1 ring-slate-200"><Zap size={20} /></span>
              <h4 className="mt-3 text-sm font-bold text-slate-800">Aucune opportunité à présenter</h4>
              <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-600">Les opportunités détectées ou ajoutées apparaîtront ici, regroupées par domaine.</p>
              <button type="button" onClick={() => onNavigateTo('veille_marche')} className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-[#0B1F4D] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F]">
                Ouvrir la veille marché <ArrowUpRight size={13} />
              </button>
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-slate-50 px-3.5 py-3 ring-1 ring-slate-200/80">
                  <div className="text-[11px] font-semibold text-slate-500">Opportunités suivies</div>
                  <div className="mt-0.5 text-xl font-extrabold text-[#11162A]">{totalDomainOpportunities.toLocaleString()}</div>
                </div>
                <div className="rounded-xl bg-brand-gold/10 px-3.5 py-3 ring-1 ring-brand-gold/30">
                  <div className="text-[11px] font-semibold text-brand-navy">Budgets renseignés · total</div>
                  <div className="mt-0.5 truncate text-base font-extrabold text-[#0B1F4D]" title={totalEstimatedBudget > 0 ? `${totalEstimatedBudget.toLocaleString()} Ar` : 'Budget non renseigné'}>
                    {totalEstimatedBudget > 0 ? `${totalEstimatedBudget.toLocaleString()} Ar` : 'Non renseigné'}
                  </div>
                </div>
              </div>
              <div className="space-y-5 border-t border-slate-100 pt-5">
                {domainOpportunities.slice(0, 5).map((item) => {
                  const percentage = Math.max(8, Math.round((item.nombre / maxDomainCount) * 100));
                  return (
                    <div key={item.domaine}>
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-bold text-[#11162A]">{item.domaine}</div>
                          <div className="mt-0.5 text-[11px] text-slate-500">
                            {item.valeurEstimee > 0 ? `Budget : ${item.valeurEstimee.toLocaleString()} Ar` : 'Budget non renseigné'}
                          </div>
                        </div>
                        <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
                          {item.nombre} opportunité{item.nombre === 1 ? '' : 's'}
                        </span>
                      </div>
                      <div role="progressbar" aria-label={`${item.domaine} : ${item.nombre} opportunité(s)`} aria-valuemin={0} aria-valuemax={maxDomainCount} aria-valuenow={item.nombre} className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full transition-[width]" style={{ width: `${percentage}%`, backgroundColor: item.couleur ?? '#0B1F4D' }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              {domainOpportunities.length > 5 && (
                <button type="button" onClick={() => onNavigateTo('opportunites_crm')} className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-[#0B1F4D] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F]">
                  Voir les {domainOpportunities.length - 5} autres domaines <ArrowUpRight size={13} />
                </button>
              )}
            </>
          )}
        </section>

        {/* Facturation - statut */}
        <section className="lg:col-span-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-emerald-700">
                <WalletCards size={15} /> Suivi financier · M7
              </div>
              <h3 className="text-lg font-bold text-[#11162A]">Facturation par statut</h3>
              <p className="mt-1 text-xs text-slate-600">
                Total engagé : <span className="font-extrabold text-[#11162A]">{totalFacturation.toLocaleString()} Ar HT</span>
              </p>
            </div>
            {facturationStatuts.length > 0 && (
              <button type="button" onClick={() => onNavigateTo('facturation_devis')} className="inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-bold text-[#0B1F4D] transition hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F]">
                Détails <ArrowUpRight size={14} />
              </button>
            )}
          </div>

          {facturationStatuts.length === 0 ? (
            <div className="mt-5 flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/80 px-5 py-7 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-brand-navy shadow-sm ring-1 ring-slate-200"><WalletCards size={22} /></span>
              <div className="mt-3 text-[11px] font-bold uppercase tracking-wide text-slate-500">Suivi prêt à démarrer</div>
              <h4 className="mt-1 text-sm font-bold text-slate-800">Aucune facture enregistrée</h4>
              <p className="mt-1 max-w-xs text-xs leading-relaxed text-slate-600">Après la création d’un devis ou d’une facture, les montants et les statuts apparaîtront dans ce panneau.</p>
              <button type="button" onClick={() => onNavigateTo('facturation_devis')} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#06132F] px-3 py-2 text-xs font-bold text-white transition hover:bg-[#06132F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F] focus-visible:ring-offset-2">
                Ouvrir la facturation <ArrowUpRight size={13} />
              </button>
            </div>
          ) : (
            <>
              <div className="relative mx-auto my-3 h-48 w-full max-w-xs">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={facturationStatuts} cx="50%" cy="50%" innerRadius={58} outerRadius={82} paddingAngle={4} dataKey="montant">
                      {facturationStatuts.map((entry, index) => <Cell key={`cell-pie-${index}`} fill={entry.couleur} />)}
                    </Pie>
                    <Tooltip
                      formatter={(value: any) => [`${Number(value).toLocaleString()} Ar`, 'Montant']}
                      contentStyle={{ backgroundColor: '#11162A', borderColor: '#334155', borderRadius: '12px', color: '#fff', fontSize: '12px' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                  <span className="text-2xl font-extrabold text-[#11162A]">{invoiceCount.toLocaleString()}</span>
                  <span className="text-[11px] font-semibold text-slate-500">facture{invoiceCount === 1 ? '' : 's'}</span>
                </div>
              </div>
              <div className="space-y-3 border-t border-slate-100 pt-4">
                {facturationStatuts.map((item) => (
                  <div key={item.statut} className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-white" style={{ backgroundColor: item.couleur }} />
                      <div className="min-w-0">
                        <div className="truncate text-xs font-bold text-slate-800">{item.statut}</div>
                        <div className="text-[11px] text-slate-500">{item.nombreFactures} facture{item.nombreFactures === 1 ? '' : 's'}</div>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xs font-extrabold text-[#11162A]">{item.montant.toLocaleString()} Ar</div>
                      <div className="text-[11px] text-slate-500">{item.pourcentage}% du total</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>

      {/* SECTION 3: Activité récente */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div>
            <h3 className="text-lg font-bold text-[#11162A] flex items-center gap-2">
              <Clock size={18} className="text-[#0B1F4D]" />
              Activité récente
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Événements récents : sessions, présences, opportunités, factures et documents
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
                  return <Calendar className="text-[#0B1F4D]" size={16} />;
                case 'presence':
                  return <Users className="text-brand-goldDark" size={16} />;
                case 'opportunite':
                  return <Zap className="text-brand-goldDark" size={16} />;
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
                className="flex w-full items-start gap-4 rounded-xl border border-slate-200/70 bg-[#F4F5F3]/80 p-3.5 text-left transition-all hover:bg-[#F4F5F3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06132F] disabled:cursor-default"
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
                      <span className="bg-[#0B1F4D]/10 text-[#0B1F4D] font-bold px-2 py-0.5 rounded">
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
