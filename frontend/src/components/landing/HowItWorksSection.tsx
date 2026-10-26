import React from 'react';

const STEPS = [
  { n: '01', emoji: '🔍', title: 'Détection & TDR', text: 'Scraping des opportunités, filtrage sémantique et génération instantanée du cahier des charges TDR.' },
  { n: '02', emoji: '📄', title: 'Offre Technique & Prix', text: 'Assemblage automatisé de la proposition technique, planning et tarification détaillée en Ariary.' },
  { n: '03', emoji: '🗓️', title: 'Préparation Session', text: 'Affectation des formateurs, réservation des salles et simulation du budget logistique prévisionnel.' },
  { n: '04', emoji: '📚', title: 'Indexation RAG', text: "Upload des supports de cours, vectorisation sémantique et génération des quiz d'évaluation." },
  { n: '05', emoji: '🎓', title: 'Attestations & Clôture', text: 'Check-in QR code, validation des notes et édition automatisée des attestations officielles signées.' },
];

export const HowItWorksSection: React.FC = () => (
  <section id="how-it-works" className="py-24 bg-slate-50 relative">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-gold/15 text-brand-goldDark text-xs font-bold uppercase tracking-wider mb-3">
          Workflow Fluide
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy">Comment fonctionne FORMA-IA ?</h2>
        <p className="mt-3 text-base text-gray-600">
          Un pipeline structuré en 5 étapes clés assurant une transition harmonieuse de la prospection jusqu'à la certification.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative">
        {STEPS.map((s, i) => {
          const last = i === STEPS.length - 1;
          return (
            <div key={s.n} className="relative bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:shadow-lg transition group">
              <div
                className={`w-10 h-10 rounded-full font-black flex items-center justify-center mb-4 text-sm shadow-md ${
                  last ? 'bg-brand-gold text-brand-darkNavy' : 'bg-brand-navy text-brand-gold'
                }`}
              >
                {s.n}
              </div>
              <div className="text-2xl mb-2">{s.emoji}</div>
              <h4 className="text-base font-bold text-brand-darkNavy mb-2">{s.title}</h4>
              <p className="text-xs text-gray-600 leading-relaxed">{s.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  </section>
);
