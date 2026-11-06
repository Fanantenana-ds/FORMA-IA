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
      "Repérez les besoins de formation et classez les opportunités selon les critères métier du projet.",
    bullets: [
      'Sources, références et dates consultables',
      'Classement par domaine et pertinence',
      'Sélection d’opportunités à examiner par l’équipe',
    ],
    image: LANDING_IMAGES.module1,
  },
  {
    number: '02',
    title: 'Génération assistée de TDR',
    description:
      "Préparez des Termes de Référence structurés à partir du besoin de formation et des gabarits disponibles.",
    bullets: [
      'Génération assistée à partir des informations du besoin',
      'Export des documents disponibles',
      'Relecture humaine avant validation',
    ],
    image: LANDING_IMAGES.module2,
  },
  {
    number: '03',
    title: 'Offres technique & financière',
    description:
      'Préparez une proposition technique et financière avec le contenu de formation, le calendrier et les montants en Ariary.',
    bullets: [
      'Trame technique + financière synchronisées',
      'Calcul automatique HT / TVA (20%) / TTC en Ariary (MGA)',
      'Revue humaine avant transmission au client',
    ],
    image: LANDING_IMAGES.module3,
  },
  {
    number: '04',
    title: 'Préparation opérationnelle',
    description:
      "Préparez l'emploi du temps et le budget prévisionnel avant le démarrage d'une session.",
    bullets: [
      'Organisation des séances de formation',
      'Prise en compte des ressources disponibles',
      'Estimation des principaux postes de coût',
    ],
    image: LANDING_IMAGES.module4,
  },
  {
    number: '05',
    title: 'Gestion des formations & Suivi',
    description:
      'Suivez les présences et les évaluations, puis préparez les attestations des participants éligibles selon le seuil du projet.',
    bullets: [
      '6 agents spécialisés pour le suivi M5',
      'Analyses des évaluations et des présences',
      'Attestations PDF soumises à validation',
    ],
    image: LANDING_IMAGES.module5,
  },
  {
    number: '06',
    title: 'Base de connaissances RAG',
    description:
      "Interrogez les supports pédagogiques indexés en langage naturel et retrouvez les références documentaires utilisées dans les réponses.",
    bullets: [
      'Indexation de documents de formation',
      'Recherche de passages liés à la question',
      'Réponse accompagnée de sources lorsqu’elles sont disponibles',
    ],
    image: LANDING_IMAGES.module6,
  },
];

export const ModulesSection: React.FC = () => (
  <section id="modules" className="py-24 bg-white">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-24">
      <div className="text-center max-w-3xl mx-auto">
        <div className="inline-flex items-center space-x-2 px-3.5 py-1 rounded-full bg-brand-gold/10 border border-brand-gold/30 mb-3">
          <span className="text-xs font-bold text-brand-navy uppercase tracking-wider">PARCOURS DE FORMATION</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-brand-darkNavy">Les modules au service du cycle de formation</h2>
        <p className="mt-3 text-base text-gray-600">
          Chaque module répond à un besoin métier précis, de la prospection au suivi des sessions.
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
                    <span className="w-5 h-5 shrink-0 rounded-full bg-brand-gold/20 text-brand-navy flex items-center justify-center mr-3 font-bold">✓</span>
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
