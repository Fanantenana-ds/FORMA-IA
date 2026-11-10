import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Bot,
  Play,
  RefreshCw,
  Loader2,
  Clock,
  Gauge,
  AlertTriangle,
  CheckCircle2,
  Info
} from 'lucide-react';
import { apiService } from '../../services/api';
import { describeVeilleError } from '../../services/veilleErrors';
import { formatRelative } from '../../services/dashboardMapping';
import { reportFrontendError } from '../../services/frontendErrorReporter';
import { consumeVoiceActionContext } from '../../services/voiceActionContext';
import type {
  DetectionStatus,
  DetectionResult,
  TavilyQuota
} from '../../services/veilleMapping';

interface DetectionAutoPanelProps {
  /** Seuls la Direction et les Assistants peuvent déclencher un passage. */
  canTrigger: boolean;
  /** Appelé après un passage réussi (résultats et option « enregistrer »). */
  onDetected: (result: DetectionResult, saved: boolean) => void | Promise<void>;
}

const RUN_STATUS_LABELS: Record<string, string> = {
  success: 'Réussie',
  partial: 'Partielle',
  degraded: 'Dégradée',
  quota_atteint: 'Quota atteint',
  error: 'Échec',
  no_results: 'Aucun résultat'
};

const TRIGGER_LABELS: Record<string, string> = {
  planifie: 'Planifiée',
  manuel: 'Manuelle'
};

const quotaBarColor = (percent: number): string =>
  percent >= 95 ? 'bg-red-500' : percent >= 80 ? 'bg-amber-500' : 'bg-[#0B1F4D]';

export const DetectionAutoPanel: React.FC<DetectionAutoPanelProps> = ({ canTrigger, onDetected }) => {
  const [status, setStatus] = useState<DetectionStatus | null>(null);
  const [quota, setQuota] = useState<TavilyQuota | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [autoSave, setAutoSave] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ tone: 'ok' | 'warn'; lines: string[] } | null>(null);
  const [progress, setProgress] = useState<Array<{ type: 'source' | 'result'; title: string; score?: number; url?: string; source?: string; deadline?: string; reference?: string; status?: string; capturedAt?: string }>>([]);
  const [streamStage, setStreamStage] = useState('Préparation');
  const voiceRunTriggered = useRef(false);

  const loadState = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    const [statusR, quotaR] = await Promise.allSettled([
      apiService.getDetectionStatus(),
      apiService.getTavilyQuota()
    ]);

    if (statusR.status === 'fulfilled') setStatus(statusR.value);
    if (quotaR.status === 'fulfilled') setQuota(quotaR.value);

    const firstError = [statusR, quotaR].find((r) => r.status === 'rejected') as
      | PromiseRejectedResult
      | undefined;
    setLoadError(firstError ? describeVeilleError(firstError.reason, 'detect') : null);
    if (!silent) setIsLoading(false);
  }, []);

  useEffect(() => {
    loadState();
  }, [loadState]);

  // Un passage déjà en cours (ex. planifié) : on suit son avancement
  const serverBusy = status?.en_cours === true;
  useEffect(() => {
    if (!serverBusy || isRunning) return;
    const timer = setInterval(() => loadState(true), 8000);
    return () => clearInterval(timer);
  }, [serverBusy, isRunning, loadState]);

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setSummary(null);
    setProgress([]);
    setStreamStage('Préparation');
    try {
      const result = await apiService.streamDetection((event, data) => {
        if (event === 'debut') setStreamStage('Recherche des sources');
        if (event === 'requete') {
          setStreamStage('Collecte des avis');
          setProgress((previous) => [...previous, { type: 'source', title: String(data.query ?? data.message ?? 'Source consultée') }].slice(-16));
        }
        if (event === 'analyse') setStreamStage('Analyse des avis');
        if (event === 'opportunite') {
          setStreamStage('Résultats disponibles');
          setProgress((previous) => [...previous, {
            type: 'result', title: String(data.titre ?? data.title ?? 'Avis sans titre'),
            score: typeof data.score === 'number' ? data.score : undefined,
            url: typeof data.source_url === 'string' && /^https:\/\//i.test(data.source_url) ? data.source_url : undefined,
            source: String(data.organizer ?? data.source_site ?? ''),
            deadline: typeof data.deadline === 'string' ? data.deadline : undefined,
            reference: typeof data.reference === 'string' ? data.reference : undefined,
            status: typeof data.current_status === 'string' ? data.current_status : undefined,
            capturedAt: typeof data.date_capture === 'string' ? data.date_capture : undefined,
          }].slice(-16));
        }
        if (event === 'fin') setStreamStage('Terminé');
      }, { syncBackend: autoSave });

      if (result.quotaReached) {
        setSummary({
          tone: 'warn',
          lines: [`Passage non lancé : quota de recherche atteint.${result.reason ? ` ${result.reason}` : ''}`]
        });
      } else {
        const stats = result.statistics;
        const sync = stats.backend_sync ?? {};
        const lines: string[] = result.demoMode ? [
          `${result.total} opportunité(s) à examiner. Sélectionnez celles qui correspondent à votre projet.`,
        ] : [
          `${result.total} opportunité(s) retenue(s) sur ${stats.queries_run ?? result.queries.length} requête(s)` +
            (stats.processing_time_seconds >= 1 ? ` en ${Math.round(stats.processing_time_seconds)} s.` : '.')
        ];
        let tone: 'ok' | 'warn' = 'ok';

        if (result.demoMode) {
          lines.push('Ces dossiers sont à vérifier avant toute acceptation.');
        } else if (autoSave) {
          if (sync.enabled === false) {
            tone = 'warn';
            lines.push(
              "L'enregistrement automatique est désactivé côté serveur (BACKEND_SYNC_ENABLED) : acceptez les marchés ci-dessous manuellement."
            );
          } else {
            lines.push(
              `${sync.sent ?? 0} enregistrée(s), ${sync.already_present ?? 0} déjà présente(s)` +
                ((sync.failed ?? 0) > 0 ? `, ${sync.failed} échec(s) d'enregistrement.` : '.')
            );
            if ((sync.failed ?? 0) > 0) tone = 'warn';
          }
        } else {
          lines.push('Aperçu : rien n\'a été enregistré. Acceptez les marchés de votre choix ci-dessous.');
        }

        const failedQueries = result.queries.filter((q) => q.status === 'error');
        if (failedQueries.length > 0) {
          tone = 'warn';
          lines.push(`${failedQueries.length} requête(s) en échec sur ${result.queries.length}.`);
        }
        if (result.status === 'degraded') {
          tone = 'warn';
          lines.push("L'analyse IA est momentanément indisponible : résultats limités.");
        }
        setSummary({ tone, lines });
        await onDetected(result, autoSave && !result.demoMode);
      }
    } catch (err) {
      reportFrontendError('component', { route: 'DetectionAutoPanel.handleRun', name: err instanceof Error ? err.name : 'UnknownError' });
      setRunError(describeVeilleError(err, 'detect'));
    } finally {
      setIsRunning(false);
      loadState(true);
    }
  };
  const handleRunRef = useRef(handleRun);
  handleRunRef.current = handleRun;

  useEffect(() => {
      const trigger = async () => {
      if (voiceRunTriggered.current) return;
      voiceRunTriggered.current = true;
      if (!canTrigger) {
        setRunError("Votre rôle ne permet pas de lancer la détection du marché.");
          voiceRunTriggered.current = false;
        return;
      }
        try { await handleRunRef.current(); }
        finally { voiceRunTriggered.current = false; }
    };
    const listener = (event: Event) => {
      const action = (event as CustomEvent<{ action?: string }>).detail?.action;
        if (action === 'lancer_veille') void trigger();
    };
    window.addEventListener('forma-ia:vocal-action', listener);
    const pending = consumeVoiceActionContext(['lancer_veille']);
      if (pending) void trigger();
    return () => window.removeEventListener('forma-ia:vocal-action', listener);
  }, [canTrigger]);

  const config = status?.configuration;
  const lastRun = status?.derniere_execution ?? null;
  const lastRunTime = lastRun?.derniere_execution ? new Date(lastRun.derniere_execution).getTime() : NaN;
  const quotaMax = quota?.configuration.quota_mensuel ?? 0;
  const busy = isRunning || serverBusy;

  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-5">
      {/* En-tête */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#0B1F4D]/10 text-[#0B1F4D] flex items-center justify-center shrink-0">
            <Bot size={20} />
          </div>
          <div>
            <h3 className="text-base font-extrabold text-[#11162A]">Détection automatique</h3>
            <p className="text-xs text-slate-600 mt-0.5 max-w-xl leading-relaxed">
              Le serveur lance lui-même des recherches prédéfinies (profil ALTIORA), fusionne les résultats, retire
              les doublons et peut enregistrer les nouvelles opportunités.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {config && (
            <span
              className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                config.planification_activee ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {config.planification_activee
                ? `Planification active · toutes les ${config.intervalle_heures} h`
                : 'Planification désactivée'}
            </span>
          )}
          {busy && (
            <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-100 text-amber-800 flex items-center gap-1">
              <Loader2 size={11} className="animate-spin" />
              Détection en cours
            </span>
          )}
          <button
            onClick={() => loadState()}
            disabled={isLoading}
            title="Actualiser l'état"
            className="p-2 text-slate-500 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all disabled:opacity-50"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {loadError && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>{loadError}</span>
        </div>
      )}

      {isLoading && !status && !loadError && (
        <div className="text-xs text-slate-500 flex items-center gap-2">
          <Loader2 size={14} className="animate-spin" />
          Chargement de l'état de la détection…
        </div>
      )}

      {config && (
        <>
          {/* Requêtes configurées */}
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase mb-1.5">
              Requêtes lancées à chaque passage ({config.requetes.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {config.requetes.map((q) => (
                <span key={q} className="px-2.5 py-1 bg-slate-100 text-slate-700 rounded-md text-[11px] font-medium">
                  {q}
                </span>
              ))}
              {config.requetes.length === 0 && (
                <span className="text-xs text-slate-500">Aucune requête configurée côté serveur.</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Critères retenus</div>
              <div className="text-sm font-extrabold text-[#11162A] mt-1">Score ≥ {config.score_minimum}</div>
              <div className="text-[11px] text-slate-500">{config.limite} opportunités au maximum</div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
              <div className="text-[10px] font-bold text-slate-400 uppercase flex items-center gap-1">
                <Clock size={11} /> Dernier passage
              </div>
              {lastRun && !Number.isNaN(lastRunTime) ? (
                <>
                  <div className="text-sm font-extrabold text-[#11162A] mt-1">{formatRelative(lastRunTime)}</div>
                  <div className="text-[11px] text-slate-500">
                    {TRIGGER_LABELS[lastRun.declenchement ?? ''] ?? lastRun.declenchement ?? '—'} ·{' '}
                    {RUN_STATUS_LABELS[lastRun.statut ?? ''] ?? lastRun.statut ?? '—'}
                  </div>
                </>
              ) : (
                <div className="text-sm font-bold text-slate-500 mt-1">Aucun passage enregistré</div>
              )}
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
              <div className="text-[10px] font-bold text-slate-400 uppercase flex items-center gap-1">
                <Gauge size={11} /> Quota de recherche web
              </div>
              {quota ? (
                <>
                  <div className="text-sm font-extrabold text-[#11162A] mt-1">
                    {quota.total_appels} / {quotaMax} appels ({quota.pourcentage_utilise}%)
                  </div>
                  <div className="w-full bg-slate-200 h-1.5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${quotaBarColor(quota.pourcentage_utilise)}`}
                      style={{ width: `${Math.min(100, quota.pourcentage_utilise)}%` }}
                    ></div>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    Passages automatiques aujourd'hui : {quota.runs_auto_aujourd_hui} /{' '}
                    {quota.configuration.max_runs_par_jour}
                  </div>
                </>
              ) : (
                <div className="text-sm font-bold text-slate-500 mt-1">—</div>
              )}
            </div>
          </div>

          {quota?.avertissement && (
            <div
              className={`p-3 rounded-xl border text-xs font-semibold flex items-start gap-2 ${
                quota.avertissement === 'critique'
                  ? 'bg-red-50 border-red-200 text-red-700'
                  : 'bg-amber-50 border-amber-200 text-amber-800'
              }`}
            >
              <AlertTriangle size={14} className="shrink-0 mt-0.5" />
              <span>
                {quota.avertissement === 'critique'
                  ? 'Quota critique : les recherches seront bientôt bloquées jusqu\'à la prochaine période.'
                  : 'Quota élevé : réservez les recherches aux besoins importants.'}
              </span>
            </div>
          )}

          {/* Dernier passage : détail */}
          {lastRun && (lastRun.total !== undefined || lastRun.erreur) && (
            <div className="text-[11px] text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-200/80">
              {lastRun.total !== undefined && (
                <span>
                  Dernier résultat : {lastRun.total} opportunité(s)
                  {lastRun.envoyees !== undefined && ` · ${lastRun.envoyees} enregistrée(s)`}
                  {lastRun.deja_presentes !== undefined && ` · ${lastRun.deja_presentes} déjà présente(s)`}
                  {(lastRun.echecs_envoi ?? 0) > 0 && ` · ${lastRun.echecs_envoi} échec(s) d'enregistrement`}
                </span>
              )}
              {lastRun.erreur && (
                <span className="block text-amber-700 font-semibold mt-0.5">Motif : {lastRun.erreur}</span>
              )}
            </div>
          )}

          {/* Commandes */}
          {canTrigger ? (
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-4 border-t border-slate-100">
              <label className="flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer max-w-xl">
                <input
                  type="checkbox"
                  checked={autoSave}
                  onChange={(e) => setAutoSave(e.target.checked)}
                  disabled={busy}
                  className="mt-0.5 accent-[#0B1F4D]"
                />
                <span>
                  <span className="font-bold">Enregistrer automatiquement les nouvelles opportunités</span>
                  <span className="block text-slate-500">
                    Décochez pour un simple aperçu : rien n'est écrit dans la base, vous choisissez ensuite les
                    marchés à accepter.
                  </span>
                </span>
              </label>

              <button
                onClick={handleRun}
                disabled={busy || config.requetes.length === 0}
                className="px-5 py-2.5 bg-[#0B1F4D] hover:bg-[#06132F] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
              >
                {isRunning ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                <span>{isRunning ? 'Détection en cours…' : 'Lancer la détection maintenant'}</span>
              </button>
            </div>
          ) : (
            <div className="text-[11px] text-slate-500 flex items-center gap-1.5 pt-3 border-t border-slate-100">
              <Info size={13} />
              Le déclenchement manuel est réservé à la Direction et aux Assistants.
            </div>
          )}
        </>
      )}

      {(isRunning || progress.length > 0) && (
        <div aria-live="polite" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Suivi de la détection</p>
              <p className="text-sm font-bold text-[#11162A] mt-1">{streamStage}</p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-800">
              {progress.filter(item => item.type === 'result').length} avis repéré(s)
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full bg-[#0B1F4D] transition-all duration-500 ${isRunning ? 'w-2/3 animate-pulse' : 'w-full'}`} />
          </div>
          <div className="max-h-72 space-y-2 overflow-y-auto">
            {progress.filter(item => item.type === 'result').map((item, index) => (
              <div key={`${item.title}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-bold leading-5 text-[#11162A]">{item.title}</p>
                    {item.source && <p className="mt-0.5 text-[11px] text-slate-500">{item.source}</p>}
                    {(item.reference || item.deadline || item.capturedAt) && <p className="mt-1 text-[11px] text-slate-500">{item.reference ? `Réf. ${item.reference}` : ''}{item.reference && (item.deadline || item.capturedAt) ? ' · ' : ''}{item.deadline ? `Échéance ${item.deadline}` : ''}{item.deadline && item.capturedAt ? ' · ' : ''}{item.capturedAt ? `Capturé le ${item.capturedAt}` : ''}</p>}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">{item.score !== undefined && <span className="rounded-lg bg-white px-2 py-1 text-[11px] font-bold text-emerald-800">{item.score}/100</span>}{item.status && <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${item.status === 'ouverte' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}`}>{item.status}</span>}</div>
                </div>
                {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-[11px] font-semibold text-[#06132F] underline">Voir l’avis original ↗</a>
                  : <span className="mt-2 block text-[11px] text-amber-700">Aucun lien public fourni</span>}
              </div>
            ))}
            {progress.filter(item => item.type === 'result').length === 0 && (
              <p className="text-xs text-slate-500">{progress.length ? `${progress.filter(item => item.type === 'source').length} source(s) parcourue(s). Les avis arrivent…` : 'Connexion au flux en cours…'}</p>
            )}
          </div>
        </div>
      )}

      {runError && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>{runError}</span>
        </div>
      )}

      {summary && (
        <div
          className={`p-3 rounded-xl border text-xs font-semibold space-y-0.5 ${
            summary.tone === 'ok'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-amber-50 border-amber-200 text-amber-800'
          }`}
        >
          {summary.lines.map((line, idx) => (
            <div key={idx} className="flex items-start gap-2">
              {idx === 0 && (
                <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
              )}
              <span className={idx === 0 ? '' : 'pl-[22px]'}>{line}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
