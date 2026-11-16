import React, { useEffect, useState } from 'react';

interface LandingNavbarProps {
  onLogin: () => void;
  onOpenDemo: () => void;
}

const NAV_LINKS = [
  { href: '#features', label: 'Fonctionnalités' },
  { href: '#modules', label: 'Modules' },
  { href: '#how-it-works', label: 'Comment ça marche' },
  { href: '#confiance', label: 'Confiance & contrôle' },
  { href: '#contact', label: 'Contact' },
];

export const LandingNavbar: React.FC<LandingNavbarProps> = ({ onLogin, onOpenDemo }) => {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      id="main-header"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'bg-white/95 shadow-md backdrop-blur-md py-3 text-brand-darkNavy' : 'bg-transparent py-4 text-white'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <a href="#hero" className="flex items-center space-x-3 group">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/20 bg-white p-0.5 shadow-lg shadow-brand-gold/20 transform group-hover:scale-105 transition-transform duration-300">
              <img
                src="/logo_altiora_prest.png"
                alt="Logo ALTIORA PREST"
                className="h-full w-full object-contain"
              />
            </div>
            <div className="flex flex-col">
              <span className={`text-2xl font-black tracking-tight transition-colors duration-300 ${scrolled ? 'text-brand-darkNavy' : 'text-white'}`}>
                FORMA<span className={scrolled ? 'text-brand-navy' : 'text-brand-gold'}>-IA</span>
              </span>
              <span className={`text-[10px] tracking-widest uppercase font-semibold transition-colors duration-300 -mt-1 ${scrolled ? 'text-brand-navy' : 'text-slate-300'}`}>
                by ALTIORA PREST
              </span>
            </div>
          </a>

          {/* Desktop links */}
          <nav className="hidden md:flex items-center space-x-8">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className={`nav-link text-sm font-medium transition-colors ${scrolled ? 'text-brand-darkNavy hover:text-brand-navy' : 'text-white hover:text-brand-gold'}`}
              >
                {l.label}
              </a>
            ))}
          </nav>

          {/* CTA */}
          <div className="hidden sm:flex items-center space-x-4">
            <button
              type="button"
              onClick={onLogin}
              className={`px-4 py-2 rounded-lg text-sm font-semibold border transition duration-200 ${
                scrolled
                  ? 'border-brand-navy/30 text-brand-navy hover:bg-slate-100'
                  : 'border-white/30 text-white hover:bg-white/10 hover:border-white'
              }`}
            >
              Se connecter
            </button>
            <button
              type="button"
              onClick={onOpenDemo}
              className="px-5 py-2.5 rounded-lg text-sm font-bold bg-linear-to-r from-brand-gold to-brand-goldDark text-brand-darkNavy hover:brightness-110 shadow-lg shadow-brand-gold/25 hover:shadow-brand-gold/40 transform hover:-translate-y-0.5 transition duration-200"
            >
              Demander une démo
            </button>
          </div>

          {/* Mobile trigger */}
          <div className="md:hidden flex items-center">
            <button
              type="button"
              aria-label="Ouvrir le menu"
              onClick={() => setMenuOpen((v) => !v)}
              className={`p-2 rounded-lg focus:outline-none ${scrolled ? 'text-brand-darkNavy hover:text-brand-navy' : 'text-white hover:text-brand-gold'}`}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden bg-brand-darkNavy/98 border-b border-brand-gold/20 px-6 py-6 transition-all duration-300">
          <div className="flex flex-col space-y-4">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setMenuOpen(false)}
                className="text-base font-medium text-slate-200 hover:text-brand-gold"
              >
                {l.label}
              </a>
            ))}
            <div className="pt-4 flex flex-col gap-3">
              <button
                type="button"
                onClick={() => { setMenuOpen(false); onLogin(); }}
                className="w-full text-center py-2.5 rounded-lg text-sm font-semibold border border-brand-gold/50 text-brand-gold"
              >
                Se connecter
              </button>
              <button
                type="button"
                onClick={() => { setMenuOpen(false); onOpenDemo(); }}
                className="w-full text-center py-2.5 rounded-lg text-sm font-bold bg-brand-gold text-brand-darkNavy shadow-md"
              >
                Demander une démo
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
