import React, { useState } from 'react';
import { X, CalendarDays, Send } from 'lucide-react';
import { Session } from '../../types';

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (session: Partial<Session>) => Promise<void>;
}

export const NewSessionModal: React.FC<NewSessionModalProps> = ({
  isOpen,
  onClose,
  onSubmit
}) => {
  const [intitule, setIntitule] = useState('');
  const [domaine, setDomaine] = useState('IA Générative & LLMs');
  const [formateur, setFormateur] = useState('Dr. Alex Moreau');
  const [dates, setDates] = useState('15 - 17 Sept. 2026');
  const [lieu, setLieu] = useState<'Présentiel' | 'Distanciel' | 'Hybride'>('Présentiel');
  const [prixUnitaire, setPrixUnitaire] = useState('1450');
  const [capacityMax, setCapacityMax] = useState('20');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!intitule) return;

    setIsSubmitting(true);
    await onSubmit({
      intitule,
      domaine,
      formateur,
      dates,
      lieu,
      prixUnitaire: parseFloat(prixUnitaire) || 1450,
      capacityMax: parseInt(capacityMax) || 20,
      participantsInscrits: 0
    });
    setIsSubmitting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-[#1B8F6E]/10 text-[#1B8F6E] flex items-center justify-center">
              <CalendarDays size={20} />
            </div>
            <h3 className="text-lg font-bold text-[#11162A]">Planifier une nouvelle session</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Intitulé de la Formation *</label>
            <input
              type="text"
              required
              value={intitule}
              onChange={(e) => setIntitule(e.target.value)}
              placeholder="ex: Architectures RAG & Fine-Tuning Llama 3"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Domaine Pédagogique</label>
              <select
                value={domaine}
                onChange={(e) => setDomaine(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              >
                <option value="IA Générative & LLMs">IA Générative & LLMs</option>
                <option value="Cybersécurité & IA">Cybersécurité & IA</option>
                <option value="Gouvernance & Compliance">Gouvernance & Compliance</option>
                <option value="Prompt Engineering">Prompt Engineering</option>
              </select>
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Formateur Référent</label>
              <select
                value={formateur}
                onChange={(e) => setFormateur(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              >
                <option value="Dr. Alex Moreau">Dr. Alex Moreau</option>
                <option value="Sophie Bernard">Sophie Bernard</option>
                <option value="Claire Dupont">Claire Dupont</option>
                <option value="Karim Benali">Karim Benali</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Dates de Formation</label>
              <input
                type="text"
                value={dates}
                onChange={(e) => setDates(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Format / Lieu</label>
              <select
                value={lieu}
                onChange={(e) => setLieu(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              >
                <option value="Présentiel">Présentiel</option>
                <option value="Distanciel">Distanciel</option>
                <option value="Hybride">Hybride</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Capacité Maximale</label>
              <input
                type="number"
                value={capacityMax}
                onChange={(e) => setCapacityMax(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Prix Unitaire / Apprenant (€)</label>
              <input
                type="number"
                value={prixUnitaire}
                onChange={(e) => setPrixUnitaire(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg font-bold"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-[#1B8F6E] text-white rounded-lg font-bold flex items-center gap-1.5"
            >
              <Send size={14} />
              <span>{isSubmitting ? 'Enregistrement...' : 'Enregistrer session'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
