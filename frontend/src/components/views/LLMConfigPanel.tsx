import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle, Check, ChevronDown, Eye, EyeOff,
  Loader2, RefreshCw, Save, Zap,
} from 'lucide-react';
import { apiService } from '../../services/api';

// ── Types ─────────────────────────────────────────────────────────────────

interface LLMModel {
  id: string;
  label: string;
  gratuit: boolean;
  recommande: boolean;
}

interface LLMConfig {
  provider: string;
  model: string;
  cle_groq_definie: boolean;
  cle_anthropic_definie: boolean;
  cle_openai_definie: boolean;
  source: 'fichier' | 'env';
}

interface ModelesCatalogue {
  providers: string[];
  models: Record<string, LLMModel[]>;
}

const PROVIDER_LABELS: Record<string, string> = {
  groq: 'Groq',
  anthropic: 'Anthropic (Claude)',
  openai: 'OpenAI (GPT)',
};

const PROVIDER_COLORS: Record<string, string> = {
  groq: 'text-orange-600 bg-orange-50 border-orange-200',
  anthropic: 'text-purple-700 bg-purple-50 border-purple-200',
  openai: 'text-green-700 bg-green-50 border-green-200',
};

const PROVIDER_SITE: Record<string, string> = {
  groq: 'https://console.groq.com/keys',
  anthropic: 'https://console.anthropic.com/settings/keys',
  openai: 'https://platform.openai.com/api-keys',
};

const iap = 'rounded-xl border border-slate-200 bg-white p-5 shadow-xs';
const btn = (variant: 'primary' | 'ghost' | 'danger' = 'primary') =>
  variant === 'primary'
    ? 'inline-flex items-center gap-2 rounded-lg bg-[#0B1F4D] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a3370] disabled:opacity-50 transition-colors'
    : variant === 'ghost'
    ? 'inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors'
    : 'inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors';

// ── Composant principal ───────────────────────────────────────────────────

export const LLMConfigPanel: React.FC = () => {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [catalogue, setCatalogue] = useState<ModelesCatalogue | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  // Formulaire
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [cleApi, setCleApi] = useState('');
  const [showKey, setShowKey] = useState(false);

  // Feedback
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const chargerConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, cat] = await Promise.all([
        apiService.getLLMConfig(),
        apiService.getAllLLMModels(),
      ]);
      const c = cfg.data ?? cfg;
      const m = cat.data ?? cat;
      setConfig(c);
      setCatalogue(m);
      setProvider(c.provider ?? 'groq');
      // Choisir le modèle par défaut du provider
      const modeles: LLMModel[] = m.models?.[c.provider] ?? [];
      const actif = modeles.find((x: LLMModel) => x.id === c.model) ?? modeles.find((x: LLMModel) => x.recommande) ?? modeles[0];
      setModel(c.model ?? actif?.id ?? '');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de charger la configuration.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { chargerConfig(); }, [chargerConfig]);

  // Quand on change de provider → pré-sélectionner le modèle recommandé
  const handleProviderChange = (p: string) => {
    setProvider(p);
    setCleApi('');
    setTestResult(null);
    const modeles: LLMModel[] = catalogue?.models?.[p] ?? [];
    const def = modeles.find(m => m.recommande) ?? modeles[0];
    setModel(def?.id ?? '');
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const body: Record<string, string> = { provider, model };
      if (cleApi.trim()) body.cle_api = cleApi.trim();
      await apiService.setLLMConfig(body);
      setSaved(true);
      setCleApi('');
      await chargerConfig();
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la sauvegarde.');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!cleApi.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiService.testLLMConnection({ provider, cle_api: cleApi.trim(), model });
      const r = result.data ?? result;
      setTestResult({ ok: r.ok ?? false, message: r.message ?? '' });
    } catch (e) {
      setTestResult({ ok: false, message: e instanceof Error ? e.message : 'Erreur réseau.' });
    } finally {
      setTesting(false);
    }
  };

  const modelesDuProvider: LLMModel[] = catalogue?.models?.[provider] ?? [];

  const cleDefinie = () => {
    if (provider === 'groq') return config?.cle_groq_definie;
    if (provider === 'anthropic') return config?.cle_anthropic_definie;
    if (provider === 'openai') return config?.cle_openai_definie;
    return false;
  };

  if (loading) {
    return (
      <div className={`${iap} flex items-center justify-center py-16`}>
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* En-tête */}
      <div className={iap}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-800">Configuration LLM</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Modifiez le fournisseur IA et les clés API sans redémarrage.
              La configuration est appliquée immédiatement.
            </p>
          </div>
          <button onClick={chargerConfig} className={btn('ghost')} title="Rafraîchir">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {/* Config active */}
        {config && (
          <div className="mt-4 flex flex-wrap gap-3">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${PROVIDER_COLORS[config.provider] ?? 'bg-slate-100 text-slate-700 border-slate-200'}`}>
              <Zap className="h-3 w-3" />
              {PROVIDER_LABELS[config.provider] ?? config.provider}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
              {config.model}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${config.source === 'fichier' ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
              {config.source === 'fichier' ? 'Config personnalisée' : 'Config .env'}
            </span>
          </div>
        )}
      </div>

      {/* Formulaire */}
      <div className={iap}>
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Modifier la configuration</h3>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Provider */}
        <div className="mb-4">
          <label className="mb-1.5 block text-xs font-medium text-slate-600">Fournisseur LLM</label>
          <div className="flex flex-wrap gap-2">
            {(catalogue?.providers ?? ['groq', 'anthropic', 'openai']).map(p => (
              <button
                key={p}
                onClick={() => handleProviderChange(p)}
                className={`rounded-lg border px-4 py-2 text-xs font-medium transition-colors ${
                  provider === p
                    ? 'border-[#0B1F4D] bg-[#0B1F4D] text-white'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                {PROVIDER_LABELS[p] ?? p}
              </button>
            ))}
          </div>
          {PROVIDER_SITE[provider] && (
            <p className="mt-1.5 text-[11px] text-slate-400">
              Obtenez votre clé sur{' '}
              <a
                href={PROVIDER_SITE[provider]}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#0B1F4D] underline hover:no-underline"
              >
                {PROVIDER_SITE[provider].replace('https://', '')}
              </a>
            </p>
          )}
        </div>

        {/* Modèle */}
        <div className="mb-4">
          <label className="mb-1.5 block text-xs font-medium text-slate-600">Modèle</label>
          {modelesDuProvider.length === 0 ? (
            <p className="text-xs text-slate-400">Chargement des modèles…</p>
          ) : (
            <div className="relative">
              <select
                value={model}
                onChange={e => setModel(e.target.value)}
                className="w-full appearance-none rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-9 text-sm text-slate-800 focus:border-[#0B1F4D] focus:outline-none focus:ring-1 focus:ring-[#0B1F4D]"
              >
                {modelesDuProvider.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                    {m.recommande ? ' ★' : ''}
                    {m.gratuit ? ' — Gratuit' : ''}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
            </div>
          )}

          {/* Badges modèle sélectionné */}
          {model && modelesDuProvider.length > 0 && (() => {
            const m = modelesDuProvider.find(x => x.id === model);
            return m ? (
              <div className="mt-2 flex gap-2">
                {m.gratuit && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">Gratuit</span>}
                {m.recommande && <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 border border-blue-200">Recommandé</span>}
                {!m.gratuit && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 border border-amber-200">Payant</span>}
              </div>
            ) : null;
          })()}
        </div>

        {/* Clé API */}
        <div className="mb-5">
          <label className="mb-1.5 block text-xs font-medium text-slate-600">
            Clé API{' '}
            <span className="font-normal text-slate-400">
              {cleDefinie() ? '(déjà définie — laissez vide pour conserver)' : '(requise)'}
            </span>
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showKey ? 'text' : 'password'}
                value={cleApi}
                onChange={e => { setCleApi(e.target.value); setTestResult(null); }}
                placeholder={cleDefinie() ? '••••••••••••••••••••' : `Collez votre clé ${PROVIDER_LABELS[provider] ?? provider}…`}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-3 pr-10 text-sm font-mono focus:border-[#0B1F4D] focus:outline-none focus:ring-1 focus:ring-[#0B1F4D]"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowKey(v => !v)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <button
              onClick={handleTest}
              disabled={!cleApi.trim() || testing}
              className={btn('ghost')}
              title="Tester la connexion sans sauvegarder"
            >
              {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
              Tester
            </button>
          </div>

          {/* Résultat du test */}
          {testResult && (
            <div className={`mt-2 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
              testResult.ok
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-red-200 bg-red-50 text-red-700'
            }`}>
              {testResult.ok
                ? <Check className="h-3.5 w-3.5 shrink-0" />
                : <AlertCircle className="h-3.5 w-3.5 shrink-0" />}
              {testResult.message}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <p className="text-[11px] text-slate-400">
            La clé est chiffrée avant d'être stockée. Elle n'est jamais retournée par l'API.
          </p>
          <button onClick={handleSave} disabled={saving} className={btn('primary')}>
            {saving
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : saved
              ? <Check className="h-4 w-4" />
              : <Save className="h-4 w-4" />}
            {saved ? 'Appliqué !' : 'Enregistrer et appliquer'}
          </button>
        </div>
      </div>

      {/* Tableau des clés définies */}
      {config && (
        <div className={iap}>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">État des clés API</h3>
          <div className="space-y-2">
            {[
              { key: 'groq', label: 'Groq', definie: config.cle_groq_definie },
              { key: 'anthropic', label: 'Anthropic (Claude)', definie: config.cle_anthropic_definie },
              { key: 'openai', label: 'OpenAI (GPT)', definie: config.cle_openai_definie },
            ].map(({ key, label, definie }) => (
              <div key={key} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${definie ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                  <span className="text-xs text-slate-700">{label}</span>
                  {config.provider === key && (
                    <span className="rounded-full bg-[#0B1F4D] px-2 py-0.5 text-[10px] font-semibold text-white">Actif</span>
                  )}
                </div>
                <span className={`text-xs font-medium ${definie ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {definie ? 'Clé définie' : 'Non configurée'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LLMConfigPanel;
