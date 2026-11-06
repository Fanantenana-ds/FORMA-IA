import React from 'react';

interface FinalCtaSectionProps {
  onOpenDemo: () => void;
  onLogin: () => void;
}

export const FinalCtaSection: React.FC<FinalCtaSectionProps> = ({ onOpenDemo, onLogin }) => (
  <section id="contact" className="relative py-20 bg-linear-to-r from-brand-navy via-[#0C245C] to-brand-darkNavy text-white overflow-hidden">
    <div className="absolute -right-20 -bottom-20 w-96 h-96 bg-brand-gold/20 rounded-full blur-3xl pointer-events-none" />
    <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8">
      <span className="inline-block px-4 py-1.5 rounded-full bg-brand-gold/15 border border-brand-gold/30 text-brand-gold font-bold text-xs uppercase tracking-wider">
        FORMA-IA · ALTIORA PREST
      </span>
      <h2 className="text-3xl sm:text-5xl font-black tracking-tight leading-tight">Une plateforme pour piloter le cycle de formation</h2>
      <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto font-normal">
        De la veille marché au suivi des sessions, FORMA-IA rassemble les outils nécessaires à la préparation et à la gestion des formations.
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
        <button
          type="button"
          onClick={onOpenDemo}
          className="w-full sm:w-auto px-8 py-4 rounded-xl font-extrabold text-brand-darkNavy bg-linear-to-r from-brand-gold to-brand-goldDark shadow-xl shadow-brand-gold/30 hover:brightness-110 transform hover:-translate-y-1 transition duration-200"
        >
          Demander une démonstration
        </button>
        <button
          type="button"
          onClick={onLogin}
          className="w-full sm:w-auto px-8 py-4 rounded-xl font-semibold text-white border border-white/20 bg-white/5 hover:bg-white/10 transition duration-200"
        >
          Accéder à l'espace membre
        </button>
      </div>
      <p className="text-xs text-slate-400">Assistance IA, sources consultables et validation humaine intégrée au parcours.</p>
    </div>
  </section>
);
