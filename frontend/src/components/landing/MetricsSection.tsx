import React from 'react';

const REPERES = [
  { valeur: '6 phases', titre: 'du parcours métier', detail: 'De la veille marché au suivi de facturation.' },
  { valeur: '6 agents', titre: 'pour le module M5', detail: 'Formulaires, niveaux, satisfaction, présence, attestations et rapport.' },
  { valeur: 'RAG', titre: 'recherche documentaire', detail: 'Les réponses peuvent renvoyer aux supports indexés consultés.' },
  { valeur: 'Revue humaine', titre: 'avant diffusion', detail: 'Les documents peuvent être relus et approuvés par un responsable.' },
];

export const MetricsSection: React.FC = () => {
  return (
    <section id="metrics" className="py-20 bg-brand-navy relative overflow-hidden text-white">
      <div className="absolute inset-0 bg-radial from-brand-gold/10 via-transparent to-transparent pointer-events-none" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="text-xs uppercase tracking-widest text-brand-gold font-bold mb-2">Repères fonctionnels</p>
          <h2 className="text-3xl sm:text-4xl font-extrabold">Ce que couvre la plateforme</h2>
          <p className="text-slate-300 mt-2 text-sm">
            Des capacités métier concrètes, présentées sans promesse de performance non mesurée.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {REPERES.map((repere) => (
            <article key={repere.titre} className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center">
              <div className="text-2xl font-extrabold text-brand-gold">{repere.valeur}</div>
              <h3 className="mt-2 text-sm font-bold text-white">{repere.titre}</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">{repere.detail}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};
