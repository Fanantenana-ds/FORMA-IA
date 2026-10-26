import React from 'react';

interface Feature {
  iconBox: string;
  path: string;
  title: string;
  text: React.ReactNode;
  footer: string;
}

const FEATURES: Feature[] = [
  {
    iconBox: 'bg-amber-500/10 text-brand-gold',
    path: 'M13 10V3L4 14h7v7l9-11h-7z',
    title: 'Détection intelligente',
    text: "Scan automatique des appels d'offres et requêtes de formation. Scoring de pertinence supérieur à 85% pour cibler vos opportunités gagnantes.",
    footer: 'Radar multi-sources & alertes',
  },
  {
    iconBox: 'bg-blue-500/10 text-brand-navy',
    path: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    title: 'Génération documentaire',
    text: 'Création en quelques secondes de TDR complets, propositions techniques et offres financières adaptées aux normes ALTIORA.',
    footer: 'HITL & validation en 1 clic',
  },
  {
    iconBox: 'bg-purple-500/10 text-purple-700',
    path: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
    title: 'Base de connaissances RAG',
    text: "Interrogez l'ensemble de votre patrimoine pédagogique en langage naturel. Indexation vectorielle PDF, DOCX et présentations PPTX.",
    footer: 'Embeddings sémantiques instantanés',
  },
  {
    iconBox: 'bg-emerald-500/10 text-emerald-700',
    path: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    title: 'Analyse & Pilotage',
    text: 'Suivi assiduité QR code, évaluations intégrées Google Forms, attestations certifiées et analytics de rentabilité en direct.',
    footer: "Tableaux de bord d'excellence",
  },
];

export const FeaturesSection: React.FC = () => (
  <section id="features" className="py-24 bg-slate-50 relative grid-bg-pattern border-y border-slate-200">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center space-x-2 px-3.5 py-1 rounded-full bg-brand-navy/5 border border-brand-navy/15 mb-3">
          <span className="text-xs font-bold text-brand-navy uppercase tracking-wider">INTELLIGENCE ARTIFICIELLE</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy tracking-tight">
          Une IA avancée à chaque étape du cycle de formation
        </h2>
        <p className="mt-4 text-base text-gray-600">
          Conçu avec les frameworks de pointe <strong>Groq</strong>, <strong>Anthropic</strong> et <strong>LangChain</strong>, notre moteur RAG vectoriel garantit rapidité, confidentialité et haute précision contextuelle.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {FEATURES.map((f) => (
          <div
            key={f.title}
            className="group bg-white p-7 rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-xl hover:border-brand-gold transition-all duration-300 transform hover:-translate-y-2 flex flex-col justify-between"
          >
            <div>
              <div className={`w-12 h-12 rounded-xl ${f.iconBox} flex items-center justify-center mb-5 group-hover:scale-110 transition-transform`}>
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d={f.path} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-brand-darkNavy mb-2 group-hover:text-brand-gold transition-colors">{f.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{f.text}</p>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-100 flex items-center text-xs font-semibold text-brand-navy">
              <span>{f.footer}</span>
              <svg className="w-4 h-4 ml-1 text-brand-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M9 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);
