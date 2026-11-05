import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, ArrowRight, BookOpen, BriefcaseBusiness, Check, CheckCircle2,
  Circle, Clock3, FileCheck2, FileText, GraduationCap, Loader2, RefreshCw,
  Search, Users, WalletCards, Workflow
} from 'lucide-react';
import { apiService } from '../../services/api';
import type { DevisFacture, Formateur, MenuSection, OpportuniteCRM, Session } from '../../types';

type Props = {
  opportunites: OpportuniteCRM[];
  sessions: Session[];
  formateurs: Formateur[];
  factures: DevisFacture[];
  onRefreshData: () => void;
  onNavigateTo: (section: MenuSection) => void;
};
type Dossier = { key: string; opportunity?: OpportuniteCRM; session?: Session };
type Review = Record<string, any>;
type Stage = { title: string; detail: string; state: 'done' | 'pending' | 'future' | 'warning'; reviewId?: string };

const asArray = (value: any, key?: string): any[] => {
  const list = Array.isArray(value) ? value : key ? value?.[key] : value;
  return Array.isArray(list) ? list : [];
};

const reviewPayload = (value: any): Review => value?.review ?? value?.data?.review ?? value ?? {};
const reviewData = (review: Review) => review?.data && typeof review.data === 'object' ? review.data : {};
const exactOpportunityId = (review: Review): string | undefined => {
  const data = reviewData(review);
  const inputs = data._inputs ?? {};
  const brief = inputs.brief ?? {};
  const sessionInfo = inputs.session_info ?? {};
  const tdrData = inputs.tdr_data ?? {};
  const value = data.opportunite_id ?? data.metadata?.opportunite_id ?? review.meta?.opportunite_id
    ?? brief.opportunite_id ?? sessionInfo.opportunite_id ?? tdrData.opportunite_id;
  return value == null ? undefined : String(value);
};
const exactSessionId = (review: Review): string | undefined => {
  const data = reviewData(review);
  const value = review.session_id ?? review.meta?.session_id ?? data.session_id ?? data.metadata?.session_id
    ?? data.session_info?.session_id ?? data.session_info?.id;
  return value == null ? undefined : String(value);
};
const statusLabel = (status?: string) => ({ approved: 'Validé', rejected: 'Refusé', pending_review: 'À valider' }[status ?? ''] ?? 'Généré');
const formatDate = (value?: string) => {
  if (!value) return 'Date non renseignée';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('fr-FR');
};

export const DossiersFormationView: React.FC<Props> = ({ opportunites, sessions, formateurs, factures, onRefreshData, onNavigateTo }) => {
  const [selectedKey, setSelectedKey] = useState('');
  const [filter, setFilter] = useState('');
  const [offers, setOffers] = useState<any[]>([]);
  const [participants, setParticipants] = useState<any[]>([]);
  const [supports, setSupports] = useState<any[]>([]);
  const [eligibility, setEligibility] = useState<any>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [loadingReviews, setLoadingReviews] = useState(false);

  const dossiers = useMemo<Dossier[]>(() => {
    const opportunityDossiers = opportunites.flatMap(opportunity => {
      const linkedSessions = sessions.filter(session => session.opportuniteId === opportunity.id);
      return linkedSessions.length
        ? linkedSessions.map(session => ({ key: `op:${opportunity.id}:session:${session.id}`, opportunity, session }))
        : [{ key: `op:${opportunity.id}`, opportunity }];
    });
    const opportunityIds = new Set(opportunites.map(opportunity => opportunity.id));
    const detachedSessions = sessions.filter(session => !session.opportuniteId || !opportunityIds.has(session.opportuniteId))
      .map(session => ({ key: `session:${session.id}`, session }));
    return [...opportunityDossiers, ...detachedSessions];
  }, [opportunites, sessions]);

  useEffect(() => {
    if (!dossiers.length) { setSelectedKey(''); return; }
    if (!dossiers.some(dossier => dossier.key === selectedKey)) setSelectedKey(dossiers[0].key);
  }, [dossiers, selectedKey]);

  const selected = dossiers.find(dossier => dossier.key === selectedKey);
  const refreshDetail = useCallback(async () => {
    if (!selected) return;
    setLoadingDetail(true); setDetailError('');
    setOffers([]); setParticipants([]); setSupports([]); setEligibility(null);
    const sessionId = selected.session?.id;
    const opportunityId = selected.opportunity?.id;
    const tasks: Promise<any>[] = [
      opportunityId ? apiService.getOffersByOpportunity(opportunityId) : Promise.resolve({ data: [] }),
      sessionId ? apiService.getParticipants(sessionId) : Promise.resolve([]),
      sessionId ? apiService.getSupports({ session_id: sessionId }) : Promise.resolve({ data: [] }),
      sessionId ? apiService.getM6Eligibility(sessionId) : Promise.resolve(null),
    ];
    const results = await Promise.allSettled(tasks);
    const errors = results.filter(result => result.status === 'rejected');
    if (results[0].status === 'fulfilled') setOffers(asArray(results[0].value, 'data').length ? asArray(results[0].value, 'data') : asArray(results[0].value, 'offres'));
    if (results[1].status === 'fulfilled') setParticipants(asArray(results[1].value, 'participants'));
    if (results[2].status === 'fulfilled') setSupports(asArray(results[2].value, 'data'));
    if (results[3].status === 'fulfilled') setEligibility(results[3].value);
    if (errors.length) setDetailError(`${errors.length} donnée(s) n’ont pas pu être chargée(s). Le reste du dossier reste consultable.`);
    setLoadingDetail(false);
  }, [selected]);

  const refreshReviews = useCallback(async () => {
    if (!selected) return;
    setLoadingReviews(true);
    try {
      const [pendingResult, approvedResult, rejectedResult, m3PendingResult] = await Promise.allSettled([
        apiService.getPendingReviews(), apiService.getReviewHistory('approved'),
        apiService.getReviewHistory('rejected'), apiService.getOfferReviews()
      ]);
      const summaries = [
        ...(pendingResult.status === 'fulfilled' ? asArray(pendingResult.value, 'reviews') : []),
        ...(approvedResult.status === 'fulfilled' ? asArray(approvedResult.value, 'reviews') : []),
        ...(rejectedResult.status === 'fulfilled' ? asArray(rejectedResult.value, 'reviews') : []),
        ...(m3PendingResult.status === 'fulfilled' ? asArray(m3PendingResult.value, 'data') : [])
      ];
      const deduped = [...new Map(summaries.filter(item => item?.review_id).map(item => [String(item.review_id), item])).values()];
      const relevantAgents = new Set(['agent_m2_tdr', 'agent_m3_technique', 'agent_m3_financiere', 'agent_m3_complete', 'agent_5_attestations', 'agent_6_report']);
      const candidates = deduped.filter(item => relevantAgents.has(item.agent_id));
      const detailed = await Promise.allSettled(candidates.map(item =>
        String(item.agent_id).startsWith('agent_m3_')
          ? apiService.getOfferReview(String(item.review_id))
          : apiService.getReview(String(item.review_id))
      ));
      const records = detailed.flatMap(result => result.status === 'fulfilled' ? [reviewPayload(result.value)] : []);
      setReviews(records);
    } catch {
      setReviews([]);
    } finally { setLoadingReviews(false); }
  }, [selected]);

  useEffect(() => { void refreshDetail(); void refreshReviews(); }, [refreshDetail, refreshReviews]);

  const opportunityId = selected?.opportunity?.id;
  const session = selected?.session;
  const related = (agentId: string) => reviews.filter(review => review.agent_id === agentId && (
    (opportunityId && exactOpportunityId(review) === opportunityId)
    || (session && exactSessionId(review) === session.id)
  )).sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')));
  const latest = (agentId: string) => related(agentId)[0];
  const reviewId = (review?: Review) => review?.review_id ? String(review.review_id) : undefined;

  const technicalReview = latest('agent_m3_technique') ?? latest('agent_m3_complete');
  const financialReview = latest('agent_m3_financiere') ?? latest('agent_m3_complete');
  const tdrReview = latest('agent_m2_tdr');
  const trainer = session ? formateurs.find(item => item.id === session.formateurId) : undefined;
  const invoices = session ? factures.filter(invoice => invoice.sessionId === session.id) : [];
  const eligibleList = asArray(eligibility?.participants ?? eligibility?.data?.participants ?? eligibility?.eligibles);
  const attendanceKnown = eligibility != null && (eligibility?.success !== false);
  const eligibleCount = Number(eligibility?.total_eligible ?? eligibility?.eligible ?? eligibleList.filter((item: any) => item.eligible ?? item.eligibilite === 'eligible').length);
  const attestations = latest('agent_5_attestations');
  const report = latest('agent_6_report');

  const stages: Stage[] = selected ? [
    { title: 'Opportunité identifiée', detail: selected.opportunity ? `${selected.opportunity.entreprise} · ${selected.opportunity.domaineIA} · ${selected.opportunity.etape}` : 'Session sans opportunité rattachée par identifiant.', state: selected.opportunity ? 'done' : 'warning' },
    { title: 'TDR', detail: tdrReview ? `${statusLabel(tdrReview.status)} · ${tdrReview.summary ?? tdrReview.review_id}` : selected.opportunity ? 'Aucune revue TDR reliée à cette opportunité.' : 'Lien opportunité absent : TDR non rattachable automatiquement.', state: tdrReview?.status === 'approved' ? 'done' : tdrReview ? 'pending' : selected.opportunity ? 'pending' : 'warning', reviewId: reviewId(tdrReview) },
    { title: 'Offre technique', detail: offers.some(item => item.trame_technique) ? `${offers.filter(item => item.trame_technique).length} version(s) enregistrée(s) dans le Backend` : technicalReview ? `${statusLabel(technicalReview.status)} · ${technicalReview.summary ?? technicalReview.review_id}` : 'Aucune offre technique enregistrée ou revue IA reliée.', state: offers.some(item => item.trame_technique) ? 'done' : technicalReview ? technicalReview.status === 'approved' ? 'done' : 'pending' : selected.opportunity ? 'pending' : 'future', reviewId: reviewId(technicalReview) },
    { title: 'Offre financière', detail: offers.some(item => item.trame_financiere) ? `${offers.filter(item => item.trame_financiere).length} version(s) enregistrée(s) dans le Backend` : financialReview ? `${statusLabel(financialReview.status)} · ${financialReview.summary ?? financialReview.review_id}` : 'Aucune offre financière enregistrée ou revue IA reliée.', state: offers.some(item => item.trame_financiere) ? 'done' : financialReview ? financialReview.status === 'approved' ? 'done' : 'pending' : selected.opportunity ? 'pending' : 'future', reviewId: reviewId(financialReview) },
    { title: 'Formateur', detail: session ? trainer ? `${trainer.prenom ?? ''} ${trainer.nom}`.trim() : session.formateur !== 'À définir' ? `${session.formateur} · identifiant formateur non résolu` : 'Aucun formateur affecté à la session.' : 'À renseigner lors de la préparation de la session.', state: trainer || (session && session.formateur !== 'À définir') ? 'done' : session ? 'pending' : 'future' },
    { title: 'Session', detail: session ? `${session.intitule} · ${formatDate(session.dateDebut)} · ${session.lieu ?? 'Lieu à confirmer'} · ${session.statut}` : 'La session de formation n’est pas encore créée ou rattachée.', state: session ? 'done' : selected.opportunity ? 'pending' : 'warning' },
    { title: 'Participants et supports', detail: session ? `${participants.length} participant(s) inscrit(s) · ${supports.length} support(s), dont ${supports.filter(item => item.statut === 'indexe').length} indexé(s)` : 'Disponible après création de la session.', state: session && (participants.length > 0 || supports.length > 0) ? 'done' : session ? 'pending' : 'future' },
    { title: 'Présences et attestations', detail: session ? attendanceKnown ? `${eligibleCount} participant(s) éligible(s) selon le retour M6${attestations ? ` · attestation(s) ${statusLabel(attestations.status).toLowerCase()}` : ''}` : 'Éligibilité non chargée ou aucune donnée de présence disponible.' : 'Disponible après la formation.', state: attestations?.status === 'approved' ? 'done' : attendanceKnown ? 'pending' : 'future', reviewId: reviewId(attestations) },
    { title: 'Rapport final', detail: report ? `${statusLabel(report.status)} · ${report.summary ?? report.review_id}` : session ? 'Aucun rapport final relié à cette session.' : 'Disponible après la formation.', state: report?.status === 'approved' ? 'done' : report ? 'pending' : session?.statut === 'Terminée' ? 'pending' : 'future', reviewId: reviewId(report) },
    { title: 'Facturation', detail: session ? invoices.length ? `${invoices.length} document(s) de facturation lié(s) à la session` : 'Aucune facture liée à cette session.' : 'Disponible après création de la session.', state: invoices.length ? 'done' : session ? 'pending' : 'future' },
  ] : [];

  const filtered = dossiers.filter(dossier => {
    const text = `${dossier.opportunity?.entreprise ?? ''} ${dossier.opportunity?.besoinFormation ?? ''} ${dossier.session?.intitule ?? ''} ${dossier.session?.client ?? ''}`.toLocaleLowerCase();
    return text.includes(filter.toLocaleLowerCase());
  });
  const completed = stages.filter(stage => stage.state === 'done').length;
  const progress = stages.length ? Math.round(completed / stages.length * 100) : 0;
  const openReview = (reviewId?: string) => {
    if (!reviewId) return;
    try { sessionStorage.setItem('formaia-review-focus', reviewId); } catch { /* sessionStorage facultatif */ }
    onNavigateTo('espace_ia');
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800"><Workflow size={14} /> Pipeline de formation</div>
            <h1 className="text-2xl font-bold text-slate-900">Dossiers de formation</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">Suivez chaque dossier de l’opportunité jusqu’au rapport final. Les liens sont établis à partir des identifiants enregistrés dans FORMA-IA.</p>
          </div>
          <button onClick={() => { onRefreshData(); void refreshDetail(); void refreshReviews(); }} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><RefreshCw size={16} /> Actualiser</button>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric icon={<BriefcaseBusiness size={17} />} label="Opportunités" value={opportunites.length} />
          <Metric icon={<GraduationCap size={17} />} label="Sessions créées" value={sessions.length} />
          <Metric icon={<FileCheck2 size={17} />} label="Sessions terminées" value={sessions.filter(item => item.statut === 'Terminée').length} />
          <Metric icon={<WalletCards size={17} />} label="Dossiers suivis" value={dossiers.length} />
        </div>
      </section>

      <div className="grid min-h-[620px] gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-4">
            <div className="mb-3 flex items-center justify-between"><h2 className="font-bold text-slate-900">Tous les dossiers</h2><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{filtered.length}</span></div>
            <label className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2"><Search size={15} className="text-slate-400" /><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Client, formation…" className="w-full bg-transparent text-sm outline-none" /></label>
          </div>
          <div className="max-h-[680px] overflow-y-auto p-2">
            {filtered.map(dossier => {
              const active = selectedKey === dossier.key;
              const title = dossier.opportunity?.entreprise ?? dossier.session?.client ?? 'Session sans client';
              const subtitle = dossier.session?.intitule ?? dossier.opportunity?.besoinFormation ?? dossier.opportunity?.domaineIA ?? 'Besoin non précisé';
              return <button key={dossier.key} onClick={() => setSelectedKey(dossier.key)} className={`mb-1 w-full rounded-xl border p-3 text-left transition ${active ? 'border-emerald-200 bg-emerald-50/70' : 'border-transparent hover:border-slate-200 hover:bg-slate-50'}`}>
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="truncate text-sm font-bold text-slate-900">{title}</div><div className="mt-1 line-clamp-2 text-xs text-slate-600">{subtitle}</div></div><ArrowRight size={15} className={active ? 'mt-1 shrink-0 text-emerald-700' : 'mt-1 shrink-0 text-slate-300'} /></div>
                <div className="mt-3 flex flex-wrap gap-1.5"><Badge>{dossier.session ? dossier.session.statut : 'Sans session'}</Badge>{!dossier.opportunity && <Badge>Opportunité non liée</Badge>}</div>
              </button>;
            })}
            {!filtered.length && <div className="p-8 text-center text-sm text-slate-500">Aucun dossier ne correspond au filtre.</div>}
          </div>
        </aside>

        <section className="min-w-0 rounded-2xl border border-slate-200 bg-white shadow-sm">
          {!selected ? <div className="p-12 text-center text-slate-500">Aucune opportunité ou session à suivre.</div> : <>
            <div className="border-b border-slate-100 p-5 sm:p-6">
              <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                <div className="min-w-0"><div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{selected.opportunity ? `Dossier opportunité · ${selected.opportunity.etape}` : 'Dossier de session · lien opportunité absent'}</div><h2 className="mt-1 truncate text-xl font-bold text-slate-900">{selected.opportunity?.entreprise ?? selected.session?.client ?? 'Formation'}</h2><p className="mt-1 text-sm text-slate-600">{selected.session?.intitule ?? selected.opportunity?.besoinFormation ?? selected.opportunity?.domaineIA}</p></div>
                <div className="min-w-[170px] rounded-xl bg-slate-50 px-4 py-3"><div className="flex items-center justify-between text-xs text-slate-500"><span>Étapes confirmées</span><strong className="text-slate-800">{completed}/{stages.length}</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-emerald-600 transition-all" style={{ width: `${progress}%` }} /></div></div>
              </div>
              {detailError && <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertCircle size={15} /> {detailError}</div>}
            </div>
            {loadingDetail || loadingReviews ? <div className="flex items-center gap-2 p-5 text-sm text-slate-500"><Loader2 size={17} className="animate-spin" /> Chargement des éléments rattachés…</div> : null}
            <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_280px]">
              <div>
                <div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-slate-900">Avancement du pipeline</h3><span className="text-xs text-slate-500">Données enregistrées</span></div>
                <div className="space-y-0">
                  {stages.map((stage, index) => <div key={stage.title} className="relative flex gap-3 pb-5 last:pb-0">
                    {index < stages.length - 1 && <div className="absolute bottom-0 left-[15px] top-8 w-px bg-slate-200" />}
                    <div className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${stage.state === 'done' ? 'bg-emerald-100 text-emerald-700' : stage.state === 'warning' ? 'bg-amber-100 text-amber-700' : stage.state === 'pending' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>
                      {stage.state === 'done' ? <Check size={16} /> : stage.state === 'warning' ? <AlertCircle size={15} /> : stage.state === 'pending' ? <Clock3 size={15} /> : <Circle size={13} />}
                    </div>
                    <div className="min-w-0 flex-1 rounded-xl border border-slate-100 bg-white px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-slate-900">{stage.title}</h4><StageBadge state={stage.state} /></div>
                      <p className="mt-1 text-sm leading-5 text-slate-600">{stage.detail}</p>
                      {stage.reviewId && <button onClick={() => openReview(stage.reviewId)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-900">{stage.state === 'pending' ? 'Ouvrir la validation IA' : 'Consulter le contenu associé'} <ArrowRight size={13} /></button>}
                    </div>
                  </div>)}
                </div>
              </div>
              <div className="space-y-3">
                <h3 className="font-bold text-slate-900">Repères du dossier</h3>
                <InfoCard icon={<BriefcaseBusiness size={16} />} label="Opportunité" value={selected.opportunity?.id ?? 'Non rattachée'} />
                <InfoCard icon={<GraduationCap size={16} />} label="Session" value={session?.id ?? 'Pas encore créée'} />
                <InfoCard icon={<Users size={16} />} label="Participants" value={session ? `${participants.length} inscrit(s)` : 'Après création de session'} />
                <InfoCard icon={<BookOpen size={16} />} label="Supports indexés" value={session ? `${supports.filter(item => item.statut === 'indexe').length}/${supports.length}` : 'Après création de session'} />
                <InfoCard icon={<FileText size={16} />} label="Facturation" value={session ? `${invoices.length} document(s)` : 'Après création de session'} />
                {session && eligibility && <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><div className="text-xs font-semibold text-slate-500">Éligibilité attestations</div><div className="mt-1 text-lg font-bold text-slate-900">{Number.isFinite(eligibleCount) ? eligibleCount : '—'} <span className="text-sm font-medium text-slate-500">éligible(s)</span></div></div>}
                <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-3 text-xs leading-5 text-blue-900"><strong>Traçabilité :</strong> un élément n’est ajouté au dossier que si son opportunité ou sa session correspond par identifiant. Les ressemblances de titre ou de client ne créent pas de faux rattachement.</div>
              </div>
            </div>
          </>}
        </section>
      </div>
    </div>
  );
};

const Metric: React.FC<{ icon: React.ReactNode; label: string; value: number }> = ({ icon, label, value }) => <div className="rounded-xl border border-slate-100 bg-slate-50 p-3"><div className="flex items-center gap-2 text-xs font-medium text-slate-500">{icon}{label}</div><div className="mt-1 text-xl font-bold text-slate-900">{value}</div></div>;
const Badge: React.FC<{ children: React.ReactNode }> = ({ children }) => <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">{children}</span>;
const StageBadge: React.FC<{ state: Stage['state'] }> = ({ state }) => {
  const config = state === 'done' ? ['Confirmé', 'bg-emerald-50 text-emerald-700'] : state === 'pending' ? ['À traiter / vérifier', 'bg-blue-50 text-blue-700'] : state === 'warning' ? ['Lien à vérifier', 'bg-amber-50 text-amber-700'] : ['Étape ultérieure', 'bg-slate-100 text-slate-500'];
  return <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${config[1]}`}>{config[0]}</span>;
};
const InfoCard: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => <div className="flex items-start gap-3 rounded-xl border border-slate-100 p-3"><span className="mt-0.5 text-emerald-700">{icon}</span><div className="min-w-0"><div className="text-xs font-semibold text-slate-500">{label}</div><div className="mt-0.5 break-all text-sm font-medium text-slate-800">{value}</div></div></div>;
