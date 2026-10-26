import React, { useEffect, useState } from 'react';

interface LandingNavbarProps {
  onLogin: () => void;
  onOpenDemo: () => void;
}

const NAV_LINKS = [
  { href: '#features', label: 'Fonctionnalités' },
  { href: '#modules', label: 'Modules' },
  { href: '#how-it-works', label: 'Comment ça marche' },
  { href: '#testimonials', label: 'Témoignages' },
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
            <div className="w-11 h-11 rounded-xl bg-linear-to-br from-brand-gold to-brand-goldDark flex items-center justify-center shadow-lg shadow-brand-gold/20 transform group-hover:scale-105 transition-transform duration-300">
              <svg className="w-6 h-6 text-brand-darkNavy" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 01-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L4.2 15.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className={`text-2xl font-black tracking-tight transition-colors duration-300 ${scrolled ? 'text-brand-darkNavy' : 'text-white'}`}>
                FORMA<span className="text-brand-gold">-IA</span>
              </span>
              <span className={`text-[10px] tracking-widest uppercase font-semibold transition-colors duration-300 -mt-1 ${scrolled ? 'text-brand-goldDark' : 'text-slate-300'}`}>
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
                className={`nav-link text-sm font-medium hover:text-brand-gold transition-colors ${scrolled ? 'text-brand-darkNavy' : 'text-white'}`}
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
              className={`p-2 rounded-lg hover:text-brand-gold focus:outline-none ${scrolled ? 'text-brand-darkNavy' : 'text-white'}`}
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
