import React, { useRef, useState } from 'react';
import { Mic, MicOff, Send, Volume2, X } from 'lucide-react';
import { apiService } from '../services/api';
import type { MenuSection } from '../types';

type Props = {
  currentSection: MenuSection;
  onNavigate: (section: MenuSection) => void;
  onCreateSession: () => void;
  onCreateOpportunity: () => void;
  onCreateInvoice: () => void;
};

const actionSections: Record<string, MenuSection> = {
  lancer_veille: 'veille_marche', afficher_opportunites: 'veille_marche',
  afficher_sessions: 'sessions_groupes', afficher_validations: 'espace_ia',
  ouvrir_formulaire_session: 'sessions_groupes', ouvrir_formulaire_seance: 'sessions_groupes',
  ouvrir_formulaires_session: 'sessions_groupes', ouvrir_analyse_niveaux: 'evaluation_competences',
  ouvrir_analyse_satisfaction: 'evaluation_competences', ouvrir_analyse_presences: 'suivi_presences',
  ouvrir_formulaire_attestation: 'sessions_groupes', ouvrir_preparation: 'opportunites_crm',
  ouvrir_formulaire_tdr: 'opportunites_crm', ouvrir_facturation: 'facturation_devis',
  ouvrir_chat_rag: 'espace_ia'
};

export const VocalAssistant: React.FC<Props> = ({ currentSection, onNavigate, onCreateSession, onCreateOpportunity, onCreateInvoice }) => {
  const [open, setOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState('');
  const recognitionRef = useRef<any>(null);

  const processCommand = async (text = transcript) => {
    if (!text.trim()) return;
    setBusy(true); setError('');
    try {
      const result = await apiService.sendVoiceCommand({ texte: text.trim(), ecran_actuel: currentSection });
      setAnswer(result);
      const spoken = result.texte_a_lire || result.reponse_vocale;
      if (spoken && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(spoken));
      }
      const action = String(result.action_frontend ?? '');
      const section = actionSections[action];
      if (section) onNavigate(section);
      if (action === 'ouvrir_formulaire_session') onCreateSession();
      if (action === 'ouvrir_formulaire_tdr') onCreateOpportunity();
      if (action === 'ouvrir_facturation') onCreateInvoice();
      if (result.prefill && Object.keys(result.prefill).length) {
        try { sessionStorage.setItem('forma_ia_voice_prefill', JSON.stringify(result.prefill)); } catch { /* stockage désactivé */ }
        window.dispatchEvent(new CustomEvent('forma-ia:vocal-prefill', { detail: result.prefill }));
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'La commande vocale n’a pas abouti.'); }
    finally { setBusy(false); }
  };

  const startListening = () => {
    const Speech = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Speech) { setError('La reconnaissance vocale n’est pas disponible dans ce navigateur. Vous pouvez saisir la commande ci-dessous.'); setOpen(true); return; }
    const recognition = new Speech();
    recognition.lang = 'fr-FR'; recognition.interimResults = false; recognition.maxAlternatives = 1;
    recognition.onresult = (event: any) => {
      const text = event.results?.[0]?.[0]?.transcript ?? '';
      setTranscript(text); setRecording(false); void processCommand(text);
    };
    recognition.onerror = (event: any) => { setError(event.error === 'not-allowed' ? 'Autorisez le microphone dans le navigateur.' : 'La dictée n’a pas pu être transcrite.'); setRecording(false); };
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition; setOpen(true); setError(''); setRecording(true); recognition.start();
  };

  const confirmExecution = async () => {
    const plan = answer?.execution_plan;
    if (!plan?.intention) return;
    setExecuting(true); setError('');
    try {
      const params = { ...(answer.prefill ?? {}), ...(plan.parameters ?? {}), ...(answer.parametres ?? {}) };
      const result = await apiService.executeVoiceAction(plan.intention, params, params);
      setAnswer((previous: any) => ({ ...previous, execution_result: result }));
      const spoken = result.message ?? 'Action traitée.';
      if ('speechSynthesis' in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(spoken));
    } catch (e) { setError(e instanceof Error ? e.message : 'L’action vocale n’a pas pu être exécutée.'); }
    finally { setExecuting(false); }
  };

  return <>
    <button onClick={() => { setOpen(v => !v); if (!open) setError(''); }} aria-label="Ouvrir l’assistant vocal" className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-[#1B8F6E] text-white shadow-xl shadow-emerald-900/20 flex items-center justify-center hover:bg-[#16785c]">
      {recording ? <MicOff size={22}/> : <Mic size={22}/>}<span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-red-500 border-2 border-white"/>
    </button>
    {open && <div className="fixed bottom-24 right-6 z-40 w-[min(390px,calc(100vw-2rem))] rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl">
      <div className="flex items-start justify-between gap-3"><div><div className="text-[10px] font-bold uppercase tracking-wider text-[#1B8F6E]">Agent vocal FORMA-IA</div><h2 className="mt-1 font-extrabold text-[#11162A]">Que souhaitez-vous faire ?</h2></div><button onClick={()=>{recognitionRef.current?.stop?.();setRecording(false);setOpen(false);}} className="p-1 text-slate-400"><X size={17}/></button></div>
      <div className="mt-3 flex gap-2"><input value={transcript} onChange={e=>setTranscript(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void processCommand();}} placeholder="Dictez ou saisissez une commande…" className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"/><button onClick={recording?()=>recognitionRef.current?.stop?.():startListening} className={`rounded-xl px-3 text-white ${recording?'bg-red-600':'bg-[#11162A]'}`} aria-label="Dicter"><Mic size={16}/></button><button disabled={busy||!transcript.trim()} onClick={()=>void processCommand()} className="rounded-xl bg-[#1B8F6E] px-3 text-white disabled:opacity-50" aria-label="Envoyer">{busy?<span className="text-xs">…</span>:<Send size={16}/>}</button></div>
      {error&&<p role="alert" className="mt-2 text-xs text-red-700">{error}</p>}
      {answer&&<div className="mt-3 rounded-xl bg-emerald-50 p-3 text-xs"><div className="flex items-center gap-1.5 font-bold text-emerald-900"><Volume2 size={14}/>{answer.texte_affiche||answer.reponse_vocale}</div>{answer.action_frontend&&<p className="mt-1 text-emerald-800">Action : {String(answer.action_frontend).replaceAll('_',' ')}</p>}{answer.parametres_manquants?.length>0&&<p className="mt-1 text-amber-800">Informations à préciser : {answer.parametres_manquants.join(', ')}</p>}{answer.prefill&&Object.keys(answer.prefill).length>0&&<details className="mt-2"><summary className="cursor-pointer font-bold">Préremplissage proposé</summary><pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify(answer.prefill,null,2)}</pre></details>}{answer.execution_plan?.intention&&!answer.execution_result&&<button disabled={executing} onClick={()=>void confirmExecution()} className="mt-3 w-full rounded-lg bg-[#1B8F6E] px-3 py-2 font-bold text-white disabled:opacity-50">{executing?'Exécution…':'Confirmer et exécuter'}</button>}{answer.execution_result&&<p className={`mt-2 font-bold ${answer.execution_result.success?'text-emerald-800':'text-red-700'}`}>{answer.execution_result.message}</p>}</div>}
    </div>}
  </>;
};
