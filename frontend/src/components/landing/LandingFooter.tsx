import React from 'react';

const QUICK_LINKS = [
  { href: '#hero', label: 'Accueil' },
  { href: '#how-it-works', label: 'Parcours métier' },
  { href: '#modules', label: 'Modules' },
  { href: '#confiance', label: 'Confiance & contrôle' },
  { href: '#contact', label: 'Contact' },
];

export const LandingFooter: React.FC = () => (
  <footer className="bg-brand-darkNavy text-slate-300 pt-16 pb-8 border-t border-brand-gold/20">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-10 pb-12">
        {/* Brand */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl border border-white/20 bg-white p-0.5">
              <img src="/logo_altiora_prest.png" alt="Logo ALTIORA PREST" className="h-full w-full object-contain" />
            </div>
            <div>
              <span className="text-xl font-black text-white">
                FORMA<span className="text-brand-gold">-IA</span>
              </span>
              <span className="block text-[10px] uppercase font-semibold text-slate-400 tracking-wider">by ALTIORA PREST</span>
            </div>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed pr-4">
            FORMA-IA accompagne ALTIORA PREST dans la gestion du cycle de formation, de la veille marché au suivi des sessions et de la facturation.
          </p>
        </div>

        {/* Quick links */}
        <div className="lg:col-span-2 space-y-3">
          <p className="text-sm font-bold uppercase tracking-wider text-white">Plateforme</p>
          <ul className="space-y-2 text-sm text-slate-400">
            {QUICK_LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="hover:text-brand-gold transition">{l.label}</a>
              </li>
            ))}
          </ul>
        </div>

        {/* Contact */}
        <div className="lg:col-span-3 space-y-3">
          <p className="text-sm font-bold uppercase tracking-wider text-white">Contact &amp; Siège</p>
          <ul className="space-y-2.5 text-sm text-slate-400">
            <li className="flex items-start"><span className="mr-2 text-brand-gold">📍</span><span>Antananarivo, Madagascar</span></li>
            <li className="flex items-center"><span className="mr-2 text-brand-gold">📞</span><span>+261 34 12 345 67</span></li>
            <li className="flex items-center">
              <span className="mr-2 text-brand-gold">✉️</span>
              <a className="hover:text-brand-gold" href="mailto:contact@altiora-prest.mg">contact@altiora-prest.mg</a>
            </li>
            <li className="flex items-center">
              <span className="mr-2 text-brand-gold">🌐</span>
              <a className="hover:text-brand-gold" href="https://www.altiora-prest.mg" rel="noopener noreferrer" target="_blank">www.altiora-prest.mg</a>
            </li>
            <li className="flex items-center text-xs text-slate-500 pt-1"><span className="mr-2">🕐</span><span>Lun - Ven : 8h00 - 17h00</span></li>
          </ul>
        </div>

        {/* Platform principles */}
        <div className="lg:col-span-3 space-y-3">
          <p className="text-sm font-bold uppercase tracking-wider text-white">Principes de la plateforme</p>
          <ul className="space-y-2 text-sm leading-relaxed text-slate-400">
            <li>Sources documentaires consultables</li>
            <li>Validation humaine des contenus à diffuser</li>
            <li>Parcours métier structuré en six phases</li>
          </ul>
        </div>
      </div>

      <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-4">
        <p>© 2026 ALTIORA PREST — FORMA-IA</p>
        <p>Antananarivo, Madagascar</p>
        <p>Assistance IA avec contrôle humain</p>
      </div>
    </div>
  </footer>
);
