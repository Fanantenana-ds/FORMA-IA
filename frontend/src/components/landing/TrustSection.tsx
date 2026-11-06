import React from 'react';
import { FileText, ShieldCheck, Workflow } from 'lucide-react';

const PRINCIPES = [
  {
    icon: FileText,
    title: 'Des éléments vérifiables',
    text: 'La veille conserve les références des avis. Le RAG relie ses réponses aux supports indexés lorsqu’il trouve des extraits utiles.',
  },
  {
    icon: ShieldCheck,
    title: 'Une validation humaine',
    text: 'Les documents préparés pour diffusion peuvent être relus et approuvés par un responsable avant leur utilisation.',
  },
  {
    icon: Workflow,
    title: 'Un parcours métier structuré',
    text: 'Les modules accompagnent les équipes de la veille marché à la préparation, au suivi des sessions et à la facturation.',
  },
];

export const TrustSection: React.FC = () => (
  <section id="confiance" className="py-24 bg-white border-t border-slate-200">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center max-w-3xl mx-auto mb-14">
        <p className="text-xs font-bold uppercase tracking-widest text-brand-navy mb-3">Confiance &amp; maîtrise</p>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy">Une IA au service des équipes, sous contrôle métier</h2>
        <p className="mt-4 text-base leading-relaxed text-slate-600">
          FORMA-IA assiste les équipes tout au long du cycle de formation, avec des sources consultables et une place claire pour la validation humaine.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {PRINCIPES.map(({ icon: Icon, title, text }) => (
          <article key={title} className="rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-sm">
            <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-navy text-brand-gold">
              <Icon size={21} aria-hidden="true" />
            </div>
            <h3 className="text-lg font-bold text-brand-darkNavy">{title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{text}</p>
          </article>
        ))}
      </div>
    </div>
  </section>
);
