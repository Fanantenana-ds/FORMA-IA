import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, ArrowRight, BookOpen, BriefcaseBusiness, CalendarDays, Check, CheckCircle2,
  Circle, Clock3, FileCheck2, FileText, GraduationCap, Loader2, RefreshCw,
  Search, Sparkles, Users, WalletCards, Workflow
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
  canManagePreparation: boolean;
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
  const projectInfo = inputs.projet_info ?? {};
  const value = data.opportunite_id ?? data.metadata?.opportunite_id ?? review.meta?.opportunite_id
    ?? brief.opportunite_id ?? sessionInfo.opportunite_id ?? tdrData.opportunite_id
    ?? projectInfo.opportunite_id;
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

export const DossiersFormationView: React.FC<Props> = ({ opportunites, sessions, formateurs, factures, onRefreshData, onNavigateTo, canManagePreparation }) => {
  const [selectedKey, setSelectedKey] = useState('');
  const [filter, setFilter] = useState('');
  const [offers, setOffers] = useState<any[]>([]);
  const [participants, setParticipants] = useState<any[]>([]);
  const [supports, setSupports] = useState<any[]>([]);
  const [eligibility, setEligibility] = useState<any>(null);
  const [preparationProject, setPreparationProject] = useState<any>(null);
  const [preparationBudget, setPreparationBudget] = useState<any>(null);
  const [preparationSchedule, setPreparationSchedule] = useState<any[]>([]);
  const [selectedOfferId, setSelectedOfferId] = useState('');
  const [preparationStartDate, setPreparationStartDate] = useState('');
  const [preparationEndDate, setPreparationEndDate] = useState('');
  const [preparationParticipants, setPreparationParticipants] = useState('');
  const [preparationTrainerRate, setPreparationTrainerRate] = useState('');
  const [preparationRoomRate, setPreparationRoomRate] = useState('');
  const [preparationBusy, setPreparationBusy] = useState(false);
  const [preparationError, setPreparationError] = useState('');
  const [preparationNotice, setPreparationNotice] = useState('');
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
  useEffect(() => {
    setOffers([]);
    setSelectedOfferId('');
    setPreparationStartDate('');
    setPreparationEndDate('');
    setPreparationParticipants(String(selected?.opportunity?.participantsEstimes || 1));
    setPreparationTrainerRate('');
    setPreparationRoomRate('');
    setPreparationError('');
    setPreparationNotice('');
  }, [selectedKey]);

  const refreshDetail = useCallback(async () => {
    if (!selected) return;
    setLoadingDetail(true); setDetailError('');
    setOffers([]); setParticipants([]); setSupports([]); setEligibility(null);
    setPreparationProject(null); setPreparationBudget(null); setPreparationSchedule([]);
    const sessionId = selected.session?.id;
    const opportunityId = selected.opportunity?.id;
    const tasks: Promise<any>[] = [
      opportunityId ? apiService.getOffersByOpportunity(opportunityId) : Promise.resolve({ data: [] }),
      sessionId ? apiService.getParticipants(sessionId) : Promise.resolve([]),
      sessionId ? apiService.getSupports({ session_id: sessionId }) : Promise.resolve({ data: [] }),
      sessionId ? apiService.getM6Eligibility(sessionId) : Promise.resolve(null),
      opportunityId ? apiService.getProjects() : Promise.resolve([]),
    ];
    const results = await Promise.allSettled(tasks);
    const errors = results.filter(result => result.status === 'rejected');
    if (results[0].status === 'fulfilled') {
      const loadedOffers = asArray(results[0].value, 'data').length ? asArray(results[0].value, 'data') : asArray(results[0].value, 'offres');
      setOffers(loadedOffers);
      const firstUsable = loadedOffers.find(item => item?.id && item?.trame_technique && item?.trame_financiere);
      setSelectedOfferId(firstUsable ? String(firstUsable.id) : '');
    }
    if (results[1].status === 'fulfilled') setParticipants(asArray(results[1].value, 'participants'));
    if (results[2].status === 'fulfilled') setSupports(asArray(results[2].value, 'data'));
    if (results[3].status === 'fulfilled') setEligibility(results[3].value);
    if (results[4].status === 'fulfilled') {
      const linkedProjects = asArray(results[4].value).filter(project => String(project.opportunite_id ?? '') === String(opportunityId ?? ''));
      linkedProjects.sort((a, b) => String(b.date_creation ?? '').localeCompare(String(a.date_creation ?? '')));
      const project = linkedProjects[0] ?? null;
      setPreparationProject(project);
      if (project) {
        const [budgetResult, scheduleResult] = await Promise.allSettled([
          apiService.getProjectBudget(String(project.id)),
          apiService.getProjectSchedule(String(project.id)),
        ]);
        if (budgetResult.status === 'fulfilled') setPreparationBudget(budgetResult.value);
        if (scheduleResult.status === 'fulfilled') setPreparationSchedule(asArray(scheduleResult.value));
      }
    }
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
      const relevantAgents = new Set(['agent_m2_tdr', 'agent_m3_technique', 'agent_m3_financiere', 'agent_m3_complete', 'agent_preparation', 'agent_5_attestations', 'agent_6_report']);
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
  const financialData = reviewData(financialReview);
  const financialDocument = financialData.offre_financiere ?? financialData;
  const financialCosts = financialDocument?.details_couts ?? {};
  const suggestedTrainerRate = Number(financialCosts.honoraires_formateur?.tarif_journalier ?? 0);
  const suggestedRoomRate = Number(financialCosts.location_salle?.tarif_journalier ?? 0);
  const preparationReview = latest('agent_preparation');
  const preparationData = reviewData(preparationReview);
  const estimatedBudget = preparationData.budget;
  const estimatedAdditionalCosts = Number(estimatedBudget?.cout_logistique ?? 0) + Number(estimatedBudget?.cout_administration ?? 0);
  const estimatedDays = asArray(preparationData.edt?.jours);
  const preparationCurrentStep = preparationProject || preparationReview?.status === 'approved'
    ? 3
    : preparationReview?.status === 'pending_review' ? 2 : 1;
  const tdrReview = latest('agent_m2_tdr');
  const usableOffers = offers.filter(item => item?.id && item?.trame_technique && item?.trame_financiere);
  const selectedOffer = usableOffers.find(item => String(item.id) === selectedOfferId);
  const technicalData = reviewData(technicalReview);
  const technicalDocument = technicalData.offre_technique ?? technicalData;
  const programmeModules = Array.isArray(technicalDocument?.programme?.modules)
    ? technicalDocument.programme.modules
      .filter((module: any) => module && (module.titre || module.nom))
      .map((module: any) => ({ titre: String(module.titre ?? module.nom), duree: String(module.duree ?? '3h') }))
    : [];

  useEffect(() => {
    if (suggestedTrainerRate > 0) setPreparationTrainerRate(current => current || String(suggestedTrainerRate));
    if (suggestedRoomRate > 0) setPreparationRoomRate(current => current || String(suggestedRoomRate));
  }, [selectedKey, suggestedTrainerRate, suggestedRoomRate]);
  const trainer = session ? formateurs.find(item => item.id === session.formateurId) : undefined;
  const invoices = session ? factures.filter(invoice => invoice.sessionId === session.id) : [];
  const indexedSupportCount = supports.filter(item => String(item.statut ?? '').toLowerCase() === 'indexe').length;
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
    { title: 'Préparation · budget et planning', detail: preparationProject ? `${preparationProject.titre} · budget ${preparationBudget?.valide ? 'validé' : 'à compléter ou valider'} · ${preparationSchedule.length} séance(s) au planning.` : preparationReview ? preparationReview.status === 'approved' ? 'Préparation approuvée par un responsable ; synchronisation Backend à effectuer.' : `${statusLabel(preparationReview.status)} · budget et planning proposés pour validation humaine.` : session && !selected.opportunity ? 'Session sans opportunité liée : le projet de préparation ne peut pas être rattaché par identifiant.' : 'Aucun projet de préparation lié à cette opportunité par identifiant.' , state: preparationProject ? preparationBudget?.valide && preparationSchedule.length > 0 ? 'done' : 'pending' : preparationReview?.status === 'rejected' ? 'warning' : preparationReview || selected.opportunity ? 'pending' : session ? 'warning' : 'future', reviewId: reviewId(preparationReview) },
    { title: 'Formateur', detail: session ? trainer ? `${trainer.prenom ?? ''} ${trainer.nom}`.trim() : session.formateur !== 'À définir' ? `${session.formateur} · identifiant formateur non résolu` : 'Aucun formateur affecté à la session.' : 'À renseigner lors de la préparation de la session.', state: trainer || (session && session.formateur !== 'À définir') ? 'done' : session ? 'pending' : 'future' },
    { title: 'Session', detail: session ? `${session.intitule} · ${formatDate(session.dateDebut)} · ${session.lieu ?? 'Lieu à confirmer'} · ${session.statut}` : 'La session de formation n’est pas encore créée ou rattachée.', state: session ? 'done' : selected.opportunity ? 'pending' : 'warning' },
    { title: 'Participants inscrits', detail: session ? participants.length ? `${participants.length} participant(s) rattaché(s) à cette session.` : 'Aucun participant inscrit pour le moment.' : 'Disponible après création de la session.', state: session && participants.length > 0 ? 'done' : session ? 'pending' : 'future' },
    { title: 'Supports pédagogiques · RAG', detail: session ? supports.length ? `${indexedSupportCount}/${supports.length} support(s) indexé(s) et exploitable(s) par le RAG.` : 'Aucun support pédagogique rattaché à cette session.' : 'Disponible après création de la session.', state: session && supports.length > 0 && indexedSupportCount === supports.length ? 'done' : session ? 'pending' : 'future' },
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

  const generatePreparation = async () => {
    if (!selected?.opportunity || !selectedOffer) return;
    const start = Date.parse(`${preparationStartDate}T12:00:00Z`);
    const end = Date.parse(`${preparationEndDate}T12:00:00Z`);
    const days = Math.floor((end - start) / 86400000) + 1;
    const participantsCount = Number(preparationParticipants);
    const trainerRate = Number(preparationTrainerRate.replace(',', '.'));
    const roomRate = Number(preparationRoomRate.replace(',', '.'));
    if (!Number.isFinite(start) || !Number.isFinite(end) || days < 1 || days > 30) {
      setPreparationError('Choisissez une période valide de 1 à 30 jours.');
      return;
    }
    if (!Number.isInteger(participantsCount) || participantsCount < 1 || participantsCount > 500) {
      setPreparationError('Le nombre de participants doit être compris entre 1 et 500.');
      return;
    }
    if (!(trainerRate > 0) || !(roomRate > 0)) {
      setPreparationError('Saisissez un tarif journalier positif pour le formateur et la salle.');
      return;
    }

    setPreparationBusy(true);
    setPreparationError('');
    setPreparationNotice('Génération du budget et du planning…');
    try {
      const result = await apiService.generatePreparation({
        offre_data: {
          id: selectedOffer.id,
          opportunite_id: selected.opportunity.id,
          reference: selectedOffer.reference ?? String(selectedOffer.id),
          titre: selectedOffer.titre || selected.opportunity.besoinFormation || 'Formation',
          duree_jours: days,
          modules: programmeModules,
        },
        projet_info: {
          client: selectedOffer.client || selected.opportunity.entreprise,
          nb_participants: participantsCount,
          opportunite_id: selected.opportunity.id,
          offre_id: selectedOffer.id,
        },
        ressources: {
          formateur: {
            nom: technicalDocument?.ressources?.formateur?.nom || 'Formateur à confirmer',
            tarif_journalier: trainerRate,
          },
          salle: { nom: 'Salle à confirmer', tarif_journalier: roomRate },
        },
        options: { date_debut: preparationStartDate, date_fin: preparationEndDate },
      });
      if (!result?.success || !result?.review_id) throw new Error(result?.message || 'La préparation n’a pas été créée.');
      setPreparationNotice('Budget et planning générés. La validation humaine est requise avant la synchronisation.');
      await refreshReviews();
    } catch (error) {
      setPreparationError(error instanceof Error ? error.message : 'Erreur pendant la génération de la préparation.');
      setPreparationNotice('');
    } finally {
      setPreparationBusy(false);
    }
  };

  const synchronizePreparation = async () => {
    const id = reviewId(preparationReview);
    if (!id || preparationReview?.status !== 'approved') return;
    setPreparationBusy(true);
    setPreparationError('');
    setPreparationNotice('Enregistrement du projet, du planning et du budget…');
    try {
      const result = await apiService.syncPreparation(id);
      if (!result?.success) throw new Error(result?.message || 'La synchronisation Backend a échoué.');
      setPreparationNotice(result.message || 'Préparation enregistrée dans le dossier.');
      await onRefreshData();
      await Promise.all([refreshDetail(), refreshReviews()]);
    } catch (error) {
      setPreparationError(error instanceof Error ? error.message : 'Erreur pendant la synchronisation Backend.');
      setPreparationNotice('');
    } finally {
      setPreparationBusy(false);
    }
  };

  const validatePreparationBudget = async () => {
    if (!preparationProject?.id || !preparationBudget) return;
    setPreparationBusy(true);
    setPreparationError('');
    setPreparationNotice('Validation du budget…');
    try {
      await apiService.saveProjectBudget(String(preparationProject.id), {
        cout_formateur: Number(preparationBudget.cout_formateur ?? 0),
        cout_salle: Number(preparationBudget.cout_salle ?? 0),
        cout_supports: Number(preparationBudget.cout_supports ?? 0),
        valide: true,
      });
      setPreparationNotice('Budget validé et enregistré.');
      await refreshDetail();
    } catch (error) {
      setPreparationError(error instanceof Error ? error.message : 'Erreur pendant la validation du budget.');
      setPreparationNotice('');
    } finally {
      setPreparationBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-brand-gold/15 px-3 py-1 text-xs font-semibold text-brand-navy"><Workflow size={14} className="text-brand-goldDark" /> Pipeline M1→M7</div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1F4D]/8 px-3 py-1 text-xs font-semibold text-[#0B1F4D]">M3 — Offre IA · Préparation · Budget · EDT</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Dossiers de formation</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">Suivez chaque dossier de l’opportunité jusqu’au rapport final — offres générées par IA, budget calculé automatiquement, emploi du temps planifié.</p>
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
              return <button key={dossier.key} onClick={() => setSelectedKey(dossier.key)} className={`mb-1 w-full rounded-xl border p-3 text-left transition ${active ? 'border-brand-gold/70 bg-brand-gold/10' : 'border-transparent hover:border-slate-200 hover:bg-slate-50'}`}>
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="truncate text-sm font-bold text-slate-900">{title}</div><div className="mt-1 line-clamp-2 text-xs text-slate-600">{subtitle}</div></div><ArrowRight size={15} className={active ? 'mt-1 shrink-0 text-brand-goldDark' : 'mt-1 shrink-0 text-slate-300'} /></div>
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
                <div className="min-w-[170px] rounded-xl bg-slate-50 px-4 py-3"><div className="flex items-center justify-between text-xs text-slate-500"><span>Étapes confirmées</span><strong className="text-slate-800">{completed}/{stages.length}</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-brand-gold transition-all" style={{ width: `${progress}%` }} /></div></div>
              </div>
              {detailError && <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertCircle size={15} /> {detailError}</div>}
            </div>
            {loadingDetail || loadingReviews ? <div className="flex items-center gap-2 p-5 text-sm text-slate-500"><Loader2 size={17} className="animate-spin" /> Chargement des éléments rattachés…</div> : null}
            <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_280px]">
              <div>
                <div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-slate-900">Avancement du pipeline</h3><span className="text-xs text-slate-500">États confirmés par les données liées</span></div>
                <div className="space-y-0">
                  {stages.map((stage, index) => <div key={stage.title} className="relative flex gap-3 pb-5 last:pb-0">
                    {index < stages.length - 1 && <div className="absolute bottom-0 left-[15px] top-8 w-px bg-slate-200" />}
                    <div className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${stage.state === 'done' ? 'bg-emerald-100 text-emerald-700' : stage.state === 'warning' ? 'bg-amber-100 text-amber-700' : stage.state === 'pending' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>
                      {stage.state === 'done' ? <Check size={16} /> : stage.state === 'warning' ? <AlertCircle size={15} /> : stage.state === 'pending' ? <Clock3 size={15} /> : <Circle size={13} />}
                    </div>
                    <div className="min-w-0 flex-1 rounded-xl border border-slate-100 bg-white px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-slate-900">{stage.title}</h4><StageBadge state={stage.state} /></div>
                      <p className="mt-1 text-sm leading-5 text-slate-600">{stage.detail}</p>
                      {stage.reviewId && <button onClick={() => openReview(stage.reviewId)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-navy hover:text-brand-goldDark">{stage.state === 'pending' ? 'Ouvrir la validation IA' : 'Consulter le contenu associé'} <ArrowRight size={13} /></button>}
                    </div>
                  </div>)}
                </div>
                {selected.opportunity && canManagePreparation && <section className="mt-6 overflow-hidden rounded-2xl border border-brand-navy/10 bg-white shadow-md shadow-brand-navy/5">
                  <div className="relative overflow-hidden bg-gradient-to-r from-brand-darkNavy via-brand-navy to-[#12336f] px-4 py-5 text-white sm:px-5">
                    <div className="pointer-events-none absolute -right-8 -top-12 h-36 w-36 rounded-full border border-brand-gold/30" />
                    <div className="pointer-events-none absolute -right-2 -top-6 h-24 w-24 rounded-full border border-brand-gold/20" />
                    <div className="relative flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-brand-gold/40 bg-brand-gold/15 text-brand-goldLight"><CalendarDays size={20} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-2"><span className="text-[10px] font-bold uppercase tracking-[0.16em] text-brand-goldLight">Étape 3 · Pipeline de formation</span><span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white/90">Préparation</span></div>
                        <h3 className="text-lg font-bold tracking-tight sm:text-xl">Préparer la formation</h3>
                        <p className="mt-1 max-w-2xl text-sm leading-5 text-slate-200">Transformez l’offre retenue en budget et planning, faites-les approuver, puis enregistrez-les dans le dossier.</p>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4 p-4 sm:p-5">
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-3" aria-label="Étapes de préparation">
                      {[
                        { title: 'Paramètres', description: 'Offre, dates, coûts' },
                        { title: 'Approbation', description: 'Vérification humaine' },
                        { title: 'Enregistrement', description: 'Dossier Backend' },
                      ].map((item, index) => {
                        const step = index + 1;
                        const isDone = step < preparationCurrentStep || (step === 3 && Boolean(preparationProject));
                        const isCurrent = step === preparationCurrentStep && !isDone;
                        return <div key={item.title} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors ${isDone ? 'border-emerald-200 bg-emerald-50/70' : isCurrent ? 'border-brand-gold/60 bg-brand-gold/10' : 'border-slate-200 bg-slate-50/70'}`}>
                          <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${isDone ? 'bg-emerald-600 text-white' : isCurrent ? 'bg-brand-navy text-brand-goldLight ring-2 ring-brand-gold/30' : 'bg-slate-200 text-slate-500'}`}>{isDone ? <Check size={15} /> : `0${step}`}</span>
                          <span className="min-w-0"><span className={`block text-xs font-bold ${isDone ? 'text-emerald-900' : isCurrent ? 'text-brand-navy' : 'text-slate-600'}`}>{item.title}</span><span className="mt-0.5 block text-[11px] text-slate-500">{item.description}</span></span>
                        </div>;
                      })}
                    </div>

                  {preparationError && <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-800"><AlertCircle size={16} className="mt-0.5 shrink-0" /><span>{preparationError}</span></div>}
                  {preparationNotice && <div role="status" className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-sm text-emerald-800"><CheckCircle2 size={16} className="mt-0.5 shrink-0" /><span>{preparationNotice}</span></div>}

                  {preparationProject ? <div className="rounded-xl border border-brand-navy/10 bg-gradient-to-br from-white to-slate-50/80 p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0"><div className="text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-700">Projet enregistré</div><div className="mt-1 font-bold text-brand-navy">{preparationProject.titre}</div><div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600"><span className="rounded-full border border-slate-200 bg-white px-2.5 py-1">{preparationSchedule.length} séance(s)</span><span className="rounded-full border border-brand-gold/30 bg-brand-gold/10 px-2.5 py-1 font-semibold text-brand-navy">Budget Backend · {Number(preparationBudget?.cout_total ?? 0).toLocaleString('fr-FR')} Ar</span></div></div>
                      {!preparationBudget?.valide && preparationBudget && <button type="button" disabled={preparationBusy} onClick={() => void validatePreparationBudget()} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-gold px-4 py-2 text-sm font-bold text-brand-darkNavy shadow-sm transition hover:-translate-y-0.5 hover:bg-brand-goldDark hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto">{preparationBusy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Valider le budget</button>}
                      {preparationBudget?.valide && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700"><CheckCircle2 size={14} /> Budget validé</span>}
                    </div>
                    {estimatedBudget?.cout_total != null && <p className="mt-4 rounded-xl border border-brand-gold/20 bg-brand-gold/5 px-3.5 py-3 text-xs leading-5 text-slate-600"><span className="font-bold text-brand-navy">Estimation complète approuvée : {Number(estimatedBudget.cout_total).toLocaleString('fr-FR')} Ar.</span> Le budget du Backend enregistre les honoraires, la salle et les supports.{estimatedAdditionalCosts > 0 ? ` Les frais logistiques et administratifs (${estimatedAdditionalCosts.toLocaleString('fr-FR')} Ar) restent détaillés dans la préparation approuvée.` : ''}</p>}
                  </div> : preparationReview?.status === 'pending_review' ? <div className="rounded-xl border border-brand-navy/15 bg-brand-navy/[0.035] p-4">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><div className="font-bold text-brand-navy">Préparation en attente de validation humaine</div><p className="mt-1 text-sm text-slate-600">{estimatedBudget?.cout_total != null ? `Budget estimé : ${Number(estimatedBudget.cout_total).toLocaleString('fr-FR')} Ar · ` : ''}${estimatedDays.length} jour(s) proposé(s) au planning.</p></div><button type="button" onClick={() => openReview(reviewId(preparationReview))} className="inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 rounded-lg bg-brand-navy px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-brand-darkNavy hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 sm:w-auto">Ouvrir la validation IA <ArrowRight size={15} /></button></div>
                  </div> : preparationReview?.status === 'approved' ? <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-4">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><div className="font-bold text-emerald-950">Préparation approuvée</div><p className="mt-1 text-sm text-emerald-900">Le projet, le planning et le budget peuvent maintenant être enregistrés dans le Backend.</p></div><button type="button" disabled={preparationBusy} onClick={() => void synchronizePreparation()} className="inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 rounded-lg bg-brand-gold px-4 py-2 text-sm font-bold text-brand-darkNavy shadow-sm transition hover:-translate-y-0.5 hover:bg-brand-goldDark hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto">{preparationBusy ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />} Enregistrer la préparation</button></div>
                  </div> : <>
                    {preparationReview?.status === 'rejected' && <div className="rounded-xl border border-brand-gold/40 bg-brand-gold/10 px-3.5 py-3 text-sm text-brand-navy"><strong>Proposition refusée.</strong> Corrigez les paramètres puis générez une nouvelle version.</div>}
                    {!usableOffers.length ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm text-slate-700">{offers.length ? 'Les offres présentes ne contiennent pas encore les volets technique et financier enregistrés.' : 'Aucune offre n’est encore enregistrée pour cette opportunité.'} Terminez d’abord la génération et l’enregistrement de l’offre complète.</p><button type="button" onClick={() => onNavigateTo('opportunites_crm')} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-navy hover:text-brand-goldDark">Ouvrir les offres <ArrowRight size={14} /></button>
                    </div> : <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 sm:p-4">
                      <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-end"><div><h4 className="text-sm font-bold text-brand-navy">Paramètres du budget et du planning</h4><p className="mt-1 text-xs text-slate-500">Les montants suggérés viennent de la proposition financière et restent modifiables.</p></div><span className="text-[10px] font-semibold uppercase tracking-wide text-brand-goldDark">Champs requis · * </span></div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20 sm:col-span-2">Offre enregistrée *
                        <select required value={selectedOfferId} onChange={event => setSelectedOfferId(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25">
                          <option value="">Sélectionner une offre</option>{usableOffers.map(item => <option key={item.id} value={String(item.id)}>{item.titre || `Offre ${item.id}`} · {item.statut || 'enregistrée'}</option>)}
                        </select>
                      </label>
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20">Date de début *<input required type="date" value={preparationStartDate} onChange={event => setPreparationStartDate(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25" /></label>
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20">Date de fin *<input required type="date" min={preparationStartDate || undefined} value={preparationEndDate} onChange={event => setPreparationEndDate(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25" /></label>
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20">Participants *<input required type="number" min="1" max="500" value={preparationParticipants} onChange={event => setPreparationParticipants(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25" /></label>
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20">Tarif formateur / jour (Ar) *<input required type="number" min="1" value={preparationTrainerRate} onChange={event => setPreparationTrainerRate(event.target.value)} placeholder="Ex. 500000" className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25" />{suggestedTrainerRate > 0 && <span className="mt-2 block font-normal text-slate-500">Suggestion reprise de la proposition financière IA.</span>}</label>
                      <label className="rounded-xl border border-slate-200 bg-white p-3.5 text-xs font-bold text-slate-700 transition hover:border-brand-gold/60 focus-within:border-brand-gold focus-within:ring-2 focus-within:ring-brand-gold/20">Tarif salle / jour (Ar) *<input required type="number" min="1" value={preparationRoomRate} onChange={event => setPreparationRoomRate(event.target.value)} placeholder="Ex. 200000" className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-brand-navy outline-none transition focus:border-brand-goldDark focus:ring-2 focus:ring-brand-gold/25" />{suggestedRoomRate > 0 && <span className="mt-2 block font-normal text-slate-500">Suggestion reprise de la proposition financière IA.</span>}</label>
                      <div className="flex flex-col gap-2 sm:col-span-2 sm:flex-row sm:items-center sm:justify-between"><p className="max-w-xl text-xs leading-5 text-slate-500">Le planning inclut chaque jour calendaire entre les dates. Vérifiez les séances et le budget dans l’espace de validation IA.</p><button type="button" disabled={preparationBusy || !selectedOfferId} onClick={() => void generatePreparation()} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand-gold px-5 py-2.5 text-sm font-extrabold text-brand-darkNavy shadow-sm transition hover:-translate-y-0.5 hover:bg-brand-goldDark hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy focus-visible:ring-offset-2 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto">{preparationBusy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Générer budget et planning</button></div>
                      </div>
                    </div>}
                  </>}
                  </div>
                </section>}
                {selected.opportunity && !canManagePreparation && <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">La préparation est consultable ici. Sa génération et sa validation sont réservées à la Direction et à l’Assistant.</div>}
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
const InfoCard: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => <div className="flex items-start gap-3 rounded-xl border border-slate-100 p-3"><span className="mt-0.5 text-brand-goldDark">{icon}</span><div className="min-w-0"><div className="text-xs font-semibold text-slate-500">{label}</div><div className="mt-0.5 break-all text-sm font-medium text-slate-800">{value}</div></div></div>;
