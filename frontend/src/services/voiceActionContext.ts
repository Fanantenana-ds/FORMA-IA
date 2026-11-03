export type VoiceActionContext = {
  action: string;
  prefill: Record<string, unknown>;
  requestedAt?: number;
};

const STORAGE_KEY = 'forma_ia_voice_action_context';

export const saveVoiceActionContext = (context: VoiceActionContext) => {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...context, requestedAt: Date.now() })); } catch { /* stockage local facultatif */ }
};

export const consumeVoiceActionContext = (allowedActions: string[]): VoiceActionContext | null => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const context = JSON.parse(raw) as VoiceActionContext;
    if (!context || (context.requestedAt && Date.now() - context.requestedAt > 120_000)) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    if (!allowedActions.includes(context.action)) return null;
    sessionStorage.removeItem(STORAGE_KEY);
    return context;
  } catch {
    return null;
  }
};

export const listenForVoiceAction = (
  allowedActions: string[],
  handler: (context: VoiceActionContext) => void,
) => {
  const listener = (event: Event) => {
    const context = (event as CustomEvent<VoiceActionContext>).detail;
    if (context && allowedActions.includes(context.action)) handler(context);
  };
  window.addEventListener('forma-ia:vocal-action', listener);
  const pending = consumeVoiceActionContext(allowedActions);
  if (pending) handler(pending);
  return () => window.removeEventListener('forma-ia:vocal-action', listener);
};
