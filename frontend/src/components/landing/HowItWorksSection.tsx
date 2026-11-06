import React from 'react';
import { BookOpen, ClipboardList, FileText, Search, Wallet, GraduationCap } from 'lucide-react';

const STEPS = [
  { n: '01', code: 'M1 + M2', icon: Search, title: 'Veille et TDR', text: 'Repérer une opportunité, consulter ses références et préparer le cahier des charges.' },
  { n: '02', code: 'M3', icon: FileText, title: 'Offre technique et financière', text: 'Construire une proposition adaptée, puis la soumettre à la revue métier.' },
  { n: '03', code: 'Préparation', icon: ClipboardList, title: 'Budget et emploi du temps', text: 'Organiser les coûts et les séances avant le démarrage de la formation.' },
  { n: '04', code: 'C3', icon: BookOpen, title: 'Supports et RAG', text: 'Indexer les documents et interroger leur contenu avec des références consultables.' },
  { n: '05', code: 'M5 + M6', icon: GraduationCap, title: 'Formation et attestations', text: 'Suivre la session, analyser les évaluations et préparer les attestations pour validation.' },
  { n: '06', code: 'M7 + M8a', icon: Wallet, title: 'Facturation et pilotage', text: 'Préparer les factures et relances, puis consulter les indicateurs disponibles.' },
];

export const HowItWorksSection: React.FC = () => (
  <section id="how-it-works" className="py-24 bg-slate-50 relative">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-gold/15 text-brand-navy text-xs font-bold uppercase tracking-wider mb-3">
          Parcours métier
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy">Du besoin de formation à son suivi</h2>
        <p className="mt-3 text-base text-gray-600">
          Six étapes relient la veille marché, la préparation, la réalisation de la formation et son suivi administratif.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 relative">
        {STEPS.map((s) => {
          const Icon = s.icon;
          return (
            <article key={s.n} className="relative bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:border-brand-gold/50 hover:shadow-lg transition group">
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-navy text-brand-gold shadow-sm"
              >
                <Icon size={19} aria-hidden="true" />
              </div>
              <div className="mb-2 flex items-center gap-2">
                <span className="text-xs font-extrabold tracking-widest text-brand-navy">{s.n}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">{s.code}</span>
              </div>
              <h3 className="text-base font-bold text-brand-darkNavy mb-2">{s.title}</h3>
              <p className="text-sm text-slate-600 leading-relaxed">{s.text}</p>
            </article>
          );
        })}
      </div>
    </div>
  </section>
);
