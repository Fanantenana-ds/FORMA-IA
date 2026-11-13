import React from 'react';
import { ArrowLeft, Cpu, Settings2 } from 'lucide-react';
import { LLMConfigPanel } from './LLMConfigPanel';
import type { AuthUser } from '../../types';

interface ParametresViewProps {
  authUser: AuthUser;
  onBack: () => void;
}

export const ParametresView: React.FC<ParametresViewProps> = ({ authUser, onBack }) => {
  const isAdmin = authUser.role === 'Dir.';

  return (
    <div className="w-full space-y-6 animate-in fade-in duration-300">

      {/* ── En-tête style pipeline (navy gradient) ── */}
      <div className="w-full overflow-hidden rounded-2xl shadow-lg">
        <div
          className="relative px-6 py-6 text-white"
          style={{ background: 'linear-gradient(135deg, #06132F 0%, #0B1F4D 60%, #0d2460 100%)' }}
        >
          {/* Cercles décoratifs */}
          <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full border border-brand-gold/20" />
          <div className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 rounded-full border border-brand-gold/15" />

          <div className="relative flex items-start justify-between gap-4">
            {/* Icône + titre */}
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-brand-gold/30 bg-brand-gold/15 text-brand-gold">
                <Settings2 size={22} />
              </div>
              <div>
                {/* Badge étape */}
                <div className="mb-1.5 inline-flex items-center rounded-full border border-white/20 bg-white/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white/80">
                  Configuration
                </div>
                <h1 className="text-2xl font-extrabold leading-tight text-white">
                  Paramètres
                </h1>
                <p className="mt-1 text-sm text-white/60">
                  Configuration de la plateforme FORMA-IA
                </p>
              </div>
            </div>

            {/* Bouton Retour — à droite */}
            <button
              type="button"
              onClick={onBack}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-white hover:bg-white/20 transition-colors"
            >
              <ArrowLeft size={14} />
              Retour
            </button>
          </div>
        </div>
      </div>

      {/* ── Config LLM — plein écran ── */}
      {isAdmin ? (
        <div className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
          <div className="flex items-center gap-3 border-b border-slate-100 bg-slate-50/60 px-6 py-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-orange-50 border border-orange-100">
              <Cpu size={16} className="text-orange-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Configuration LLM</h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Modifiez le fournisseur IA, le modèle et les clés API sans redémarrage. La configuration est appliquée immédiatement.
              </p>
            </div>
          </div>
          <div className="p-6">
            <LLMConfigPanel />
          </div>
        </div>
      ) : (
        <div className="w-full rounded-2xl border border-slate-100 bg-slate-50 p-12 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-200">
            <Settings2 size={24} className="text-slate-400" />
          </div>
          <p className="text-sm font-bold text-slate-600">Accès réservé à la Direction</p>
          <p className="mt-1 text-xs text-slate-400">Les paramètres avancés sont gérés par le compte Direction.</p>
        </div>
      )}
    </div>
  );
};

export default ParametresView;
