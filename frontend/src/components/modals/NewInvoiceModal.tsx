import React, { useState } from 'react';
import { X, ReceiptText, Send } from 'lucide-react';
import { DevisFacture } from '../../types';

interface NewInvoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (fac: Partial<DevisFacture>) => Promise<void>;
}

export const NewInvoiceModal: React.FC<NewInvoiceModalProps> = ({
  isOpen,
  onClose,
  onSubmit
}) => {
  const [type, setType] = useState<'Devis' | 'Facture'>('Devis');
  const [client, setClient] = useState('');
  const [montantHT, setMontantHT] = useState('12000');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!client) return;

    setIsSubmitting(true);
    await onSubmit({
      type,
      client,
      montantHT: parseFloat(montantHT) || 12000
    });
    setIsSubmitting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center">
              <ReceiptText size={20} />
            </div>
            <h3 className="text-lg font-bold text-[#11162A]">Émettre un Devis ou Facture</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Type de document</label>
            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-100 rounded-lg">
              <button
                type="button"
                onClick={() => setType('Devis')}
                className={`py-2 rounded-md font-bold text-xs ${type === 'Devis' ? 'bg-[#1B8F6E] text-white' : 'text-slate-600'}`}
              >
                Devis de Formation
              </button>
              <button
                type="button"
                onClick={() => setType('Facture')}
                className={`py-2 rounded-md font-bold text-xs ${type === 'Facture' ? 'bg-[#11162A] text-white' : 'text-slate-600'}`}
              >
                Facture Réglable
              </button>
            </div>
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Nom du Client / Entreprise *</label>
            <input
              type="text"
              required
              value={client}
              onChange={(e) => setClient(e.target.value)}
              placeholder="ex: Schneider Electric"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
            />
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Montant Hors Taxes (Ar HT)</label>
            <input
              type="number"
              value={montantHT}
              onChange={(e) => setMontantHT(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
            />
          </div>

          <div className="p-3 bg-[#F4F5F3] rounded-xl text-slate-600">
            <div className="flex justify-between font-medium">
              <span>Montant HT :</span>
              <strong>{(parseFloat(montantHT) || 0).toLocaleString()} Ar</strong>
            </div>
            <div className="flex justify-between font-medium mt-1">
              <span>TVA (20%) :</span>
              <span>{((parseFloat(montantHT) || 0) * 0.2).toLocaleString()} Ar</span>
            </div>
            <div className="flex justify-between font-extrabold text-[#11162A] mt-2 pt-2 border-t border-slate-200 text-sm">
              <span>Total TTC :</span>
              <strong>{((parseFloat(montantHT) || 0) * 1.2).toLocaleString()} Ar TTC</strong>
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
              <span>Générer document</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
