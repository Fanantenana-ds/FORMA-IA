import React from 'react';
import { LANDING_IMAGES } from './landingImages';

const PARTNERS = [
  { name: 'ALTIORA PREST', dot: 'bg-brand-gold' },
  { name: 'ENI Fianarantsoa', dot: 'bg-red-600' },
  { name: 'Groq LPU', dot: 'bg-amber-500' },
  { name: 'LangChain', dot: 'bg-emerald-600' },
  { name: 'Anthropic Claude', dot: 'bg-indigo-600' },
];

const TESTIMONIALS = [
  {
    quote:
      '« FORMA-IA nous a fait gagner 70% de temps sur la production documentaire et la préparation des sessions. C\'est l\'outil indispensable pour moderniser l\'offre de formation professionnelle à Madagascar. »',
    name: 'M. RANAIVOSOA Sandampamianina',
    role: 'Co-gérant, ALTIORA PREST',
    img: LANDING_IMAGES.person1,
  },
  {
    quote:
      '« La base RAG a transformé notre façon de capitaliser sur nos formations passées. Nos équipes génèrent des syllabus et évaluations certifiées en quelques clics. »',
    name: 'Mme Voahirana RAZAFINDRABE',
    role: 'Directrice Pédagogique & Formation',
    img: LANDING_IMAGES.person2,
  },
  {
    quote:
      '« Les 6 agents IA nous font gagner un temps précieux sur le suivi des sessions, les émargements instantanés et la clôture administrative. »',
    name: 'M. Ando ANDRIANARISOA',
    role: 'Formateur Lead IA & Data',
    img: LANDING_IMAGES.person3,
  },
];

export const TestimonialsSection: React.FC = () => (
  <section id="testimonials" className="py-24 bg-white border-t border-slate-200">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center mb-16">
        <p className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-8">
          Propulsé par des technologies d'élite &amp; partenariats académiques
        </p>
        <div className="flex flex-wrap items-center justify-center gap-8 md:gap-14 opacity-75 grayscale hover:grayscale-0 transition-all duration-300">
          {PARTNERS.map((p) => (
            <div key={p.name} className="flex items-center space-x-2 font-bold text-xl text-slate-800">
              <span className={`w-3 h-3 rounded-full ${p.dot}`} />
              <span>{p.name}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {TESTIMONIALS.map((t) => (
          <div
            key={t.name}
            className="p-8 rounded-2xl bg-linear-to-br from-slate-50 to-white border border-slate-200 hover:border-brand-gold/50 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-4">
              <div className="flex text-brand-gold space-x-1">
                {'★★★★★'.split('').map((s, i) => (
                  <span key={i}>{s}</span>
                ))}
              </div>
              <blockquote className="text-gray-700 text-sm sm:text-base leading-relaxed italic">{t.quote}</blockquote>
            </div>
            <div className="flex items-center space-x-4 pt-6 mt-6 border-t border-slate-100">
              <img
                alt={`${t.name} - ${t.role}`}
                src={t.img.src}
                className="w-12 h-12 rounded-full object-cover border-2 border-brand-gold shadow-md shrink-0"
              />
              <div>
                <p className="font-bold text-brand-darkNavy text-sm">{t.name}</p>
                <p className="text-xs text-gray-500">{t.role}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);
