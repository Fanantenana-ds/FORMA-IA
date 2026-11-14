import React, { useEffect, useMemo, useState } from 'react';
import {
  Star,
  Mail,
  Phone,
  MapPin,
  Plus,
  X,
  Search,
  Award,
  UserPlus,
  Pencil,
  Trash2,
  Loader2,
  AlertTriangle,
  Lock,
  CheckCircle2,
  Sparkles,
  FileUp,
  ClipboardList,
  FileSignature,
  CalendarDays,
  GraduationCap
} from 'lucide-react';
import { PageHeader } from '../PageHeader';
import { Formateur, StatutFormateur, Session, OpportuniteCRM } from '../../types';
import { apiService, ApiError } from '../../services/api';
import {
  EMPTY_FORMATEUR_FORM,
  STATUT_LABELS,
  formValuesFromFormateur,
  formateurFullName,
  specialitesList,
  toCreatePayload,
  toUpdatePayload
} from '../../services/formateurMapping';
import type { FormateurFormValues } from '../../services/formateurMapping';

interface FormateursStaffViewProps {
  formateurs: Formateur[];
  /** Seule la Direction peut créer, modifier ou supprimer. */
  canManage: boolean;
  /** Recharge les données de l'application après une modification. */
  onRefreshData?: () => Promise<void> | void;
  sessions: Session[];
  opportunites?: OpportuniteCRM[];
}

const describeError = (err: unknown): string => {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (err.status === 401) return 'Votre session a expiré. Veuillez vous reconnecter.';
    if (err.status === 403) return "Votre rôle ne permet pas cette action (réservée à la Direction).";
    if (err.status === 404) return "Ce formateur n'existe plus. La liste va être actualisée.";
    if (err.status === 422) return `Informations invalides : ${err.message}`;
    if (err.status >= 500) return `Erreur du serveur : ${err.message}`;
    return err.message;
  }
  return 'Une erreur inattendue est survenue.';
};

const statutStyle = (statut: StatutFormateur): string =>
  statut === 'Disponible'
    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
    : statut === 'En session'
    ? 'bg-amber-100 text-amber-800 border border-amber-200'
    : 'bg-slate-100 text-slate-700 border border-slate-200';

const scoreStyle = (score: number): string =>
  score >= 75 ? 'text-emerald-700' : score >= 50 ? 'text-amber-700' : 'text-red-600';

const recommandationStyle = (reco: string): string => {
  const r = reco.toLowerCase();
  return r === 'oui'
    ? 'bg-emerald-100 text-emerald-800'
    : r === 'non'
    ? 'bg-red-100 text-red-700'
    : 'bg-amber-100 text-amber-800';
};

const inputClass =
  'w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#0B1F4D] focus:outline-none';

export const FormateursStaffView: React.FC<FormateursStaffViewProps> = ({
  formateurs,
  canManage,
  onRefreshData,
  sessions,
  opportunites = []
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statutFilter, setStatutFilter] = useState<'Tous' | StatutFormateur>('Tous');

  // Formulaire : null = fermé, 'new' = création, sinon le formateur modifié
  const [editing, setEditing] = useState<'new' | Formateur | null>(null);
  const [form, setForm] = useState<FormateurFormValues>(EMPTY_FORMATEUR_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<Formateur | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [pageError, setPageError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [candidateBusyId, setCandidateBusyId] = useState('');
  const [candidatePanelError, setCandidatePanelError] = useState('');
  const [newTrainerAccount, setNewTrainerAccount] = useState<{ email: string; password: string } | null>(null);
  const [candidateCv, setCandidateCv] = useState<any>(null);
  const [interviewPack, setInterviewPack] = useState<any>(null);
  const [interviewBusyId, setInterviewBusyId] = useState('');
  const [cvFiles, setCvFiles] = useState<File[]>([]);
  const [cvRole, setCvRole] = useState('Formateur');
  const [cvDomain, setCvDomain] = useState('');
  const [cvSkills, setCvSkills] = useState('');
  const [cvResults, setCvResults] = useState<any[]>([]);
  const [selectedTrainerId, setSelectedTrainerId] = useState('');
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [contractBusy, setContractBusy] = useState(false);
  const [contractReview, setContractReview] = useState('');
  const [evalScore, setEvalScore] = useState('');
  const [evalAttendance, setEvalAttendance] = useState('');
  const [evaluationBusy, setEvaluationBusy] = useState(false);
  const [approvedContracts, setApprovedContracts] = useState<any[]>([]);
  const [emailBusyId, setEmailBusyId] = useState('');
  const [emailDraft, setEmailDraft] = useState<{ candidate: any; reviewId: string; type: string; email: string; subject: string; body: string; approved: boolean } | null>(null);
  const [unverifiedCandidateIds, setUnverifiedCandidateIds] = useState<Set<string>>(new Set());

  const refreshCandidates = async () => {
    const rows = await apiService.getCandidates();
    setCandidates(rows);
    const oldScores = rows.filter((candidate: any) => candidate.score_preselection === 50 && candidate.review_id_preselection);
    const reviews = await Promise.allSettled(oldScores.map((candidate: any) => apiService.getReview(candidate.review_id_preselection)));
    setUnverifiedCandidateIds(new Set(oldScores.filter((_: any, index: number) => {
      const result = reviews[index];
      return result.status === 'fulfilled' && (result.value.review ?? result.value).data?.metadata?.source === 'fallback_template';
    }).map((candidate: any) => String(candidate.id))));
  };
  useEffect(() => { if (canManage) void refreshCandidates().catch(e => setCandidatePanelError(e.message)); }, [canManage]);
  useEffect(() => { if (canManage) void apiService.getApprovedTrainerContracts().then((r:any)=>setApprovedContracts(r.reviews ?? [])).catch(()=>setApprovedContracts([])); }, [canManage, contractReview]);
  const decideCandidate = async (candidate: any, decision: 'ACCEPTER' | 'REFUSER') => {
    setCandidateBusyId(String(candidate.id)); setCandidatePanelError('');
    try {
      const result: any = await apiService.decideCandidate(String(candidate.id), decision);
      await refreshCandidates(); await onRefreshData?.();
      if (decision === 'ACCEPTER' && result.compte_formateur?.mot_de_passe_initial) {
        setNewTrainerAccount({ email: result.compte_formateur.email, password: result.compte_formateur.mot_de_passe_initial });
        setSuccessMsg('Candidat accepté, formateur affecté à sa session et compte de connexion créé.');
      } else setSuccessMsg(decision === 'ACCEPTER' ? 'Candidat accepté et formateur affecté à sa session.' : 'Candidature refusée.');
    }
    catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'La décision n’a pas été enregistrée.'); }
    finally { setCandidateBusyId(''); }
  };
  const openCandidateCv = async (id:string) => { try { setCandidateCv(await apiService.getCandidateCv(id)); } catch(e) { setCandidatePanelError(e instanceof Error?e.message:'Lecture du CV impossible.'); } };
  const candidateCriteria = (candidate: any) => {
    const session = sessions.find(item => item.id === candidate.session_id);
    const offer = opportunites.find(item => item.id === session?.opportuniteId);
    return {
      poste: candidate.poste_vise || session?.intitule || 'Formateur',
      domaine: offer?.domaineIA || session?.domaine || candidate.poste_vise || 'Formation',
      competences: [candidate.poste_vise, session?.domaine].filter(Boolean),
      formation: session?.intitule || '',
      formation_domaine: session?.domaine || '',
      offre_description: offer?.besoinFormation || session?.intitule || ''
    };
  };
  const reanalyzeCandidate = async (candidate: any) => {
    setInterviewBusyId(String(candidate.id)); setCandidatePanelError('');
    try {
      const cv = await apiService.getCandidateCv(String(candidate.id));
      const cvText = String(cv.cv_texte ?? cv.texte ?? '').trim();
      if (cvText.length < 50) throw new Error('Le texte du CV est absent ou trop court pour une analyse fiable.');
      const generated = await apiService.preselectTrainerCv({ cv_texte: cvText, criteres_poste: candidateCriteria(candidate) });
      const data = generated.data ?? generated;
      const reviewId = generated.review_id ?? data._review_id;
      const analyzed = data.metadata?.source === 'llm' && typeof data.score_global === 'number';
      if (analyzed && reviewId) {
        await apiService.updateCandidate(String(candidate.id), { score_preselection: data.score_global, review_id_preselection: reviewId });
        await refreshCandidates();
      } else setUnverifiedCandidateIds(previous => new Set(previous).add(String(candidate.id)));
      setInterviewPack({ candidate, reviewId, score: analyzed ? data.score_global : null, decision: analyzed ? data.decision : null, summary: analyzed ? data.synthese : 'Analyse IA indisponible. Aucun score ni question ne peut être attribué automatiquement. Vérifiez le CV et relancez l’analyse.', questions: analyzed && Array.isArray(data.questions_entretien) ? data.questions_entretien : [], source: data.metadata?.source });
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'Impossible de relancer l’analyse du CV.'); }
    finally { setInterviewBusyId(''); }
  };
  const openInterviewQuestions = async (candidate: any) => {
    setInterviewBusyId(String(candidate.id)); setCandidatePanelError('');
    try {
      let review: any = null;
      let reviewId = candidate.review_id_preselection;
      if (reviewId) {
        const response = await apiService.getReview(reviewId);
        review = response.review ?? response;
      } else { await reanalyzeCandidate(candidate); return; }
      const payload = review?.data ?? review?.review?.data ?? {};
      const analyzed = payload.metadata?.source !== 'fallback_template' && typeof payload.score_global === 'number';
      const questions = analyzed ? payload.questions_entretien ?? payload.questions ?? [] : [];
      setInterviewPack({ candidate, reviewId, score: analyzed ? payload.score_global : null, decision: analyzed ? payload.decision : null, summary: analyzed ? payload.synthese : 'Analyse IA indisponible. Le score et les questions génériques précédents ne constituent pas une évaluation de ce CV.', questions: Array.isArray(questions) ? questions : [], source: payload.metadata?.source });
      if (!analyzed) setUnverifiedCandidateIds(previous => new Set(previous).add(String(candidate.id)));
      if (analyzed && !questions.length) setCandidatePanelError('L’analyse n’a pas fourni de questions ciblées. Relancez-la avec le CV et la formation liée.');
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'Impossible de charger les questions d’entretien.'); }
    finally { setInterviewBusyId(''); }
  };
  const downloadCandidateCv = async (id:string, filename:string) => { try { const blob=await apiService.downloadCandidateCv(id);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename||'cv-candidat';a.click();URL.revokeObjectURL(url); } catch(e) { setCandidatePanelError(e instanceof Error?e.message:'Téléchargement du CV impossible.'); } };

  const analyzeCvFiles = async () => {
    if (!cvFiles.length) { setCandidatePanelError('Sélectionnez un ou plusieurs CV à analyser.'); return; }
    setCandidateBusyId('bulk'); setCandidatePanelError(''); setCvResults([]);
    const results: any[] = [];
    try {
      for (const file of cvFiles) {
        try {
          const response = await apiService.analyzeTrainerCv(file, { poste: cvRole, domaine: cvDomain || cvRole, competences: cvSkills.split(',').map(s => s.trim()).filter(Boolean) });
          const data = response?.data ?? response;
          results.push({ filename: file.name, reviewId: response?.review_id ?? data?._review_id, ...data, questions_entretien: data?.questions_entretien ?? data?.questions });
        } catch (e) { results.push({ filename: file.name, error: e instanceof Error ? e.message : 'Analyse impossible' }); }
      }
      setCvResults(results.sort((a,b) => Number(b.score_global ?? b.score ?? 0) - Number(a.score_global ?? a.score ?? 0)));
      flash(`${results.filter(r => !r.error).length}/${results.length} CV analysé(s). Les fiches sont soumises au HITL dans l’Espace IA.`);
      setCvFiles([]);
    } finally { setCandidateBusyId(''); }
  };

  const createContract = async () => {
    const trainer = formateurs.find(f => f.id === selectedTrainerId);
    const session = sessions.find(s => s.id === selectedSessionId);
    if (!trainer || !session) { setCandidatePanelError('Choisissez un formateur et une session.'); return; }
    if (!(trainer.tarifJournalier && trainer.tarifJournalier > 0)) { setCandidatePanelError('Renseignez d’abord le tarif journalier du formateur.'); return; }
    const dates = [session.dateDebut, session.dateFin].filter(Boolean) as string[];
    if (!dates.length) { setCandidatePanelError('La session doit avoir une date de début pour préparer le contrat.'); return; }
    const start = new Date(`${dates[0]}T12:00:00`); const end = new Date(`${dates[dates.length - 1]}T12:00:00`);
    const days = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / 86400000) + 1);
    setContractBusy(true); setCandidatePanelError('');
    try {
      const result = await apiService.generateTrainerContract({ formateur: { nom: formateurFullName(trainer), adresse: trainer.adresse, telephone: trainer.telephone, email: trainer.email, tarif_journalier: trainer.tarifJournalier }, session: { titre: session.intitule, dates, nb_jours: days, lieu: session.lieu || 'Antananarivo', nb_participants: session.participantsInscrits, description: session.domaine } });
      const reviewId = result.review_id ?? result.data?._review_id;
      setContractReview(reviewId ?? '');
      flash(`Contrat généré pour ${formateurFullName(trainer)} — ${session.intitule}. Validation obligatoire dans l’Espace IA${reviewId ? ` (${reviewId})` : ''}.`);
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'La génération du contrat a échoué.'); }
    finally { setContractBusy(false); }
  };

  const generateEvaluationReport = async () => {
    const trainer = formateurs.find(f => f.id === selectedTrainerId); const session = sessions.find(s => s.id === selectedSessionId);
    if (!trainer || !session || !evalScore || !evalAttendance) { setCandidatePanelError('Choisissez un formateur, une session et renseignez les données M5 de satisfaction et de présence.'); return; }
    setEvaluationBusy(true); setCandidatePanelError('');
    try {
      const result = await apiService.analyzeTrainerEvaluation({ formateur: formateurFullName(trainer), formateur_id: trainer.id, session: session.intitule, donnees_session: { satisfaction: { score_moyen: Number(evalScore), points_positifs: [], points_negatifs: [] }, presences: { taux_moyen_pct: Number(evalAttendance), anomalies: false }, rapport: `Synthèse M5 de la session ${session.intitule}` } });
      const id = result.review_id ?? result.data?._review_id;
      flash(`Rapport d’évaluation généré${id ? ` (${id})` : ''} et envoyé au circuit HITL. Après approbation, la synthèse sera visible dans Évaluation compétences.`);
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'La génération du rapport a échoué.'); }
    finally { setEvaluationBusy(false); }
  };

  const prepareHrEmail = async (candidate: any, type: 'CONVOCATION'|'ACCEPTATION'|'REFUS') => {
    setEmailBusyId(String(candidate.id)); setCandidatePanelError('');
    try {
      const name = `${candidate.prenom ?? ''} ${candidate.nom ?? ''}`.trim();
      const result = await apiService.draftTrainerEmail({ type_email: type, destinataire: name, contexte: { email: candidate.email, poste: candidate.poste_vise, session_id: candidate.session_id, session: sessions.find(s=>s.id===candidate.session_id)?.intitule } });
      const data = result.data ?? {};
      if (!result.success || !result.review_id || !data.objet || !data.corps) throw new Error('Le brouillon est incomplet. Aucun e-mail n’a été envoyé.');
      setEmailDraft({ candidate, reviewId: result.review_id, type, email: String(candidate.email ?? ''), subject: String(data.objet), body: String(data.corps), approved: false });
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'Le brouillon RH n’a pas pu être généré.'); }
    finally { setEmailBusyId(''); }
  };
  const saveHrEmailDraft = async () => {
    if (!emailDraft || emailDraft.approved) return;
    if (!emailDraft.subject.trim() || !emailDraft.body.trim()) { setCandidatePanelError('Renseignez l’objet et le message avant de sauvegarder.'); return; }
    setEmailBusyId(String(emailDraft.candidate.id)); setCandidatePanelError('');
    try {
      await apiService.updateTrainerEmailDraft(emailDraft.reviewId, { objet: emailDraft.subject.trim(), corps: emailDraft.body.trim() });
      flash('Brouillon enregistré. Aucun e-mail n’a été envoyé.');
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'Enregistrement du brouillon impossible.'); }
    finally { setEmailBusyId(''); }
  };
  const sendHrEmailDraft = async () => {
    if (!emailDraft) return;
    if (!emailDraft.email.trim() || !emailDraft.subject.trim() || !emailDraft.body.trim()) { setCandidatePanelError('Vérifiez le destinataire, l’objet et le message avant l’envoi.'); return; }
    setEmailBusyId(String(emailDraft.candidate.id)); setCandidatePanelError('');
    try {
      if (!emailDraft.approved) {
        await apiService.updateTrainerEmailDraft(emailDraft.reviewId, { objet: emailDraft.subject.trim(), corps: emailDraft.body.trim() });
        await apiService.approveReview(emailDraft.reviewId, 'Brouillon relu et validé dans la fiche candidat.');
        setEmailDraft(previous => previous ? { ...previous, approved: true } : null);
      }
      await apiService.sendTrainerEmail(emailDraft.reviewId, emailDraft.email.trim());
      setEmailDraft(null);
      flash(`E-mail envoyé à ${emailDraft.email.trim()}.`);
    } catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'L’envoi de l’e-mail a échoué. Le brouillon reste consultable ici.'); }
    finally { setEmailBusyId(''); }
  };

  const downloadApprovedContract = async (reviewId: string) => {
    try { const blob = await apiService.downloadTrainerContract(reviewId); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `contrat_formateur_${reviewId}.docx`; link.click(); URL.revokeObjectURL(url); }
    catch (e) { setCandidatePanelError(e instanceof Error ? e.message : 'Téléchargement du contrat impossible.'); }
  };

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return formateurs.filter((f) => {
      if (statutFilter !== 'Tous' && f.statut !== statutFilter) return false;
      if (!term) return true;
      return (
        formateurFullName(f).toLowerCase().includes(term) ||
        (f.email?.toLowerCase().includes(term) ?? false) ||
        (f.specialite?.toLowerCase().includes(term) ?? false)
      );
    });
  }, [formateurs, searchTerm, statutFilter]);

  const evalues = formateurs.filter((f) => f.scoreMoyen !== undefined);
  const scoreMoyenGlobal = evalues.length
    ? evalues.reduce((acc, f) => acc + (f.scoreMoyen ?? 0), 0) / evalues.length
    : null;
  const disponibles = formateurs.filter((f) => f.statut === 'Disponible').length;

  const openCreate = () => {
    setForm(EMPTY_FORMATEUR_FORM);
    setFormError(null);
    setEditing('new');
  };

  const openEdit = (f: Formateur) => {
    setForm(formValuesFromFormateur(f));
    setFormError(null);
    setEditing(f);
  };

  const closeForm = () => {
    if (isSaving) return;
    setEditing(null);
  };

  const setField = <K extends keyof FormateurFormValues>(key: K, value: FormateurFormValues[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const flash = (message: string) => {
    setSuccessMsg(message);
    setTimeout(() => setSuccessMsg(null), 4000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;

    if (form.nom.trim().length < 2) {
      setFormError('Le nom doit contenir au moins 2 caractères.');
      return;
    }
    if (form.tarifJournalier.trim() && !(parseFloat(form.tarifJournalier.replace(',', '.')) > 0)) {
      setFormError('Le tarif journalier doit être un nombre strictement positif.');
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      if (editing === 'new') {
        const created = await apiService.createFormateur(toCreatePayload(form));
        flash(`Formateur « ${formateurFullName(created)} » ajouté.`);
      } else {
        const updated = await apiService.updateFormateur(editing.id, toUpdatePayload(form));
        flash(`Formateur « ${formateurFullName(updated)} » mis à jour.`);
      }
      setEditing(null);
      if (onRefreshData) await onRefreshData();
    } catch (err) {
      setFormError(describeError(err));
      if (err instanceof ApiError && err.status === 404 && onRefreshData) await onRefreshData();
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setPageError(null);
    try {
      await apiService.deleteFormateur(deleteTarget.id);
      flash(`Formateur « ${formateurFullName(deleteTarget)} » supprimé.`);
      setDeleteTarget(null);
      if (onRefreshData) await onRefreshData();
    } catch (err) {
      setPageError(describeError(err));
      setDeleteTarget(null);
      if (err instanceof ApiError && err.status === 404 && onRefreshData) await onRefreshData();
    } finally {
      setIsDeleting(false);
    }
  };

  // Détection des sessions sans formateur et chevauchements de dates
  const sessionsNonAffectees = sessions.filter(s => !s.formateur);
  const sessionsAvecDates = sessions.filter(s => s.dateDebut && s.dateFin);
  const chevauchements: Session[] = [];
  for (let i = 0; i < sessionsAvecDates.length; i++) {
    for (let j = i + 1; j < sessionsAvecDates.length; j++) {
      const a = sessionsAvecDates[i];
      const b = sessionsAvecDates[j];
      const debutA = new Date(a.dateDebut!), finA = new Date(a.dateFin!);
      const debutB = new Date(b.dateDebut!), finB = new Date(b.dateFin!);
      if (debutA <= finB && debutB <= finA) {
        if (!chevauchements.find(s => s.id === a.id)) chevauchements.push(a);
        if (!chevauchements.find(s => s.id === b.id)) chevauchements.push(b);
      }
    }
  }
  const aConflitDeDates = chevauchements.length > 0;
  const formateursDispo = formateurs.filter(f => f.statut === 'Disponible');

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <PageHeader
        icon={<GraduationCap size={22} />}
        badge="M4 · Ressources Humaines"
        title="Formateurs & Staff"
        subtitle="Affectez les formateurs internes ou recrutez selon la charge de sessions simultanées."
        actions={canManage ? (
          <button onClick={openCreate} className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25 transition-colors cursor-pointer">
            <UserPlus size={14} />
            <span>Ajouter un formateur</span>
          </button>
        ) : undefined}
      />

      {/* ── Bandeau intelligent M4 ── */}
      {sessionsNonAffectees.length > 0 && (
        <div className={`rounded-2xl border p-5 ${aConflitDeDates ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}>
          <div className="flex flex-col sm:flex-row sm:items-start gap-4">
            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${aConflitDeDates ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
              <GraduationCap size={22} />
            </div>
            <div className="flex-1 min-w-0">
              {aConflitDeDates ? (
                <>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-700">Sessions simultanées détectées · Recrutement recommandé</span>
                  </div>
                  <p className="text-sm font-bold text-amber-900">
                    {chevauchements.length} session{chevauchements.length > 1 ? 's' : ''} ont des dates qui se chevauchent — un seul formateur interne ne peut pas couvrir toutes les formations en même temps.
                  </p>
                  <p className="mt-1 text-xs text-amber-700">
                    Utilisez la section <strong>Recrutement assisté IA</strong> ci-dessous pour analyser des CV, préparer les entretiens et générer les contrats.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {chevauchements.slice(0, 3).map(s => (
                      <span key={s.id} className="rounded-lg bg-amber-100 border border-amber-200 px-2.5 py-1 text-xs font-semibold text-amber-800">
                        {s.intitule.length > 35 ? s.intitule.slice(0, 35) + '…' : s.intitule}
                      </span>
                    ))}
                    {chevauchements.length > 3 && <span className="rounded-lg bg-amber-100 px-2.5 py-1 text-xs text-amber-700">+{chevauchements.length - 3} autres</span>}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">Affectation directe possible · Pas de conflit de planning</span>
                  </div>
                  <p className="text-sm font-bold text-emerald-900">
                    {sessionsNonAffectees.length} session{sessionsNonAffectees.length > 1 ? 's' : ''} sans formateur affecté — les sessions ne se chevauchent pas, un formateur interne peut les couvrir.
                  </p>
                  <p className="mt-1 text-xs text-emerald-700">
                    {formateursDispo.length > 0
                      ? `${formateursDispo.length} formateur${formateursDispo.length > 1 ? 's' : ''} disponible${formateursDispo.length > 1 ? 's' : ''} : ${formateursDispo.map(f => `${f.prenom ?? ''} ${f.nom}`.trim()).join(', ')}.`
                      : 'Aucun formateur marqué "Disponible" pour le moment — vérifiez les statuts ci-dessous.'}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {sessionsNonAffectees.slice(0, 3).map(s => (
                      <span key={s.id} className="rounded-lg bg-emerald-100 border border-emerald-200 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                        {s.intitule.length > 35 ? s.intitule.slice(0, 35) + '…' : s.intitule}
                      </span>
                    ))}
                    {sessionsNonAffectees.length > 3 && <span className="rounded-lg bg-emerald-100 px-2.5 py-1 text-xs text-emerald-700">+{sessionsNonAffectees.length - 3} autres</span>}
                  </div>
                </>
              )}
            </div>
            <div className="shrink-0">
              {aConflitDeDates ? (
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-2 text-xs font-bold text-white">
                  Recrutement externe
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white">
                  Affectation interne
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {sessionsNonAffectees.length === 0 && sessions.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
          <p className="text-sm font-semibold text-slate-700">Toutes les sessions ont un formateur affecté.</p>
        </div>
      )}

      {canManage && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-5">
        <div className="flex items-center gap-2"><Sparkles size={18} className="text-[#0B1F4D]"/><div><h2 className="font-extrabold text-[#11162A]">M4 · Recrutement assisté</h2><p className="mt-1 text-xs text-slate-500">Analyse comparative des CV, préparation des entretiens et contrats soumis à validation humaine.</p></div></div>
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-slate-200 p-4 space-y-3"><h3 className="font-bold text-sm text-[#11162A] flex items-center gap-2"><FileUp size={15}/>Présélection de plusieurs CV</h3>
            <label className="block text-[11px] font-bold uppercase text-slate-600">CV PDF, Word ou image<input type="file" multiple accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.txt" onChange={e=>setCvFiles(Array.from(e.target.files ?? []))} className="mt-1 block w-full text-xs normal-case font-normal"/></label>
            <div className="grid sm:grid-cols-2 gap-2"><label className="text-[11px] font-bold uppercase text-slate-600">Poste ciblé<input value={cvRole} onChange={e=>setCvRole(e.target.value)} className={`${inputClass} mt-1 text-xs normal-case font-normal`}/></label><label className="text-[11px] font-bold uppercase text-slate-600">Domaine<input value={cvDomain} onChange={e=>setCvDomain(e.target.value)} placeholder="Ex. Data, IA…" className={`${inputClass} mt-1 text-xs normal-case font-normal`}/></label></div>
            <label className="block text-[11px] font-bold uppercase text-slate-600">Compétences recherchées<input value={cvSkills} onChange={e=>setCvSkills(e.target.value)} placeholder="Python, pédagogie, analyse de données" className={`${inputClass} mt-1 text-xs normal-case font-normal`}/></label>
            <button disabled={!cvFiles.length || !!candidateBusyId} onClick={()=>void analyzeCvFiles()} className="w-full py-2.5 bg-[#0B1F4D] text-white rounded-xl text-xs font-bold flex justify-center items-center gap-2 disabled:opacity-50">{candidateBusyId==='bulk'?<Loader2 size={14} className="animate-spin"/>:<ClipboardList size={14}/>}Analyser et comparer {cvFiles.length || ''} CV</button>
          </div>
          <div className="rounded-xl border border-slate-200 p-4"><h3 className="font-bold text-sm text-[#11162A] mb-3">Entretiens et contrats</h3><div className="space-y-2"><select value={selectedTrainerId} onChange={e=>setSelectedTrainerId(e.target.value)} className={inputClass}><option value="">Choisir un formateur enregistré</option>{formateurs.map(t=><option key={t.id} value={t.id}>{formateurFullName(t)} · {t.specialite || 'Spécialité non renseignée'}</option>)}</select><select value={selectedSessionId} onChange={e=>setSelectedSessionId(e.target.value)} className={inputClass}><option value="">Choisir la session liée</option>{sessions.map(s=><option key={s.id} value={s.id}>{s.intitule} · {s.dateDebut || 'date à définir'}</option>)}</select><button disabled={contractBusy || !selectedSessionId || !selectedTrainerId} onClick={()=>void createContract()} className="w-full py-2.5 bg-[#11162A] text-white rounded-xl text-xs font-bold flex justify-center items-center gap-2 disabled:opacity-50">{contractBusy?<Loader2 size={14} className="animate-spin"/>:<FileSignature size={14}/>}Générer le contrat · validation HITL</button>{contractReview&&<p className="text-[11px] text-emerald-800">Contrat {contractReview} en attente dans Espace IA.</p>}</div>
            <div className="mt-4 border-t pt-3"><h4 className="font-bold text-xs text-slate-700 flex items-center gap-2"><CalendarDays size={14}/>Rapport d’évaluation depuis M5</h4><div className="mt-2 grid grid-cols-2 gap-2"><label className="text-[10px] font-bold uppercase text-slate-500">Satisfaction / 5<input type="number" min="0" max="5" step="0.1" value={evalScore} onChange={e=>setEvalScore(e.target.value)} className={`${inputClass} mt-1 text-xs`}/></label><label className="text-[10px] font-bold uppercase text-slate-500">Présence %<input type="number" min="0" max="100" value={evalAttendance} onChange={e=>setEvalAttendance(e.target.value)} className={`${inputClass} mt-1 text-xs`}/></label></div><button disabled={evaluationBusy} onClick={()=>void generateEvaluationReport()} className="mt-2 w-full py-2 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-bold flex justify-center gap-2 items-center disabled:opacity-50">{evaluationBusy?<Loader2 size={14} className="animate-spin"/>:<Sparkles size={14}/>}Générer le rapport et soumettre au HITL</button></div>
          </div>
        </div>
        {!!cvResults.length&&<div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-slate-500 uppercase text-[10px]"><tr><th className="p-3">CV</th><th className="p-3">Score</th><th className="p-3">Décision IA</th><th className="p-3">Questions d’entretien</th><th className="p-3">Validation</th></tr></thead><tbody className="divide-y divide-slate-100">{cvResults.map((r,i)=><tr key={`${r.filename}-${i}`} className="align-top"><td className="p-3 font-bold">{r.filename}{r.error&&<p className="text-red-600 font-normal">{r.error}</p>}</td><td className="p-3 font-extrabold text-[#0B1F4D]">{r.score_global ?? r.score ?? '—'}{r.score_global!=null||r.score!=null?'/100':''}</td><td className="p-3">{r.decision ?? r.recommandation ?? 'En analyse'}</td><td className="p-3"><ul className="list-disc pl-4 space-y-1">{Array.isArray(r.questions_entretien)&&r.questions_entretien.slice(0,5).map((q:any,j:number)=><li key={j}>{typeof q==='string'?q:q.question??JSON.stringify(q)}</li>)}</ul></td><td className="p-3 text-amber-700">{r.reviewId ? `À valider · ${r.reviewId}` : 'Consulter Espace IA'}</td></tr>)}</tbody></table></div>}
        {approvedContracts.length>0&&<div className="border-t border-slate-100 pt-4"><h3 className="font-bold text-sm text-[#11162A]">Contrats approuvés · prêts à télécharger</h3><div className="mt-2 space-y-2">{approvedContracts.map((review:any)=><div key={review.review_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50/50 p-3"><span className="text-xs font-semibold text-slate-700">{review.summary ?? `Contrat ${review.review_id}`}</span><button onClick={()=>void downloadApprovedContract(review.review_id)} className="rounded-lg bg-[#0B1F4D] px-3 py-2 text-[11px] font-bold text-white">Télécharger le contrat</button></div>)}</div></div>}
        {candidatePanelError && <p role="alert" className="text-xs text-red-700">{candidatePanelError}</p>}
      </section>}
      {canManage && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-extrabold text-[#11162A]">Candidatures formateur</h2><p className="mt-1 text-xs text-slate-500">Les candidatures déposées depuis les liens publics de session apparaissent ici. L’analyse IA prépare les questions à utiliser pendant l’entretien.</p></div></div>{candidatePanelError && <p role="alert" className="mt-3 text-xs text-red-700">{candidatePanelError}</p>}<div className="mt-4 space-y-2">{candidates.filter(c => c.decision_preselection !== 'NON_RETENU' && !c.formateur_id).map(candidate => <div key={candidate.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div><div className="text-sm font-bold text-slate-800">{candidate.prenom} {candidate.nom}</div><div className="text-xs text-slate-500">{candidate.email} · {candidate.telephone} · {candidate.poste_vise}</div><div className="text-[11px] text-slate-500">Formation liée : {candidate.session_id || 'Aucune'} · CV : {candidate.cv_filename || 'CV reçu'} · {candidate.decision_preselection || 'À étudier'}{candidate.score_preselection != null && !unverifiedCandidateIds.has(String(candidate.id)) ? ` · Score IA ${Math.round(candidate.score_preselection)}/100` : unverifiedCandidateIds.has(String(candidate.id)) ? ' · Analyse IA à relancer' : ''}</div><button onClick={() => void openCandidateCv(candidate.id)} className="mt-1 mr-3 text-[11px] font-bold text-blue-700 underline">Lire le CV</button><button onClick={() => void downloadCandidateCv(candidate.id,candidate.cv_filename)} className="mt-1 mr-3 text-[11px] font-bold text-blue-700 underline">Télécharger le fichier</button><button disabled={interviewBusyId===String(candidate.id)} onClick={() => void (unverifiedCandidateIds.has(String(candidate.id)) || !candidate.review_id_preselection ? reanalyzeCandidate(candidate) : openInterviewQuestions(candidate))} className="mt-1 text-[11px] font-bold text-[#0B1F4D] underline disabled:opacity-50">{interviewBusyId===String(candidate.id)?'Analyse…':unverifiedCandidateIds.has(String(candidate.id)) || !candidate.review_id_preselection?'Analyser le CV selon l’offre':'Voir les questions d’entretien'}</button></div><div className="flex flex-wrap gap-2"><button disabled={emailBusyId===String(candidate.id)} onClick={() => void prepareHrEmail(candidate,'CONVOCATION')} className="rounded-lg bg-blue-50 px-3 py-2 text-[11px] font-bold text-blue-700 disabled:opacity-50">Préparer convocation</button><button disabled={emailBusyId===String(candidate.id)} onClick={() => void prepareHrEmail(candidate,'ACCEPTATION')} className="rounded-lg bg-emerald-50 px-3 py-2 text-[11px] font-bold text-emerald-800 disabled:opacity-50">Préparer offre</button><button disabled={emailBusyId===String(candidate.id)} onClick={() => void prepareHrEmail(candidate,'REFUS')} className="rounded-lg bg-slate-100 px-3 py-2 text-[11px] font-bold text-slate-700 disabled:opacity-50">Préparer refus</button><button disabled={!!candidateBusyId} onClick={() => void decideCandidate(candidate,'REFUSER')} className="rounded-lg bg-red-50 px-3 py-2 text-xs font-bold text-red-700 disabled:opacity-50">Refuser</button><button disabled={!!candidateBusyId} onClick={() => void decideCandidate(candidate,'ACCEPTER')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Accepter après entretien</button></div></div>)}{!candidates.filter(c => c.decision_preselection !== 'NON_RETENU' && !c.formateur_id).length && <p className="text-xs text-slate-500">Aucune candidature en attente.</p>}</div>{candidateCv && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"><div className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5"><div className="flex justify-between"><h3 className="font-extrabold">CV · {candidateCv.prenom} {candidateCv.nom}</h3><button onClick={()=>setCandidateCv(null)} className="font-bold">Fermer</button></div><p className="mt-1 text-xs text-slate-500">{candidateCv.fichier}</p><pre className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-xs">{candidateCv.cv_texte}</pre></div></div>}{interviewPack&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"><section className="max-h-[88vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl"><div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-3"><div><span className="text-[10px] font-bold uppercase tracking-wider text-[#0B1F4D]">Guide d’entretien · M4</span><h3 className="mt-1 text-lg font-extrabold text-[#11162A]">{interviewPack.candidate.prenom} {interviewPack.candidate.nom}</h3><p className="mt-1 text-xs text-slate-500">{interviewPack.candidate.poste_vise} · {interviewPack.candidate.session_id ? sessions.find(s=>s.id===interviewPack.candidate.session_id)?.intitule ?? 'Formation liée' : 'Candidature RH'}{interviewPack.score!=null?` · Score IA ${Math.round(interviewPack.score)}/100`:''}</p></div><button onClick={()=>setInterviewPack(null)} className="rounded-lg px-2 py-1 text-sm font-bold text-slate-500 hover:bg-slate-100">Fermer</button></div>{interviewPack.summary&&<p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">{interviewPack.summary}</p>}<div className="mt-4 space-y-2">{interviewPack.questions.map((q:any,i:number)=><article key={i} className="flex gap-3 rounded-xl border border-slate-200 p-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-xs font-extrabold text-[#0B1F4D]">{i+1}</span><div><h4 className="text-xs font-bold text-[#11162A]">{typeof q==='string'?q:q.question??q.titre??'Question d’entretien'}</h4>{typeof q==='object'&&q.objectif&&<p className="mt-1 text-[11px] text-slate-500">À évaluer : {q.objectif}</p>}</div></article>)}{!interviewPack.questions.length&&<p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">Aucune question fiable n’est disponible. Relancez l’analyse du CV avec les critères de la formation liée.</p>}</div><div className="mt-4 flex flex-wrap justify-between gap-2 border-t pt-3"><span className="self-center text-[10px] text-slate-400">Review IA : {interviewPack.reviewId ?? 'non générée'}</span><div className="flex gap-2"><button disabled={!!interviewBusyId} onClick={()=>void reanalyzeCandidate(interviewPack.candidate)} className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 disabled:opacity-50">{interviewBusyId?'Analyse…':'Relancer l’analyse ciblée'}</button><button onClick={()=>window.print()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white">Imprimer le guide</button></div></div></section></div>}</section>}

      {emailDraft && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
        <section role="dialog" aria-modal="true" aria-label="Vérification du courriel RH" className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl">
          <div className="flex items-start justify-between gap-3 border-b pb-3"><div><span className="text-[10px] font-bold uppercase tracking-wider text-[#0B1F4D]">Brouillon RH · {emailDraft.type.toLowerCase()}</span><h3 className="mt-1 text-lg font-extrabold text-[#11162A]">Relire avant l’envoi</h3><p className="mt-1 text-xs text-slate-500">Aucun message ne part tant que vous ne cliquez pas sur « Valider et envoyer ».</p></div><button type="button" onClick={() => setEmailDraft(null)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Fermer le brouillon"><X size={18}/></button></div>
          {candidatePanelError && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">{candidatePanelError}</p>}
          <div className="mt-4 space-y-3"><label className="block text-xs font-bold text-slate-600">Destinataire<input readOnly value={emailDraft.email} className={`${inputClass} mt-1 text-xs bg-slate-100`}/></label><label className="block text-xs font-bold text-slate-600">Objet<input disabled={emailDraft.approved} value={emailDraft.subject} onChange={e=>setEmailDraft(previous=>previous?{...previous,subject:e.target.value}:null)} className={`${inputClass} mt-1 text-xs disabled:opacity-60`}/></label><label className="block text-xs font-bold text-slate-600">Message<textarea disabled={emailDraft.approved} value={emailDraft.body} onChange={e=>setEmailDraft(previous=>previous?{...previous,body:e.target.value}:null)} rows={14} className={`${inputClass} mt-1 resize-y text-xs leading-relaxed disabled:opacity-60`}/></label></div>
          {emailDraft.approved && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">Brouillon approuvé. Si l’envoi a échoué, vous pouvez réessayer sans recréer le message.</p>}
          <div className="mt-4 flex flex-wrap justify-end gap-2 border-t pt-4"><button type="button" onClick={() => setEmailDraft(null)} className="rounded-lg bg-slate-100 px-4 py-2 text-xs font-bold text-slate-700">Fermer</button><button type="button" disabled={!!emailBusyId || emailDraft.approved} onClick={() => void saveHrEmailDraft()} className="rounded-lg bg-blue-50 px-4 py-2 text-xs font-bold text-blue-800 disabled:opacity-50">Enregistrer sans envoyer</button><button type="button" disabled={!!emailBusyId || !emailDraft.email.trim() || !emailDraft.subject.trim() || !emailDraft.body.trim()} onClick={() => void sendHrEmailDraft()} className="rounded-lg bg-[#0B1F4D] px-4 py-2 text-xs font-bold text-white disabled:opacity-50">{emailBusyId ? 'Traitement…' : emailDraft.approved ? 'Réessayer l’envoi' : 'Valider et envoyer'}</button></div>
        </section>
      </div>}

      {!canManage && (
        <div className="p-3 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 text-xs font-medium flex items-center gap-2">
          <Lock size={14} className="shrink-0" />
          Lecture seule : seule la Direction peut ajouter, modifier ou supprimer un formateur.
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={14} className="shrink-0" />
          {successMsg}
        </div>
      )}

      {newTrainerAccount && <div role="status" className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-xs text-blue-900"><div className="font-extrabold">Compte formateur créé — transmettez ces accès au formateur</div><div className="mt-2">E-mail : <strong>{newTrainerAccount.email}</strong></div><div className="mt-1">Mot de passe initial : <strong className="select-all font-mono">{newTrainerAccount.password}</strong></div><button onClick={() => { void navigator.clipboard?.writeText('E-mail : ' + newTrainerAccount.email + '\nMot de passe : ' + newTrainerAccount.password); }} className="mt-3 rounded-lg bg-white px-3 py-1.5 font-bold text-blue-800">Copier les accès</button><button onClick={() => setNewTrainerAccount(null)} className="ml-2 rounded-lg bg-blue-100 px-3 py-1.5 font-bold text-blue-800">Masquer</button></div>}

      {pageError && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>{pageError}</span>
        </div>
      )}

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Formateurs</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{formateurs.length}</div>
          <p className="text-xs text-blue-600 font-semibold mt-1">Enregistrés dans la base</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Score moyen d'évaluation</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1 flex items-center gap-1.5">
            <Star size={20} className="fill-amber-400 text-amber-400" />
            <span>{scoreMoyenGlobal !== null ? `${Math.round(scoreMoyenGlobal)} / 100` : '—'}</span>
          </div>
          <p className="text-xs text-emerald-600 font-semibold mt-1">
            {evalues.length} formateur(s) évalué(s)
          </p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Disponibilité immédiate</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{disponibles}</div>
          <p className="text-xs text-[#0B1F4D] font-semibold mt-1">Prêts pour de nouvelles sessions</p>
        </div>
      </div>

      {/* Recherche + filtre de statut */}
      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filtrer par nom, spécialité ou email..."
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
          />
        </div>
        <select
          value={statutFilter}
          onChange={(e) => setStatutFilter(e.target.value as 'Tous' | StatutFormateur)}
          className="px-3 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
        >
          <option value="Tous">Tous les statuts</option>
          {STATUT_LABELS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Grille des formateurs */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {filtered.map((f) => {
          const specs = specialitesList(f);
          return (
            <div
              key={f.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between hover:border-[#0B1F4D]/40 transition-all space-y-4"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-12 h-12 rounded-xl bg-[#0B1F4D] text-white flex items-center justify-center text-lg font-extrabold shrink-0">
                      {formateurFullName(f).charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-base font-extrabold text-[#11162A] truncate">{formateurFullName(f)}</h3>
                      <div className="text-xs text-slate-400 font-medium mt-0.5">
                        {f.nbSessions !== undefined ? `${f.nbSessions} session(s)` : 'Aucune session renseignée'}
                      </div>
                    </div>
                  </div>

                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-extrabold shrink-0 ${statutStyle(f.statut)}`}>
                    {f.statut}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Spécialités</div>
                  {specs.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {specs.map((spec, idx) => (
                        <span key={idx} className="bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-md text-xs font-semibold">
                          {spec}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">Non renseignées</span>
                  )}
                </div>

                <div className="space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200/80 mb-3">
                  <div className="flex items-center gap-2">
                    <Mail size={13} className="text-slate-400 shrink-0" />
                    <span className="font-medium text-slate-700 truncate">{f.email ?? 'Email non renseigné'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone size={13} className="text-slate-400 shrink-0" />
                    <span className="font-medium text-slate-700">{f.telephone ?? 'Téléphone non renseigné'}</span>
                  </div>
                  {f.adresse && (
                    <div className="flex items-center gap-2">
                      <MapPin size={13} className="text-slate-400 shrink-0" />
                      <span className="font-medium text-slate-700 truncate">{f.adresse}</span>
                    </div>
                  )}
                </div>

                {/* Évaluation IA */}
                <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200/80 text-xs space-y-2">
                  <div className="flex items-center justify-between font-bold text-emerald-900">
                    <span className="flex items-center gap-1.5">
                      <Award size={14} className="text-emerald-700" />
                      Évaluation post-session
                    </span>
                    {f.scoreMoyen !== undefined ? (
                      <span className={`font-extrabold ${scoreStyle(f.scoreMoyen)}`}>
                        {Math.round(f.scoreMoyen)} / 100
                      </span>
                    ) : (
                      <span className="text-slate-400 font-semibold">Pas encore évalué</span>
                    )}
                  </div>
                  {f.recommandation && (
                    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${recommandationStyle(f.recommandation)}`}>
                      Recommandation : {f.recommandation}
                    </span>
                  )}
                  {f.notesInternes && (
                    <p className="text-[11px] text-slate-600 line-clamp-2" title={f.notesInternes}>
                      {f.notesInternes}
                    </p>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div>
                  <span className="text-slate-400 font-medium text-[10px] uppercase block">Tarif journalier</span>
                  <strong className="text-sm font-extrabold text-[#11162A]">
                    {f.tarifJournalier !== undefined ? `${f.tarifJournalier.toLocaleString()} Ar / jour` : 'Non renseigné'}
                  </strong>
                </div>

                {canManage && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openEdit(f)}
                      className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Pencil size={13} />
                      <span>Modifier</span>
                    </button>
                    <button
                      onClick={() => setDeleteTarget(f)}
                      className="px-3 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Trash2 size={13} />
                      <span>Supprimer</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
          <p className="font-bold text-xs text-slate-700">
            {formateurs.length === 0 ? 'Aucun formateur enregistré pour le moment.' : 'Aucun formateur ne correspond au filtre.'}
          </p>
          {formateurs.length === 0 && canManage && (
            <p className="text-[11px] text-slate-400 mt-1">Utilisez « Ajouter un formateur » pour créer le premier.</p>
          )}
        </div>
      )}

      {/* ===== Formulaire de création / modification ===== */}
      {editing && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5 max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3 border-slate-100">
              <div className="flex items-center gap-2">
                {editing === 'new' ? (
                  <UserPlus size={20} className="text-[#0B1F4D]" />
                ) : (
                  <Pencil size={20} className="text-[#0B1F4D]" />
                )}
                <h2 className="text-lg font-extrabold text-[#11162A]">
                  {editing === 'new' ? 'Ajouter un formateur' : 'Modifier le formateur'}
                </h2>
              </div>
              <button onClick={closeForm} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg cursor-pointer">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Nom *</label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    maxLength={100}
                    value={form.nom}
                    onChange={(e) => setField('nom', e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Prénom</label>
                  <input
                    type="text"
                    maxLength={100}
                    value={form.prenom}
                    onChange={(e) => setField('prenom', e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Email</label>
                  <input
                    type="email"
                    maxLength={200}
                    value={form.email}
                    onChange={(e) => setField('email', e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Téléphone</label>
                  <input
                    type="text"
                    maxLength={30}
                    value={form.telephone}
                    onChange={(e) => setField('telephone', e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <label className="font-extrabold text-slate-700 block mb-1">Adresse</label>
                <input
                  type="text"
                  maxLength={300}
                  value={form.adresse}
                  onChange={(e) => setField('adresse', e.target.value)}
                  className={inputClass}
                />
              </div>

              <div>
                <label className="font-extrabold text-slate-700 block mb-1">
                  Spécialités (séparées par des virgules)
                </label>
                <input
                  type="text"
                  maxLength={200}
                  value={form.specialite}
                  onChange={(e) => setField('specialite', e.target.value)}
                  className={inputClass}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Tarif journalier (Ar)</label>
                  <input
                    type="number"
                    min="1"
                    step="any"
                    value={form.tarifJournalier}
                    onChange={(e) => setField('tarifJournalier', e.target.value)}
                    className={inputClass}
                  />
                  {editing !== 'new' && (
                    <p className="text-[10px] text-slate-400 mt-1">Laissé vide, le tarif actuel est conservé.</p>
                  )}
                </div>
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Statut</label>
                  <select
                    value={form.statut}
                    onChange={(e) => setField('statut', e.target.value as StatutFormateur)}
                    className={`${inputClass} font-bold`}
                  >
                    {STATUT_LABELS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="font-extrabold text-slate-700 block mb-1">Notes internes</label>
                <textarea
                  rows={3}
                  value={form.notesInternes}
                  onChange={(e) => setField('notesInternes', e.target.value)}
                  className={inputClass}
                />
              </div>

              {formError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 font-semibold flex items-start gap-2">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={closeForm}
                  disabled={isSaving}
                  className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold cursor-pointer disabled:opacity-50"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-5 py-2.5 bg-[#0B1F4D] hover:bg-[#06132F] text-white rounded-xl font-bold flex items-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  <span>{isSaving ? 'Enregistrement…' : editing === 'new' ? 'Ajouter' : 'Enregistrer'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Confirmation de suppression ===== */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center gap-2 text-red-700">
              <Trash2 size={20} />
              <h2 className="text-lg font-extrabold">Supprimer ce formateur ?</h2>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              <strong className="text-[#11162A]">{formateurFullName(deleteTarget)}</strong> sera supprimé définitivement,
              ainsi que les dossiers de candidature qui lui sont rattachés. Cette action est irréversible.
            </p>
            <div className="flex items-center justify-end gap-2 text-xs">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold cursor-pointer disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center gap-2 cursor-pointer disabled:opacity-60"
              >
                {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                <span>{isDeleting ? 'Suppression…' : 'Supprimer définitivement'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
