import React, { useState } from 'react';
import { X, Zap, Building2, User, Mail, DollarSign, Send } from 'lucide-react';
import { OpportuniteCRM } from '../../types';

interface NewOpportunityModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (opp: Partial<OpportuniteCRM>) => Promise<void>;
}

export const NewOpportunityModal: React.FC<NewOpportunityModalProps> = ({
  isOpen,
  onClose,
  onSubmit
}) => {
  const [entreprise, setEntreprise] = useState('');
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [domaineIA, setDomaineIA] = useState('IA Générative & LLMs');
  const [besoinFormation, setBesoinFormation] = useState('');
  const [montantEstime, setMontantEstime] = useState('15000');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!entreprise || !contactName) return;

    setIsSubmitting(true);
    await onSubmit({
      entreprise,
      contactName,
      contactEmail,
      domaineIA,
      besoinFormation: besoinFormation || 'Acculturation et ateliers pratiques IA pour équipes métiers',
      montantEstime: parseFloat(montantEstime) || 15000
    });
    setIsSubmitting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center">
              <Zap size={20} />
            </div>
            <h3 className="text-lg font-bold text-[#11162A]">Saisir une nouvelle opportunité CRM</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Nom de l'Entreprise Client *</label>
            <input
              type="text"
              required
              value={entreprise}
              onChange={(e) => setEntreprise(e.target.value)}
              placeholder="ex: Safran Tech"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Nom du Contact *</label>
              <input
                type="text"
                required
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                placeholder="ex: Pierre Martin"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Email Contact</label>
              <input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="p.martin@safran.fr"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
              />
            </div>
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Domaine IA</label>
            <select
              value={domaineIA}
              onChange={(e) => setDomaineIA(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
            >
              <option value="IA Générative & LLMs">IA Générative & LLMs</option>
              <option value="Cybersécurité & IA">Cybersécurité & IA</option>
              <option value="Prompt Engineering Business">Prompt Engineering Business</option>
              <option value="Machine Learning & MLOps">Machine Learning & MLOps</option>
              <option value="EU AI Act & Compliance">EU AI Act & Compliance</option>
            </select>
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Besoin / Cahier des charges</label>
            <textarea
              value={besoinFormation}
              onChange={(e) => setBesoinFormation(e.target.value)}
              rows={2}
              placeholder="Description du besoin de formation..."
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Montant Estimé (Ar HT)</label>
            <input
              type="number"
              value={montantEstime}
              onChange={(e) => setMontantEstime(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#1B8F6E]"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-bold"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-lg font-bold flex items-center gap-1.5"
            >
              <Send size={14} />
              <span>{isSubmitting ? 'Envoi REST...' : 'Créer opportunité'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
