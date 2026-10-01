import React, { useState } from 'react';
import {
  GraduationCap,
  Star,
  Mail,
  Phone,
  Calendar,
  CheckCircle2,
  Clock,
  Plus,
  X,
  Search,
  Award,
  MessageSquare,
  FileText,
  UserPlus,
  Building2,
  ThumbsUp,
  Sparkles
} from 'lucide-react';
import { Formateur, EvaluationFormateur } from '../../types';

interface FormateursStaffViewProps {
  formateurs: Formateur[];
  onAddFormateur?: (formateur: Formateur) => void;
  onAddEvaluation?: (evaluation: EvaluationFormateur) => void;
}

export const FormateursStaffView: React.FC<FormateursStaffViewProps> = ({
  formateurs,
  onAddFormateur,
  onAddEvaluation
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedFormateurForEval, setSelectedFormateurForEval] = useState<Formateur | null>(null);
  const [isEvalModalOpen, setIsEvalModalOpen] = useState(false);

  // New Formateur Form State
  const [newNom, setNewNom] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newTel, setNewTel] = useState('');
  const [newSpecialites, setNewSpecialites] = useState('IA Générative, LangChain, Python');
  const [newStatut, setNewStatut] = useState<'Disponible' | 'En session' | 'Indisponible'>('Disponible');
  const [newTarif, setNewTarif] = useState('1500000');
  const [newAvatar, setNewAvatar] = useState('https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150');

  // New Evaluation Form State
  const [evalApprenant, setEvalApprenant] = useState('');
  const [evalEntreprise, setEvalEntreprise] = useState('');
  const [evalPedagogie, setEvalPedagogie] = useState(5);
  const [evalMaitrise, setEvalMaitrise] = useState(5);
  const [evalSupports, setEvalSupports] = useState(5);
  const [evalPonctualite, setEvalPonctualite] = useState(5);
  const [evalCommentaire, setEvalCommentaire] = useState('');

  // Preset avatars for quick selection
  const avatarPresets = [
    'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150',
    'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=150',
    'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=150',
    'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=150',
    'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=150'
  ];

  const filteredFormateurs = formateurs.filter(
    (f) =>
      f.nom.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.specialites.some((s) => s.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleCreateFormateur = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNom.trim() || !newEmail.trim()) return;

    const created: Formateur = {
      id: `form-${Date.now()}`,
      nom: newNom.trim(),
      email: newEmail.trim(),
      telephone: newTel.trim() || '+261 34 00 000 00',
      specialites: newSpecialites.split(',').map((s) => s.trim()).filter(Boolean),
      statut: newStatut,
      tarifJournalier: parseFloat(newTarif) || 1200000,
      tauxSatisfaction: 5.0,
      sessionsCompteur: 0,
      avatarUrl: newAvatar,
      evaluations: []
    };

    if (onAddFormateur) {
      onAddFormateur(created);
    }

    // Reset Form
    setNewNom('');
    setNewEmail('');
    setNewTel('');
    setIsAddModalOpen(false);
  };

  const handleCreateEvaluation = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFormateurForEval || !evalApprenant.trim() || !evalCommentaire.trim()) return;

    const avg = Number(((evalPedagogie + evalMaitrise + evalSupports + evalPonctualite) / 4).toFixed(1));

    const newEval: EvaluationFormateur = {
      id: `eval-${Date.now()}`,
      formateurId: selectedFormateurForEval.id,
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

    // Reset
    setEvalApprenant('');
    setEvalEntreprise('');
    setEvalCommentaire('');
    setIsEvalModalOpen(false);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-blue-100 text-blue-800">
              Ressources Humaines & Experts
            </span>
            <span className="text-xs text-slate-400 font-medium">• Pool d'intervenants certifiés FORMA-IA</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Formateurs & Staff</h1>
          <p className="text-slate-600 text-xs mt-1">
            Gestion du corps professoral, habilitations Qualiopi, tarifs et fiches d'évaluations individuelles.
          </p>
        </div>

        {/* Action Button: Ajouter un formateur */}
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition-all cursor-pointer shrink-0"
        >
          <UserPlus size={16} />
          <span>Ajouter un formateur</span>
        </button>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Formateurs Actifs</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{formateurs.length} Experts</div>
          <p className="text-xs text-blue-600 font-semibold mt-1">Habilités Qualiopi BPF</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Taux Moy. de Satisfaction</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1 flex items-center gap-1.5">
            <Star size={20} className="fill-amber-400 text-amber-400" />
            <span>
              {(
                formateurs.reduce((acc, f) => acc + f.tauxSatisfaction, 0) / (formateurs.length || 1)
              ).toFixed(2)}{' '}
              / 5
            </span>
          </div>
          <p className="text-xs text-emerald-600 font-semibold mt-1">Évaluations à chaud enregistrées</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Disponibilité Immédiate</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">
            {formateurs.filter((f) => f.statut === 'Disponible').length} Disponibles
          </div>
          <p className="text-xs text-[#1B8F6E] font-semibold mt-1">Prêts pour nouvelles sessions</p>
        </div>
      </div>

      {/* Search Input Bar */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filtrer les formateurs par nom, spécialité ou email..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
        />
      </div>

      {/* Grid of Formateurs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredFormateurs.map((f) => {
          const evals = f.evaluations || [];
          return (
            <div
              key={f.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between hover:border-[#1B8F6E]/40 transition-all space-y-4"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <img
                      src={f.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150'}
                      alt={f.nom}
                      className="w-12 h-12 rounded-xl object-cover border border-slate-200 shadow-xs"
                    />
                    <div>
                      <h3 className="text-base font-extrabold text-[#11162A]">{f.nom}</h3>
                      <div className="flex items-center gap-1.5 text-xs text-amber-500 font-bold mt-0.5">
                        <Star size={14} className="fill-amber-400" />
                        <span>{f.tauxSatisfaction} / 5</span>
                        <span className="text-slate-400 font-medium">({f.sessionsCompteur} sessions)</span>
                      </div>
                    </div>
                  </div>

                  <span
                    className={`px-2.5 py-1 rounded-full text-[11px] font-extrabold ${
                      f.statut === 'Disponible'
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        : f.statut === 'En session'
                        ? 'bg-amber-100 text-amber-800 border border-amber-200'
                        : 'bg-slate-100 text-slate-700 border border-slate-200'
                    }`}
                  >
                    {f.statut}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Spécialités IA</div>
                  <div className="flex flex-wrap gap-1.5">
                    {f.specialites.map((spec, idx) => (
                      <span key={idx} className="bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-md text-xs font-semibold">
                        {spec}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200/80 mb-3">
                  <div className="flex items-center gap-2">
                    <Mail size={13} className="text-slate-400 shrink-0" />
                    <span className="font-medium text-slate-700">{f.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone size={13} className="text-slate-400 shrink-0" />
                    <span className="font-medium text-slate-700">{f.telephone}</span>
                  </div>
                </div>

                {/* Individual Evaluation Summary Section */}
                <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200/80 text-xs space-y-2">
                  <div className="flex items-center justify-between font-bold text-emerald-900">
                    <span className="flex items-center gap-1.5">
                      <Award size={14} className="text-emerald-700" />
                      Évaluation individuelle ({evals.length} avis)
                    </span>
                    <span className="text-emerald-700 font-extrabold">{f.tauxSatisfaction} / 5</span>
                  </div>

                  {evals.length > 0 ? (
                    <div className="text-[11px] text-slate-700 italic bg-white/80 p-2 rounded border border-emerald-100">
                      "{evals[0].commentaire}"
                      <div className="not-italic font-bold text-slate-500 text-[10px] mt-1">
                        — {evals[0].apprenantNom} ({evals[0].entreprise})
                      </div>
                    </div>
                  ) : (
                    <p className="text-[11px] text-slate-500">Aucune évaluation enregistrée pour ce formateur.</p>
                  )}
                </div>
              </div>

              {/* Bottom Actions */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div>
                  <span className="text-slate-400 font-medium text-[10px] uppercase block">Tarif journalier</span>
                  <strong className="text-sm font-extrabold text-[#11162A]">
                    {f.tarifJournalier.toLocaleString()} Ar / jour
                  </strong>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setSelectedFormateurForEval(f);
                      setIsEvalModalOpen(true);
                    }}
                    className="px-3 py-2 bg-[#11162A] hover:bg-[#1B8F6E] text-white rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Star size={13} className="fill-amber-400 text-amber-400" />
                    <span>Ajouter avis</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ======================================================== */}
      {/* MODAL 1 : FORMULAIRE D'AJOUT D'UN FORMATEUR              */}
      {/* ======================================================== */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex items-center justify-between border-b pb-3 border-slate-100">
              <div className="flex items-center gap-2">
                <UserPlus size={20} className="text-[#1B8F6E]" />
                <h2 className="text-lg font-extrabold text-[#11162A]">Ajouter un nouveau formateur</h2>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateFormateur} className="space-y-4 text-xs">
              <div>
                <label className="font-extrabold text-slate-700 block mb-1">Nom et Prénom *</label>
                <input
                  type="text"
                  required
                  value={newNom}
                  onChange={(e) => setNewNom(e.target.value)}
                  placeholder="ex: Dr. Hasina RANAIVO"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Email Professionnel *</label>
                  <input
                    type="email"
                    required
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="h.ranaivo@forma-ia.mg"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Téléphone *</label>
                  <input
                    type="text"
                    required
                    value={newTel}
                    onChange={(e) => setNewTel(e.target.value)}
                    placeholder="+261 34 12 345 67"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="font-extrabold text-slate-700 block mb-1">
                  Spécialités IA (séparées par des virgules) *
                </label>
                <input
                  type="text"
                  required
                  value={newSpecialites}
                  onChange={(e) => setNewSpecialites(e.target.value)}
                  placeholder="Agents IA, CrewAI, FastAPI, Python"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Statut Initial</label>
                  <select
                    value={newStatut}
                    onChange={(e) => setNewStatut(e.target.value as any)}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  >
                    <option value="Disponible">Disponible</option>
                    <option value="En session">En session</option>
                    <option value="Indisponible">Indisponible</option>
                  </select>
                </div>

                <div>
                  <label className="font-extrabold text-slate-700 block mb-1">Tarif Journalier (Ar HT / jour) *</label>
                  <input
                    type="number"
                    required
                    value={newTarif}
                    onChange={(e) => setNewTarif(e.target.value)}
                    placeholder="1500000"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl font-bold focus:ring-2 focus:ring-[#1B8F6E] focus:outline-none"
                  />
                </div>
              </div>

              {/* Avatar Selector */}
              <div>
                <label className="font-extrabold text-slate-700 block mb-1.5">Photo de Profil (Avatar)</label>
                <div className="flex items-center gap-2">
                  {avatarPresets.map((url, i) => (
                    <img
                      key={i}
                      src={url}
                      alt="avatar preset"
                      onClick={() => setNewAvatar(url)}
                      className={`w-10 h-10 rounded-xl object-cover cursor-pointer border-2 transition-all ${
                        newAvatar === url ? 'border-[#1B8F6E] ring-2 ring-[#1B8F6E]/20 scale-105' : 'border-slate-200'
                      }`}
                    />
                  ))}
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <CheckCircle2 size={15} />
                  <span>Enregistrer le formateur</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL 2 : AJOUTER UNE EVALUATION A UN FORMATEUR          */}
      {/* ======================================================== */}
      {isEvalModalOpen && selectedFormateurForEval && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b pb-3 border-slate-100">
              <div>
                <div className="text-[10px] font-bold text-[#1B8F6E] uppercase">Formulaire d'évaluation</div>
                <h2 className="text-base font-extrabold text-[#11162A]">
                  Évaluer : {selectedFormateurForEval.nom}
                </h2>
              </div>
              <button
                onClick={() => setIsEvalModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateEvaluation} className="space-y-3 text-xs">
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
                  <label className="font-extrabold text-slate-700 block mb-1">Entreprise *</label>
                  <input
                    type="text"
                    required
                    value={evalEntreprise}
                    onChange={(e) => setEvalEntreprise(e.target.value)}
                    placeholder="ex: TELMA / Bank Of Africa"
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E]"
                  />
                </div>
              </div>

              {/* Ratings */}
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
                <label className="font-extrabold text-slate-700 block mb-1">Avis / Commentaire à chaud *</label>
                <textarea
                  rows={3}
                  required
                  value={evalCommentaire}
                  onChange={(e) => setEvalCommentaire(e.target.value)}
                  placeholder="Explication claire des concepts, animation dynamique de la formation..."
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl font-medium focus:ring-2 focus:ring-[#1B8F6E]"
                ></textarea>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsEvalModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl font-bold cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#1B8F6E] text-white rounded-xl font-bold flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <Star size={14} className="fill-white" />
                  <span>Publier l'évaluation</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
