import React, { useEffect, useRef, useState } from 'react';
import { PageHeader } from '../PageHeader';
import { LLMConfigPanel } from './LLMConfigPanel';

function renderMarkdown(text: string): string {
  return text
    // Headings
    .replace(/^### (.+)$/gm, '<h4 class="text-sm font-extrabold text-slate-800 mt-4 mb-1.5 flex items-center gap-1.5"><span class="inline-block w-1 h-4 rounded-full bg-brand-gold/60 mr-1"></span>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="text-base font-extrabold text-[#0B1F4D] mt-5 mb-2 pb-1.5 border-b-2 border-brand-gold/30">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 class="text-lg font-extrabold text-[#06132F] mt-5 mb-2">$1</h2>')
    // Bold — couleur navy pour ressortir
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong class="font-extrabold text-[#0B1F4D]"><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-extrabold text-[#0B1F4D]">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em class="italic text-slate-600 not-italic font-medium">$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-[#0B1F4D]/8 text-[#0B1F4D] rounded-md px-1.5 py-0.5 text-[11px] font-mono border border-[#0B1F4D]/12">$1</code>')
    // Blockquote
    .replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-brand-gold/50 pl-3 my-2 text-slate-600 italic text-[12px] bg-amber-50/40 py-1 rounded-r-lg">$1</blockquote>')
    // Source references [file, p. X]
    .replace(/\[([^\]]+,\s*(?:p\.|diapo)\s*\d+[^\]]*)\]/g, '<span class="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5 ml-0.5">📎 $1</span>')
    // Bullet lists
    .replace(/^- (.+)$/gm, '<li class="ml-1 flex gap-2"><span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-gold/70"></span><span>$1</span></li>')
    .replace(/(<li[^>]*>.*<\/li>(\n|$))+/gs, (m) => `<ul class="pl-2 my-2.5 space-y-1.5 text-slate-700 text-[13px]">${m}</ul>`)
    // Numbered lists
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-1 text-slate-700" style="list-style-type:decimal">$2</li>')
    .replace(/(<li[^>]*style="list-style-type:decimal"[^>]*>.*<\/li>(\n|$))+/gs, (m) => `<ol class="list-decimal pl-5 my-2.5 space-y-1.5 text-slate-700 text-[13px]">${m}</ol>`)
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="border-slate-200 my-4" />')
    // Paragraphs
    .replace(/\n\n/g, '</p><p class="mt-3 text-[13px] leading-relaxed text-slate-700">')
    .replace(/\n/g, '<br />')
    // Wrap
    .replace(/^(.+)/, '<p class="text-[13px] leading-relaxed text-slate-700">$1')
    + '</p>';
}
import { AlertCircle, Archive, Award, Check, CheckCheck, Copy, Download, Eye, FileText, Loader2, MessageCircle, Paperclip, Pencil, PlusCircle, Send, ShieldCheck, ThumbsDown, ThumbsUp, Trash2, Upload, X, Zap } from 'lucide-react';
import { apiService } from '../../services/api';
import { MenuSection } from '../../types';

type Tab = 'reviews' | 'history' | 'supports' | 'chat' | 'syllabus' | 'config_llm';
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Une erreur est survenue.';
const panel = 'bg-white p-5 rounded-2xl border border-slate-200 shadow-xs';
const supportStatusStyle: Record<string, string> = {
  en_attente: 'bg-slate-100 text-slate-600', en_cours: 'bg-blue-50 text-blue-700',
  indexe: 'bg-emerald-50 text-emerald-700', deja_indexe: 'bg-emerald-50 text-emerald-700',
  erreur: 'bg-red-50 text-red-700', ocr_necessaire: 'bg-amber-50 text-amber-800',
  non_indexable_image: 'bg-amber-50 text-amber-800',
  archive: 'bg-slate-200 text-slate-500',
};
const supportStatusLabel: Record<string, string> = {
  en_attente: 'En attente', en_cours: 'Indexation en cours', indexe: 'Indexé', deja_indexe: 'Déjà indexé',
  erreur: "Erreur d'indexation", ocr_necessaire: 'OCR nécessaire', non_indexable_image: 'Image non indexable',
  archive: 'Archivé',
};
const indexingStageLabel: Record<string, string> = {
  extraction: 'Extraction du texte', decoupage: 'Nettoyage et découpage',
  vectorisation: 'Création des vecteurs', enregistrement: 'Enregistrement des passages',
  termine: 'Indexation terminée',
};
const labels: Record<string, string> = {
  resume: 'Résumé', synthese: 'Synthèse', progression: 'Progression', competences: 'Compétences',
  points_forts: 'Points forts', axes_amelioration: "Axes d'amélioration", recommandations: 'Recommandations',
  nps: 'NPS', score_global: 'Score global', moyenne: 'Moyenne', commentaires: 'Commentaires',
  sentiment: 'Sentiment', participant: 'Participant', nom: 'Nom', prenom: 'Prénom',
  reponses: 'Réponses', question: 'Question', score: 'Score', niveau: 'Niveau',
  avant: 'Avant la formation', apres: 'Après la formation', taux: 'Taux',
  titre: 'Titre', domaine: 'Domaine', session_id: 'Session', date: 'Date'
};
const humanize = (key: string) => labels[key.toLowerCase()] ?? key.replace(/[_-]+/g, ' ').replace(/^./, c => c.toUpperCase());
const documentAgents = ['agent_m2_tdr', 'agent_m3_technique', 'agent_m3_financiere'];
const editableDocument = (review: any): Record<string, any> | null => {
  if (review?.status !== 'pending_review') return null;
  if (!documentAgents.includes(String(review?.agent_id))) return null;
  const data = review?.data;
  if (!data || typeof data !== 'object') return null;
  if (review.agent_id === 'agent_m2_tdr') return data.data && typeof data.data === 'object' ? data.data : null;
  return Object.fromEntries(Object.entries(data).filter(([key]) => !key.startsWith('_') && !['metadata', 'success'].includes(key)));
};
const setDocumentField = (source: any, path: (string | number)[], value: unknown): any => {
  if (!path.length) return value;
  const [head, ...tail] = path;
  const copy = Array.isArray(source) ? [...source] : { ...(source ?? {}) };
  copy[head] = setDocumentField(copy[head], tail, value);
  return copy;
};
const DocumentFields: React.FC<{ value: any; path?: (string | number)[]; onChange: (path: (string | number)[], value: unknown) => void; allowNumbers: boolean }> = ({ value, path = [], onChange, allowNumbers }) => {
  if (Array.isArray(value)) return <div className="space-y-2">{value.map((item, index) => <div key={index} className="rounded-xl border border-slate-200 bg-white p-3"><span className="text-[10px] font-bold text-slate-500">Élément {index + 1}</span><DocumentFields value={item} path={[...path, index]} onChange={onChange} allowNumbers={allowNumbers} /></div>)}</div>;
  if (value && typeof value === 'object') return <div className="space-y-3">{Object.entries(value).filter(([key]) => !key.startsWith('_')).map(([key, item]) => <div key={key}><label className="mb-1 block text-[11px] font-bold text-slate-600">{humanize(key)}</label><DocumentFields value={item} path={[...path, key]} onChange={onChange} allowNumbers={allowNumbers} /></div>)}</div>;
  if (typeof value === 'number') return <input type="number" step="any" value={value} disabled={!allowNumbers} onChange={event => onChange(path, Number(event.target.value))} className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs disabled:bg-slate-100" />;
  if (typeof value === 'boolean') return <input type="checkbox" checked={value} disabled={!allowNumbers} onChange={event => onChange(path, event.target.checked)} className="accent-[#0B1F4D]" />;
  return <textarea value={value == null ? '' : String(value)} onChange={event => onChange(path, event.target.value)} rows={String(value ?? '').length > 150 ? 4 : 2} className="w-full resize-y rounded-lg border border-slate-300 bg-white p-2 text-xs leading-relaxed" />;
};
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

const workflowForReview = (reviewId: string) => {
  try {
    for (let index = 0; index < sessionStorage.length; index += 1) {
      const key = sessionStorage.key(index);
      if (!key?.startsWith('formaia-m2-m3-')) continue;
      const workflow = JSON.parse(sessionStorage.getItem(key) ?? 'null');
      if (workflow && [workflow.tdrReviewId, workflow.techniqueReviewId, workflow.financeReviewId].includes(reviewId)) {
        return { key, workflow };
      }
    }
  } catch { /* stockage de session indisponible */ }
  return null;
};

const updateWorkflow = (reviewId: string, changes: Record<string, unknown>) => {
  const found = workflowForReview(reviewId);
  if (!found) return false;
  try { sessionStorage.setItem(found.key, JSON.stringify({ ...found.workflow, ...changes })); return true; }
  catch { return false; }
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
      return <div className="space-y-3">{metrics.length > 0 && <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{metrics.map(([key, val]) => <div key={key} className="rounded-xl bg-gradient-to-br from-emerald-50 to-slate-50 p-3"><div className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{humanize(key)}</div><div className="mt-1 text-lg font-extrabold text-[#0B1F4D]">{renderNode(val, depth + 1)}</div></div>)}</div>}{rest.map(([key, val]) => <section key={key} className="rounded-xl border border-slate-200 bg-white p-3.5"><h3 className="mb-2 text-xs font-extrabold text-[#11162A]">{humanize(key)}</h3><div className="text-xs text-slate-700">{renderNode(val, depth + 1)}</div></section>)}</div>;
    }
    return String(node);
  };
  return <div className="max-h-[560px] space-y-3 overflow-auto rounded-2xl bg-slate-50 p-3">{renderNode(content)}</div>;
};

export const EspaceIAView: React.FC<{ readOnly?: boolean; trainerMode?: boolean; onNavigateToSection?: (section: MenuSection) => void }> = ({ readOnly = false, trainerMode = false, onNavigateToSection }) => {
  const [tab, setTab] = useState<Tab>(readOnly ? 'supports' : 'reviews');
  const [reviews, setReviews] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [historyStatus, setHistoryStatus] = useState<'all' | 'approved' | 'rejected'>('all');
  const [selected, setSelected] = useState<any>(null);
  const [attestationPreview, setAttestationPreview] = useState<{ numero: string; url: string } | null>(null);
  const [attestationBusy, setAttestationBusy] = useState('');
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewsLoading, setReviewsLoading] = useState(false);
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
  const [ragConversations, setRagConversations] = useState<any[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [renamingConvId, setRenamingConvId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);
  const [feedbacks, setFeedbacks] = useState<Record<number, 'positif' | 'negatif'>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [documentEdit, setDocumentEdit] = useState<Record<string, any> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [continueMarket, setContinueMarket] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const loadReviews = async () => {
    // La revue M2 est la source principale : l'afficher sans attendre les
    // listes complémentaires RAG/M3, qui ne doivent pas bloquer le TDR.
    const backend = await apiService.getPendingReviews();
    if (backend?.success === false) throw new Error(backend.error ?? 'Le backend n’a pas pu charger les validations en attente.');
    const regularReviews = (backend.reviews ?? []).filter((item: any) => !String(item.agent_id ?? '').startsWith('agent_rag_'));
    setReviews(regularReviews);

    const [ragResult, offerResult] = await Promise.allSettled([apiService.getRagReviews(), apiService.getOfferReviews()]);
    const rag = ragResult.status === 'fulfilled' ? ragResult.value : { data: [] };
    const offers = offerResult.status === 'fulfilled' ? offerResult.value : { data: [] };
    // Toutes les validations doivent être consultables ici, y compris TDR,
    // offres technique/financière et contenus RAG. Les retirer de la liste
    // faisait apparaître un compteur sans aperçu correspondant.
    const ragReviews = Array.isArray(rag.data) ? rag.data : [];
    const offerReviews = Array.isArray(offers.data) ? offers.data : [];
    const unique = new Map<string, any>();
    [...regularReviews, ...offerReviews, ...ragReviews].forEach((item: any) => {
      const id = item.review_id ?? item.id;
      if (id != null) unique.set(String(id), item);
    });
    setReviews([...unique.values()]);
  };
  const refreshReviews = async () => {
    setReviewsLoading(true);
    setError('');
    try { await loadReviews(); }
    catch (e) { setError(errorText(e)); }
    finally { setReviewsLoading(false); }
  };
  const loadHistory = async () => {
    const [approved, rejected] = await Promise.all([
      apiService.getReviewHistory('approved'), apiService.getReviewHistory('rejected')
    ]);
    setHistory([...(approved.reviews ?? []), ...(rejected.reviews ?? [])]
      .sort((a: any, b: any) => String(b.reviewed_at ?? '').localeCompare(String(a.reviewed_at ?? ''))));
  };
  const loadRagConversations = async () => {
    setConversationsLoading(true);
    try {
      const result = await apiService.getRagConversations();
      setRagConversations(Array.isArray(result?.data) ? result.data : []);
    } catch { /* silencieux — la liste des conversations est optionnelle */ }
    finally { setConversationsLoading(false); }
  };

  const newConversation = () => {
    setConversationId(null);
    setMessages([]);
    setDraft('');
    setError('');
    setStreamingStatus('');
    setFeedbacks({});
  };

  const resumeConversation = async (conv: any) => {
    if (conv.conversation_id === conversationId) return;
    setError(''); setStreamingStatus('');
    try {
      const detail = await apiService.getRagConversation(conv.conversation_id);
      const echanges: Array<{ role: 'user' | 'assistant'; text: string }> = (detail.echanges ?? []).map((e: any) => ({
        role: e.role === 'utilisateur' ? 'user' : 'assistant',
        text: e.texte ?? '',
      }));
      setMessages(echanges);
      setConversationId(conv.conversation_id);
    } catch (e) { setError(errorText(e)); }
  };

  const deleteRagConversation = async (id: string) => {
    if (!window.confirm('Supprimer cette conversation ? Cette action est irréversible.')) return;
    try {
      await apiService.deleteRagConversation(id);
      if (conversationId === id) newConversation();
      await loadRagConversations();
    } catch (e) { setError(errorText(e)); }
  };

  const startRename = (conv: any) => {
    setRenamingConvId(conv.conversation_id);
    setRenameValue(conv.titre || '');
  };

  const confirmRename = async (id: string) => {
    const titre = renameValue.trim();
    if (titre) {
      try { await apiService.renameRagConversation(id, titre); } catch (_) { /* ignore */ }
      setRagConversations(prev => prev.map(c => c.conversation_id === id ? { ...c, titre } : c));
    }
    setRenamingConvId(null);
  };

  const copyMessage = async (text: string, idx: number) => {
    try {
      let copied = false;
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(text);
          copied = true;
        } catch { /* Essayer le mécanisme compatible avec les contextes HTTP locaux. */ }
      }
      if (!copied) {
        const temporary = document.createElement('textarea');
        temporary.value = text;
        temporary.setAttribute('readonly', '');
        temporary.style.position = 'fixed';
        temporary.style.opacity = '0';
        document.body.appendChild(temporary);
        temporary.select();
        const copied = document.execCommand('copy');
        temporary.remove();
        if (!copied) throw new Error('Copie refusée par le navigateur.');
      }
      setCopiedMsgIdx(idx);
      window.setTimeout(() => setCopiedMsgIdx(current => current === idx ? null : current), 1800);
    } catch {
      setError('La copie a échoué. Autorisez le presse-papiers dans le navigateur puis réessayez.');
    }
  };

  const sendFeedback = async (idx: number, fb: 'positif' | 'negatif') => {
    if (!conversationId) return;
    setFeedbacks(prev => ({ ...prev, [idx]: fb }));
    try {
      await apiService.feedbackRagMessage(conversationId, idx, fb);
    } catch (_) { /* feedback non bloquant */ }
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
  useEffect(() => { setError(''); setNotice(''); if (tab === 'reviews') void refreshReviews(); if (tab === 'history') loadHistory().catch(e => setError(errorText(e))); if (tab === 'supports' || tab === 'chat') loadSupports().catch(e => setError(errorText(e))); if (tab === 'chat') loadRagConversations(); if (tab === 'syllabus') apiService.getRagFormations().then(data => setFormations(Array.isArray(data) ? data : data.data ?? data.formations ?? [])).catch(e => setError(errorText(e))); }, [tab, formationCode, sessionId]);
  // Continue à refléter les étapes réellement enregistrées côté backend,
  // y compris lorsque l'indexation dépasse le délai d'attente de l'upload.
  useEffect(() => {
    if (tab !== 'supports') return;
    const pending = supports.filter(s => (s.statut_indexation ?? s.statut) === 'en_cours' && (s.hash ?? s.doc_hash));
    if (!pending.length) return;
    let cancelled = false;
    const refresh = async () => {
      const results = await Promise.allSettled(pending.map(async support => {
        const hash = support.hash ?? support.doc_hash;
        const response: any = await apiService.getRagIndexStatus(hash);
        const entry = response?.data ?? response;
        return { hash, entry };
      }));
      if (cancelled) return;
      setSupports(previous => {
        const latest = new Map<string, any>(results.filter((r): r is PromiseFulfilledResult<{hash: string; entry: any}> => r.status === 'fulfilled').map(r => [r.value.hash, r.value.entry]));
        return previous.map(support => {
          const update = latest.get(support.hash ?? support.doc_hash);
          return update ? {
            ...support,
            ...update,
            statut_indexation: update.statut ?? update.statut_indexation ?? support.statut_indexation,
          } : support;
        });
      });
    };
    const timer = window.setInterval(() => { void refresh(); }, 2200);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [tab, supports]);
  // Scroll automatique vers le bas à chaque nouveau message
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const openReview = async (item: any) => {
    setSelected(item); setReviewLoading(true); setError(''); setDocumentEdit(null);
    setAttestationPreview(current => { if (current) URL.revokeObjectURL(current.url); return null; });
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
  useEffect(() => {
    if (!reviews.length) return;
    let focusId = '';
    try { focusId = sessionStorage.getItem('formaia-review-focus') ?? ''; } catch { return; }
    // Une ouverture ciblée n'est demandée qu'après une génération explicite.
    // Sans identifiant, ne jamais appeler /reviews/ (qui redirige et provoque
    // un préflight CORS inutile dans certaines configurations locales).
    if (!focusId) return;
    const item = reviews.find(review => String(review.review_id ?? review.id) === focusId);
    sessionStorage.removeItem('formaia-review-focus');
    if (item) {
      void openReview(item);
      return;
    }
    // Si la liste n'a pas encore reçu la nouvelle revue, demander son détail
    // avec l'identifiant retourné par la génération TDR au lieu d'ouvrir un
    // panneau vide.
    setReviewLoading(true);
    apiService.getReview(focusId)
      .then(response => {
        const detail = unwrapReview(response);
        if (!detail || detail.success === false || !(detail.review_id ?? detail.id)) {
          throw new Error(`La validation ${focusId} n’est pas disponible dans le backend.`);
        }
        setSelected(detail);
      })
      .catch(e => setError(errorText(e)))
      .finally(() => setReviewLoading(false));
  }, [reviews]);
  const saveManualDocument = async () => {
    const id = String(selected?.review_id ?? selected?.id ?? '');
    if (!id || !documentEdit || !selected?.updated_at) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await apiService.updateReviewDocument(id, documentEdit, selected.updated_at);
      const review = response.review;
      if (!response.success || !review) throw new Error("La modification n'a pas été enregistrée.");
      if (review.agent_id === 'agent_m2_tdr') {
        updateWorkflow(id, { generatedTdr: review.data.data, tdrFiles: review.data.files });
      } else if (review.agent_id === 'agent_m3_technique') {
        updateWorkflow(id, { techniqueDocument: review.data });
      } else if (review.agent_id === 'agent_m3_financiere') {
        const costs = review.data?.details_couts ?? {};
        const workflow = workflowForReview(id)?.workflow;
        updateWorkflow(id, {
          financeDocument: review.data,
          financeInputs: {
            ...workflow?.financeInputs,
            trainerRate: Number(costs.honoraires_formateur?.tarif_journalier ?? workflow?.financeInputs?.trainerRate ?? 0),
            trainerDays: Number(costs.honoraires_formateur?.nb_jours ?? workflow?.financeInputs?.trainerDays ?? 0),
            roomRate: Number(costs.location_salle?.tarif_journalier ?? workflow?.financeInputs?.roomRate ?? 0),
            roomDays: Number(costs.location_salle?.nb_jours ?? workflow?.financeInputs?.roomDays ?? 0),
            supportRate: Number(costs.supports_pedagogiques?.forfait_participant ?? workflow?.financeInputs?.supportRate ?? 0),
            participants: Number(costs.supports_pedagogiques?.nb_participants ?? workflow?.financeInputs?.participants ?? 0),
            logistics: Number(costs.logistique?.montant ?? workflow?.financeInputs?.logistics ?? 0),
            adminPercent: Number(costs.administration?.pourcentage ?? workflow?.financeInputs?.adminPercent ?? 0)
          }
        });
      }
      setSelected(review); setDocumentEdit(null);
      setNotice("Modifications enregistrées. Vérifiez la nouvelle version avant de l'approuver.");
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  const correctDocument = async () => {
    const id = String(selected?.review_id ?? selected?.id ?? '');
    const agent = String(selected?.agent_id ?? '');
    const feedback = reviewNote.trim();
    if (!id || !['agent_m2_tdr', 'agent_m3_technique', 'agent_m3_financiere'].includes(agent)) return;
    if (feedback.length < 5) { setError('Décrivez la correction souhaitée en au moins 5 caractères.'); return; }
    const found = workflowForReview(id);
    const workflow = found?.workflow;
    if (agent !== 'agent_m2_tdr' && !workflow) {
      setError("Le dossier source de cette offre n'est plus disponible dans cette session du navigateur. Ouvrez le dossier marché avant de demander une correction.");
      return;
    }
    setBusy(true); setError(''); setNotice('');
    try {
      let result: any;
      let workflowChanges: Record<string, unknown>;
      if (agent === 'agent_m2_tdr') {
        const brief = selected?.data?._inputs?.brief ?? (workflow ? { ...workflow.tdrBrief, opportunite_id: found?.key.slice('formaia-m2-m3-'.length) } : null);
        if (!brief) throw new Error("Le brief d'origine du TDR est introuvable.");
        result = await apiService.rectifyTdr({ review_id: id, feedback, brief });
        workflowChanges = { generatedTdr: result.data ?? null, tdrFiles: result.files ?? {}, tdrReviewId: result.review_id, tdrApproved: false, tdrSynchronized: false, docTab: 'tdr' };
      } else if (agent === 'agent_m3_technique') {
        if (!workflow.generatedTdr) throw new Error('Le TDR source est absent du dossier marché.');
        const source = workflow.techniqueRequest ?? {};
        result = await apiService.rectifyOfferTechnique({
          review_id: id, feedback,
          tdr_data: source.tdr_data ?? workflow.generatedTdr,
          session_info: source.session_info ?? { titre: workflow.generatedTdr.titre, client: workflow.tdrBrief?.client, opportunite_id: found?.key.slice('formaia-m2-m3-'.length), duree: workflow.tdrBrief?.duree }
        });
        workflowChanges = { techniqueDocument: result.data ?? null, techniqueReviewId: result.review_id, techniqueApproved: false, financeDocument: null, financeReviewId: '', financeApproved: false, offerSaved: false, docTab: 'technical' };
      } else {
        if (!workflow.techniqueApproved || !workflow.techniqueDocument) throw new Error("Validez d'abord l'offre technique dans ce dossier.");
        const options = workflow.offerOptions ?? {};
        result = await apiService.rectifyOfferFinanciere({
          review_id: id, feedback, offre_technique: workflow.techniqueDocument,
          options: { nb_participants: workflow.financeInputs?.participants || options.participants, type_formateur: options.trainerType, type_salle: options.roomType, tva_applicable: options.vat, inclure_logistique: options.logistics, inclure_administration: options.administration }
        });
        const costs = result.data?.details_couts ?? {};
        workflowChanges = {
          financeDocument: result.data ?? null, financeReviewId: result.review_id, financeApproved: false, offerSaved: false, docTab: 'financial',
          financeInputs: {
            ...workflow.financeInputs,
            trainerRate: Number(costs.honoraires_formateur?.tarif_journalier ?? workflow.financeInputs?.trainerRate ?? 0),
            trainerDays: Number(costs.honoraires_formateur?.nb_jours ?? workflow.financeInputs?.trainerDays ?? 0),
            roomRate: Number(costs.location_salle?.tarif_journalier ?? workflow.financeInputs?.roomRate ?? 0),
            roomDays: Number(costs.location_salle?.nb_jours ?? workflow.financeInputs?.roomDays ?? 0),
            supportRate: Number(costs.supports_pedagogiques?.forfait_participant ?? workflow.financeInputs?.supportRate ?? 0),
            participants: Number(costs.supports_pedagogiques?.nb_participants ?? workflow.financeInputs?.participants ?? 0),
            logistics: Number(costs.logistique?.montant ?? workflow.financeInputs?.logistics ?? 0),
            adminPercent: Number(costs.administration?.pourcentage ?? workflow.financeInputs?.adminPercent ?? 0)
          }
        };
      }
      if (!result?.success || !result.review_id) throw new Error(result?.message ?? "La nouvelle version du document n'a pas été créée.");
      updateWorkflow(id, workflowChanges);
      setReviewNote('');
      setNotice("Nouvelle version créée. Vérifiez-la avant de l'approuver.");
      await loadReviews();
      await openReview({ review_id: result.review_id, agent_id: agent });
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  const reviewAction = async (approve: boolean) => {
    const id = selected?.review_id ?? selected?.id;
    if (!id) return;
    if (!approve && reviewNote.trim().length < 3) { setError('Le motif du rejet doit contenir au moins 3 caractères.'); return; }
    const reviewerNote = reviewNote.trim() || 'OK';
    setBusy(true); setError(''); setContinueMarket(false);
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
        if (String(selected?.agent_id) === 'agent_m3_technique') {
          if (updateWorkflow(id, approve ? { techniqueApproved: true, docTab: 'financial' } : { techniqueApproved: false, techniqueDocument: null, techniqueReviewId: '', financeDocument: null, financeReviewId: '', financeApproved: false, offerSaved: false, docTab: 'technical' }) && approve) setContinueMarket(true);
          if (approve) actionNotice = "Offre technique approuvée. Vous pouvez générer l'offre financière dans le dossier du marché.";
        }
        if (String(selected?.agent_id) === 'agent_m3_financiere') {
          if (updateWorkflow(id, approve ? { financeApproved: true, docTab: 'financial' } : { financeApproved: false, financeDocument: null, financeReviewId: '', offerSaved: false, docTab: 'financial' }) && approve) setContinueMarket(true);
          if (approve) actionNotice = 'Offre financière approuvée. Enregistrez les deux volets dans le dossier du marché.';
        }
        if (approve && String(selected?.agent_id) === 'agent_m3_complete') {
          await apiService.syncOffer(id, selected?.data?.opportunite_id ?? selected?.data?._inputs?.tdr_data?.opportunite_id ?? selected?.opportunite_id);
          actionNotice = 'Offre approuvée et synchronisée avec le backend.';
        }
      } else {
        const agent = String(selected?.agent_id ?? '');
        if (!approve) {
          await apiService.rejectReview(id, reviewNote);
          if (agent === 'agent_m2_tdr') updateWorkflow(id, { generatedTdr: null, tdrReviewId: '', tdrApproved: false, tdrSynchronized: false, techniqueDocument: null, techniqueReviewId: '', techniqueApproved: false, financeDocument: null, financeReviewId: '', financeApproved: false, offerSaved: false, docTab: 'tdr' });
        }
        else if (agent === 'agent_m2_tdr') {
          await apiService.approveTdr(id, reviewerNote);
          if (updateWorkflow(id, { tdrApproved: true, docTab: 'technical' })) setContinueMarket(true);
          try {
            await apiService.syncTdr(id, selected?.data?.opportunite_id ?? selected?.opportunite_id);
            updateWorkflow(id, { tdrSynchronized: true });
            actionNotice = "TDR approuvé et enregistré. Vous pouvez générer l'offre technique dans le dossier du marché.";
          } catch (syncError) {
            setError(`TDR approuvé, mais son enregistrement a échoué : ${errorText(syncError)}`);
            actionNotice = 'TDR approuvé. Reprenez son enregistrement dans le dossier du marché.';
          }
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

  const saveBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = filename; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const previewAttestation = async (item: any) => {
    const reviewId = String(selected?.review_id ?? selected?.id ?? '');
    const numero = String(item?.numero_unique ?? '');
    if (!reviewId || !numero) return;
    setAttestationBusy(numero); setError('');
    try {
      const blob = await apiService.previewAttestation(reviewId, numero);
      setAttestationPreview(current => { if (current) URL.revokeObjectURL(current.url); return { numero, url: URL.createObjectURL(blob) }; });
    } catch (e) { setError(errorText(e)); }
    finally { setAttestationBusy(''); }
  };
  const downloadAttestation = async (item: any) => {
    const reviewId = String(selected?.review_id ?? selected?.id ?? '');
    const numero = String(item?.numero_unique ?? '');
    if (!reviewId || !numero) return;
    setAttestationBusy(numero); setError('');
    try { saveBlob(await apiService.downloadAttestation(reviewId, numero), `${numero}.pdf`); }
    catch (e) { setError(errorText(e)); }
    finally { setAttestationBusy(''); }
  };
  const downloadAttestationZip = async () => {
    const reviewId = String(selected?.review_id ?? selected?.id ?? '');
    if (!reviewId) return;
    setAttestationBusy('zip'); setError('');
    try { saveBlob(await apiService.downloadAttestationsZip(reviewId), `attestations-${reviewId}.zip`); }
    catch (e) { setError(errorText(e)); }
    finally { setAttestationBusy(''); }
  };
  const approveOneAttestation = async (item: any) => {
    const reviewId = String(selected?.review_id ?? selected?.id ?? '');
    const numero = String(item?.numero_unique ?? '');
    if (!reviewId || !numero) return;
    setAttestationBusy(numero); setError('');
    try {
      const result = await apiService.approveAttestationInBatch(reviewId, numero, reviewNote.trim() || 'Validée par la direction');
      setNotice(result.lot_approved ? 'Toutes les attestations du lot sont approuvées. Le téléchargement est disponible.' : `Attestation ${numero} approuvée.`);
      setReviewNote('');
      await loadReviews();
      await openReview({ review_id: reviewId, agent_id: 'agent_5_attestations' });
    } catch (e) { setError(errorText(e)); }
    finally { setAttestationBusy(''); }
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
      if (!uploaded.chemin_fichier) throw new Error("Le backend n'a pas retourné le chemin du support téléversé.");
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
            setNotice(status === 'indexe' ? `Support indexé et rattaché à la formation ${code}. Les recherches ciblées utiliseront ce document.` : result.data?.message || result.message || `L'indexation du document a terminé avec le statut « ${supportStatusLabel[status] ?? status} ».`);
            break;
          }
          if (attempt === 11) { await loadSupports(code, sessionId); setNotice(`Support rattaché à la session ; l'indexation continue en arrière-plan. Son statut reste visible dans la liste des supports.`); }
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
      setNotice(`Syllabus généré et envoyé pour validation humaine${reviewId ? ` · ${reviewId}` : ''}. Consultez l'onglet Validation IA.`);
      setSyllabusForm(previous => ({ ...previous, modules: '' }));
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const sendMessage = async (text = draft) => {
    const message = text.trim(); if (!message || busy) return;
    if (trainerMode && !sessionId) { setError("Sélectionnez d'abord une session qui vous est affectée."); return; }
    setMessages(prev => [...prev, { role: 'user', text: message }, { role: 'assistant', text: '' }]); setDraft(''); setBusy(true); setError(''); setStreamingStatus("Connexion à l'assistant documentaire…");
    try {
      await apiService.chatRagStream({ message, conversation_id: conversationId, formation_code: formationCode || null, session_id: sessionId || null, module: chatModule || null }, event => {
        if (event.type === 'status') setStreamingStatus(event.message ?? 'Préparation de la réponse…');
        if (event.type === 'token') {
          const fragment = event.text ?? '';
          if (fragment) {
            setMessages(previous => {
              const next = [...previous]; const last = next[next.length - 1];
              if (last?.role === 'assistant') next[next.length - 1] = { ...last, text: last.text + fragment };
              return next;
            });
            setStreamingStatus('Rédaction de la réponse…');
          }
        }
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
          const referenceDiagnostic = event.trace_id ? ` (référence ${event.trace_id})` : '';
          const messageErreur = `${event.message ?? 'Erreur pendant la génération de la réponse.'}${referenceDiagnostic}`;
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
    } finally {
      setBusy(false); setStreamingStatus('');
      // Actualiser la liste des conversations en arrière-plan
      loadRagConversations();
    }
  };

  const tabs: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
    ...(!readOnly ? [{ id: 'reviews' as const, label: 'Validation IA', icon: <ShieldCheck size={15} /> }] : []),
    ...(!readOnly ? [{ id: 'history' as const, label: 'Historique', icon: <FileText size={15} /> }] : []),
    ...(!readOnly ? [{ id: 'syllabus' as const, label: 'Générer un syllabus', icon: <FileText size={15} /> }] : []),
    { id: 'supports', label: 'Supports RAG', icon: <Paperclip size={15} /> },
    { id: 'chat', label: 'Chat documentaire', icon: <MessageCircle size={15} /> },
    ...(!readOnly ? [{ id: 'config_llm' as const, label: 'Config LLM', icon: <Zap size={15} /> }] : []),
  ];
  return <div className="space-y-6 animate-in fade-in duration-300">
    <PageHeader
      icon={<Zap size={22} />}
      badge="Pipeline IA"
      title="Espace IA"
      subtitle="Validez les contenus générés par IA, gérez la base documentaire RAG et utilisez le chat intelligent."
    />

    {/* Barre d'onglets séparée — pleine largeur, style pill */}
    <div className="flex items-center gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-xs scrollbar-none">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => { setTab(t.id); setSelected(null); setDocumentEdit(null); }}
          className={`flex shrink-0 items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all whitespace-nowrap ${
            tab === t.id
              ? 'bg-brand-navy text-white shadow-sm'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
          }`}
        >
          {t.icon}
          {t.label}
          {t.id === 'reviews' && reviews.length > 0 && (
            <span className="ml-0.5 h-4 min-w-4 px-1 rounded-full bg-amber-500 text-white text-[9px] font-extrabold flex items-center justify-center">{reviews.length}</span>
          )}
        </button>
      ))}
    </div>

    {/* Bandeau HITL — visible uniquement sur l'onglet reviews avec contenus en attente */}
    {tab === 'reviews' && reviews.length > 0 && (
      <div className="flex items-start gap-3 rounded-xl border border-[#0B1F4D]/20 bg-gradient-to-r from-[#0B1F4D]/5 to-white p-4">
        <div className="h-10 w-10 shrink-0 rounded-xl bg-[#0B1F4D] flex items-center justify-center">
          <ShieldCheck size={18} className="text-white" />
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-[#0B1F4D] mb-0.5">HITL — Human in the Loop</div>
          <p className="text-sm font-bold text-[#11162A]">{reviews.length} contenu{reviews.length > 1 ? 's' : ''} généré{reviews.length > 1 ? 's' : ''} par IA — validation humaine requise</p>
          <p className="text-[11px] text-slate-600 mt-0.5">Chaque document IA doit être relu et approuvé par un responsable avant tout envoi au client ou enregistrement en base.</p>
        </div>
      </div>
    )}

    {error && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex gap-2"><AlertCircle size={15} />{error}</div>}
    {notice && <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold"><span>{notice}</span>{continueMarket && <button type="button" onClick={() => onNavigateToSection?.('opportunites_crm')} className="rounded-lg bg-emerald-700 px-3 py-2 font-bold text-white">Continuer le dossier du marché</button>}</div>}

    {tab === 'reviews' && <div className="grid lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)] gap-4">
      <section className={panel}><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h2 className="font-extrabold text-[#11162A]">À valider</h2><div className="flex items-center gap-2"><span className="text-xs bg-emerald-50 text-emerald-700 rounded-full px-2.5 py-1 font-bold">{reviews.length}</span><button type="button" onClick={() => void refreshReviews()} disabled={reviewsLoading} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-bold text-slate-600 disabled:opacity-50">{reviewsLoading ? 'Actualisation…' : 'Actualiser'}</button></div></div>
        {reviews.length ? <div className="space-y-2">{reviews.map((r, i) => { const id = String(r.review_id ?? r.id ?? i); return <div key={id} className={`flex items-center gap-2 rounded-xl border p-2 ${selected?.review_id === id ? 'border-[#0B1F4D] bg-emerald-50/50' : 'border-slate-200 hover:border-slate-300'}`}><button onClick={() => openReview(r)} className="min-w-0 flex-1 p-1 text-left"><div className="truncate font-bold text-sm text-[#11162A]">{r.title ?? r.titre ?? r.summary ?? r.agent_id ?? 'Contenu généré'}</div><div className="mt-1 truncate text-[11px] text-slate-500">{r.agent_id ?? r.type ?? 'Agent IA'} · {r.created_at ? new Date(r.created_at).toLocaleString('fr-FR') : r.date_creation ?? ''}</div></button><button type="button" aria-label={`Supprimer la validation ${id}`} title="Supprimer cette validation" disabled={deletingReviewId !== '' || busy} onClick={() => void deleteReview(r)} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-red-100 bg-red-50 text-red-600 transition hover:bg-red-100 disabled:cursor-wait disabled:opacity-50">{deletingReviewId === id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}</button></div>; })}</div> : reviewsLoading ? <p className="text-xs text-slate-500">Chargement des validations…</p> : <p className="text-xs text-slate-500">Aucun contenu en attente de validation.</p>}
      </section>
      <section className={panel}>{selected ? <><div className="flex items-start justify-between gap-3"><div><h2 className="font-extrabold text-[#11162A]">{selected.summary ?? selected.title ?? 'Aperçu du contenu à valider'}</h2><p className="text-[11px] text-slate-500 mt-1">{selected.agent_id ?? selected.type ?? selected.review_id} · {selected.criticity ?? ''} · {selected.created_at ? new Date(selected.created_at).toLocaleString('fr-FR') : ''}</p></div><div className="flex items-center gap-2">{selected.agent_id === 'agent_5_attestations' && selected.status === 'approved' && <button type="button" disabled={attestationBusy !== ''} onClick={()=>void downloadAttestationZip()} className="flex items-center gap-1.5 rounded-lg bg-[#11162A] px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50"><Archive size={14}/>Télécharger le ZIP</button>}<button onClick={() => setSelected(null)} className="p-1.5 text-slate-400 hover:text-slate-700"><X size={16} /></button></div></div>{!reviewLoading && !documentEdit && editableDocument(selected) && <button type="button" onClick={() => setDocumentEdit(structuredClone(editableDocument(selected)))} className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-xs font-bold text-slate-700">Modifier manuellement</button>}{reviewLoading ? <div className="mt-6 flex min-h-48 items-center justify-center gap-2 text-sm font-semibold text-slate-500"><Loader2 size={18} className="animate-spin text-[#0B1F4D]" />Chargement du dossier…</div> : <>{documentEdit ? <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3"><p className="mb-3 text-xs text-blue-900">Modifiez les champs, enregistrez, puis approuvez la version mise à jour. Les montants calculés de l'offre financière restent à ajuster dans le dossier marché.</p><div className="max-h-[560px] overflow-auto rounded-lg bg-white p-3"><DocumentFields value={documentEdit} onChange={(path, value) => setDocumentEdit(current => current ? setDocumentField(current, path, value) : null)} allowNumbers={selected.agent_id !== 'agent_m3_financiere'} /></div><div className="mt-3 flex justify-end gap-2"><button type="button" onClick={() => setDocumentEdit(null)} className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-slate-700">Annuler</button><button type="button" disabled={busy} onClick={() => void saveManualDocument()} className="rounded-lg bg-blue-800 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Enregistrer les modifications</button></div></div> : selected.agent_id === 'agent_5_attestations' ? <div className="mt-4 space-y-4"><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-emerald-50 p-3"><div className="text-[10px] font-bold uppercase text-emerald-700">Attestations préparées</div><div className="mt-1 text-2xl font-extrabold text-emerald-800">{selected.data?.total_pdf_generated ?? selected.data?.attestations?.length ?? 0}</div></div><div className="rounded-xl bg-slate-50 p-3"><div className="text-[10px] font-bold uppercase text-slate-500">Lot de formation</div><div className="mt-1 truncate text-sm font-extrabold text-[#11162A]">{selected.meta?.session_title ?? selected.data?.session_id ?? 'Session'}</div></div><div className="rounded-xl bg-amber-50 p-3"><div className="text-[10px] font-bold uppercase text-amber-700">Validation</div><div className="mt-1 text-sm font-extrabold text-amber-800">{selected.status === 'approved' ? 'Lot approuvé' : 'Requise avant remise'}</div></div></div><div className="space-y-3">{(selected.data?.attestations ?? []).map((item:any)=><article key={item.numero_unique} className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 p-4"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-extrabold text-[#11162A]">{[item.participant?.prenom,item.participant?.nom].filter(Boolean).join(' ') || item.participant?.nom}</h3><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-extrabold text-emerald-800">{item.participant?.taux_presence != null ? `${item.participant.taux_presence}% de présence` : 'Éligible · ≥75%'}</span><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${item.approval_status === 'approved' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{item.approval_status === 'approved' ? 'Approuvée' : 'À valider'}</span></div><p className="mt-1 text-[11px] text-slate-500">{item.numero_unique} · {item.content?.details?.formation ?? ''}</p></div><div className="flex flex-wrap gap-2"><button type="button" disabled={attestationBusy!==''} onClick={()=>void previewAttestation(item)} className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-[11px] font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><Eye size={14}/>{attestationBusy===item.numero_unique?'Ouverture…':'Aperçu PDF'}</button>{item.approval_status === 'approved' ? <button type="button" disabled={attestationBusy!==''} onClick={()=>void downloadAttestation(item)} className="flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50"><Download size={14}/>Télécharger</button> : item.approval_status !== 'approved' && <button type="button" disabled={attestationBusy!==''} onClick={()=>void approveOneAttestation(item)} className="flex items-center gap-1.5 rounded-lg bg-[#0B1F4D] px-3 py-2 text-[11px] font-bold text-white disabled:opacity-50"><Check size={14}/>{attestationBusy===item.numero_unique?'Validation…':'Approuver'}</button>}</div></div>{attestationPreview?.numero === item.numero_unique && <iframe title={`Aperçu ${item.numero_unique}`} src={attestationPreview.url} className="h-[520px] w-full bg-slate-100"/>}</article>)}</div><div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3 text-[11px] leading-relaxed text-blue-900">Vérifiez le nom, les dates, les compétences et le numéro de chaque document. Les téléchargements individuels et le ZIP sont ouverts après validation.</div></div> : <div className="mt-4"><ReviewContent value={selected} /></div>}<textarea disabled={documentEdit !== null} value={reviewNote} onChange={e => setReviewNote(e.target.value)} placeholder="Note de validation, motif de rejet ou correction demandée" rows={2} className="mt-3 w-full p-3 bg-white border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]" /><div className="flex justify-end gap-2 mt-3"><button disabled={busy || documentEdit !== null} onClick={() => reviewAction(false)} className="px-4 py-2 bg-red-50 text-red-700 rounded-lg text-xs font-bold">Rejeter</button>{['agent_m2_tdr', 'agent_m3_technique', 'agent_m3_financiere'].includes(String(selected.agent_id)) && <button disabled={busy || reviewLoading || documentEdit !== null} onClick={() => void correctDocument()} className="px-4 py-2 bg-blue-50 text-blue-800 rounded-lg text-xs font-bold">Demander une correction à l'IA</button>}<button disabled={busy || documentEdit !== null} onClick={() => reviewAction(true)} className="px-4 py-2 bg-[#0B1F4D] text-white rounded-lg text-xs font-bold flex gap-1.5 items-center">{busy ? <Loader2 size={14} className="animate-spin" /> : selected.agent_id === 'agent_5_attestations' ? <CheckCheck size={14}/> : <Check size={14} />}{selected.agent_id === 'agent_5_attestations' ? 'Approuver toutes' : 'Approuver'}</button></div></>}</> : <div className="h-full min-h-56 flex flex-col items-center justify-center text-center text-slate-400"><FileText size={30} className="mb-2" /><p className="text-xs font-semibold">Sélectionnez un contenu pour le consulter.</p></div>}</section>
    </div>}

    {tab === 'history' && <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)]">
      <section className={panel}><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-extrabold text-[#11162A]">Décisions conservées</h2><p className="mt-1 text-xs text-slate-500">TDR, offres et autres contenus soumis à validation humaine.</p></div><button type="button" onClick={() => void loadHistory().catch(e => setError(errorText(e)))} className="text-xs font-bold text-[#0B1F4D]">Actualiser</button></div>
        <div className="mb-4 flex flex-wrap gap-2">{(['all', 'approved', 'rejected'] as const).map(status => <button key={status} type="button" onClick={() => setHistoryStatus(status)} className={`rounded-full px-3 py-1.5 text-xs font-bold ${historyStatus === status ? 'bg-[#11162A] text-white' : 'bg-slate-100 text-slate-600'}`}>{status === 'all' ? 'Toutes' : status === 'approved' ? 'Approuvées' : 'Rejetées'}</button>)}</div>
        <div className="max-h-[620px] space-y-2 overflow-auto">{history.filter(item => historyStatus === 'all' || item.status === historyStatus).map((item: any) => { const id = String(item.review_id ?? item.id); return <div key={id} className={`relative rounded-xl border ${selected?.review_id === id ? 'border-[#0B1F4D] bg-emerald-50/50' : 'border-slate-200 hover:border-slate-300'}`}><button type="button" onClick={() => void openReview(item)} className="w-full p-3 text-left"><span className={`mb-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${item.status === 'approved' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>{item.status === 'approved' ? 'Approuvé' : 'Rejeté'}</span><strong className="block text-sm text-[#11162A]">{item.summary ?? item.agent_id ?? 'Contenu IA'}</strong><span className="mt-1 block text-[11px] text-slate-500">{item.agent_id} · {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString('fr-FR') : 'Date non renseignée'}</span></button><button type="button" disabled={busy} title="Supprimer définitivement" onClick={async () => { if (!confirm('Supprimer définitivement cette décision de l\'historique ?')) return; setBusy(true); setError(''); try { await apiService.deleteHistoryReview(id); if (selected?.review_id === id) setSelected(null); await loadHistory(); setNotice('Décision supprimée de l\'historique.'); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }} className="absolute right-2 top-2 rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"><Trash2 size={13} /></button></div>; })}{!history.some(item => historyStatus === 'all' || item.status === historyStatus) && <p className="text-xs text-slate-500">Aucune décision dans cette catégorie.</p>}</div>
      </section>
      <section className={panel}>{selected ? <><div className="flex items-start justify-between gap-3"><div><h2 className="font-extrabold text-[#11162A]">{selected.summary ?? selected.agent_id ?? 'Décision'}</h2><p className="mt-1 text-xs text-slate-500">{selected.review_id} · {selected.reviewed_at ? new Date(selected.reviewed_at).toLocaleString('fr-FR') : ''}</p></div><button type="button" onClick={() => setSelected(null)} className="text-slate-500"><X size={16} /></button></div>{reviewLoading ? <p className="mt-4 text-xs text-slate-500">Chargement…</p> : <><div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-700"><strong>{selected.status === 'approved' ? 'Note de validation' : 'Motif du rejet'}</strong><p className="mt-1 whitespace-pre-wrap">{selected.status === 'approved' ? selected.reviewer_note || 'Aucune note' : selected.rejection_reason || 'Aucun motif'}</p>{selected.manual_edits_count > 0 && <p className="mt-2">Modifications manuelles avant décision : {selected.manual_edits_count}</p>}</div><div className="mt-4"><ReviewContent value={selected} /></div>{Array.isArray(selected.revision_history) && selected.revision_history.length > 0 && <details className="mt-4 rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-xs font-bold text-[#11162A]">Versions avant validation ({selected.revision_history.length})</summary><div className="mt-3 space-y-3">{selected.revision_history.map((revision: any, index: number) => <div key={index} className="rounded-lg bg-slate-50 p-3"><p className="mb-2 text-xs font-bold text-slate-600">Version {index + 1} · {revision.updated_at ? new Date(revision.updated_at).toLocaleString('fr-FR') : 'Date inconnue'}</p><ReviewContent value={{ data: revision.data }} /></div>)}</div></details>}</>}</> : <p className="text-xs text-slate-500">Sélectionnez une décision pour revoir son contenu et sa note.</p>}</section>
    </div>}

    {tab === 'syllabus' && <div className="grid gap-4 lg:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.15fr)]">
      <form onSubmit={generateSyllabus} className={`${panel} space-y-4`}>
        <div><h2 className="font-extrabold text-[#11162A]">Générer un syllabus avec le RAG</h2><p className="mt-1 text-xs text-slate-500">Le syllabus s'appuie sur les supports indexés et passe en validation humaine avant utilisation.</p></div>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Formation du catalogue *<select required value={syllabusForm.formation_code} onChange={e => setSyllabusForm(previous => ({ ...previous, formation_code: e.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal normal-case text-slate-800"><option value="">Sélectionner une formation</option>{formations.map((formation: any) => <option key={formation.code ?? formation.formation_code} value={formation.code ?? formation.formation_code}>{formation.code ?? formation.formation_code} — {formation.titre ?? formation.nom}</option>)}</select></label>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Modules et durées *<textarea required value={syllabusForm.modules} onChange={e => setSyllabusForm(previous => ({ ...previous, modules: e.target.value }))} rows={7} placeholder={'Introduction | 1 jour\nAtelier pratique | 3h\nÉvaluation | 2h'} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm font-normal normal-case text-slate-800"/><span className="mt-1 block text-[10px] font-normal normal-case text-slate-500">Une ligne par module au format « titre | durée ».</span></label>
        <label className="block text-[11px] font-bold uppercase text-slate-600">Format<select value={syllabusForm.format} onChange={e => setSyllabusForm(previous => ({ ...previous, format: e.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal normal-case"><option value="présentiel">Présentiel</option><option value="distanciel">Distanciel</option><option value="hybride">Hybride</option></select></label>
        <button disabled={busy || !syllabusForm.formation_code} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0B1F4D] px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50">{busy ? <Loader2 size={15} className="animate-spin"/> : <FileText size={15}/>}Générer et soumettre à validation</button>
      </form>
      <section className={`${panel} space-y-4`}><h2 className="font-extrabold text-[#11162A]">Documents de formation</h2><p className="text-xs leading-relaxed text-slate-600">Les syllabus générés apparaissent dans <strong>Validation IA</strong>. Les supports nécessaires au RAG se déposent dans l'onglet <strong>Supports RAG</strong>, puis sont indexés pour enrichir les prochains syllabus.</p><button type="button" onClick={() => setTab('supports')} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-bold text-[#11162A]">Ouvrir les supports documentaires</button>{formations.length === 0 && <p className="rounded-lg bg-amber-50 p-3 text-[11px] text-amber-800">Le catalogue de formations n'est pas disponible. Vérifiez le backend RAG avant de générer le syllabus.</p>}</section>
    </div>}

    {tab === 'supports' && <div className="grid lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)] gap-4">
      {(!readOnly || trainerMode) && <form onSubmit={upload} className={`${panel} space-y-4`}><div><h2 className="font-extrabold text-[#11162A]">Ajouter un support de formation</h2><p className="mt-1 text-[11px] leading-relaxed text-slate-500">{trainerMode ? 'Choisissez une session qui vous est affectée ; le document ne sera visible que dans celle-ci.' : 'Chaque support est classé par session puis par module pour éviter de mélanger les contenus.'}</p></div><div><label className="block font-bold text-slate-600 text-[11px] uppercase mb-1">Session de formation *</label><select required value={sessionId} onChange={e => { const id = e.target.value; setSessionId(id); setFormationCode(sessions.find((item: any) => item.id === id)?.formation_code ?? ''); setModule(''); }} className="w-full px-3 py-2.5 border border-slate-300 bg-slate-50 rounded-xl text-sm"><option value="">Sélectionner une session</option>{sessions.map((item: any) => <option key={item.id} value={item.id}>{item.titre}{item.formation_code ? ` — ${item.formation_code}` : ''}</option>)}</select></div><div><label className="block font-bold text-slate-600 text-[11px] uppercase mb-1">Séance / module pédagogique *</label><input required list="rag-session-modules" value={module} onChange={e => setModule(e.target.value)} placeholder="Choisir une séance ou saisir un module" className="w-full px-3 py-2.5 border border-slate-300 bg-slate-50 rounded-xl text-sm" /><datalist id="rag-session-modules">{(sessions.find((item: any) => item.id === sessionId)?.modules ?? []).map((name: string) => <option key={name} value={name} />)}</datalist><p className="mt-1 text-[10px] text-slate-500">Les thèmes des séances planifiées et les modules déjà classés sont proposés. Vous pouvez aussi saisir un autre module.</p></div><label className="flex items-center gap-3 border border-dashed border-slate-300 rounded-xl p-4 cursor-pointer hover:border-[#0B1F4D]"><Upload size={18} className="text-[#0B1F4D]" /><span className="text-xs text-slate-600">{file?.name ?? 'Choisir un PDF, DOCX, PPTX, XLSX, TXT ou MD'}</span><input type="file" accept=".pdf,.docx,.pptx,.xlsx,.txt,.md" className="hidden" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><button disabled={busy || !file || !sessionId || !module.trim()} className="w-full py-2.5 bg-[#0B1F4D] text-white rounded-xl text-xs font-bold flex justify-center gap-2 items-center">{busy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}Indexer dans cette session</button></form>}
      <section className={panel}><div className="flex justify-between items-center mb-4"><div><h2 className="font-extrabold text-[#11162A]">Supports de formation</h2><p className="mt-1 text-[10px] text-slate-500">Chaque document est isolé par session et repéré par son module pédagogique.</p></div><button onClick={() => loadSupports().catch(e => setError(errorText(e)))} className="text-xs font-bold text-[#0B1F4D]">Actualiser</button></div>{sessions.length > 0 && <div className="mb-4 flex flex-wrap gap-2"><button onClick={() => { setSessionId(''); setFormationCode(''); }} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${sessionId ? 'bg-slate-100 text-slate-600' : 'bg-[#11162A] text-white'}`}>Toutes les sessions</button>{sessions.map((item: any) => <button key={item.id} onClick={() => { setSessionId(item.id); setFormationCode(item.formation_code ?? ''); }} className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${sessionId === item.id ? 'bg-emerald-700 text-white' : 'bg-emerald-50 text-emerald-800'}`}>{item.titre}</button>)}</div>}{supports.length ? <div className="max-h-[440px] space-y-2 overflow-auto">{supports.map((s: any, i) => {
  const status = s.statut_indexation ?? s.statut ?? 'en_attente';
  const progress = s.progression && typeof s.progression === 'object' ? s.progression : {};
  const chunksPrepared = Number(progress.chunks_prepares ?? 0);
  const chunksIndexed = Number(progress.chunks_indexes ?? 0);
  const hasChunkProgress = chunksPrepared > 0 && Number.isFinite(chunksPrepared) && Number.isFinite(chunksIndexed);
  const progressPercent = hasChunkProgress ? Math.min(100, Math.round(chunksIndexed / chunksPrepared * 100)) : null;
  const stage = indexingStageLabel[String(progress.etape ?? '')] ?? (status === 'en_cours' ? 'Préparation de l’indexation' : '');
  const docHash = s.hash ?? s.doc_hash ?? s.id;
  const course = formations.find((f: any) => f.code === s.formation_code);
  const trainingSession = sessions.find((item: any) => item.id === s.session_id);
  const isArchived = status === 'archive';
  const canArchive = status === 'indexe' || status === 'deja_indexe';
  const handleArchive = async () => {
    if (!docHash) return;
    try {
      await apiService.archiveSupport(docHash);
      setSupports(prev => prev.map(sup => (sup.hash ?? sup.doc_hash) === docHash ? { ...sup, statut: 'archive', message: 'Archivé — chunks retirés, fichier conservé.' } : sup));
      setNotice('Support archivé. Les recherches ne l\'utiliseront plus. Vous pouvez le restaurer à tout moment.');
    } catch (e) { setError(errorText(e)); }
  };
  const handleRestore = async () => {
    if (!docHash) return;
    try {
      await apiService.restoreSupport(docHash);
      setSupports(prev => prev.map(sup => (sup.hash ?? sup.doc_hash) === docHash ? { ...sup, statut: 'en_cours', message: 'Restauration en cours…' } : sup));
      setNotice('Restauration lancée en arrière-plan. Actualisez dans quelques secondes.');
    } catch (e) { setError(errorText(e)); }
  };
  const handleDelete = async () => {
    if (!docHash || !window.confirm(`Supprimer définitivement « ${s.fichier ?? s.nom_fichier ?? s.filename ?? 'ce support'} » ? Le fichier et ses éventuels chunks seront supprimés.`)) return;
    try {
      await apiService.deleteSupport(docHash);
      setSupports(prev => prev.filter(sup => (sup.hash ?? sup.doc_hash ?? sup.id) !== docHash));
      setNotice('Support supprimé, ainsi que son fichier et ses éventuels chunks indexés.');
    } catch (e) { setError(errorText(e)); }
  };
  return (
    <div key={docHash ?? i} className={`flex items-start justify-between gap-3 rounded-xl border p-3 ${isArchived ? 'border-slate-200 bg-slate-50 opacity-70' : 'border-slate-200'}`}>
      <div className="min-w-0 flex-1">
        <div className={`truncate font-bold text-sm ${isArchived ? 'text-slate-400 line-through' : 'text-[#11162A]'}`}>{s.fichier ?? s.nom_fichier ?? s.filename ?? 'Support'}</div>
        <div className="mt-1 text-[11px] font-semibold text-emerald-800">{trainingSession?.titre ?? s.session_id ?? 'Session non classée'}{s.formation_code ? ` · ${s.formation_code}` : ''}{course?.titre ? ` — ${course.titre}` : ''}{s.module ? ` · ${s.module}` : ''}</div>
        {s.message && <p className="mt-1 text-[10px] text-slate-500">{s.message}</p>}
        {status === 'en_cours' && <div className="mt-3 max-w-xl rounded-lg border border-blue-100 bg-blue-50/60 p-2.5" aria-live="polite">
          <div className="flex items-center justify-between gap-3 text-[10px] font-semibold text-blue-900"><span className="flex items-center gap-1.5"><Loader2 size={12} className="animate-spin" />{stage}</span>{progressPercent !== null && <span>{progressPercent}%</span>}</div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-blue-100">{progressPercent !== null ? <div className="h-full rounded-full bg-blue-600 transition-[width] duration-500" style={{ width: `${progressPercent}%` }} /> : <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-600" />}</div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[9px] text-blue-800">{Number.isFinite(Number(progress.nb_pages)) && progress.nb_pages != null && <span>{progress.nb_pages} page(s) lues</span>}{hasChunkProgress && <span>{chunksIndexed}/{chunksPrepared} passages vectorisés</span>}{progress.lots_total != null && <span>{progress.lots_indexes ?? 0}/{progress.lots_total} lots enregistrés</span>}{progress.modele_embed && <span>Modèle : {progress.modele_embed}</span>}</div>
        </div>}
      </div>
      <div className="flex flex-col items-end gap-1.5 shrink-0">
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${supportStatusStyle[status] ?? 'bg-slate-100 text-slate-600'}`}>{supportStatusLabel[status] ?? status}</span>
        {!readOnly && canArchive && (
          <button type="button" onClick={handleArchive} title="Archiver ce support (retire les chunks, fichier conservé)" className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 transition">
            Archiver
          </button>
        )}
        {!readOnly && isArchived && (
          <button type="button" onClick={handleRestore} title="Restaurer ce support (ré-indexation depuis le fichier conservé)" className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 transition">
            Restaurer
          </button>
        )}
        {!readOnly && !trainerMode && docHash && status !== 'en_cours' && (
          <button type="button" onClick={handleDelete} title="Supprimer définitivement ce support et ses éventuels chunks" className="flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700 transition hover:bg-red-100">
            <Trash2 size={11} /> Supprimer
          </button>
        )}
      </div>
    </div>
  );
})}</div> : <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">{sessionId ? `Aucun support enregistré pour la session sélectionnée.` : 'Aucun support disponible.'}</p>}</section>
    </div>}

    {tab === 'chat' && (
      <div className={`grid gap-4 ${ragConversations.length > 0 && sidebarOpen ? 'lg:grid-cols-[260px_minmax(0,1fr)]' : ''}`}>

        {/* ── Sidebar conversations ── */}
        {ragConversations.length > 0 && sidebarOpen && (
          <aside className="flex flex-col gap-0 h-fit rounded-2xl overflow-hidden border border-slate-200 shadow-sm"
            style={{ background: 'linear-gradient(180deg, #0B1F4D 0%, #06132F 100%)' }}>
            {/* Header sidebar */}
            <div className="px-4 pt-4 pb-3 border-b border-white/10">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-extrabold text-sm text-white tracking-tight flex items-center gap-2">
                  <MessageCircle size={14} style={{ color: '#D4AF37' }} />Conversations
                </h3>
                <div className="flex items-center gap-1">
                  {conversationsLoading && <Loader2 size={12} className="animate-spin text-white/40" />}
                  <button type="button" onClick={() => setSidebarOpen(false)} title="Masquer le panneau" className="p-1.5 rounded-lg text-white/30 hover:text-white/80 hover:bg-white/10 transition">
                    <X size={13} />
                  </button>
                </div>
              </div>
              <button type="button" onClick={newConversation}
                className="flex items-center gap-2 w-full rounded-xl px-3 py-2.5 text-xs font-bold transition-all"
                style={{ background: 'rgba(212,175,55,0.12)', border: '1px solid rgba(212,175,55,0.3)', color: '#D4AF37' }}>
                <PlusCircle size={13} />Nouvelle conversation
              </button>
            </div>
            {/* Liste conversations */}
            <div className="px-3 pb-3 space-y-1 max-h-[420px] overflow-y-auto">
              {ragConversations.map((conv: any) => (
                <div key={conv.conversation_id}
                  className="group relative rounded-xl p-2.5 transition-all cursor-pointer"
                  style={{
                    background: conversationId === conv.conversation_id ? 'rgba(212,175,55,0.12)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${conversationId === conv.conversation_id ? 'rgba(212,175,55,0.35)' : 'rgba(255,255,255,0.07)'}`,
                  }}>
                  {renamingConvId === conv.conversation_id ? (
                    <div className="flex items-center gap-1">
                      <input autoFocus value={renameValue} onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') void confirmRename(conv.conversation_id); if (e.key === 'Escape') setRenamingConvId(null); }}
                        className="flex-1 min-w-0 text-xs border border-white/20 rounded bg-white/10 text-white px-1.5 py-1 outline-none" />
                      <button type="button" onClick={() => void confirmRename(conv.conversation_id)} className="p-1 rounded text-emerald-400"><Check size={11} /></button>
                      <button type="button" onClick={() => setRenamingConvId(null)} className="p-1 rounded text-white/40"><X size={11} /></button>
                    </div>
                  ) : (
                    <>
                      <button type="button" onClick={() => void resumeConversation(conv)} className="w-full text-left min-w-0 pr-8">
                        <div className="truncate text-xs font-semibold text-white/90">{conv.titre || 'Conversation'}</div>
                        <div className="mt-0.5 text-[10px] text-white/35">
                          {conv.nb_echanges} échange{conv.nb_echanges > 1 ? 's' : ''}{conv.mis_a_jour_le ? ` · ${new Date(conv.mis_a_jour_le * 1000).toLocaleDateString('fr-FR')}` : ''}
                        </div>
                      </button>
                      <div className="absolute right-1.5 top-1.5 flex gap-0.5 opacity-0 group-hover:opacity-100 transition">
                        <button type="button" onClick={() => startRename(conv)} title="Renommer" className="p-1 rounded text-white/30 hover:text-white/80 hover:bg-white/10"><Pencil size={10} /></button>
                        <button type="button" onClick={() => void deleteRagConversation(conv.conversation_id)} title="Supprimer" className="p-1 rounded text-white/30 hover:text-red-400 hover:bg-red-500/10"><Trash2 size={10} /></button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
            <div className="px-4 pb-3 text-[10px] text-white/20 border-t border-white/8 pt-2">Max 20 conversations conservées.</div>
          </aside>
        )}

        {/* ── Zone de chat principale premium ── */}
        <section className="flex flex-col rounded-2xl border border-slate-200 shadow-sm overflow-hidden bg-white" style={{ minHeight: 560 }}>

          {/* Header chat — fond navy */}
          <div className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            style={{ background: 'linear-gradient(135deg, #0B1F4D 0%, #06132F 100%)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="flex items-center gap-3 min-w-0">
              {/* Bouton toggle sidebar */}
              {ragConversations.length > 0 && !sidebarOpen && (
                <button type="button" onClick={() => setSidebarOpen(true)} title="Afficher les conversations"
                  className="flex items-center gap-1.5 shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all"
                  style={{ background: 'rgba(212,175,55,0.12)', border: '1px solid rgba(212,175,55,0.3)', color: '#D4AF37' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
                </button>
              )}
              <div className="min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ background: 'rgba(212,175,55,0.15)', border: '1px solid rgba(212,175,55,0.3)' }}>
                  <MessageCircle size={14} style={{ color: '#D4AF37' }} />
                </div>
                <h2 className="font-extrabold text-sm text-white tracking-tight">Assistant documentaire</h2>
                <div className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: '#D4AF37' }} />
                  <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: '#D4AF37' }} />
                </div>
              </div>
              <p className="text-[11px] text-white/40 pl-9">
                {sessionId
                  ? `Session : ${sessions.find((item: any) => item.id === sessionId)?.titre ?? sessionId}${chatModule ? ` · ${chatModule}` : ''}`
                  : trainerMode ? 'Choisissez une session qui vous est affectée.' : 'Catalogue, inventaire et synthèses disponibles — choisissez une session pour son contenu.'}
              </p>
              </div>
            </div>
            <div className="flex flex-col gap-1.5 sm:items-end">
              <select required={trainerMode} value={sessionId}
                onChange={e => { const id = e.target.value; setSessionId(id); setFormationCode(sessions.find((item: any) => item.id === id)?.formation_code ?? ''); setChatModule(''); }}
                className="px-3 py-2 rounded-lg text-xs font-semibold text-white/90 outline-none focus:ring-1 focus:ring-brand-gold/50"
                style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)' }}>
                <option value="" style={{ background: '#0B1F4D' }}>{trainerMode ? 'Choisir ma session' : 'Toutes les sessions'}</option>
                {sessions.map((item: any) => <option key={item.id} value={item.id} style={{ background: '#0B1F4D' }}>{item.titre}{item.formation_code ? ` — ${item.formation_code}` : ''}</option>)}
              </select>
              {sessionId && (sessions.find((item: any) => item.id === sessionId)?.modules?.length ?? 0) > 0 && (
                <select value={chatModule} onChange={e => setChatModule(e.target.value)}
                  className="px-3 py-2 rounded-lg text-xs font-semibold text-white/90 outline-none"
                  style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)' }}>
                  <option value="" style={{ background: '#0B1F4D' }}>Tous les modules</option>
                  {sessions.find((item: any) => item.id === sessionId)?.modules.map((name: string) => <option key={name} value={name} style={{ background: '#0B1F4D' }}>{name}</option>)}
                </select>
              )}
            </div>
          </div>

          {/* Zone messages */}
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5" style={{ minHeight: 320, maxHeight: 480, background: '#F8F9FB' }}>
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full py-16 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
                  style={{ background: 'linear-gradient(135deg, #0B1F4D, #06132F)', boxShadow: '0 8px 32px rgba(11,31,77,0.25)' }}>
                  <MessageCircle size={28} className="text-white/80" />
                </div>
                <p className="text-sm font-bold text-slate-700 mb-1">Comment puis-je vous aider ?</p>
                <p className="text-[11px] text-slate-400 max-w-sm leading-relaxed">Posez toute question sur vos formations — le contenu est extrait directement des supports indexés, sans hallucination.</p>
                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                  {[
                    { icon: '📋', label: 'Résumé du contenu', q: 'Fais un résumé structuré du contenu de cette formation.' },
                    { icon: '🔍', label: 'Chercher un sujet', q: 'Où est expliqué ce sujet dans les supports ?' },
                    { icon: '📊', label: 'Synthèse thématique', q: 'Génère une synthèse thématique des points clés.' },
                    { icon: '📝', label: 'Exercices disponibles', q: 'Quels exercices pratiques sont disponibles dans les supports ?' },
                  ].map(({ icon, label, q }) => (
                    <button key={q} type="button" onClick={() => void sendMessage(q)}
                      className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-xs font-semibold text-slate-600 hover:border-[#0B1F4D]/40 hover:bg-[#0B1F4D]/3 hover:text-[#0B1F4D] transition-all shadow-xs group">
                      <span className="text-base">{icon}</span>
                      <span>{label}</span>
                      <svg className="ml-auto text-slate-300 group-hover:text-[#0B1F4D]/50 transition" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => {
              const isStreaming = busy && i === messages.length - 1 && m.role === 'assistant';
              const isUser = m.role === 'user';
              const progressLabel = streamingStatus.toLocaleLowerCase();
              const activeStage = /rédaction|redaction|réponse prête|reponse prete|finalisation/.test(progressLabel) || (isStreaming && Boolean(m.text))
                ? 2 : /recherche|passage|support|document/.test(progressLabel) ? 1 : 0;
              return (
                <div key={i} className={`group flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-2`}>
                  <div className={`max-w-[85%] ${isUser ? '' : ''}`}>
                    {/* Bulle message */}
                    <div className={`relative px-4 py-3 rounded-2xl text-sm leading-relaxed ${isUser
                      ? 'text-white rounded-br-sm'
                      : 'text-slate-800 rounded-bl-sm bg-white border border-slate-200'}`}
                      style={isUser ? {
                        background: 'linear-gradient(135deg, #0B1F4D 0%, #06132F 100%)',
                        boxShadow: '0 4px 16px rgba(11,31,77,0.25)',
                      } : {
                        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                      }}>

                      {/* Loader streaming */}
                      {isStreaming && !m.text ? (
                        <div className="min-w-56 space-y-3" role="status" aria-live="polite">
                          <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                            <Loader2 size={13} className="animate-spin text-[#0B1F4D]" />
                            <span>{streamingStatus || 'Préparation…'}</span>
                          </div>
                          <div className="flex gap-2 text-[10px]">
                            {['Compréhension', 'Recherche RAG', 'Rédaction'].map((stage, si) => (
                              <div key={stage} className="flex items-center gap-1 rounded-lg px-2 py-1 transition-colors"
                                style={{
                                  background: si < activeStage ? 'rgba(16,122,96,0.08)' : si === activeStage ? '#fff' : 'rgba(0,0,0,0.03)',
                                  border: `1px solid ${si < activeStage ? 'rgba(16,122,96,0.25)' : si === activeStage ? 'rgba(11,31,77,0.2)' : 'rgba(0,0,0,0.08)'}`,
                                  color: si < activeStage ? '#167a60' : si === activeStage ? '#0B1F4D' : '#94a3b8',
                                  fontWeight: si === activeStage ? 700 : 500,
                                }}>
                                <span>{si < activeStage ? '✓' : si === activeStage ? '●' : '○'}</span>{stage}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : <>
                        {isStreaming && m.text && (
                          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700">
                            <span className="relative flex h-1.5 w-1.5">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            </span>
                            Rédaction en cours…
                          </div>
                        )}
                        {m.text
                          ? isUser
                            ? <span className="whitespace-pre-wrap text-[13px] leading-relaxed">{m.text}{isStreaming && <span className="inline-block w-0.5 h-3.5 bg-white/70 ml-0.5 align-middle animate-pulse" />}</span>
                            : isStreaming
                              ? <div className="prose-chat"><span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }} /><span className="inline-block w-0.5 h-4 bg-[#0B1F4D]/70 ml-0.5 align-middle animate-[pulse_0.8s_ease-in-out_infinite]" /></div>
                              : <div className="prose-chat"><span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }} /></div>
                          : isStreaming ? null : ''}
                      </>}

                      {/* Actions hover */}
                      {m.text && !isStreaming && (
                        <div className={`absolute -bottom-6 ${isUser ? 'right-0' : 'left-0'} flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition`}>
                          <button type="button" onClick={() => copyMessage(m.text, i)}
                            className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-white border border-slate-200 text-[10px] text-slate-500 hover:text-[#0B1F4D] shadow-sm transition">
                            {copiedMsgIdx === i ? <Check size={10} className="text-emerald-600" /> : <Copy size={10} />}
                            {copiedMsgIdx === i ? 'Copié' : 'Copier'}
                          </button>
                          {!isUser && (<>
                            <button type="button" onClick={() => void sendFeedback(i, 'positif')}
                              className={`p-1 rounded-md border shadow-sm transition ${feedbacks[i] === 'positif' ? 'bg-emerald-50 border-emerald-300 text-emerald-600' : 'bg-white border-slate-200 text-slate-400 hover:text-emerald-600'}`}>
                              <ThumbsUp size={10} />
                            </button>
                            <button type="button" onClick={() => void sendFeedback(i, 'negatif')}
                              className={`p-1 rounded-md border shadow-sm transition ${feedbacks[i] === 'negatif' ? 'bg-red-50 border-red-300 text-red-600' : 'bg-white border-slate-200 text-slate-400 hover:text-red-500'}`}>
                              <ThumbsDown size={10} />
                            </button>
                          </>)}
                        </div>
                      )}
                    </div>

                    {/* Sources */}
                    {m.sources && m.sources.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {m.sources.map((s: any, j: number) => (
                          <span key={j} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[10px] font-semibold"
                            style={{ background: 'rgba(16,122,96,0.07)', border: '1px solid rgba(16,122,96,0.18)', color: '#167a60' }}>
                            <FileText size={9} />
                            {s.fichier ?? s.filename ?? 'Document'}{s.page ? `, p. ${s.page}` : ''}
                            {s.score ? <span className="ml-1 opacity-60">{Math.round(s.score * 100)}%</span> : ''}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Suggestions */}
                    {m.suggestions && m.suggestions.length > 0 && m.role === 'assistant' && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {m.suggestions.map((suggestion, j) => (
                          <button key={j} type="button" onClick={() => void sendMessage(suggestion)}
                            className="rounded-xl bg-white border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[#0B1F4D] hover:text-[#0B1F4D] hover:bg-slate-50 transition shadow-sm">
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Input bar premium */}
          <div className="px-4 py-3 border-t border-slate-100 bg-white">
            <form onSubmit={e => { e.preventDefault(); void sendMessage(); }}
              className="flex items-center gap-2 rounded-2xl px-3 py-2 transition-all"
              style={{ border: '1.5px solid', borderColor: draft ? '#0B1F4D' : '#e2e8f0', boxShadow: draft ? '0 0 0 3px rgba(11,31,77,0.06)' : 'none', background: '#fafafa' }}>
              <MessageCircle size={15} className="shrink-0 text-slate-400" />
              <input
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }}
                placeholder="Posez votre question sur les supports de formation…"
                className="flex-1 min-w-0 bg-transparent text-sm text-slate-800 placeholder:text-slate-400 outline-none"
              />
              <button
                type="submit"
                disabled={busy || !draft.trim() || (trainerMode && !sessionId)}
                className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold text-white transition-all disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg, #0B1F4D, #06132F)', boxShadow: '0 2px 8px rgba(11,31,77,0.3)' }}>
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                {busy ? '' : 'Envoyer'}
              </button>
            </form>
            <p className="mt-1.5 text-center text-[10px] text-slate-400">MODE STRICT — Réponses fondées uniquement sur les documents indexés</p>
          </div>
        </section>
      </div>
    )}

    {tab === 'config_llm' && (
      <div className="w-full">
        <LLMConfigPanel />
      </div>
    )}
  </div>;
};

