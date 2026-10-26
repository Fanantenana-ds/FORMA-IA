import React from 'react';

const SOCIALS = [
  {
    label: 'LinkedIn',
    fill: true,
    path: 'M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 8.76a1.45 1.45 0 0 0 0-2.9 1.45 1.45 0 0 0 0 2.9m1.38 9.74v-8.37H5.08v8.37h2.76z',
  },
  {
    label: 'Facebook',
    fill: true,
    path: 'M22 12c0-5.52-4.48-10-10-10S2 6.48 2 12c0 4.84 3.44 8.87 8 9.8V15H8v-3h2V9.5C10 7.57 11.57 6 13.5 6H16v3h-2c-.55 0-1 .45-1 1v2h3v3h-3v6.95c5.05-.5 9-4.76 9-9.95z',
  },
  {
    label: 'Site Web',
    fill: false,
    path: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
  },
];

const QUICK_LINKS = [
  { href: '#hero', label: 'Accueil' },
  { href: '#features', label: 'Fonctionnalités' },
  { href: '#modules', label: 'Modules' },
  { href: '#how-it-works', label: 'Comment ça marche' },
  { href: '#testimonials', label: 'Témoignages' },
];

export const LandingFooter: React.FC = () => (
  <footer className="bg-brand-darkNavy text-slate-300 pt-16 pb-8 border-t border-brand-gold/20">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-10 pb-12">
        {/* Brand */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-linear-to-br from-brand-gold to-brand-goldDark flex items-center justify-center text-brand-darkNavy font-black">
              AI
            </div>
            <div>
              <span className="text-xl font-black text-white">
                FORMA<span className="text-brand-gold">-IA</span>
              </span>
              <span className="block text-[10px] uppercase font-semibold text-slate-400 tracking-wider">by ALTIORA PREST</span>
            </div>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed pr-4">
            Cabinet de référence en ingénierie pédagogique, formation continue et conseil stratégique. FORMA-IA est la première solution souveraine d'IA générative dédiée aux organismes formateurs de la Grande Île.
          </p>
          <div className="flex space-x-3 pt-2">
            {SOCIALS.map((s) => (
              <a
                key={s.label}
                href="#"
                aria-label={s.label}
                className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-brand-gold hover:bg-brand-gold hover:text-brand-darkNavy transition"
              >
                <svg
                  className="w-4 h-4"
                  viewBox="0 0 24 24"
                  fill={s.fill ? 'currentColor' : 'none'}
                  stroke={s.fill ? undefined : 'currentColor'}
                >
                  <path d={s.path} strokeLinecap="round" strokeLinejoin="round" strokeWidth={s.fill ? undefined : 2} />
                </svg>
              </a>
            ))}
          </div>
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

        {/* Legal */}
        <div className="lg:col-span-3 space-y-3">
          <p className="text-sm font-bold uppercase tracking-wider text-white">Cadre Légal &amp; Académique</p>
          <ul className="space-y-2 text-sm text-slate-400">
            <li><a className="hover:text-brand-gold transition" href="#">Mentions légales</a></li>
            <li><a className="hover:text-brand-gold transition" href="#">Politique de confidentialité</a></li>
            <li><a className="hover:text-brand-gold transition" href="#">Conditions Générales d'Utilisation</a></li>
            <li><span className="text-slate-400">Partenaire académique : <strong className="text-brand-gold">ENI</strong></span></li>
          </ul>
        </div>
      </div>

      <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-4">
        <p>© 2026 ALTIORA PREST — Tous droits réservés.</p>
        <p>Développé avec <span className="text-brand-gold">❤️</span> à Antananarivo, Madagascar</p>
        <p className="font-mono text-slate-400">Version 1.0 (Propulsée par IA)</p>
      </div>
    </div>
  </footer>
);
