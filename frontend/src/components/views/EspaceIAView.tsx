import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, FileText, Loader2, MessageCircle, Paperclip, Send, ShieldCheck, Trash2, Upload, X } from 'lucide-react';
import { apiService } from '../../services/api';

type Tab = 'reviews' | 'supports' | 'chat' | 'syllabus';
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Une erreur est survenue.';
const panel = 'bg-white p-5 rounded-2xl border border-slate-200 shadow-xs';
const supportStatusStyle: Record<string, string> = {
  en_attente: 'bg-slate-100 text-slate-600', en_cours: 'bg-blue-50 text-blue-700',
  indexe: 'bg-emerald-50 text-emerald-700', deja_indexe: 'bg-emerald-50 text-emerald-700',
  erreur: 'bg-red-50 text-red-700', ocr_necessaire: 'bg-amber-50 text-amber-800',
  non_indexable_image: 'bg-amber-50 text-amber-800'
};
const supportStatusLabel: Record<string, string> = {
  en_attente: 'En attente', en_cours: 'Indexation en cours', indexe: 'Indexé', deja_indexe: 'Déjà indexé',
  erreur: 'Erreur d’indexation', ocr_necessaire: 'OCR nécessaire', non_indexable_image: 'Image non indexable'
};
const labels: Record<string, string> = {
  resume: 'Résumé', synthese: 'Synthèse', progression: 'Progression', competences: 'Compétences',
  points_forts: 'Points forts', axes_amelioration: 'Axes d’amélioration', recommandations: 'Recommandations',
  nps: 'NPS', score_global: 'Score global', moyenne: 'Moyenne', commentaires: 'Commentaires',
  sentiment: 'Sentiment', participant: 'Participant', nom: 'Nom', prenom: 'Prénom',
  reponses: 'Réponses', question: 'Question', score: 'Score', niveau: 'Niveau',
  avant: 'Avant la formation', apres: 'Après la formation', taux: 'Taux',
  titre: 'Titre', domaine: 'Domaine', session_id: 'Session', date: 'Date'
};
const humanize = (key: string) => labels[key.toLowerCase()] ?? key.replace(/[_-]+/g, ' ').replace(/^./, c => c.toUpperCase());
const isOfferReview = (review: any) => String(review?.agent_id ?? '').startsWith('agent_m3_')
  || /(?:^|-)AM3(?:-|$)/i.test(String(review?.review_id ?? review?.id ?? ''));
const readableValue = (value: any): any => {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try { return JSON.parse(trimmed); } catch { return value; }
  }
  return value;
};

const unwrapReview = (value: any) => {
  let current = value;
  for (let depth = 0; depth < 4 && current && typeof current === 'object'; depth += 1) {
    if (current.review && typeof current.review === 'object') { current = current.review; continue; }
    if (current.success === true && current.data && typeof current.data === 'object') { current = current.data; continue; }
    break;
  }
  return current;
};

const ReviewContent: React.FC<{ value: any }> = ({ value }) => {
  const content = readableValue(value?.data ?? value?.contenu ?? value);
  const renderNode = (node: any, depth = 0): React.ReactNode => {
    node = readableValue(node);
    if (node === null || node === undefined || node === '') return <span className="text-slate-400">—</span>;
    if (typeof node === 'boolean') return <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${node ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}`}>{node ? 'Oui' : 'Non'}</span>;
    if (typeof node === 'number') return <span className="font-bold tabular-nums">{Number.isInteger(node) ? node : node.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}</span>;
    if (typeof node === 'string') return <span className="whitespace-pre-wrap leading-relaxed">{node}</span>;
    if (Array.isArray(node)) {
      if (!node.length) return <span className="text-xs text-slate-400">Aucun élément</span>;
      const objects = node.filter(x => x && typeof readableValue(x) === 'object' && !Array.isArray(readableValue(x)));
      if (objects.length === node.length) {
        const columns = [...new Set(objects.flatMap((item: any) => Object.keys(readableValue(item)).filter(k => !k.startsWith('_'))))].slice(0, 5);
        return <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr>{columns.map(col => <th key={col} className="px-3 py-2.5">{humanize(col)}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{objects.map((item: any, i: number) => <tr key={i} className="align-top">{columns.map(col => <td key={col} className="px-3 py-2.5 text-slate-700">{renderNode(readableValue(item)[col], depth + 1)}</td>)}</tr>)}</tbody></table></div>;
      }
      return <div className="space-y-2">{node.map((item, i) => <div key={i} className="rounded-xl border border-slate-100 bg-white p-3 text-sm">{renderNode(item, depth + 1)}</div>)}</div>;
    }
    if (typeof node === 'object') {
      const entries = Object.entries(node).filter(([key, val]) => !key.startsWith('_') && key !== 'success' && val !== undefined && val !== null && val !== '');
      if (!entries.length) return <span className="text-xs text-slate-400">Aucun détail fourni</span>;
      const metrics = depth === 0 ? entries.filter(([, val]) => typeof readableValue(val) === 'number' || typeof readableValue(val) === 'boolean') : [];
      const rest = metrics.length ? entries.filter(([key]) => !metrics.some(([metric]) => metric === key)) : entries;
      return <div className="space-y-3">{metrics.length > 0 && <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{metrics.map(([key, val]) => <div key={key} className="rounded-xl bg-gradient-to-br from-emerald-50 to-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{humanize(key)}</div><div className="mt-1 text-lg font-extrabold text-[#1B8F6E]">{renderNode(val, depth + 1)}</div></div>)}</div>}{rest.map(([key, val]) => <section key={key} className="rounded-xl border border-slate-200 bg-white p-3.5"><h3 className="mb-2 text-xs font-extrabold text-[#11162A]">{humanize(key)}</h3><div className="text-xs text-slate-700">{renderNode(val, depth + 1)}</div></section>)}</div>;
    }
    return String(node);
  };
  return <div className="max-h-[560px] space-y-3 overflow-auto rounded-2xl bg-slate-50 p-3">{renderNode(content)}</div>;
};

export const EspaceIAView: React.FC<{ readOnly?: boolean; trainerMode?: boolean }> = ({ readOnly = false, trainerMode = false }) => {
  const [tab, setTab] = useState<Tab>(readOnly ? 'supports' : 'reviews');
  const [reviews, setReviews] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [deletingReviewId, setDeletingReviewId] = useState('');
  const [supports, setSupports] = useState<any[]>([]);
  const [formations, setFormations] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [chatModule, setChatModule] = useState('');
  const [formationCode, setFormationCode] = useState('');
  const [module, setModule] = useState('');
  const [syllabusForm, setSyllabusForm] = useState({ formation_code: '', modules: '', format: 'présentiel' });
  const [file, setFile] = useState<File | null>(null);
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string; sources?: any[]; suggestions?: string[] }>>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [streamingStatus, setStreamingStatus] = useState('');

  const loadReviews = async () => {
    const responses = await Promise.allSettled([apiService.getPendingReviews(), apiService.getRagReviews(), apiService.getOfferReviews()]);
    if (responses.every(result => result.status === 'rejected')) throw new Error('Impossible de charger les validations. Vérifiez la connexion au backend.');
    const backend = responses[0].status === 'fulfilled' ? responses[0].value : { reviews: [] };
    const rag = responses[1].status === 'fulfilled' ? responses[1].value : { data: [] };
    const offers = responses[2].status === 'fulfilled' ? responses[2].value : { data: [] };
    // Toutes les validations doivent être consultables ici, y compris TDR,
    // offres technique/financière et contenus RAG. Les retirer de la liste
    // faisait apparaître un compteur sans aperçu correspondant.
    const regularReviews = (backend.reviews ?? []).filter((item: any) => !String(item.agent_id ?? '').startsWith('agent_rag_'));
    const ragReviews = Array.isArray(rag.data) ? rag.data : [];
    const offerReviews = Array.isArray(offers.data) ? offers.data : [];
    const unique = new Map<string, any>();
    [...regularReviews, ...offerReviews, ...ragReviews].forEach((item: any) => unique.set(String(item.review_id ?? item.id), item));
    setReviews([...unique.values()]);
  };
  const loadSupports = async (formationFilter = formationCode, sessionFilter = sessionId) => {
    const params = sessionFilter ? { session_id: sessionFilter } : formationFilter ? { formation_code: formationFilter } : {};
    const [list, courses, sessionResponse] = await Promise.all([apiService.getSupports(params), apiService.getRagFormations(), apiService.getRagSessions()]);
    const availableCourses = Array.isArray(courses) ? courses : courses.data ?? courses.formations ?? [];
    const sessionRows = Array.isArray(sessionResponse) ? sessionResponse : sessionResponse.data ?? [];
    setSupports(Array.isArray(list) ? list : list.data ?? list.supports ?? []);
    setFormations(availableCourses);
    setSessions(sessionRows);
    if (trainerMode && !sessionFilter && !sessionId && sessionRows.length === 1) {
      setSessionId(sessionRows[0].id);
      setFormationCode(sessionRows[0].formation_code ?? '');
    }
  };
  useEffect(() => { setError(''); setNotice(''); if (tab === 'reviews') loadReviews().catch(e => setError(errorText(e))); if (tab === 'supports' || tab === 'chat') loadSupports().catch(e => setError(errorText(e))); if (tab === 'syllabus') apiService.getRagFormations().then(data => setFormations(Array.isArray(data) ? data : data.data ?? data.formations ?? [])).catch(e => setError(errorText(e))); }, [tab, formationCode, sessionId]);

  const openReview = async (item: any) => {
    setSelected(item); setReviewLoading(true); setError('');
    try {
      const id = item.review_id ?? item.id;
      const isRag = String(item.agent_id ?? '').startsWith('agent_rag_');
      const isOffer = isOfferReview(item);
      const data = isRag ? await apiService.getRagReview(id) : isOffer ? await apiService.getOfferReview(id) : await apiService.getReview(id);
      const detail = unwrapReview(data);
      setSelected(detail && typeof detail === 'object' ? detail : item);
    }
    catch (e) { setError(errorText(e)); }
    finally { setReviewLoading(false); }
  };
  const reviewAction = async (approve: boolean) => {
    const id = selected?.review_id ?? selected?.id;
    if (!id) return;
    if (!approve && reviewNote.trim().length < 3) { setError('Le motif du rejet doit contenir au moins 3 caractères.'); return; }
    const reviewerNote = reviewNote.trim() || 'OK';
    setBusy(true); setError('');
    let actionNotice = '';
    try {
      const isRag = String(selected?.agent_id ?? '').startsWith('agent_rag_');
      const isOffer = isOfferReview(selected);
      if (isRag) {
        if (approve) await apiService.approveRagReview(id, reviewerNote);
        else await apiService.rejectRagReview(id, reviewNote);
      } else if (isOffer) {
        if (approve) await apiService.approveOfferReview(id, reviewerNote);
        else await apiService.rejectOfferReview(id, reviewNote);
        if (approve && String(selected?.agent_id) === 'agent_m3_complete') {
          await apiService.syncOffer(id, selected?.data?.opportunite_id ?? selected?.data?._inputs?.tdr_data?.opportunite_id ?? selected?.opportunite_id);
          actionNotice = 'Offre approuvée et synchronisée avec le backend.';
        }
      } else {
        const agent = String(selected?.agent_id ?? '');
        if (!approve) await apiService.rejectReview(id, reviewNote);
        else if (agent === 'agent_m2_tdr') {
          await apiService.approveTdr(id, reviewerNote);
          await apiService.syncTdr(id, selected?.data?.opportunite_id ?? selected?.opportunite_id);
          actionNotice = 'TDR approuvé et synchronisé avec le backend.';
        } else {
          await apiService.approveReview(id, reviewerNote);
          if (agent === 'agent_m3_complete') {
            await apiService.syncOffer(id, selected?.data?.opportunite_id ?? selected?.opportunite_id);
            actionNotice = 'Offre approuvée et synchronisée avec le backend.';
          }
          if (agent.includes('m7') || agent.includes('relance')) await apiService.syncInvoiceReminder(id);
          if (agent.includes('m7') || agent.includes('relance')) actionNotice = 'Relance approuvée et enregistrée avec le backend.';
          if (agent === 'agent_m4_evaluation') {
            const trainerId = selected?.meta?.formateur_id ?? selected?.data?.formateur_id;
            if (!trainerId) throw new Error('Cette évaluation ne contient pas le dossier du formateur associé. Regénérez-la depuis Évaluation compétences.');
            await apiService.syncTrainerEvaluation(id, trainerId);
            actionNotice = 'Évaluation approuvée et ajoutée à la synthèse du formateur.';
          }
          if (agent === 'agent_3_satisfaction') {
            const trainerId = selected?.meta?.formateur_id;
            const trainerName = selected?.meta?.formateur_nom;
            if (trainerId && trainerName) {
              const satisfaction = selected?.data?.statistiques ?? {};
              const score = satisfaction?.notes?.note_globale ?? satisfaction?.notes?.satisfaction ?? null;
              const result = await apiService.analyzeTrainerEvaluation({
                formateur: trainerName,
                formateur_id: trainerId,
                session: selected?.meta?.session_title ?? selected?.data?.session ?? selected?.summary ?? 'Session de formation',
                donnees_session: {
                  satisfaction: {
                    score_moyen: score,
                    points_positifs: selected?.data?.points_forts ?? [],
                    points_negatifs: selected?.data?.axes_amelioration ?? []
                  },
                  presences: selected?.meta?.taux_presence != null ? { taux_moyen_pct: Number(selected.meta.taux_presence), anomalies: false } : {},
                  rapport: selected?.data?.interpretation ?? selected?.summary ?? ''
                }
              });
              actionNotice = `Satisfaction M5 validée ; le rapport M4 du formateur est créé et attend sa validation${result.review_id ? ` (${result.review_id})` : ''}.`;
            }
          }
          if (agent.includes('forms')) {
            const published = await apiService.publishFormationForms(id, selected?.data?.titre ?? selected?.title ?? selected?.titre ?? 'Formation');
            const urls = Object.values(published.forms_urls ?? {}).filter(Boolean).join(' · ');
            actionNotice = urls ? `Formulaires approuvés et publiés : ${urls}` : published.message ?? 'Formulaires approuvés et publication demandée.';
          }
        }
      }
      const agent = String(selected?.agent_id ?? '');
      const wasSynced = !isRag && (agent === 'agent_m2_tdr' || agent === 'agent_m3_complete' || agent.includes('m7') || agent.includes('relance'));
      setNotice(approve ? (actionNotice || (wasSynced ? 'Contenu approuvé et synchronisé avec le backend.' : 'Contenu approuvé.')) : 'Contenu rejeté.'); setSelected(null); setReviewNote(''); await loadReviews();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const deleteReview = async (item: any) => {
    const id = String(item.review_id ?? item.id ?? '');
    if (!id || deletingReviewId) return;
    if (!window.confirm('Supprimer cette validation en attente ? Cette action ne peut pas être annulée.')) return;
    setDeletingReviewId(id); setError(''); setNotice('');
    try {
      const isRag = String(item.agent_id ?? '').startsWith('agent_rag_');
      const isOffer = isOfferReview(item);
      if (isRag) await apiService.deleteRagReview(id);
      else if (isOffer) await apiService.deleteOfferReview(id);
      else await apiService.deleteReview(id);
      if (String(selected?.review_id ?? selected?.id ?? '') === id) setSelected(null);
      setNotice('Validation en attente supprimée.');
      await loadReviews();
    } catch (e) { setError(errorText(e)); }
    finally { setDeletingReviewId(''); }
  };
  const upload = async (e: React.FormEvent) => {
    e.preventDefault(); if (!file || !sessionId) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const code = formationCode.trim();
      const uploaded: any = await apiService.uploadSupport(file, code, sessionId, 'support', module.trim() || undefined);
      if (!uploaded.chemin_fichier) throw new Error('Le backend n’a pas retourné le chemin du support téléversé.');
      await apiService.indexSupport(uploaded.chemin_fichier, code, sessionId, module.trim() || undefined);
      setFile(null); setModule(''); await loadSupports(code, sessionId);
      if (uploaded.hash) {
        setNotice(`Support associé à ${code} : indexation en cours…`);
        for (let attempt = 0; attempt < 12; attempt += 1) {
          await new Promise(resolve => window.setTimeout(resolve, 1500));
          const result: any = await apiService.getRagIndexStatus(uploaded.hash);
          const indexed = result.data ?? result;
          const status = indexed.statut;
          setSupports(previous => previous.map(support => (support.hash ?? support.doc_hash) === uploaded.hash ? { ...support, ...indexed } : support));
          if (status === 'indexe' || status === 'erreur' || status === 'ocr_necessaire' || status === 'non_indexable_image') {
            await loadSupports(code, sessionId);
            setNotice(status === 'indexe' ? `Support indexé et rattaché à la formation ${code}. Les recherches ciblées utiliseront ce document.` : result.data?.message || result.message || `L’indexation du document a terminé avec le statut « ${supportStatusLabel[status] ?? status} ».`);
            break;
          }
          if (attempt === 11) { await loadSupports(code, sessionId); setNotice(`Support rattaché à la session ; l’indexation continue en arrière-plan. Son statut reste visible dans la liste des supports.`); }
        }
      } else {
        setNotice(`Support rattaché à ${code} et indexation lancée.`);
      }
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const generateSyllabus = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const rows = syllabusForm.modules.split('\n').map(line => line.trim()).filter(Boolean);
      const modules = rows.map((line, index) => {
        const [titre, duree] = line.split('|').map(part => part.trim());
        if (!titre || !duree) throw new Error(`Ligne ${index + 1} : indiquez « Module | durée » (ex. Atelier | 3h).`);
        return { titre, duree, contenus: '', methodes: '', objectif_lie: `Module ${index + 1}` };
      });
      if (!modules.length) throw new Error('Ajoutez au moins un module avec sa durée.');
      const result = await apiService.generateSyllabus({ formation_code: syllabusForm.formation_code, modules, options: { format: syllabusForm.format } });
      const reviewId = result?._review_id ?? result?.review_id ?? result?.data?._review_id;
      setNotice(`Syllabus généré et envoyé pour validation humaine${reviewId ? ` · ${reviewId}` : ''}. Consultez l’onglet Validation IA.`);
      setSyllabusForm(previous => ({ ...previous, modules: '' }));
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const sendMessage = async (text = draft) => {
    const message = text.trim(); if (!message || busy) return;
    if (trainerMode && !sessionId) { setError('Sélectionnez d’abord une session qui vous est affectée.'); return; }
    setMessages(prev => [...prev, { role: 'user', text: message }, { role: 'assistant', text: '' }]); setDraft(''); setBusy(true); setError(''); setStreamingStatus('Connexion à l’assistant documentaire…');
    try {
      await apiService.chatRagStream({ message, conversation_id: conversationId, formation_code: formationCode || null, session_id: sessionId || null, module: chatModule || null }, event => {
        if (event.type === 'status') setStreamingStatus(event.message ?? 'Préparation de la réponse…');
        if (event.type === 'token') setMessages(previous => {
          const next = [...previous]; const last = next[next.length - 1];
          if (last?.role === 'assistant') next[next.length - 1] = { ...last, text: last.text + (event.text ?? '') };
          return next;
        });
        if (event.type === 'meta') {
          const data = event.data ?? {};
          if (data.conversation_id) setConversationId(data.conversation_id);
          setMessages(previous => {
            const next = [...previous]; const last = next[next.length - 1];
            if (last?.role === 'assistant') next[next.length - 1] = { ...last, sources: trainerMode ? [] : data.sources ?? [], suggestions: data.suggestions ?? [] };
            return next;
          });
        }
        if (event.type === 'error') {
          const messageErreur = event.message ?? 'Erreur pendant la génération de la réponse.';
          setError(messageErreur);
          setMessages(previous => {
            const next = [...previous]; const last = next[next.length - 1];
            if (last?.role === 'assistant' && !last.text) next[next.length - 1] = { ...last, text: messageErreur };
            return next;
          });
        }
      });
    } catch (e) {
      setError(errorText(e));
      setMessages(previous => previous.filter((item, index) => !(index === previous.length - 1 && item.role === 'assistant' && !item.text)));
    } finally { setBusy(false); setStreamingStatus(''); }
  };

  const tabs: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
    ...(!readOnly ? [{ id: 'reviews' as const, label: 'Validation IA', icon: <ShieldCheck size={15} /> }] : []),
    ...(!readOnly ? [{ id: 'syllabus' as const, label: 'Générer un syllabus', icon: <FileText size={15} /> }] : []),
    { id: 'supports', label: 'Supports RAG', icon: <Paperclip size={15} /> },
    { id: 'chat', label: 'Chat documentaire', icon: <MessageCircle size={15} /> }
  ];
  return <div className="space-y-6 animate-in fade-in duration-300">
    <div className={`${panel} flex flex-col md:flex-row md:items-center md:justify-between gap-4`}>
      <div><div className="text-[11px] font-bold uppercase tracking-wider text-[#1B8F6E]">Services connectés au backend</div><h1 className="text-2xl font-extrabold text-[#11162A] mt-1">Espace IA</h1><p className="text-xs text-slate-500 mt-1">Validez les contenus générés, alimentez la base documentaire et échangez avec vos supports.</p></div>
      <div className="flex gap-1.5 bg-slate-100 p-1.5 rounded-xl text-xs font-bold flex-wrap">{tabs.map(t => <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-2 rounded-lg flex items-center gap-1.5 ${tab === t.id ? 'bg-white text-[#11162A] shadow-xs' : 'text-slate-500'}`}>{t.icon}{t.label}</button>)}</div>
    </div>
    {error && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex gap-2"><AlertCircle size={15} />{error}</div>}
    {notice && <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">{notice}</div>}

    {tab === 'reviews' && <div className="grid lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)] gap-4">
      <section className={panel}><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="font-extrabold text-[#11162A]">À valider</h2><span className="text-xs bg-emerald-50 text-emerald-700 rounded-full px-2.5 py-1 font-bold">{reviews.length}</span></div>
        {reviews.length ? <div className="space-y-2">{reviews.map((r, i) => { const id = String(r.review_id ?? r.id ?? i); return <div key={id} className={`flex items-center gap-2 rounded-xl border p-2 ${selected?.review_id === id ? 'border-[#1B8F6E] bg-emerald-50/50' : 'border-slate-200 hover:border-slate-300'}`}><button onClick={() => openReview(r)} className="min-w-0 flex-1 p-1 text-left"><div className="truncate font-bold text-sm text-[#11162A]">{r.title ?? r.titre ?? r.summary ?? r.agent_id ?? 'Contenu généré'}</div><div className="mt-1 truncate text-[11px] text-slate-500">{r.agent_id ?? r.type ?? 'Agent IA'} · {r.created_at ? new Date(r.created_at).toLocaleString('fr-FR') : r.date_creation ?? ''}</div></button><button type="button" aria-label={`Supprimer la validation ${id}`} title="Supprimer cette validation" disabled={deletingReviewId !== '' || busy} onClick={() => void deleteReview(r)} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-100 bg-red-50 text-red-600 transition hover:bg-red-100 disabled:cursor-wait disabled:opacity-50">{deletingReviewId === id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}</button></div>; })}</div> : <p className="text-xs text-slate-500">Aucun contenu en attente de validation.</p>}
      </section>
      <section className={panel}>{selected ? <><div className="flex items-start justify-between gap-3"><div><h2 className="font-extrabold text-[#11162A]">{selected.summary ?? selected.title ?? 'Aperçu du contenu à valider'}</h2><p className="text-[11px] text-slate-500 mt-1">{selected.agent_id ?? selected.type ?? selected.review_id} · {selected.criticity ?? ''} · {selected.created_at ? new Date(selected.created_at).toLocaleString('fr-FR') : ''}</p></div><button onClick={() => setSelected(null)} className="p-1.5 text-slate-400 hover:text-slate-700"><X size={16} /></button></div>{reviewLoading ? <div className="mt-6 flex min-h-48 items-center justify-center gap-2 text-sm font-semibold text-slate-500"><Loader2 size={18} className="animate-spin text-[#1B8F6E]" />Chargement de l’aperçu complet…</div> : <><div className="mt-4"><ReviewContent value={selected} /></div><textarea value={reviewNote} onChange={e => setReviewNote(e.target.value)} placeholder="Note d’approbation ou motif du rejet (3 caractères minimum)" rows={2} className="mt-3 w-full p-3 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]" /><div className="flex justify-end gap-2 mt-3"><button disabled={busy} onClick={() => reviewAction(false)} className="px-4 py-2 bg-red-50 text-red-700 rounded-lg text-xs font-bold">Rejeter</button><button disabled={busy} onClick={() => reviewAction(true)} className="px-4 py-2 bg-[#1B8F6E] text-white rounded-lg text-xs font-bold flex gap-1.5 items-center">{busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}Approuver</button></div></>}</> : <div className="h-full min-h-56 flex flex-col items-center justify-center text-center text-slate-400"><FileText size={30} className="mb-2" /><p className="text-xs font-semibold">Sélectionnez un contenu pour le consulter.</p></div>}</section>
    </div>}

    {tab === 'syllabus' && <div className="grid gap-4 lg:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.15fr)]">
      <form onSubmit={generateSyllabus} className={`${panel} space-y-4`}>
        <div><h2 className="font-extrabold text-[#11162A]">Générer un syllabus avec le RAG</h2><p className="mt-1 text-xs text-slate-500">Le syllabus s’appuie sur les supports indexés et passe en validation humaine avant utilisation.</p></div>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Formation du catalogue *<select required value={syllabusForm.formation_code} onChange={e => setSyllabusForm(previous => ({ ...previous, formation_code: e.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal normal-case text-slate-800"><option value="">Sélectionner une formation</option>{formations.map((formation: any) => <option key={formation.code ?? formation.formation_code} value={formation.code ?? formation.formation_code}>{formation.code ?? formation.formation_code} — {formation.titre ?? formation.nom}</option>)}</select></label>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Modules et durées *<textarea required value={syllabusForm.modules} onChange={e => setSyllabusForm(previous => ({ ...previous, modules: e.target.value }))} rows={7} placeholder={'Introduction | 1 jour\nAtelier pratique | 3h\nÉvaluation | 2h'} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm font-normal normal-case text-slate-800"/><span className="mt-1 block text-[10px] font-normal normal-case text-slate-500">Une ligne par module au format « titre | durée ».</span></label>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Format<select value={syllabusForm.format} onChange={e => setSyllabusForm(previous => ({ ...previous, format: e.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal normal-case"><option value="présentiel">Présentiel</option><option value="distanciel">Distanciel</option><option value="hybride">Hybride</option></select></label>
        <button disabled={busy || !syllabusForm.formation_code} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#1B8F6E] px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50">{busy ? <Loader2 size={15} className="animate-spin"/> : <FileText size={15}/>}Générer et soumettre à validation</button>
      </form>
      <section className={`${panel} space-y-4`}><h2 className="font-extrabold text-[#11162A]">Documents de formation</h2><p className="text-xs leading-relaxed text-slate-600">Les syllabus générés apparaissent dans <strong>Validation IA</strong>. Les supports nécessaires au RAG se déposent dans l’onglet <strong>Supports RAG</strong>, puis sont indexés pour enrichir les prochains syllabus.</p><button type="button" onClick={() => setTab('supports')} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-bold text-[#11162A]">Ouvrir les supports documentaires</button>{formations.length === 0 && <p className="rounded-lg bg-amber-50 p-3 text-[11px] text-amber-800">Le catalogue de formations n’est pas disponible. Vérifiez le backend RAG avant de générer le syllabus.</p>}</section>
    </div>}

    {tab === 'supports' && <div className="grid lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)] gap-4">
      {(!readOnly || trainerMode) && <form onSubmit={upload} className={`${panel} space-y-4`}><div><h2 className="font-extrabold text-[#11162A]">Ajouter un support de formation</h2><p className="mt-1 text-[11px] leading-relaxed text-slate-500">{trainerMode ? 'Choisissez une session qui vous est affectée ; le document ne sera visible que dans celle-ci.' : 'Chaque support est classé par session puis par module pour éviter de mélanger les contenus.'}</p></div><div><label className="block font-bold text-slate-600 text-[11px] uppercase mb-1">Session de formation *</label><select required value={sessionId} onChange={e => { const id = e.target.value; setSessionId(id); setFormationCode(sessions.find((item: any) => item.id === id)?.formation_code ?? ''); setModule(''); }} className="w-full px-3 py-2.5 border border-slate-300 bg-slate-50 rounded-xl text-sm"><option value="">Sélectionner une session</option>{sessions.map((item: any) => <option key={item.id} value={item.id}>{item.titre}{item.formation_code ? ` — ${item.formation_code}` : ''}</option>)}</select></div><div><label className="block font-bold text-slate-600 text-[11px] uppercase mb-1">Séance / module pédagogique *</label><input required list="rag-session-modules" value={module} onChange={e => setModule(e.target.value)} placeholder="Choisir une séance ou saisir un module" className="w-full px-3 py-2.5 border border-slate-300 bg-slate-50 rounded-xl text-sm" /><datalist id="rag-session-modules">{(sessions.find((item: any) => item.id === sessionId)?.modules ?? []).map((name: string) => <option key={name} value={name} />)}</datalist><p className="mt-1 text-[10px] text-slate-500">Les thèmes des séances planifiées et les modules déjà classés sont proposés. Vous pouvez aussi saisir un autre module.</p></div><label className="flex items-center gap-3 border border-dashed border-slate-300 rounded-xl p-4 cursor-pointer hover:border-[#1B8F6E]"><Upload size={18} className="text-[#1B8F6E]" /><span className="text-xs text-slate-600">{file?.name ?? 'Choisir un PDF, DOCX, PPTX, XLSX, TXT ou MD'}</span><input type="file" accept=".pdf,.docx,.pptx,.xlsx,.txt,.md" className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><button disabled={busy || !file || !sessionId || !module.trim()} className="w-full py-2.5 bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex justify-center gap-2 items-center">{busy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}Indexer dans cette session</button></form>}
      <section className={panel}><div className="flex justify-between items-center mb-4"><div><h2 className="font-extrabold text-[#11162A]">Supports de formation</h2><p className="mt-1 text-[10px] text-slate-500">Chaque document est isolé par session et repéré par son module pédagogique.</p></div><button onClick={() => loadSupports().catch(e => setError(errorText(e)))} className="text-xs font-bold text-[#1B8F6E]">Actualiser</button></div>{sessions.length > 0 && <div className="mb-4 flex flex-wrap gap-2"><button onClick={() => { setSessionId(''); setFormationCode(''); }} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${sessionId ? 'bg-slate-100 text-slate-600' : 'bg-[#11162A] text-white'}`}>Toutes les sessions</button>{sessions.map((item: any) => <button key={item.id} onClick={() => { setSessionId(item.id); setFormationCode(item.formation_code ?? ''); }} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${sessionId === item.id ? 'bg-emerald-700 text-white' : 'bg-emerald-50 text-emerald-800'}`}>{item.titre}</button>)}</div>}{supports.length ? <div className="max-h-[440px] space-y-2 overflow-auto">{supports.map((s: any, i) => { const status = s.statut_indexation ?? s.statut ?? 'en_attente'; const course = formations.find((f: any) => f.code === s.formation_code); const trainingSession = sessions.find((item: any) => item.id === s.session_id); return <div key={s.hash ?? s.doc_hash ?? s.id ?? i} className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 p-3"><div className="min-w-0"><div className="truncate font-bold text-sm text-[#11162A]">{s.fichier ?? s.nom_fichier ?? s.filename ?? 'Support'}</div><div className="mt-1 text-[11px] font-semibold text-emerald-800">{trainingSession?.titre ?? s.session_id ?? 'Session non classée'}{s.formation_code ? ` · ${s.formation_code}` : ''}{course?.titre ? ` — ${course.titre}` : ''}{s.module ? ` · ${s.module}` : ''}</div>{s.message && <p className="mt-1 text-[10px] text-slate-500">{s.message}</p>}</div><span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${supportStatusStyle[status] ?? 'bg-slate-100 text-slate-600'}`}>{supportStatusLabel[status] ?? status}</span></div>; })}</div> : <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">{sessionId ? `Aucun support enregistré pour la session sélectionnée.` : 'Aucun support disponible.'}</p>}</section>
    </div>}

    {tab === 'chat' && <section className={`${panel} max-w-4xl mx-auto`}><div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100"><div><h2 className="font-extrabold text-[#11162A]">Assistant documentaire</h2><p className="text-[11px] text-slate-500 mt-1">{sessionId ? `Recherche isolée dans la session « ${sessions.find((item: any) => item.id === sessionId)?.titre ?? sessionId} »${chatModule ? ` · module ${chatModule}` : ''}.` : trainerMode ? 'Choisissez une session qui vous est affectée.' : 'Le catalogue, l’inventaire et les synthèses peuvent couvrir votre espace ; choisissez une session pour les questions sur son contenu.'}</p></div><div className="flex flex-col gap-2 sm:items-end"><select required={trainerMode} value={sessionId} onChange={e => { const id = e.target.value; setSessionId(id); setFormationCode(sessions.find((item: any) => item.id === id)?.formation_code ?? ''); setChatModule(''); }} className="px-3 py-2 border border-slate-300 bg-white rounded-lg text-xs"><option value="">{trainerMode ? 'Choisir ma session' : 'Toutes les sessions'}</option>{sessions.map((item: any) => <option key={item.id} value={item.id}>{item.titre}{item.formation_code ? ` — ${item.formation_code}` : ''}</option>)}</select>{sessionId && (sessions.find((item: any) => item.id === sessionId)?.modules?.length ?? 0) > 0 && <select value={chatModule} onChange={e => setChatModule(e.target.value)} className="px-3 py-2 border border-slate-300 bg-white rounded-lg text-xs"><option value="">Tous les modules de la session</option>{sessions.find((item: any) => item.id === sessionId)?.modules.map((name: string) => <option key={name} value={name}>{name}</option>)}</select>}</div></div>
      <div className="min-h-[300px] max-h-[480px] overflow-y-auto py-4 space-y-3">{messages.length === 0 && <div className="text-center text-slate-400 py-20"><MessageCircle size={30} className="mx-auto mb-2" /><p className="text-xs">Posez une question sur les documents de formation.</p></div>}{messages.map((m, i) => <div key={i} className={`max-w-[90%] p-3 rounded-xl text-xs whitespace-pre-wrap ${m.role === 'user' ? 'ml-auto bg-[#1B8F6E] text-white' : 'mr-auto bg-slate-50 text-slate-700 border border-slate-200'}`}><div>{m.text || (busy && i === messages.length - 1 ? streamingStatus || 'Préparation de la réponse…' : '')}</div>{!trainerMode && m.sources?.length ? <div className="mt-3 pt-2 border-t border-slate-200/70 text-[11px]">Sources : {m.sources.map((s: any, j: number) => <span key={j} className="mr-2">{s.fichier ?? s.filename ?? 'Document'}{s.page ? `, p. ${s.page}` : ''}</span>)}</div> : null}{m.suggestions?.map((suggestion, j) => <button key={j} onClick={() => sendMessage(suggestion)} className="mt-2 mr-2 px-2.5 py-1 rounded-full bg-white border border-slate-200 text-[#1B8F6E] font-bold">{suggestion}</button>)}</div>)}</div>
      {busy && streamingStatus && <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-500"><Loader2 size={13} className="animate-spin text-[#1B8F6E]" />{streamingStatus}</div>}
      <form onSubmit={e => { e.preventDefault(); void sendMessage(); }} className="flex gap-2 border-t border-slate-100 pt-3"><input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Votre question sur les supports…" className="flex-1 min-w-0 px-3 py-2.5 border border-slate-300 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]" /><button disabled={busy || !draft.trim() || (trainerMode && !sessionId)} className="px-4 py-2.5 bg-[#1B8F6E] text-white rounded-xl text-xs font-bold flex items-center gap-1.5">{busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}Envoyer</button></form>
    </section>}
  </div>;
};

