import React, { useState } from 'react';
import {
  Award,
  CheckCircle2,
  TrendingUp,
  Star,
  User,
  MessageSquare,
  Building2,
  Calendar,
  Plus,
  X,
  Filter,
  BarChart2,
  Sparkles,
  ThumbsUp
} from 'lucide-react';
import { Formateur, EvaluationFormateur } from '../../types';

interface EvaluationCompetencesViewProps {
  formateurs: Formateur[];
  onAddEvaluation?: (evaluation: EvaluationFormateur) => void;
}

export const EvaluationCompetencesView: React.FC<EvaluationCompetencesViewProps> = ({
  formateurs,
  onAddEvaluation
}) => {
  const [activeTab, setActiveTab] = useState<'matrice' | 'par_formateur'>('par_formateur');
  const [selectedFormateurId, setSelectedFormateurId] = useState<string>(
    formateurs.length > 0 ? formateurs[0].id : ''
  );

  const [isAddEvalModalOpen, setIsAddEvalModalOpen] = useState(false);

  // Form states for adding evaluation in this view
  const [evalApprenant, setEvalApprenant] = useState('');
  const [evalEntreprise, setEvalEntreprise] = useState('');
  const [evalPedagogie, setEvalPedagogie] = useState(5);
  const [evalMaitrise, setEvalMaitrise] = useState(5);
  const [evalSupports, setEvalSupports] = useState(5);
  const [evalPonctualite, setEvalPonctualite] = useState(5);
  const [evalCommentaire, setEvalCommentaire] = useState('');

  const competencesData = [
    { module: 'Maîtrise des Prompts & Ingénierie de Contextes', acquise: 94, participants: 210 },
    { module: 'Fine-Tuning & RAG (Retrieval-Augmented Generation)', acquise: 88, participants: 145 },
    { module: 'Sécurité, Biais & Confidentialité des Données IA', acquise: 96, participants: 380 },
    { module: 'Déploiement d\'Agents IA Autonomes (CrewAI / LangGraph)', acquise: 82, participants: 92 },
    { module: 'Conformité Réglementaire EU AI Act', acquise: 91, participants: 175 }
  ];

  const currentFormateur =
    formateurs.find((f) => f.id === selectedFormateurId) || formateurs[0];

  const evaluationsList = currentFormateur?.evaluations || [];

  // Calculate average scores across criteria for current formateur
  const avgPedagogie = evaluationsList.length
    ? (evaluationsList.reduce((acc, e) => acc + e.notePedagogie, 0) / evaluationsList.length).toFixed(1)
    : '5.0';

  const avgMaitrise = evaluationsList.length
    ? (evaluationsList.reduce((acc, e) => acc + e.noteMaitriseTech, 0) / evaluationsList.length).toFixed(1)
    : '5.0';

  const avgSupports = evaluationsList.length
    ? (evaluationsList.reduce((acc, e) => acc + e.noteSupports, 0) / evaluationsList.length).toFixed(1)
    : '4.8';

  const avgPonctualite = evaluationsList.length
    ? (evaluationsList.reduce((acc, e) => acc + e.notePonctualite, 0) / evaluationsList.length).toFixed(1)
    : '5.0';

  const handleAddEvaluationSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentFormateur || !evalApprenant.trim() || !evalCommentaire.trim()) return;

    const avg = Number(((evalPedagogie + evalMaitrise + evalSupports + evalPonctualite) / 4).toFixed(1));

    const newEval: EvaluationFormateur = {
      id: `eval-${Date.now()}`,
      formateurId: currentFormateur.id,
      apprenantNom: evalApprenant.trim(),
      entreprise: evalEntreprise.trim() || 'Entreprise Partenaire',
      date: new Date().toLocaleDateString('fr-FR'),
      notePedagogie: evalPedagogie,
      noteMaitriseTech: evalMaitrise,
      noteSupports: evalSupports,
      notePonctualite: evalPonctualite,
      noteMoyenne: avg,
      commentaire: evalCommentaire.trim(),
      recommande: avg >= 4
    };

    if (onAddEvaluation) {
      onAddEvaluation(newEval);
    }

    setEvalApprenant('');
    setEvalEntreprise('');
    setEvalCommentaire('');
    setIsAddEvalModalOpen(false);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-[#1B8F6E]/10 text-[#1B8F6E]">
              Assurance Qualité & Qualiopi BPF
            </span>
            <span className="text-xs text-slate-400 font-medium">• Évaluations individuelles des formateurs</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Évaluation & Compétences</h1>
          <p className="text-slate-600 text-xs mt-1">
            Suivi individuel des évaluations par formateur, grilles d'acquisition et retours d'expérience à chaud.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('par_formateur')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'par_formateur'
                ? 'bg-[#1B8F6E] text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Star size={15} />
            <span>Évaluations par Formateur</span>
          </button>

          <button
            onClick={() => setActiveTab('matrice')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'matrice'
                ? 'bg-white text-[#11162A] shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <BarChart2 size={15} className="text-[#1B8F6E]" />
            <span>Matrice Qualiopi Globale</span>
          </button>
        </div>
      </div>

      {/* Global Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs text-center">
          <div className="text-3xl font-extrabold text-[#11162A]">98.2%</div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Satisfaction Globale</div>
          <p className="text-[11px] text-emerald-600 mt-1 font-semibold">Enquêtes à chaud post-formation</p>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs text-center">
          <div className="text-3xl font-extrabold text-[#11162A]">91.5%</div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Taux d'Acquisition</div>
          <p className="text-[11px] text-emerald-600 mt-1 font-semibold">Validé par QCM & Mise en pratique</p>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs text-center">
          <div className="text-3xl font-extrabold text-[#11162A]">100%</div>
          <div className="text-xs font-bold text-slate-500 uppercase mt-1">Conformité Qualiopi</div>
          <p className="text-[11px] text-[#1B8F6E] mt-1 font-semibold">Audit BPF & Critère 4 validé</p>
        </div>
      </div>

      {/* ======================================================== */}
      {/* ONGLET 1 : EVALUATIONS INDIVIDUELLES PAR FORMATEUR       */}
      {/* ======================================================== */}
      {activeTab === 'par_formateur' && (
        <div className="space-y-6">
          {/* Formateur Selector Row */}
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 w-full md:w-auto">
              <span className="text-xs font-bold text-slate-500 uppercase shrink-0">Choisir le formateur :</span>
              <select
                value={selectedFormateurId}
                onChange={(e) => setSelectedFormateurId(e.target.value)}
                className="w-full md:w-64 p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold text-xs text-[#11162A] focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
              >
                {formateurs.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.nom} ({f.tauxSatisfaction}★ - {f.specialites[0]})
                  </option>
                ))}
              </select>
            </div>

            {currentFormateur && (
              <button
                onClick={() => setIsAddEvalModalOpen(true)}
                className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition-colors cursor-pointer shrink-0"
              >
                <Plus size={16} />
                <span>Ajouter une évaluation pour {currentFormateur.nom.split(' ')[0]}</span>
              </button>
            )}
          </div>

          {currentFormateur && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Formateur Scorecard */}
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-6">
                <div className="text-center space-y-3">
                  <img
                    src={currentFormateur.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150'}
                    alt={currentFormateur.nom}
                    className="w-20 h-20 rounded-2xl object-cover mx-auto border-2 border-[#1B8F6E]/20 shadow-md"
                  />
                  <div>
                    <h2 className="text-lg font-extrabold text-[#11162A]">{currentFormateur.nom}</h2>
                    <p className="text-xs text-slate-500 font-medium">{currentFormateur.email}</p>
                  </div>

                  {/* Main Score badge */}
                  <div className="inline-flex items-center gap-2 bg-amber-50 px-4 py-2 rounded-xl border border-amber-200">
                    <Star size={22} className="fill-amber-400 text-amber-400" />
                    <span className="text-2xl font-black text-amber-900">{currentFormateur.tauxSatisfaction}</span>
                    <span className="text-xs font-bold text-amber-700">/ 5.0</span>
                  </div>
                </div>

                {/* Score Breakdown by Criteria */}
                <div className="space-y-3 pt-4 border-t border-slate-100 text-xs">
                  <h3 className="font-extrabold text-slate-800 uppercase text-[10px]">Detail des notes par critère</h3>

                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between font-bold text-slate-700 mb-1">
                        <span>Pédagogie & Clarté</span>
                        <span className="text-[#1B8F6E]">{avgPedagogie} / 5</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: `${(Number(avgPedagogie) / 5) * 100}%` }}
                        ></div>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between font-bold text-slate-700 mb-1">
                        <span>Maîtrise Technique IA</span>
                        <span className="text-[#1B8F6E]">{avgMaitrise} / 5</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: `${(Number(avgMaitrise) / 5) * 100}%` }}
                        ></div>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between font-bold text-slate-700 mb-1">
                        <span>Qualité des Supports</span>
                        <span className="text-[#1B8F6E]">{avgSupports} / 5</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: `${(Number(avgSupports) / 5) * 100}%` }}
                        ></div>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between font-bold text-slate-700 mb-1">
                        <span>Ponctualité & Animation</span>
                        <span className="text-[#1B8F6E]">{avgPonctualite} / 5</span>
                      </div>
                      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-[#1B8F6E] h-full rounded-full"
                          style={{ width: `${(Number(avgPonctualite) / 5) * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-1">
                  <div className="font-bold text-slate-800">Spécialités :</div>
                  <div className="flex flex-wrap gap-1">
                    {currentFormateur.specialites.map((s, idx) => (
                      <span key={idx} className="bg-white border border-slate-200 px-2 py-0.5 rounded text-[11px] font-semibold">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: Learner Reviews List */}
              <div className="lg:col-span-2 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-extrabold text-[#11162A] flex items-center gap-2">
                    <MessageSquare size={18} className="text-[#1B8F6E]" />
                    <span>Retours & Avis des Apprenants ({evaluationsList.length})</span>
                  </h3>
                </div>

                <div className="space-y-4">
                  {evaluationsList.map((ev) => (
                    <div
                      key={ev.id}
                      className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3 hover:border-[#1B8F6E]/30 transition-all"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="w-8 h-8 rounded-full bg-[#11162A] text-white flex items-center justify-center font-bold text-xs">
                            {ev.apprenantNom.charAt(0)}
                          </span>
                          <div>
                            <div className="font-extrabold text-[#11162A] text-xs">{ev.apprenantNom}</div>
                            <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1">
                              <Building2 size={12} className="text-[#1B8F6E]" />
                              <span>{ev.entreprise}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[11px] text-slate-400 font-mono">{ev.date}</span>
                          <span className="px-2.5 py-1 bg-amber-100 text-amber-900 rounded-lg text-xs font-extrabold flex items-center gap-1">
                            <Star size={12} className="fill-amber-500 text-amber-500" />
                            {ev.noteMoyenne} / 5
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-slate-700 italic bg-slate-50 p-3 rounded-xl border border-slate-200/60 leading-relaxed">
                        "{ev.commentaire}"
                      </p>

                      <div className="flex items-center gap-4 text-[11px] font-semibold text-slate-500 pt-1">
                        <span>Pédagogie: <strong className="text-slate-800">{ev.notePedagogie}/5</strong></span>
                        <span>Maîtrise: <strong className="text-slate-800">{ev.noteMaitriseTech}/5</strong></span>
                        <span>Supports: <strong className="text-slate-800">{ev.noteSupports}/5</strong></span>
                        <span>Ponctualité: <strong className="text-slate-800">{ev.notePonctualite}/5</strong></span>
                      </div>
                    </div>
                  ))}

                  {evaluationsList.length === 0 && (
                    <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
                      <MessageSquare size={32} className="mx-auto text-slate-300 mb-2" />
                      <p className="font-bold text-xs text-slate-700">Aucune évaluation enregistrée pour ce formateur.</p>
                      <button
                        onClick={() => setIsAddEvalModalOpen(true)}
                        className="mt-3 px-4 py-2 bg-[#1B8F6E] text-white text-xs font-bold rounded-xl"
                      >
                        Créer la première évaluation
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* ONGLET 2 : MATRICE QUALIOPI ET MODULES                   */}
      {/* ======================================================== */}
      {activeTab === 'matrice' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <h3 className="text-base font-extrabold text-[#11162A] mb-2">
            Matrice d'acquisition des compétences par module IA
          </h3>

          <div className="space-y-4">
            {competencesData.map((item, idx) => (
              <div key={idx} className="space-y-1.5 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
                <div className="flex items-center justify-between text-xs font-bold text-[#11162A]">
                  <span>{item.module}</span>
                  <span className="text-[#1B8F6E]">{item.acquise}% de réussite ({item.participants} apprenants)</span>
                </div>
                <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
                  <div className="bg-[#1B8F6E] h-full rounded-full" style={{ width: `${item.acquise}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MODAL: NOUVELLE EVALUATION */}
      {isAddEvalModalOpen && currentFormateur && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b pb-3 border-slate-100">
              <div>
                <div className="text-[10px] font-bold text-[#1B8F6E] uppercase">Nouvelle évaluation</div>
                <h2 className="text-base font-extrabold text-[#11162A]">Formateur : {currentFormateur.nom}</h2>
              </div>
              <button
                onClick={() => setIsAddEvalModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAddEvaluationSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Nom de l'apprenant *</label>
                  <input
                    type="text"
                    required
                    value={evalApprenant}
                    onChange={(e) => setEvalApprenant(e.target.value)}
                    placeholder="ex: Mialy RAKOTO"
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E]"
                  />
                </div>

                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Entreprise client *</label>
                  <input
                    type="text"
                    required
                    value={evalEntreprise}
                    onChange={(e) => setEvalEntreprise(e.target.value)}
                    placeholder="ex: Bank Of Africa / TELMA"
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
                <div>
                  <label className="font-bold text-slate-600 block mb-1">Pédagogie ({evalPedagogie}/5)</label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={evalPedagogie}
                    onChange={(e) => setEvalPedagogie(Number(e.target.value))}
                    className="w-full accent-[#1B8F6E]"
                  />
                </div>

                <div>
                  <label className="font-bold text-slate-600 block mb-1">Maîtrise Tech ({evalMaitrise}/5)</label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={evalMaitrise}
                    onChange={(e) => setEvalMaitrise(Number(e.target.value))}
                    className="w-full accent-[#1B8F6E]"
                  />
                </div>

                <div>
                  <label className="font-bold text-slate-600 block mb-1">Supports ({evalSupports}/5)</label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={evalSupports}
                    onChange={(e) => setEvalSupports(Number(e.target.value))}
                    className="w-full accent-[#1B8F6E]"
                  />
                </div>

                <div>
                  <label className="font-bold text-slate-600 block mb-1">Ponctualité ({evalPonctualite}/5)</label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={evalPonctualite}
                    onChange={(e) => setEvalPonctualite(Number(e.target.value))}
                    className="w-full accent-[#1B8F6E]"
                  />
                </div>
              </div>

              <div>
                <label className="font-extrabold text-slate-700 block mb-1">Avis & Commentaire *</label>
                <textarea
                  rows={3}
                  required
                  value={evalCommentaire}
                  onChange={(e) => setEvalCommentaire(e.target.value)}
                  placeholder="Appréciation générale sur les compétences et l'animation du formateur..."
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E]"
                ></textarea>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddEvalModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl font-bold cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#1B8F6E] text-white rounded-xl font-bold flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <Star size={14} className="fill-white" />
                  <span>Enregistrer l'évaluation</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
