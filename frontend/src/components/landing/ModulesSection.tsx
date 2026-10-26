import React from 'react';
import { LANDING_IMAGES } from './landingImages';

interface ModuleItem {
  number: string;
  title: string;
  description: string;
  bullets: string[];
  image: { alt: string; src: string };
}

const MODULES: ModuleItem[] = [
  {
    number: '01',
    title: 'Veille marché intelligente',
    description:
      "Détectez automatiquement les opportunités d'affaires. L'IA analyse, résume et classe les opportunités par domaine avec un score de pertinence dynamique et contextualisé.",
    bullets: [
      "Analyse multi-sources continue (URLs d'appels d'offres, PDF, textes libres)",
      'Scoring automatique > 85% selon vos compétences clés',
      "Alertes immédiates des nouveaux appels à manifestation d'intérêt",
    ],
    image: LANDING_IMAGES.module1,
  },
  {
    number: '02',
    title: 'Génération assistée de TDR',
    description:
      "Produisez des Termes de Référence complets et conformes en moins de 60 secondes. L'IA respecte rigoureusement les gabarits ALTIORA et vos exigences pédagogiques.",
    bullets: [
      'Conformité stricte aux gabarits officiels ALTIORA PREST',
      'Export immédiat en formats Microsoft Word (.docx) et PDF',
      'Validation humaine intégrée (HITL — Human-in-the-loop)',
    ],
    image: LANDING_IMAGES.module2,
  },
  {
    number: '03',
    title: 'Offres technique & financière',
    description:
      'Générez en un clic des offres commerciales hautement persuasives et structurées : architecture de formation, méthodologie, chronogramme, grille tarifaire et calculs de taxes en Ariary.',
    bullets: [
      'Trame technique + financière synchronisées',
      'Calcul automatique HT / TVA (20%) / TTC en Ariary (MGA)',
      "Workflow d'approbation et signature avant transmission client",
    ],
    image: LANDING_IMAGES.module3,
  },
  {
    number: '04',
    title: 'Préparation opérationnelle',
    description:
      "Planifiez l'emploi du temps, affectez formateurs et salles adaptées, et estimez instantanément le budget prévisionnel de chaque session de montée en compétences.",
    bullets: [
      "Emploi du temps visuel interactif et gestion des conflits d'horaires",
      'Affectation assistée selon expertises des formateurs et équipements requis',
      'Budget prévisionnel auto-calculé (pauses-café, honoraires, logistique)',
    ],
    image: LANDING_IMAGES.module4,
  },
  {
    number: '05',
    title: 'Gestion des formations & Suivi',
    description:
      'Assurez un suivi sans faille : émargement QR code digital, évaluations initiales et finales via Google Forms, enquêtes de satisfaction et génération automatique des attestations certifiées PDF pour les participants méritants (≥ 80%).',
    bullets: [
      '6 agents IA autonomes dédiés au suivi de cohorte',
      'Émargement instantané par QR code & sync Google Forms',
      'Génération d\'attestations certifiées en lot avec cachet ALTIORA',
    ],
    image: LANDING_IMAGES.module5,
  },
  {
    number: '06',
    title: 'Base de connaissances RAG',
    description:
      "Centralisez tout le capital intellectuel de votre organisme. Posez vos questions en langage naturel : l'IA explore vos documents vectorisés, cite précisément les sources et synthétise syllabus, questionnaires et fiches réflexes.",
    bullets: [
      'Ingestion multi-formats : PDF, DOCX, PPTX, XLSX',
      'Recherche sémantique vectorielle avec score de similarité',
      'Capitalisation continue pour un enrichissement pérenne du savoir',
    ],
    image: LANDING_IMAGES.module6,
  },
];

export const ModulesSection: React.FC = () => (
  <section id="modules" className="py-24 bg-white">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-24">
      <div className="text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center space-x-2 px-3.5 py-1 rounded-full bg-brand-gold/10 border border-brand-gold/30 mb-3">
          <span className="text-xs font-bold text-brand-goldDark uppercase tracking-wider">SUITE LOGICIELLE INTÉGRÉE</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy">Les 6 Modules Fondamentaux de FORMA-IA</h2>
        <p className="mt-3 text-base text-gray-600">
          Une architecture puissante pensée pour les cabinets de formation, consultants et institutions éducatives à Madagascar et en Afrique.
        </p>
      </div>

      {MODULES.map((m, idx) => {
        const imageLeft = idx % 2 === 1;
        return (
          <div key={m.number} className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className={`lg:col-span-6 space-y-5 ${imageLeft ? 'lg:order-2' : ''}`}>
              <span className="px-3 py-1 text-xs font-black uppercase tracking-wider rounded-md bg-brand-navy text-brand-gold">
                Module {m.number}
              </span>
              <h3 className="text-2xl sm:text-3xl font-extrabold text-brand-darkNavy">{m.title}</h3>
              <p className="text-gray-600 leading-relaxed">{m.description}</p>
              <ul className="space-y-3 pt-2">
                {m.bullets.map((b) => (
                  <li key={b} className="flex items-center text-sm font-medium text-gray-700">
                    <span className="w-5 h-5 shrink-0 rounded-full bg-brand-gold/20 text-brand-goldDark flex items-center justify-center mr-3 font-bold">✓</span>
                    {b}
                  </li>
                ))}
              </ul>
            </div>
            <div className={`lg:col-span-6 ${imageLeft ? 'lg:order-1' : ''}`}>
              <div className="relative rounded-2xl overflow-hidden shadow-2xl border border-brand-gold/20 group">
                <img
                  alt={m.image.alt}
                  src={m.image.src}
                  className="w-full h-auto object-cover transform group-hover:scale-105 transition duration-500"
                />
                <div className="absolute inset-0 bg-linear-to-t from-brand-darkNavy/40 via-transparent to-transparent pointer-events-none" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  </section>
);
