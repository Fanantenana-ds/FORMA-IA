import React, { useState } from 'react';
import { X, Server, RefreshCw, CheckCircle, AlertTriangle, Send, Copy, Code } from 'lucide-react';
import { ApiConfig } from '../types';
import { apiService } from '../services/api';

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
  const [urlInput, setUrlInput] = useState(apiConfig.baseUrl);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; json?: string } | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState('/api/dashboard/kpis');

  if (!isOpen) return null;

  const handleSaveAndTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    apiService.setBaseUrl(urlInput);

    try {
      const isOk = await apiService.checkHealth();
      if (isOk) {
        setTestResult({
          success: true,
          message: `Connexion réussie avec ${urlInput} ! Statut HTTP 200 OK.`
        });
      } else {
        setTestResult({
          success: false,
          message: `Impossible de joindre le serveur REST à ${urlInput}. Assurez-vous que votre serveur backend (e.g. FastAPI, Express, Django) tourne sur le port 8000.`
        });
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        message: `Erreur réseau : ${err.message || 'Serveur indisponible'}`
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleTestEndpoint = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const res = await fetch(`${urlInput}${selectedEndpoint}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      setTestResult({
        success: res.ok,
        message: `Réponse HTTP ${res.status} de ${selectedEndpoint}`,
        json: JSON.stringify(data, null, 2)
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: `Erreur lors de la requête vers ${urlInput}${selectedEndpoint} : ${err.message}. Passage automatique sur le jeu de données local.`,
        json: JSON.stringify({ note: "Backend 127.0.0.1:8000 hors ligne dans cette démonstration.", fallback: "Données mock chargées" }, null, 2)
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
            <div className="w-9 h-9 rounded-xl bg-[#1B8F6E]/10 flex items-center justify-center text-[#1B8F6E]">
              <Server size={20} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800">
                Configuration API REST (127.0.0.1:8000)
              </h3>
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
                {apiConfig.isConnected
                  ? 'Connecté au serveur REST local'
                  : 'Mode Simulation / Standalone (Local REST)'}
              </span>
              {apiConfig.isConnected ? (
                <>Le frontend FORMA-IA reçoit et envoie en temps réel des requêtes à <code className="bg-emerald-100 px-1 py-0.5 rounded font-mono">{apiConfig.baseUrl}</code>.</>
              ) : (
                <>Le serveur REST à l'adresse <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">{apiConfig.baseUrl}</code> n'a pas répondu. L'interface utilise les données de démonstration interactives.</>
              )}
            </div>
          </div>

          {/* URL Input */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5">
              Adresse URL de l'API REST Backend
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="http://127.0.0.1:8000"
                className="flex-1 px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-sm font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] focus:bg-white"
              />
              <button
                onClick={handleSaveAndTest}
                disabled={isTesting}
                className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs disabled:opacity-50"
              >
                {isTesting ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />}
                <span>Tester & Enregistrer</span>
              </button>
            </div>
          </div>

          {/* Endpoint Live Tester */}
          <div className="pt-3 border-t border-slate-100">
            <label className="block text-xs font-bold text-slate-700 uppercase mb-1.5 flex items-center gap-1">
              <Code size={14} className="text-[#1B8F6E]" />
              Tester un Endpoint spécifique
            </label>
            <div className="flex gap-2 mb-3">
              <select
                value={selectedEndpoint}
                onChange={(e) => setSelectedEndpoint(e.target.value)}
                className="flex-1 px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-xs font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
              >
                <option value="/api/dashboard/kpis">GET /api/dashboard/kpis</option>
                <option value="/api/dashboard/opportunities-by-domain">GET /api/dashboard/opportunities-by-domain</option>
                <option value="/api/dashboard/invoicing-status">GET /api/dashboard/invoicing-status</option>
                <option value="/api/dashboard/recent-activities">GET /api/dashboard/recent-activities</option>
                <option value="/api/sessions">GET /api/sessions</option>
                <option value="/api/opportunities">GET /api/opportunities</option>
                <option value="/api/trainers">GET /api/trainers</option>
                <option value="/api/invoices">GET /api/invoices</option>
              </select>
              <button
                onClick={handleTestEndpoint}
                disabled={isTesting}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1"
              >
                Exécuter
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
