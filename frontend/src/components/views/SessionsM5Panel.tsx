import React, { useEffect, useMemo, useState } from 'react';
import { Archive, Award, CheckCircle2, Download, Eye, FileText, Loader2, Pencil, ReceiptText, Save, ShieldCheck, Trash2, TrendingUp, Users, X } from 'lucide-react';
import { apiService } from '../../services/api';
import type { VoiceActionContext } from '../../services/voiceActionContext';
import type { MenuSection } from '../../types';

type Attendance = { id: string; statut: 'PRESENT' | 'ABSENT' | 'RETARD' | 'EXCUSE'; heure_arrivee?: string; motif_absence?: string };
type Person = { id: string; nom: string; prenom?: string };

const formatAnalysisValue = (value: unknown) => {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toLocaleString('fr-FR', { maximumFractionDigits: 1 });
  return value == null || value === '' ? '—' : String(value);
};

const AnalysisResult: React.FC<{ analysis: any }> = ({ analysis }) => {
  const stats = analysis?.statistiques ?? {};
  const isLevelAnalysis = stats.score_moyen_avant != null || stats.score_moyen_apres != null;
  const scoreCards = isLevelAnalysis
    ? [
        { label: 'Score moyen avant', value: `${formatAnalysisValue(stats.score_moyen_avant)} / 100`, tone: 'text-slate-800' },
        { label: 'Score moyen après', value: `${formatAnalysisValue(stats.score_moyen_apres)} / 100`, tone: 'text-slate-800' },
        { label: 'Progression moyenne', value: `${Number(stats.progression_absolue ?? 0) > 0 ? '+' : ''}${formatAnalysisValue(stats.progression_absolue)} pts`, tone: Number(stats.progression_absolue ?? 0) >= 0 ? 'text-emerald-700' : 'text-rose-700' },
        { label: 'Participants analysés', value: formatAnalysisValue(stats.nb_participants), tone: 'text-slate-800' },
      ]
    : Object.entries(stats.notes ?? stats)
        .filter(([, value]) => ['string', 'number'].includes(typeof value))
        .slice(0, 4)
        .map(([label, value]) => ({ label: label.replaceAll('_', ' '), value: formatAnalysisValue(value), tone: 'text-slate-800' }));
  const distributions = isLevelAnalysis ? [
    { title: 'Niveaux avant', values: analysis.distribution_avant },
    { title: 'Niveaux après', values: analysis.distribution_apres },
  ] : [];
  const cases = analysis.cas_remarquables ?? {};
  const highlighted = [cases.meilleure_progression, ...(cases.progressions_faibles ?? [])]
    .filter((item: any, index: number, rows: any[]) => item && rows.findIndex(row => row?.nom === item.nom) === index);
  const recommendations = Array.isArray(analysis.recommandations) ? analysis.recommandations : [];

  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="border-b border-slate-100 bg-gradient-to-r from-emerald-50 to-white p-5">
      <div className="flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-wide text-emerald-800"><TrendingUp size={15}/>Résultat de l’analyse</div>
      <p className="mt-2 text-sm font-semibold leading-relaxed text-slate-800">{analysis.resume ?? 'Analyse terminée.'}</p>
      {analysis.interpretation && <p className="mt-2 text-xs leading-relaxed text-slate-600">{analysis.interpretation}</p>}
    </div>
    {scoreCards.length > 0 && <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">{scoreCards.map(card => <div key={card.label} className="rounded-xl border border-slate-100 bg-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{card.label}</div><div className={`mt-1 text-xl font-extrabold tabular-nums ${card.tone}`}>{card.value}</div></div>)}</div>}
    {distributions.length > 0 && <div className="grid gap-4 px-5 pb-5 md:grid-cols-2">{distributions.map(group => <div key={group.title} className="rounded-xl border border-slate-200 p-4"><h3 className="mb-3 text-xs font-extrabold text-slate-800">{group.title}</h3><div className="space-y-3">{[['debutants', 'Débutants', 'bg-amber-500'], ['intermediaires', 'Intermédiaires', 'bg-blue-500'], ['avances', 'Avancés', 'bg-emerald-500']].map(([key, label, color]) => { const value = group.values?.[key] ?? {}; const percent = Number.parseFloat(String(value.pourcentage ?? '0')) || 0; return <div key={key}><div className="mb-1 flex justify-between text-[11px]"><span className="font-medium text-slate-600">{label} <span className="text-slate-400">({value.nb ?? 0})</span></span><strong className="text-slate-700">{value.pourcentage ?? '0%'}</strong></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}/></div></div>; })}</div></div>)}</div>}
    {highlighted.length > 0 && <div className="border-t border-slate-100 px-5 py-4"><h3 className="mb-2 flex items-center gap-2 text-xs font-extrabold text-slate-800"><Users size={14}/>Progressions remarquables</h3><div className="grid gap-2 sm:grid-cols-2">{highlighted.map((person: any) => <div key={person.nom} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs"><span className="truncate font-semibold text-slate-700">{person.nom}</span><span className={`shrink-0 font-extrabold tabular-nums ${Number(person.gain) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>{Number(person.avant)} → {Number(person.apres)} <span className="text-[10px]">({Number(person.gain) > 0 ? '+' : ''}{Number(person.gain)} pts)</span></span></div>)}</div></div>}
    {recommendations.length > 0 && <div className="border-t border-slate-100 px-5 py-4"><h3 className="mb-2 text-xs font-extrabold text-slate-800">Recommandations</h3><ul className="space-y-2">{recommendations.map((recommendation: string, index: number) => <li key={`${index}-${recommendation}`} className="flex gap-2 text-xs leading-relaxed text-slate-600"><span className="font-black text-emerald-600">{index + 1}.</span><span>{recommendation}</span></li>)}</ul></div>}
    {analysis.metadata && <div className="border-t border-slate-100 px-5 py-3 text-[10px] text-slate-400">Source : {analysis.metadata.source === 'llm' ? 'analyse assistée par IA' : 'analyse automatique'}{analysis.metadata.duration_seconds != null ? ` · ${formatAnalysisValue(analysis.metadata.duration_seconds)} s` : ''}{analysis.metadata.participants_incomplets ? ` · ${analysis.metadata.participants_incomplets} participant(s) écarté(s), score incomplet` : ''}</div>}
    <details className="border-t border-slate-100 px-5 py-3"><summary className="cursor-pointer text-[11px] font-bold text-slate-500">Données techniques (JSON)</summary><pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-[10px] leading-relaxed text-emerald-100">{JSON.stringify(analysis, null, 2)}</pre></details>
  </section>;
};

const AttestationBatchCard: React.FC<{ batch: any; sessionTitle: string; busy: string; onDownloadPdf: (reviewId: string, numero: string) => void; onPreviewPdf: (reviewId: string, numero: string) => void; onEdit: (numero: string, content: any) => Promise<void>; onDelete: (numero: string) => Promise<void>; onDownloadZip: (reviewId: string) => void }> = ({ batch, sessionTitle, busy, onDownloadPdf, onPreviewPdf, onEdit, onDelete, onDownloadZip }) => {
  const attestations = Array.isArray(batch.attestations) ? batch.attestations : [];
  const available = attestations.filter((item: any) => item.numero_unique && item.pdf_generated !== false);
  const approvedCount = available.filter((item: any) => item.approval_status === 'approved').length;
  const zipReady = batch.status === 'approved' && available.length > 0 && approvedCount === available.length;
  const failures = Array.isArray(batch.failed) ? batch.failed : [];
  const statusLabel = batch.status === 'approved' ? 'Lot approuvé' : 'Validation humaine requise';
  return <section className="border-b border-slate-100 bg-gradient-to-br from-slate-50 via-white to-emerald-50/60 p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><Award size={17} className="text-emerald-700"/><h4 className="text-sm font-extrabold text-[#11162A]">Attestations préparées</h4></div><p className="mt-1 text-xs text-slate-500">{sessionTitle} · {statusLabel}</p></div>{zipReady && <button type="button" disabled={busy !== ''} onClick={() => onDownloadZip(batch.reviewId)} className="inline-flex items-center gap-2 rounded-xl bg-[#11162A] px-4 py-2.5 text-xs font-extrabold text-white shadow-sm hover:bg-slate-800 disabled:cursor-wait disabled:opacity-50">{busy === 'zip' ? <Loader2 size={14} className="animate-spin"/> : <Archive size={14}/>}Télécharger le lot ZIP</button>}</div>
    <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-slate-200 bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">PDF prêts</div><div className="mt-1 text-xl font-extrabold text-[#11162A]">{available.length}</div></div><div className="rounded-xl border border-emerald-100 bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-emerald-700">Approuvés</div><div className="mt-1 text-xl font-extrabold text-emerald-800">{approvedCount} / {available.length}</div></div><div className="rounded-xl border border-blue-100 bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-blue-700">Référence du lot</div><div className="mt-1 truncate text-xs font-extrabold text-blue-900">{batch.reviewId}</div></div></div>
    {attestations.length > 0 ? <div className="mt-4 grid gap-3">{attestations.map((item: any) => {
      const details = item.content?.details ?? {};
      const name = [item.participant?.prenom, item.participant?.nom].filter(Boolean).join(' ') || item.participant?.nom || 'Participant';
      const hasPdf = !!item.numero_unique && item.pdf_generated !== false;
      const isApproved = item.approval_status === 'approved';
      return <AttestationItemCard key={item.numero_unique} item={item} details={details} name={name} sessionTitle={sessionTitle} hasPdf={hasPdf} isApproved={isApproved} busy={busy} reviewId={batch.reviewId} onDownloadPdf={onDownloadPdf} onPreviewPdf={onPreviewPdf} onEdit={onEdit} onDelete={onDelete}/>;
    })}</div> : <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-extrabold text-amber-900">Aucun PDF n’a été généré dans ce lot.</p><p className="mt-1 text-xs leading-relaxed text-amber-800">Le téléchargement est masqué pour éviter un ZIP vide. Vérifiez les pointages et les erreurs du lot, puis relancez la préparation.</p>{failures.length > 0 && <ul className="mt-3 space-y-1 text-[11px] text-amber-900">{failures.map((failure: any, index: number) => <li key={index}>• {failure.participant?.nom ?? 'Participant'} : {failure.error ?? 'échec de génération'}</li>)}</ul>}</div>}
  </section>;
};

const AttestationItemCard: React.FC<{ item: any; details: any; name: string; sessionTitle: string; hasPdf: boolean; isApproved: boolean; busy: string; reviewId: string; onDownloadPdf: (reviewId: string, numero: string) => void; onPreviewPdf: (reviewId: string, numero: string) => void; onEdit: (numero: string, content: any) => Promise<void>; onDelete: (numero: string) => Promise<void> }> = ({ item, details, name, sessionTitle, hasPdf, isApproved, busy, reviewId, onDownloadPdf, onPreviewPdf, onEdit, onDelete }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState<any>(() => structuredClone(item.content ?? {}));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  useEffect(() => { setContent(structuredClone(item.content ?? {})); }, [item.content]);
  const setField = (key: string, value: string) => setContent((current: any) => ({ ...current, [key]: value }));
  const setDetail = (key: string, value: string) => setContent((current: any) => ({ ...current, details: { ...current.details, [key]: value } }));
  const save = async () => { setSaving(true); try { await onEdit(item.numero_unique, content); setEditing(false); } finally { setSaving(false); } };
  return <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xs"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3"><div><h5 className="text-sm font-extrabold text-[#11162A]">{name}</h5><p className="mt-0.5 text-[11px] text-slate-500">{isApproved ? 'Attestation validée par la direction' : 'En attente de validation humaine'}</p></div><span className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold ${isApproved ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{isApproved ? 'Approuvée' : 'À valider'}</span></div>
    <div className="grid gap-3 p-4 sm:grid-cols-3"><div className="rounded-lg bg-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">1 · Formation</div><div className="mt-1 text-xs font-bold text-slate-800">{details.formation || sessionTitle}</div><div className="mt-1 text-[11px] text-slate-500">{details.dates || details.lieu || 'Session de formation'}</div></div><div className="rounded-lg bg-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">2 · Assiduité</div><div className="mt-1 text-xs font-extrabold text-slate-800">{item.participant?.taux_presence != null ? `${item.participant.taux_presence}% de présence` : 'Éligible au seuil requis'}</div><div className="mt-1 text-[11px] text-slate-500">Seuil d’éligibilité : 75 %</div></div><div className="rounded-lg bg-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">3 · Référence</div><div className="mt-1 break-all text-xs font-extrabold text-slate-800">{item.numero_unique || 'Numéro indisponible'}</div><div className="mt-1 text-[11px] text-slate-500">{hasPdf ? 'Fichier PDF généré' : 'Aucun fichier PDF disponible'}</div></div></div>
    {editing && <div className="grid gap-3 border-t border-slate-100 bg-white p-4 sm:grid-cols-2">{[['titre_attestation','Titre'],['introduction','Introduction'],['corps','Texte principal'],['cloture','Formule finale'],['lieu_emission','Lieu d’émission'],['date_emission','Date d’émission']].map(([key,label]) => <label key={key} className="text-[11px] font-bold text-slate-600">{label}<input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-normal" value={content[key] ?? ''} onChange={event => setField(key,event.target.value)}/></label>)}{Object.entries(content.details ?? {}).map(([key,value]) => <label key={key} className="text-[11px] font-bold capitalize text-slate-600">{key}<input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-normal" value={String(value ?? '')} onChange={event => setDetail(key,event.target.value)}/></label>)}<label className="text-[11px] font-bold text-slate-600 sm:col-span-2">Compétences vérifiées · une par ligne<textarea className="mt-1 min-h-24 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-normal" value={(content.competences ?? []).join('\n')} onChange={event => setContent((current:any)=>({...current,competences:event.target.value.split('\n')}))}/></label>{saveError && <p className="text-xs font-semibold text-rose-700 sm:col-span-2">{saveError}</p>}<div className="flex flex-wrap justify-end gap-2 sm:col-span-2"><button type="button" onClick={()=>{setEditing(false);setSaveError('');}} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600"><X size={13}/>Annuler</button><button type="button" disabled={saving} onClick={()=>{setSaveError('');void save().catch(error=>setSaveError(error instanceof Error?error.message:'Enregistrement impossible.'));}} className="inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{saving?<Loader2 size={13} className="animate-spin"/>:<Save size={13}/>}Enregistrer et recréer le PDF</button></div></div>}
    <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/70 px-4 py-3">{!isApproved && <><button type="button" disabled={!hasPdf || busy !== ''} onClick={()=>setEditing(value=>!value)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50"><Pencil size={13}/>Modifier</button><button type="button" disabled={busy !== ''} onClick={()=>void onDelete(item.numero_unique)} className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-bold text-rose-700 disabled:opacity-50"><Trash2 size={13}/>Supprimer</button></>}{hasPdf ? isApproved ? <button type="button" disabled={busy !== ''} onClick={()=>onDownloadPdf(reviewId,item.numero_unique)} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3.5 py-2 text-xs font-extrabold text-white disabled:opacity-50">{busy===item.numero_unique?<Loader2 size={14} className="animate-spin"/>:<Download size={14}/>}Télécharger</button> : <button type="button" disabled={busy !== ''} onClick={()=>onPreviewPdf(reviewId,item.numero_unique)} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3.5 py-2 text-xs font-extrabold text-white disabled:opacity-50"><Eye size={14}/>Prévisualiser</button> : <span className="text-[11px] font-semibold text-amber-800">PDF indisponible ; corrigez les prérequis puis relancez la génération.</span>}</div>
  </article>;
};


export const SessionsM5Panel: React.FC<{ sessionId: string; sessionTitle: string; domain?: string; formationCode?: string; formateurId?: string; tauxPresence?: number; sessionStatus?: string; sessionDateStart?: string; sessionDateEnd?: string; sessionLocation?: string; sessionTrainer?: string; participants: Person[]; trainerMode?: boolean; voiceAction?: VoiceActionContext | null; onNavigateToSection?: (section: MenuSection) => void; onOpenNewInvoice?: (sessionId?: string) => void }> = ({ sessionId, sessionTitle, domain, formationCode, formateurId, tauxPresence, sessionStatus, sessionDateStart, sessionDateEnd, sessionLocation, sessionTrainer, participants, trainerMode = false, voiceAction, onNavigateToSection, onOpenNewInvoice }) => {
  const [seances, setSeances] = useState<any[]>([]);
  const [attendance, setAttendance] = useState<Record<string, Attendance>>({});
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [start, setStart] = useState('09:00'); const [end, setEnd] = useState('12:00');
  const [theme, setTheme] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [trainers, setTrainers] = useState<any[]>([]); const [trainer, setTrainer] = useState(formateurId ?? '');
  const [analysis, setAnalysis] = useState<any>(null); const [analysisBusy, setAnalysisBusy] = useState(false);
  const [m6, setM6] = useState<any>(null); const [m6Busy, setM6Busy] = useState(false);
  const [attestationBatch, setAttestationBatch] = useState<any>(null);
  const [attestationDownloadBusy, setAttestationDownloadBusy] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const load = async () => {
    const list = await apiService.getSeances(sessionId); setSeances(list);
    const rows = await Promise.all(list.map(async (item: any) => [item.id, await apiService.getPresenceForSession(item.id)] as const));
    const next: Record<string, Attendance> = {};
    rows.forEach(([seanceId, items]) => items.forEach((item: any) => { next[`${seanceId}:${item.participant_id}`] = { id: item.id, statut: item.statut, heure_arrivee: item.heure_arrivee, motif_absence: item.motif_absence }; }));
    setAttendance(next);
  };
  useEffect(() => { setTrainer(formateurId ?? ''); }, [formateurId, sessionId]);
  useEffect(() => { let live = true; Promise.all([apiService.getSeances(sessionId), trainerMode ? Promise.resolve([]) : apiService.getSessionTrainerOptions()]).then(async ([list, staff]) => { if (!live) return; setSeances(list); setTrainers(staff); const rows = await Promise.all(list.map(async (item: any) => [item.id, await apiService.getPresenceForSession(item.id)] as const)); if (!live) return; const next: Record<string, Attendance> = {}; rows.forEach(([sid, items]) => items.forEach((item: any) => { next[`${sid}:${item.participant_id}`] = { id:item.id, statut:item.statut, heure_arrivee:item.heure_arrivee, motif_absence:item.motif_absence }; })); setAttendance(next); }).catch(e => setError(e.message)); return () => { live = false; }; }, [sessionId, trainerMode]);
  useEffect(() => {
    if (trainerMode) return;
    let live = true;
    const loadAttestationBatch = async () => {
      let reviewId = '';
      try { reviewId = localStorage.getItem(`formaia-attestations-${sessionId}`) ?? ''; } catch { /* stockage local indisponible */ }
      if (!reviewId) {
        try {
          const history = await apiService.getReviewHistory('approved', 'agent_5_attestations');
          const match = (history.reviews ?? []).find((item: any) => String(item.meta?.session_id ?? '') === String(sessionId));
          reviewId = String(match?.review_id ?? '');
        } catch { /* L'historique ne doit pas bloquer la fiche de session. */ }
      }
      if (!reviewId) return;
      try {
        const response = await apiService.getReview(reviewId);
        const review = response.review;
        if (!live || review?.agent_id !== 'agent_5_attestations' || String(review.meta?.session_id ?? review.data?.session_id ?? '') !== String(sessionId)) return;
        setAttestationBatch({ reviewId, status: review.status, updatedAt: review.updated_at, attestations: review.data?.attestations ?? [], failed: review.data?.failed_participants ?? [] });
      } catch { /* La validation reste accessible depuis Espace IA. */ }
    };
    void loadAttestationBatch();
    return () => { live = false; };
  }, [sessionId, trainerMode]);
  const create = async (e: React.FormEvent) => { e.preventDefault(); if (!theme.trim()) return; setBusy(true); setError(''); try { await apiService.createSeance(sessionId, { date, heure_debut:start, heure_fin:end, duree:`${start}–${end}`, theme:theme.trim(), formateur_id:trainerMode ? formateurId : trainer || formateurId || undefined }); await load(); setTheme(''); setNotice('Séance créée pour cette journée de formation.'); } catch(e) { setError(e instanceof Error ? e.message : 'Création séance impossible.'); } finally { setBusy(false); } };
  const save = async (seanceId: string, participantId: string, statut: Attendance['statut'], extra: Partial<Attendance> = {}) => {
    const key = `${seanceId}:${participantId}`, current = attendance[key]; const optimistic = { ...(current ?? { id:'', statut }), statut, ...extra } as Attendance;
    setAttendance(prev => ({ ...prev, [key]: optimistic })); setError(''); setNotice('Enregistrement…');
    try { const data: any = current?.id ? await apiService.updatePresence(current.id, statut, extra) : await apiService.createPresence(seanceId, participantId, statut, extra); setAttendance(prev => ({ ...prev, [key]: { ...optimistic, id: data.id ?? current?.id ?? '' } })); setNotice('Présence enregistrée automatiquement.'); }
    catch(e) { setError(e instanceof Error ? e.message : 'Enregistrement de présence impossible.'); await load().catch(()=>{}); }
  };
  const rate = (personId:string) => { if(!seances.length) return 0; const ok=seances.filter(s=>['PRESENT','RETARD'].includes(attendance[`${s.id}:${personId}`]?.statut)).length; return Math.round(ok/seances.length*100); };
  const analyzeLevels = async () => { setAnalysisBusy(true);setError('');try{const result=await apiService.analyserNiveauxDb(sessionId);if(!result.success){setError(result.message||'Analyse des niveaux impossible.');return;}setAnalysis(result.data??result);}catch(e){setError(e instanceof Error?e.message:'Analyse des niveaux impossible.');}finally{setAnalysisBusy(false);} };
  const analyzeSatisfaction = async () => { setAnalysisBusy(true);setError('');try{const result=await apiService.analyserSatisfactionDb(sessionId);if(!result.success){setError(result.message||'Analyse de satisfaction impossible.');return;}const linkedTrainer=trainers.find((item:any)=>String(item.userId)===String(formateurId));setAnalysis(result.data??result);if(linkedTrainer)setNotice('Analyse liée au profil du formateur. Après validation HITL, son rapport M4 sera généré automatiquement.');}catch(e){setError(e instanceof Error?e.message:'Analyse de satisfaction impossible.');}finally{setAnalysisBusy(false);} };
  const refreshM6 = async () => { setM6Busy(true); setError(''); try { setM6(await apiService.getM6Eligibility(sessionId)); } catch(e) { setError(e instanceof Error ? e.message : 'Vérification des présences impossible.'); } finally { setM6Busy(false); } };
  const focusReviewInAiSpace = (reviewId: string) => {
    try { sessionStorage.setItem('formaia-review-focus', reviewId); } catch { /* L'ouverture manuelle reste possible. */ }
    onNavigateToSection?.('espace_ia');
  };
  const generateM6 = async () => {
    setM6Busy(true); setError(''); setNotice('');
    try {
      const result = await apiService.generateSessionAttestations(sessionId);
      if (!result?.success) throw new Error(result?.message ?? 'Génération impossible.');
      const data = result.data ?? {};
      const pdfCount = Number(data.total_pdf_generated ?? data.total_generated ?? 0);
      if (pdfCount <= 0) {
        const failure = data.failed_participants?.[0]?.error;
        throw new Error(failure ? `Aucun PDF n’a été généré : ${failure}` : 'Aucun PDF n’a été généré pour cette session. Vérifiez les données et le journal backend.');
      }
      const reviewId = result.review_id ?? data._review_id;
      if (!reviewId) throw new Error(`${pdfCount} PDF généré(s), mais le dossier de validation n’a pas été retourné. Aucun téléchargement ne peut être ouvert.`);
      let savedReview: any = null;
      try { savedReview = (await apiService.getReview(String(reviewId))).review; } catch { /* Le message de génération reste disponible même si le rechargement échoue. */ }
      const batch = { reviewId: String(reviewId), status: savedReview?.status ?? 'pending_review', updatedAt: savedReview?.updated_at, attestations: savedReview?.data?.attestations ?? data.attestations ?? [], failed: savedReview?.data?.failed_participants ?? data.failed_participants ?? [] };
      setAttestationBatch(batch);
      try { localStorage.setItem(`formaia-attestations-${sessionId}`, String(reviewId)); } catch { /* L'historique HITL permettra de retrouver le lot approuvé. */ }
      setNotice(`${pdfCount} PDF préparé(s). Ouverture de la validation ; le téléchargement sera disponible après approbation.`);
      focusReviewInAiSpace(String(reviewId));
      await refreshM6();
    } catch(e) { setError(e instanceof Error ? e.message : 'Génération des attestations impossible.'); }
    finally { setM6Busy(false); }
  };
  const saveDownloadedFile = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.style.display = 'none';
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
  const downloadPdf = async (reviewId: string, numero: string) => {
    setAttestationDownloadBusy(numero); setError('');
    try {
      const blob = await apiService.downloadAttestation(reviewId, numero);
      if (!(blob instanceof Blob) || blob.size === 0) throw new Error('Le serveur n’a retourné aucun fichier PDF.');
      saveDownloadedFile(blob, `${numero}.pdf`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Téléchargement du PDF impossible.'); }
    finally { setAttestationDownloadBusy(''); }
  };
  const previewPdf = async (reviewId: string, numero: string) => {
    const previewWindow = window.open('', '_blank');
    setAttestationDownloadBusy(numero); setError('');
    try {
      const blob = await apiService.previewAttestation(reviewId, numero);
      if (!(blob instanceof Blob) || blob.size === 0) throw new Error('Le serveur n’a retourné aucun PDF à prévisualiser.');
      const url = URL.createObjectURL(blob);
      if (previewWindow) { previewWindow.location.href = url; window.setTimeout(() => URL.revokeObjectURL(url), 60000); }
      else { saveDownloadedFile(blob, `${numero}-apercu.pdf`); setNotice('La fenêtre d’aperçu a été bloquée ; le PDF a été téléchargé.'); }
    } catch (e) { previewWindow?.close(); setError(e instanceof Error ? e.message : 'Prévisualisation impossible.'); }
    finally { setAttestationDownloadBusy(''); }
  };
  const editAttestation = async (numero: string, content: any) => {
    if (!attestationBatch?.updatedAt) throw new Error('Rechargez le lot d’attestations avant de modifier le contenu.');
    try {
      const response = await apiService.editPendingAttestation(attestationBatch.reviewId, numero, content, attestationBatch.updatedAt);
      const review = response.review;
      setAttestationBatch((current: any) => ({ ...current, status: review.status, updatedAt: review.updated_at, attestations: review.data?.attestations ?? [] }));
      setNotice('Attestation modifiée. Le nouveau PDF attend une validation humaine.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Modification de l’attestation impossible.'); throw e; }
  };
  const deleteAttestation = async (numero: string) => {
    if (!attestationBatch?.updatedAt || !window.confirm(`Supprimer l’attestation ${numero} du lot en attente ?`)) return;
    try {
      const response = await apiService.deletePendingAttestation(attestationBatch.reviewId, numero, attestationBatch.updatedAt);
      const review = response.review;
      setAttestationBatch((current: any) => ({ ...current, status: review.status, updatedAt: review.updated_at, attestations: review.data?.attestations ?? [] }));
      setNotice('Attestation retirée du lot en attente.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Suppression de l’attestation impossible.'); }
  };
  const downloadAttestationZip = async (reviewId: string) => {
    setAttestationDownloadBusy('zip'); setError('');
    try {
      const blob = await apiService.downloadAttestationsZip(reviewId);
      if (!(blob instanceof Blob) || blob.size === 0) throw new Error('Le serveur n’a retourné aucun ZIP d’attestations.');
      saveDownloadedFile(blob, `attestations-${reviewId}.zip`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Téléchargement du ZIP impossible.'); }
    finally { setAttestationDownloadBusy(''); }
  };
  const generateReport = async () => {
    setReportBusy(true); setError(''); setNotice('');
    try {
      const eligibility = await apiService.getM6Eligibility(sessionId);
      if (!eligibility?.pointages_complets) {
        throw new Error(`Complétez les ${eligibility?.pointages_manquants ?? ''} pointage(s) manquant(s) avant de générer le rapport.`);
      }
      const session = eligibility.session ?? {};
      const people = Array.isArray(eligibility.participants) ? eligibility.participants : [];
      if (!people.length) throw new Error('Aucun participant inscrit : le rapport ne peut pas être établi.');
      const totalPresents = people.filter((person: any) => Number(person.nb_presences ?? 0) > 0).length;
      const presenceMoyenne = people.reduce((sum: number, person: any) => sum + Number(person.taux_presence ?? 0), 0) / people.length;
      const entreprises = [...new Set(people.map((person: any) => String(person.entreprise ?? '').trim()).filter(Boolean))];
      const result = await apiService.generateFormationReport({
        ...session,
        id: session.id ?? sessionId,
        titre: session.titre ?? sessionTitle,
        domaine: session.domaine ?? domain ?? formationCode ?? 'Formation',
        formation_code: session.formation_code ?? formationCode,
        date_debut: session.date_debut ?? sessionDateStart ?? '',
        date_fin: session.date_fin ?? sessionDateEnd ?? '',
        lieu: session.lieu ?? sessionLocation ?? 'À préciser',
        formateur: session.formateur ?? sessionTrainer ?? 'À préciser',
        duree_jours: Number(session.duree_jours ?? new Set(seances.map((item: any) => item.date)).size),
        duree_heures: session.duree_heures ?? undefined,
        total_inscrits: people.length,
        total_presents: totalPresents,
        taux_presence: `${presenceMoyenne.toFixed(1)}%`,
        entreprises,
      });
      if (!result?.success) throw new Error(result?.message ?? 'La génération du rapport a échoué.');
      const reviewId = result.review_id ?? result.data?._review_id;
      if (!reviewId) throw new Error('Le rapport a été préparé, mais son dossier de validation est introuvable.');
      focusReviewInAiSpace(String(reviewId));
      setNotice('Rapport final préparé à partir des données de présence et ouvert dans Espace IA pour validation.');
    } catch(e) { setError(e instanceof Error ? e.message : 'Génération du rapport de formation impossible.'); }
    finally { setReportBusy(false); }
  };
  useEffect(() => {
    if (!voiceAction) return;
    const data = voiceAction.prefill ?? {};
    if (voiceAction.action === 'ouvrir_formulaire_seance') {
      if (data.date || data.date_seance) setDate(String(data.date ?? data.date_seance));
      if (data.heure_debut || data.heure) setStart(String(data.heure_debut ?? data.heure));
      if (data.heure_fin) setEnd(String(data.heure_fin));
      if (data.theme || data.intitule) setTheme(String(data.theme ?? data.intitule));
      setNotice('Séance préparée dans la session sélectionnée. Vérifiez la date et le thème, puis validez sa création.');
    } else if (voiceAction.action === 'ouvrir_analyse_niveaux') {
      void analyzeLevels();
    } else if (voiceAction.action === 'ouvrir_analyse_satisfaction') {
      void analyzeSatisfaction();
    } else if (voiceAction.action === 'ouvrir_analyse_presences') {
      setNotice('La consultation des présences de cette session est ouverte. L’analyse automatique dédiée n’est pas raccordée à cet écran.');
    } else if (voiceAction.action === 'ouvrir_formulaire_attestation') {
      setNotice('La session est ouverte. Vérifiez les présences et l’éligibilité avant toute génération d’attestations.');
    } else if (voiceAction.action === 'ouvrir_formulaires_session') {
      setNotice('Session sélectionnée. La génération et la publication des formulaires doivent encore être raccordées à cet écran.');
    }
  // Le traitement doit s'exécuter une seule fois par commande vocale.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceAction]);
  const allStatuses = useMemo(() => [{v:'PRESENT',l:'Présent'},{v:'ABSENT',l:'Absent'},{v:'RETARD',l:'Retard'},{v:'EXCUSE',l:'Excusé'}] as const, []);
  const renderAttendanceCell = (seance: any, person: Person) => {
    const current = attendance[`${seance.id}:${person.id}`];
    if (trainerMode) {
      const label = allStatuses.find(status => status.v === current?.statut)?.l ?? 'À saisir';
      return <td key={seance.id} className="p-3"><span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 font-bold text-slate-700">{label}</span></td>;
    }
    return <td key={seance.id} className="space-y-1 p-2">
      <select value={current?.statut ?? ''} onChange={event => void save(seance.id, person.id, event.target.value as Attendance['statut'])} className="w-full rounded border border-slate-300 bg-white p-2">
        <option value="">À saisir</option>{allStatuses.map(status => <option key={status.v} value={status.v}>{status.l}</option>)}
      </select>
      {current?.statut === 'RETARD' && <input type="time" aria-label="Heure d’arrivée" value={current.heure_arrivee ?? ''} onChange={event => void save(seance.id, person.id, 'RETARD', {heure_arrivee:event.target.value})} className="w-full rounded border p-1.5"/>}
      {current?.statut === 'ABSENT' && <input placeholder="Motif (facultatif)" value={current.motif_absence ?? ''} onChange={event => setAttendance(previous => ({...previous, [`${seance.id}:${person.id}`]: {...current, motif_absence:event.target.value}}))} onBlur={event => void save(seance.id, person.id, 'ABSENT', {motif_absence:event.target.value})} className="w-full rounded border p-1.5"/>}
    </td>;
  };
  return <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"><div><h2 className="font-extrabold text-[#11162A]">Séances et présences · M5</h2><p className="mt-1 text-xs text-slate-500">{trainerMode ? 'Ajoutez une séance pour chaque journée de votre formation. Les présences restent consultables.' : 'Créez les séances, puis renseignez les présences par participant. Chaque changement est sauvegardé immédiatement.'}</p></div>
    <form onSubmit={create} className="grid gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-6"><label className="text-[11px] font-bold text-slate-600">Date<input required type="date" value={date} onChange={e=>setDate(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600">Début<input required type="time" value={start} onChange={e=>setStart(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600">Fin<input required type="time" value={end} onChange={e=>setEnd(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label><label className="text-[11px] font-bold text-slate-600 md:col-span-2">Thème<input required value={theme} onChange={e=>setTheme(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"/></label>{!trainerMode && <label className="text-[11px] font-bold text-slate-600">Formateur<select value={trainer} onChange={e=>setTrainer(e.target.value)} className="mt-1 w-full rounded-lg border bg-white p-2"><option value="">Formateur de session</option>{trainers.map(t=><option key={t.id ?? t.userId} value={t.id ?? t.userId}>{t.prenom} {t.nom}</option>)}</select></label>}<button disabled={busy} className="rounded-lg bg-[#1B8F6E] px-4 py-2 text-xs font-bold text-white md:col-span-6">{busy?'Création…':'Ajouter une séance'}</button></form>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700">{error}</p>}{notice && <p className="text-xs text-emerald-700">{notice}</p>}
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-600"><tr><th className="p-3">Participant</th><th className="p-3">Taux présence</th>{seances.map(seance => <th key={seance.id} className="min-w-44 p-3">{seance.date}<br/><span className="font-normal">{seance.heure_debut ?? ''} {seance.theme}</span></th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100">{participants.map(person => <tr key={person.id}><td className="p-3 font-semibold">{person.prenom ? `${person.prenom} ` : ''}{person.nom}</td><td className="p-3 font-bold">{rate(person.id)}%</td>{seances.map(seance => renderAttendanceCell(seance, person))}</tr>)}</tbody>
      </table>
    </div>
    {!trainerMode && <div className="grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2"><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la progression avant / après</h3><p className="text-[11px] text-slate-500">Les scores de positionnement (lien inscription) et de test final (lien post-formation) sont lus directement depuis la base de données.</p><button disabled={analysisBusy} onClick={()=>void analyzeLevels()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{analysisBusy?'Analyse en cours…':'Analyser les niveaux'}</button></div><div className="space-y-2 rounded-xl bg-slate-50 p-4"><h3 className="font-bold text-slate-800">Analyser la satisfaction</h3><p className="text-[11px] text-slate-500">Les réponses au questionnaire de satisfaction (lien post-formation) sont lues directement depuis la base de données.</p><button disabled={analysisBusy} onClick={()=>void analyzeSatisfaction()} className="rounded-lg bg-[#11162A] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{analysisBusy?'Analyse en cours…':'Analyser la satisfaction'}</button></div></div>}
    {!trainerMode && <section className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-white to-emerald-50/70 shadow-sm"><div className="flex flex-col gap-4 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700"><Award size={22}/></span><div><h3 className="font-extrabold text-[#11162A]">Attestations de formation · M6</h3><p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-500">Le seuil réglementaire du projet est de 75 %. Les taux sont recalculés depuis les pointages enregistrés. Toute séance sans pointage doit être complétée avant la génération.</p></div></div><div className="flex flex-wrap gap-2"><button type="button" disabled={m6Busy} onClick={()=>void refreshM6()} className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{m6Busy?<Loader2 size={14} className="mr-1 inline animate-spin"/>:<ShieldCheck size={14} className="mr-1 inline"/>}Vérifier l’éligibilité</button><button type="button" disabled={m6Busy||!m6?.total_eligible||!m6?.pointages_complets} onClick={()=>void generateM6()} className="rounded-xl bg-[#1B8F6E] px-4 py-2.5 text-xs font-extrabold text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-45">{m6Busy?<Loader2 size={14} className="mr-1 inline animate-spin"/>:<Award size={14} className="mr-1 inline"/>}Préparer les attestations</button></div></div>{attestationBatch && <AttestationBatchCard batch={attestationBatch} sessionTitle={sessionTitle} busy={attestationDownloadBusy} onDownloadPdf={(reviewId, numero) => void downloadPdf(reviewId, numero)} onPreviewPdf={(reviewId, numero) => void previewPdf(reviewId, numero)} onEdit={editAttestation} onDelete={deleteAttestation} onDownloadZip={reviewId => void downloadAttestationZip(reviewId)}/>}{m6 && <div className="space-y-4 p-5"><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-slate-100 bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Participants inscrits</div><div className="mt-1 text-2xl font-extrabold text-[#11162A]">{m6.total_participants}</div></div><div className="rounded-xl border border-emerald-100 bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-emerald-700">Éligibles · seuil 75 %</div><div className="mt-1 text-2xl font-extrabold text-emerald-700">{m6.total_eligible}</div></div><div className={`rounded-xl border p-3 ${m6.pointages_complets?'border-slate-100 bg-white':'border-amber-200 bg-amber-50'}`}><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">État des pointages</div><div className={`mt-1 text-sm font-extrabold ${m6.pointages_complets?'text-emerald-700':'text-amber-800'}`}>{m6.pointages_complets?'Complets':`${m6.pointages_manquants} à compléter`}</div></div></div><div className="overflow-x-auto rounded-xl border border-slate-200 bg-white"><table className="min-w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Participant</th><th className="px-4 py-3">Présence</th><th className="px-4 py-3">Pointages</th><th className="px-4 py-3">Décision</th></tr></thead><tbody className="divide-y divide-slate-100">{m6.participants.map((person:any)=><tr key={person.id}><td className="px-4 py-3 font-bold text-slate-800">{person.nom}</td><td className="px-4 py-3"><div className="flex items-center gap-2"><div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${person.eligible_attestation?'bg-emerald-500':'bg-rose-500'}`} style={{width:`${Math.min(100,person.taux_presence)}%`}}/></div><span className="font-extrabold tabular-nums text-slate-700">{person.taux_presence}%</span></div></td><td className="px-4 py-3 text-slate-600">{person.nb_presences}/{person.nb_seances}{person.pointages_manquants?` · ${person.pointages_manquants} manquant(s)`:''}</td><td className="px-4 py-3"><span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-extrabold ${person.eligible_attestation?'bg-emerald-100 text-emerald-800':person.pointages_manquants?'bg-amber-100 text-amber-800':'bg-rose-100 text-rose-800'}`}>{person.eligible_attestation?<CheckCircle2 size={12}/>:null}{person.eligible_attestation?'Éligible':person.pointages_manquants?'À compléter':'Non éligible'}</span></td></tr>)}</tbody></table></div><p className="flex items-center gap-2 text-[11px] text-slate-500"><ShieldCheck size={14} className="text-emerald-700"/>Les compétences proposées proviennent des supports indexés, du syllabus approuvé ou des thèmes de séances. La direction conserve la validation finale avant distribution.</p></div>}</section>}
    {!trainerMode && <section className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-extrabold text-[#11162A]">Clôture de la formation</h3><p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-500">Le rapport est préparé à partir des informations de la session et des présences enregistrées. Les données de progression ou de satisfaction absentes restent non renseignées et le contenu passe en validation humaine. La facture créée ici sera directement rattachée à cette session.</p>{sessionStatus !== 'Terminée' && <p className="mt-2 text-[11px] font-semibold text-amber-700">Rapport et facturation disponibles après la date de fin ({sessionDateEnd ?? 'à préciser'}).</p>}</div><div className="flex shrink-0 flex-wrap gap-2"><button type="button" disabled={reportBusy || sessionStatus !== 'Terminée'} onClick={() => void generateReport()} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#11162A] px-4 py-3 text-xs font-extrabold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45">{reportBusy ? <Loader2 size={15} className="animate-spin"/> : <FileText size={15}/>} {reportBusy ? 'Génération…' : 'Générer le rapport'}</button><button type="button" disabled={sessionStatus !== 'Terminée'} onClick={() => onOpenNewInvoice?.(sessionId)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#1B8F6E] px-4 py-3 text-xs font-extrabold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-45"><ReceiptText size={15}/>Créer la facture liée</button></div></section>}
    {analysis && <AnalysisResult analysis={analysis}/>}
  </section>;
};
