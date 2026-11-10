import React, { useState } from 'react';
import { X, Zap, DollarSign, Send } from 'lucide-react';
import { OpportuniteCRM } from '../../types';

interface NewOpportunityModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (opp: Partial<OpportuniteCRM>) => Promise<void>;
}

export const NewOpportunityModal: React.FC<NewOpportunityModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [objet, setObjet] = useState('');
  const [domaine, setDomaine] = useState('IA');
  const [contenu, setContenu] = useState('');
  const [budget, setBudget] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!objet.trim() || !contenu.trim()) return;
    setIsSubmitting(true);
    setError('');
    try {
      await onSubmit({ entreprise: objet.trim(), domaineIA: domaine, besoinFormation: contenu.trim(), montantEstime: Number(budget) || 0 });
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'L’opportunité n’a pas pu être enregistrée.');
    } finally { setIsSubmitting(false); }
  };

  return <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
    <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100"><div className="flex items-center gap-2"><div className="w-9 h-9 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center"><Zap size={20} /></div><h3 className="text-lg font-bold text-[#11162A]">Nouvelle opportunité</h3></div><button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
        <div><label className="block font-bold text-slate-700 uppercase mb-1">Objet *</label><input required value={objet} onChange={e => setObjet(e.target.value)} placeholder="ex. Formation cybersécurité IA" className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#0B1F4D]" /></div>
        <div><label className="block font-bold text-slate-700 uppercase mb-1">Domaine</label><select value={domaine} onChange={e => setDomaine(e.target.value)} className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"><option value="IA">Intelligence artificielle</option><option value="DATA">Data</option><option value="DEVOPS">DevOps</option><option value="DEVELOPPEMENT">Développement</option><option value="BUREAUTIQUE">Bureautique</option><option value="AUTRE">Autre</option></select></div>
        <div><label className="block font-bold text-slate-700 uppercase mb-1">Contenu / description *</label><textarea required value={contenu} onChange={e => setContenu(e.target.value)} rows={4} placeholder="Décrivez le besoin, la formation attendue ou l'annonce…" className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800 focus:ring-2 focus:ring-[#0B1F4D]" /></div>
        <div><label className="block font-bold text-slate-700 uppercase mb-1 flex items-center gap-1"><DollarSign size={13} /> Budget estimé (Ar)</label><input type="number" min="0" value={budget} onChange={e => setBudget(e.target.value)} className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800" /></div>
        {error && <div role="alert" className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{error}</div>}
        <div className="pt-3 border-t border-slate-100 flex justify-end gap-2"><button type="button" onClick={onClose} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-bold">Annuler</button><button type="submit" disabled={isSubmitting} className="px-5 py-2 bg-[#0B1F4D] hover:bg-[#06132F] text-white rounded-lg font-bold flex items-center gap-1.5"><Send size={14} /><span>{isSubmitting ? 'Enregistrement…' : 'Créer opportunité'}</span></button></div>
      </form>
    </div>
  </div>;
};
