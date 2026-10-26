import React from 'react';
import { ParticlesCanvas } from './ParticlesCanvas';
import { LANDING_IMAGES } from './landingImages';


const TRUST_PILLS = ['Détection d\'opportunités IA', 'Génération documentaire assistée', 'Base de connaissances RAG'];

const CheckIcon = () => (
  <svg className="w-4 h-4 mr-1.5 text-brand-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
  </svg>
);

export const HeroSection: React.FC = () => (
  <section
    id="hero"
    className="relative min-h-screen pt-28 pb-20 md:pt-36 md:pb-28 bg-linear-to-br from-brand-navy via-[#0A183D] to-brand-darkNavy flex items-center overflow-hidden"
  >
    <ParticlesCanvas />
    <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-gold/15 rounded-full blur-3xl pointer-events-none" />
    <div className="absolute bottom-10 right-1/4 w-[500px] h-[500px] bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />

    <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
        {/* Left column */}
        <div className="lg:col-span-7 text-left space-y-6">
          <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-brand-gold/10 border border-brand-gold/30 backdrop-blur-md shadow-inner">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-gold animate-ping" />
            <span className="text-xs uppercase tracking-widest font-bold text-brand-gold">✨ Propulsé par l'IA &amp; RAG Vectoriel</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white leading-tight tracking-tight">
            L'<span className="text-gold-gradient">intelligence artificielle</span> au service de votre formation
          </h1>

          <p className="text-base sm:text-lg text-slate-300 max-w-2xl font-normal leading-relaxed">
            FORMA-IA automatise la veille marché, la génération de documents, la préparation de sessions et la capitalisation documentaire — pour que vous vous concentriez sur l'essentiel : <span className="text-white font-semibold">former</span>.
          </p>

          <div className="flex flex-wrap gap-2.5 pt-2">
            {TRUST_PILLS.map((t) => (
              <span key={t} className="inline-flex items-center text-xs font-semibold px-3 py-1.5 rounded-md bg-white/5 border border-white/10 text-slate-200">
                <CheckIcon />
                {t}
              </span>
            ))}
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-4">
            <a
              href="#modules"
              className="inline-flex justify-center items-center px-7 py-3.5 rounded-xl font-bold text-brand-darkNavy bg-linear-to-r from-brand-gold via-amber-400 to-brand-goldDark shadow-xl shadow-brand-gold/25 hover:shadow-brand-gold/40 transform hover:-translate-y-0.5 transition duration-200 text-base"
            >
              Découvrir la plateforme
              <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M14 5l7 7m0 0l-7 7m7-7H3" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            </a>
            <a
              href="#how-it-works"
              className="inline-flex justify-center items-center px-7 py-3.5 rounded-xl font-semibold text-white border border-white/20 bg-white/5 backdrop-blur hover:bg-white/10 hover:border-brand-gold/50 transition duration-200 text-base group"
            >
              <svg className="w-5 h-5 mr-2 text-brand-gold group-hover:scale-110 transition-transform" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              Voir la démo
            </a>
          </div>

          <div className="pt-6 border-t border-white/10 flex items-center space-x-3 text-xs text-slate-400">
            <div className="flex -space-x-2">
              <span className="w-7 h-7 rounded-full bg-brand-gold text-brand-darkNavy font-black flex items-center justify-center text-[10px] ring-2 ring-brand-navy">AP</span>
              <span className="w-7 h-7 rounded-full bg-slate-700 text-white font-bold flex items-center justify-center text-[10px] ring-2 ring-brand-navy">ENI</span>
              <span className="w-7 h-7 rounded-full bg-sky-600 text-white font-bold flex items-center justify-center text-[10px] ring-2 ring-brand-navy">IA</span>
            </div>
            <p>
              Déjà utilisé par l'équipe <strong className="text-white font-medium">ALTIORA PREST</strong> et ses partenaires à Madagascar.
            </p>
          </div>
        </div>

        {/* Right column */}
        <div className="lg:col-span-5 relative flex items-center justify-center min-h-[460px]">
          <div className="absolute -inset-4 rounded-3xl border border-dashed border-brand-gold/30 animate-spin-slow pointer-events-none" />
          <div className="absolute -inset-1 rounded-3xl border border-brand-gold/20 animate-pulse-glow pointer-events-none" />

          <div className="relative w-full max-w-[420px] aspect-[4/5] rounded-2xl overflow-hidden border border-brand-gold/30 shadow-2xl shadow-brand-navy/60 group">
            <img
              alt={LANDING_IMAGES.hero.alt}
              className="w-full h-full object-cover object-center transform group-hover:scale-105 transition-transform duration-700 ease-out"
              src={LANDING_IMAGES.hero.src}
            />
            <div className="absolute inset-0 bg-linear-to-t from-brand-darkNavy/80 via-brand-darkNavy/20 to-transparent pointer-events-none" />
            <div
              className="absolute inset-0 pointer-events-none opacity-15"
              style={{
                backgroundSize: '24px 24px',
                backgroundImage: 'linear-gradient(to right, #D4AF37 1px, transparent 1px), linear-gradient(to bottom, #D4AF37 1px, transparent 1px)',
              }}
            />
            <div className="absolute top-1/3 left-1/4 w-2 h-2 rounded-full bg-brand-gold shadow-[0_0_12px_#D4AF37] animate-ping pointer-events-none opacity-60" />
            <div className="absolute top-1/2 right-1/4 w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_12px_#38BDF8] animate-pulse pointer-events-none opacity-70" />

            <div className="absolute bottom-4 left-4 right-4 p-3 rounded-xl bg-brand-darkNavy/85 backdrop-blur-md border border-brand-gold/30 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold text-white">Directrice Pédagogique &amp; Formation</p>
                <p className="text-[10px] text-brand-gold font-mono tracking-wider">FORMA-IA Copilote Actif</p>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-gold/20 text-brand-gold border border-brand-gold/40">
                En ligne
              </span>
            </div>
          </div>

          {/* Floating cards */}
          <div className="absolute -top-4 -right-2 sm:-right-4 p-3 bg-brand-darkNavy/95 backdrop-blur-md rounded-xl border border-brand-gold/40 shadow-xl animate-float-slow max-w-[220px] z-20">
            <div className="flex items-center space-x-2.5">
              <span className="text-lg">🎯</span>
              <div>
                <p className="text-[10px] font-bold text-brand-gold uppercase tracking-wider">Opportunité détectée</p>
                <p className="text-xs font-semibold text-white">92% pertinence</p>
              </div>
            </div>
          </div>

          <div className="absolute top-8 -left-4 sm:-left-6 p-3 bg-brand-darkNavy/95 backdrop-blur-md rounded-xl border border-brand-gold/30 shadow-xl animate-float-med max-w-[200px] z-20" style={{ animationDelay: '1s' }}>
            <div className="flex items-center space-x-2.5">
              <span className="text-lg">📄</span>
              <div>
                <p className="text-[10px] font-bold text-sky-400 uppercase tracking-wider">TDR Généré</p>
                <p className="text-xs font-semibold text-white">Prêt en 45s (HITL)</p>
              </div>
            </div>
          </div>

          <div className="absolute bottom-16 -right-3 sm:-right-5 p-3 bg-brand-darkNavy/95 backdrop-blur-md rounded-xl border border-brand-gold/40 shadow-xl animate-float-slow max-w-[230px] z-20" style={{ animationDelay: '2s' }}>
            <div className="flex items-center space-x-2.5">
              <span className="text-lg">💰</span>
              <div>
                <p className="text-[10px] font-bold text-brand-gold uppercase tracking-wider">Budget Calculé</p>
                <p className="text-xs font-bold text-white">2 450 000 Ar (TTC)</p>
              </div>
            </div>
          </div>

          <div className="absolute bottom-6 -left-4 sm:-left-6 p-3 bg-brand-darkNavy/95 backdrop-blur-md rounded-xl border border-brand-gold/30 shadow-xl animate-float-med max-w-[210px] z-20" style={{ animationDelay: '1.5s' }}>
            <div className="flex items-center space-x-2.5">
              <span className="text-lg">🔍</span>
              <div>
                <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Recherche RAG</p>
                <p className="text-xs font-semibold text-white">5 sources trouvées</p>
              </div>
            </div>
          </div>

          <div className="absolute top-1/2 -right-6 sm:-right-8 -translate-y-1/2 p-2.5 bg-brand-darkNavy/95 backdrop-blur-md rounded-xl border border-brand-gold/40 shadow-xl animate-float-slow hidden sm:flex items-center space-x-2 z-20" style={{ animationDelay: '2.8s' }}>
            <span className="text-base">✍️</span>
            <span className="text-xs font-medium text-white">
              <strong className="text-brand-gold">24 attestations</strong> générées
            </span>
          </div>
        </div>
      </div>
    </div>
  </section>
);
