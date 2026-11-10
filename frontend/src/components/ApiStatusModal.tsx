import React, { useState } from 'react';
import { X, Server, RefreshCw, CheckCircle, AlertTriangle, UserCheck, Activity } from 'lucide-react';
import { ApiConfig } from '../types';
import { apiService, ApiError } from '../services/api';

interface ApiStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiConfig: ApiConfig;
}

export const ApiStatusModal: React.FC<ApiStatusModalProps> = ({
  isOpen,
  onClose,
  apiConfig
}) => {
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; json?: string } | null>(null);

  if (!isOpen) return null;

  const handleTestHealth = async () => {
    setIsTesting(true);
    setTestResult(null);
    const ok = await apiService.checkHealth();
    setTestResult(
      ok
        ? { success: true, message: `Le serveur ${apiConfig.baseUrl} répond (GET /health : 200 OK).` }
        : {
            success: false,
            message: `Impossible de joindre ${apiConfig.baseUrl}. Vérifiez que le backend est démarré et que VITE_API_URL est correct.`
          }
    );
    setIsTesting(false);
  };

  const handleTestSession = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const user = await apiService.fetchCurrentUser();
      setTestResult({
        success: true,
        message: 'Session valide (GET /api/v1/auth/me : 200 OK).',
        json: JSON.stringify(user, null, 2)
      });
    } catch (err) {
      setTestResult({
        success: false,
        message:
          err instanceof ApiError
            ? `Échec de la vérification de session (${err.status || 'réseau'}) : ${err.message}`
            : 'Échec de la vérification de session.'
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#0B1F4D]/10 flex items-center justify-center text-[#0B1F4D]">
              <Server size={20} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800">Connexion à l'API REST</h3>
              <p className="text-xs text-slate-500">
                Communication avec le backend de la plateforme FORMA-IA
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-5 space-y-5">
          {/* Status banner */}
          <div
            className={`p-3.5 rounded-xl border flex items-start gap-3 ${
              apiConfig.isConnected
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}
          >
            {apiConfig.isConnected ? (
              <CheckCircle className="text-emerald-600 shrink-0 mt-0.5" size={18} />
            ) : (
              <AlertTriangle className="text-amber-600 shrink-0 mt-0.5" size={18} />
            )}
            <div className="text-xs leading-relaxed">
              <span className="font-bold block mb-0.5">
                {apiConfig.isConnected ? 'Backend joignable' : 'Backend injoignable'}
              </span>
              {apiConfig.isConnected ? (
                <>Le frontend communique avec <code className="bg-emerald-100 px-1 py-0.5 rounded font-mono">{apiConfig.baseUrl}</code>.</>
              ) : (
                <>Le serveur <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">{apiConfig.baseUrl}</code> n'a pas répondu.</>
              )}
              {apiConfig.lastPingTime && (
                <span className="block mt-1 opacity-80">Dernière vérification : {apiConfig.lastPingTime}</span>
              )}
            </div>
          </div>

          {/* URL (lecture seule) */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              Adresse du backend
            </label>
            <input
              type="text"
              readOnly
              value={apiConfig.baseUrl}
              className="w-full px-3.5 py-2.5 bg-slate-100 border border-slate-300 rounded-lg text-sm font-mono text-slate-700 cursor-not-allowed"
            />
            <p className="text-[11px] text-slate-500 mt-1.5">
              Définie par la variable <code className="font-mono">VITE_API_URL</code> du fichier <code className="font-mono">.env</code>. Redémarrez le serveur de développement après toute modification.
            </p>
          </div>

          {/* Tests */}
          <div className="pt-3 border-t border-slate-100">
            <div className="flex flex-wrap gap-2 mb-3">
              <button
                onClick={handleTestHealth}
                disabled={isTesting}
                className="px-4 py-2 bg-[#0B1F4D] hover:bg-[#06132F] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs disabled:opacity-50"
              >
                {isTesting ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                <span>Tester la connexion</span>
              </button>
              <button
                onClick={handleTestSession}
                disabled={isTesting}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                <UserCheck size={14} />
                <span>Vérifier ma session</span>
              </button>
            </div>

            {testResult && (
              <div className="p-3 bg-slate-900 rounded-xl text-slate-200 font-mono text-xs overflow-x-auto space-y-2 border border-slate-800">
                <div className={`font-bold flex items-center gap-1.5 ${testResult.success ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {testResult.success ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                  <span>{testResult.message}</span>
                </div>
                {testResult.json && (
                  <pre className="text-[11px] text-slate-300 bg-slate-950 p-2.5 rounded-lg max-h-40 overflow-y-auto">
                    {testResult.json}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
