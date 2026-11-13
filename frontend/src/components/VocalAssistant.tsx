import React, { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Mic, Send, Volume2, X, Zap } from 'lucide-react';
import { apiService } from '../services/api';
import { canAccessSection, type MenuSection, type Session, type UserRole } from '../types';
import { saveVoiceActionContext } from '../services/voiceActionContext';

type Props = {
  currentRole: UserRole;
  currentSection: MenuSection;
  sessions: Session[];
  onNavigate: (section: MenuSection) => void;
  onCreateSession: () => void;
  onCreateOpportunity: () => void;
  onCreateInvoice: () => void;
};

const actionSections: Record<string, MenuSection> = {
  ouvrir_tableau_bord: 'tableau_de_bord', ouvrir_formateurs: 'formateurs_staff',
  ouvrir_evaluation: 'evaluation_competences', ouvrir_suivi_presences: 'suivi_presences',
  ouvrir_espace_ia: 'espace_ia',
  lancer_veille: 'veille_marche', afficher_opportunites: 'veille_marche',
  afficher_sessions: 'sessions_groupes', afficher_validations: 'espace_ia',
  ouvrir_formulaire_session: 'sessions_groupes', ouvrir_formulaire_seance: 'sessions_groupes',
  ouvrir_formulaires_session: 'sessions_groupes', ouvrir_analyse_niveaux: 'evaluation_competences',
  ouvrir_analyse_satisfaction: 'evaluation_competences', ouvrir_analyse_presences: 'suivi_presences',
  ouvrir_formulaire_attestation: 'sessions_groupes', ouvrir_preparation: 'opportunites_crm',
  ouvrir_formulaire_tdr: 'opportunites_crm', ouvrir_formulaire_offre: 'opportunites_crm',
  ouvrir_facturation: 'facturation_devis',
  ouvrir_chat_rag: 'espace_ia'
};

const contextualActions = new Set([
  'lancer_veille', 'ouvrir_formulaire_tdr', 'ouvrir_formulaire_offre',
  'ouvrir_formulaire_seance', 'ouvrir_formulaires_session', 'ouvrir_analyse_niveaux',
  'ouvrir_analyse_satisfaction', 'ouvrir_analyse_presences', 'ouvrir_formulaire_attestation',
]);

const QUICK_COMMANDS = [
  'Tableau de bord',
  'Lancer la veille',
  'Voir les sessions',
  'Espace IA',
  'Facturation',
  'Nouvelles opportunités',
];

const voiceText = (text: string) => {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'fr-FR';
  utterance.rate = 1.02;
  const frenchVoices = window.speechSynthesis.getVoices().filter(v => v.lang.toLowerCase().startsWith('fr'));
  utterance.voice = frenchVoices.find(v => /paul|thomas|henri|male|homme/i.test(v.name)) ?? frenchVoices[0] ?? null;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
};

type HistoryItem =
  | { type: 'user'; text: string }
  | { type: 'ai'; text: string; action?: string; confiance?: number; execution_plan?: any; execution_result?: any; parametres_manquants?: string[] };

export const VocalAssistant: React.FC<Props> = ({
  currentRole, currentSection, sessions, onNavigate,
  onCreateSession, onCreateOpportunity: _onCreateOpportunity, onCreateInvoice: _onCreateInvoice
}) => {
  const [open, setOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const recognitionRef = useRef<any>(null);
  const busyRef = useRef(false);
  const clarificationContext = useRef<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, busy]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  const speak = (text: string) => {
    if (text && 'speechSynthesis' in window) voiceText(text);
  };

  const processCommand = async (text = transcript) => {
    const command = text.trim();
    if (!command || busyRef.current) return;
    const normalized = command.toLocaleLowerCase('fr-FR').replace(/[.!?]+$/g, '').trim();
    if (/^(confirme|je confirme|oui confirme|confirmer|execute|exécute|valide)$/.test(normalized) && answer?.execution_plan?.intention) {
      await confirmExecution();
      return;
    }
    if (/^(annule|annuler|stop|j'annule)$/.test(normalized)) {
      clarificationContext.current = [];
      setAnswer(null);
      setTranscript('');
      setError('Action annulée.');
      speak("D'accord, action annulée.");
      return;
    }
    busyRef.current = true;
    setBusy(true); setError('');
    setHistory(h => [...h, { type: 'user', text: command }]);
    setTranscript('');
    try {
      const sessionsDisponibles = sessions.slice(0, 50).map(s => ({
        id: s.id, titre: s.intitule, code: s.code,
        date_debut: s.dateDebut, dates: s.dates, formation_code: s.formationCode
      }));
      const result = await apiService.sendVoiceCommand({
        texte: command,
        ecran_actuel: currentSection,
        contexte_action: clarificationContext.current,
        sessions_disponibles: sessionsDisponibles
      });
      setAnswer(result);
      const spoken = result.texte_a_lire || result.reponse_vocale;
      speak(spoken);
      setHistory(h => [...h, {
        type: 'ai',
        text: result.texte_affiche || result.reponse_vocale,
        action: result.action_frontend ? String(result.action_frontend) : undefined,
        confiance: result.confiance,
        execution_plan: result.execution_plan,
        parametres_manquants: result.parametres_manquants,
      }]);
      const action = String(result.action_frontend ?? '');
      const section = actionSections[action];
      if (result.etat === 'a_preciser') clarificationContext.current = [...clarificationContext.current, command].slice(-8);
      else clarificationContext.current = [];
      if (section && result.parametres_manquants?.length === 0) {
        if (!canAccessSection(currentRole, section)) {
          setError("Votre rôle ne permet pas d'ouvrir cet écran.");
          speak("Votre rôle ne permet pas d'ouvrir cet écran.");
          return;
        }
        const context = { action, prefill: result.prefill ?? result.parametres ?? {} };
        if (section === currentSection) {
          window.dispatchEvent(new CustomEvent('forma-ia:vocal-action', { detail: context }));
        } else {
          if (contextualActions.has(action)) saveVoiceActionContext(context);
          onNavigate(section);
        }
      }
      if (action === 'ouvrir_formulaire_session') onCreateSession();
      if (result.prefill && Object.keys(result.prefill).length) {
        try { sessionStorage.setItem('forma_ia_voice_prefill', JSON.stringify(result.prefill)); } catch { /* désactivé */ }
        window.dispatchEvent(new CustomEvent('forma-ia:vocal-prefill', { detail: result.prefill }));
      }
    } catch (e) { setError(e instanceof Error ? e.message : "La commande vocale n'a pas abouti."); }
    finally { busyRef.current = false; setBusy(false); }
  };

  const startListening = () => {
    const Speech = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Speech) {
      setError('La reconnaissance vocale nécessite Chrome. Vous pouvez saisir la commande ci-dessous.');
      setOpen(true);
      return;
    }
    const recognition = new Speech();
    recognition.lang = 'fr-FR'; recognition.interimResults = true; recognition.maxAlternatives = 1;
    recognition.onresult = (event: any) => {
      let finalText = ''; let interimText = '';
      for (let idx = event.resultIndex; idx < event.results.length; idx++) {
        const t = event.results[idx]?.[0]?.transcript ?? '';
        if (event.results[idx].isFinal) finalText += t;
        else interimText += t;
      }
      if (finalText.trim()) {
        const t = finalText.trim();
        setTranscript(t); setRecording(false); void processCommand(t);
      } else if (interimText) setTranscript(interimText.trim());
    };
    recognition.onerror = (event: any) => {
      const msgs: Record<string, string> = {
        'not-allowed': 'Autorisez le microphone dans Chrome.',
        'service-not-allowed': 'Service vocal Chrome indisponible.',
        'audio-capture': 'Aucun microphone détecté.',
        'no-speech': 'Aucune parole détectée. Réessayez.',
        network: 'Connexion réseau instable.',
      };
      if (event.error !== 'aborted') setError(msgs[event.error] ?? 'Dictée impossible. Saisissez la commande.');
      setRecording(false);
    };
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition;
    setOpen(true); setError(''); setTranscript(''); setRecording(true);
    try { recognition.start(); } catch { setRecording(false); setError('Microphone déjà utilisé.'); }
  };

  const confirmExecution = async () => {
    const plan = answer?.execution_plan;
    if (!plan?.intention) return;
    setExecuting(true); setError('');
    try {
      const params = { ...(answer.prefill ?? {}), ...(plan.parameters ?? {}), ...(answer.parametres ?? {}) };
      const result = await apiService.executeVoiceAction(plan.intention, params, params);
      setAnswer((prev: any) => ({ ...prev, execution_result: result }));
      setHistory(h => h.map((item, i) =>
        i === h.length - 1 && item.type === 'ai'
          ? { ...item, execution_result: result }
          : item
      ));
      speak(result.message ?? 'Action traitée.');
    } catch (e) { setError(e instanceof Error ? e.message : "L'action n'a pas pu être exécutée."); }
    finally { setExecuting(false); }
  };

  const closePanel = () => {
    recognitionRef.current?.stop?.();
    setRecording(false);
    setOpen(false);
  };

  const confidenceColor = (c?: number) => {
    if (!c) return 'text-slate-400';
    if (c >= 0.85) return 'text-emerald-400';
    if (c >= 0.60) return 'text-amber-400';
    return 'text-red-400';
  };

  const lastAiItem = [...history].reverse().find(h => h.type === 'ai') as Extract<HistoryItem, { type: 'ai' }> | undefined;

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => { setOpen(v => !v); if (!open) setError(''); }}
        aria-label="Ouvrir l'agent vocal FORMA-IA"
        title="Agent vocal IA — FORMA-IA"
        className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-[#0B1F4D] text-white shadow-xl shadow-[#0B1F4D]/30 flex items-center justify-center hover:bg-[#06132F] transition-colors"
      >
        <Bot size={22} />
        <span className={`absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white ${recording ? 'bg-red-500 animate-pulse' : busy ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}`}>
          <Mic size={9} />
        </span>
      </button>

      {/* Panel */}
      {open && (
        <div
          className="fixed bottom-24 right-6 z-40 flex flex-col rounded-2xl overflow-hidden shadow-2xl shadow-black/40"
          style={{ width: 'min(420px, calc(100vw - 2rem))', height: 520 }}
        >
          {/* Header */}
          <div className="flex items-center gap-2.5 px-4 py-3 bg-[#0B1F4D] border-b border-white/10 shrink-0">
            <div className="h-8 w-8 rounded-xl bg-emerald-500/20 flex items-center justify-center">
              <Bot size={16} className="text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-white leading-none">Agent Vocal IA</div>
              <div className="text-[10px] text-slate-400 mt-0.5 truncate">FORMA-IA · {currentSection.replace(/_/g, ' ')}</div>
            </div>
            <button
              onClick={closePanel}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              aria-label="Fermer"
            >
              <X size={15} />
            </button>
          </div>

          {/* Quick commands */}
          <div className="flex gap-1.5 px-3 py-2 bg-[#0d2460] border-b border-white/10 overflow-x-auto shrink-0 scrollbar-none">
            {QUICK_COMMANDS.map(cmd => (
              <button
                key={cmd}
                onClick={() => void processCommand(cmd)}
                disabled={busy}
                className="shrink-0 rounded-full border border-white/15 px-2.5 py-1 text-[10px] font-medium text-slate-300 hover:bg-white/10 hover:border-emerald-400/50 hover:text-white whitespace-nowrap transition-colors disabled:opacity-40"
              >
                {cmd}
              </button>
            ))}
          </div>

          {/* Chat area */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-[#0a1a40]"
          >
            {history.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center pb-6">
                <div className="h-14 w-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-3">
                  <Bot size={26} className="text-emerald-400 opacity-60" />
                </div>
                <p className="text-slate-400 text-sm font-medium">Que souhaitez-vous faire ?</p>
                <p className="text-slate-600 text-xs mt-1">Utilisez le micro ou tapez une commande</p>
              </div>
            )}

            {history.map((item, i) =>
              item.type === 'user' ? (
                <div key={i} className="flex justify-end">
                  <div className="max-w-[78%] rounded-2xl rounded-br-sm bg-[#1a3a7a] px-3.5 py-2.5 text-sm text-white shadow-sm">
                    {item.text}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex gap-2.5">
                  <div className="shrink-0 mt-1 h-7 w-7 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                    <Bot size={13} className="text-emerald-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="rounded-2xl rounded-bl-sm bg-white/8 px-3.5 py-2.5 text-sm text-slate-200 leading-relaxed">
                      {item.text}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {item.action && item.action !== 'undefined' && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/25 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                          <Zap size={8} />
                          {item.action.replace(/_/g, ' ')}
                        </span>
                      )}
                      {item.confiance !== undefined && item.confiance > 0 && (
                        <span className={`text-[10px] font-semibold ${confidenceColor(item.confiance)}`}>
                          {Math.round(item.confiance * 100)}%
                        </span>
                      )}
                      {item.parametres_manquants && item.parametres_manquants.length > 0 && (
                        <span className="text-[10px] text-amber-400">
                          Préciser : {item.parametres_manquants.join(', ')}
                        </span>
                      )}
                      {item.execution_result && (
                        <span className={`text-[10px] font-semibold ${item.execution_result.success ? 'text-emerald-400' : 'text-red-400'}`}>
                          {item.execution_result.message}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            )}

            {/* Typing indicator */}
            {busy && (
              <div className="flex gap-2.5">
                <div className="shrink-0 mt-1 h-7 w-7 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                  <Bot size={13} className="text-emerald-400 animate-pulse" />
                </div>
                <div className="rounded-2xl rounded-bl-sm bg-white/8 px-4 py-3 flex items-center gap-1">
                  {[0, 1, 2].map(j => (
                    <span
                      key={j}
                      className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce"
                      style={{ animationDelay: `${j * 150}ms` }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/20 text-xs text-red-300 shrink-0">
              {error}
            </div>
          )}

          {/* Confirm execution */}
          {lastAiItem?.execution_plan?.intention && !lastAiItem?.execution_result && (
            <div className="px-3 py-2 bg-amber-500/10 border-t border-amber-500/20 shrink-0">
              <button
                disabled={executing}
                onClick={() => void confirmExecution()}
                className="w-full rounded-xl bg-amber-500 hover:bg-amber-400 px-3 py-2 text-xs font-bold text-white disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                <ChevronDown size={13} className="rotate-[-90deg]" />
                {executing ? 'Exécution en cours…' : `Confirmer : ${lastAiItem.execution_plan.intention.replace(/_/g, ' ')}`}
              </button>
            </div>
          )}

          {/* Input */}
          <div className="flex gap-2 p-3 bg-[#0B1F4D] border-t border-white/10 shrink-0">
            <input
              ref={inputRef}
              value={transcript}
              onChange={e => setTranscript(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) void processCommand(); }}
              placeholder={recording ? 'Écoute en cours…' : 'Tapez ou dictez une commande…'}
              className="min-w-0 flex-1 rounded-xl bg-white/8 border border-white/15 px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-400/50 focus:bg-white/10 transition-colors"
            />
            <button
              onClick={recording ? () => { recognitionRef.current?.stop?.(); } : startListening}
              className={`rounded-xl px-3 transition-colors ${recording ? 'bg-red-500 hover:bg-red-400 animate-pulse' : 'bg-white/10 hover:bg-white/20'} text-white`}
              aria-label={recording ? 'Arrêter la dictée' : 'Dicter'}
            >
              <Mic size={16} />
            </button>
            <button
              disabled={busy || !transcript.trim()}
              onClick={() => void processCommand()}
              className="rounded-xl bg-emerald-500 hover:bg-emerald-400 px-3 text-white disabled:opacity-40 transition-colors"
              aria-label="Envoyer"
            >
              {busy ? <Volume2 size={16} className="animate-pulse" /> : <Send size={16} />}
            </button>
          </div>
        </div>
      )}
    </>
  );
};
