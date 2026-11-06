import React, { useEffect, useState } from 'react';
import { X, ReceiptText, Send } from 'lucide-react';
import { DevisFacture, Session } from '../../types';

interface NewInvoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (fac: Partial<DevisFacture>) => Promise<void>;
  sessions: Session[];
  initialSessionId?: string;
}

export const NewInvoiceModal: React.FC<NewInvoiceModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  sessions,
  initialSessionId
}) => {
  const [client, setClient] = useState('');
  const [clientAdresse, setClientAdresse] = useState('');
  const [clientSiret, setClientSiret] = useState('');
  const [clientRcs, setClientRcs] = useState('');
  const [clientTva, setClientTva] = useState('');
  const [montantHT, setMontantHT] = useState('');
  const [tvaTaux, setTvaTaux] = useState('20');
  const [dateEcheance, setDateEcheance] = useState(() => {
    const due = new Date(); due.setDate(due.getDate() + 30); return due.toISOString().slice(0, 10);
  });
  const [sessionId, setSessionId] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    if (!initialSessionId) {
      setSessionId('');
      setClient('');
      return;
    }
    setSessionId(initialSessionId);
    const selected = sessions.find(item => item.id === initialSessionId);
    if (selected?.client) setClient(selected.client);
  }, [isOpen, initialSessionId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!client.trim() || Number(montantHT) <= 0 || !dateEcheance) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        type: 'Facture', client: client.trim(), clientAdresse: clientAdresse.trim(), clientSiret: clientSiret.trim(),
        clientRcs: clientRcs.trim(), clientTva: clientTva.trim(), montantHT: Number(montantHT),
        tvaTaux: Number(tvaTaux), dateEcheance, sessionId: sessionId || undefined
      });
      onClose();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'La facture n’a pas pu être créée.');
    } finally { setIsSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-2xl max-h-[92vh] w-full p-6 shadow-2xl border border-slate-200 overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center">
              <ReceiptText size={20} />
            </div>
            <h3 className="text-lg font-bold text-[#11162A]">Émettre une facture</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs">
          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Session terminée (facultatif)</label>
            <select value={sessionId} onChange={e => { const next = e.target.value; setSessionId(next); const session = sessions.find(item => item.id === next); if (session?.client) setClient(session.client); }} className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800">
              <option value="">Facture hors session</option>
              {sessions.filter(session => session.statut === 'Terminée').map(session => <option key={session.id} value={session.id}>{session.intitule} · {session.client ?? 'Client à renseigner'}</option>)}
            </select>
            {sessionId && <p className="mt-1 text-[10px] text-slate-500">La facture sera rattachée à cette session terminée. Saisissez le montant HT convenu.</p>}
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

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div><h4 className="text-xs font-extrabold uppercase tracking-wide text-[#11162A]">Coordonnées légales du client</h4><p className="mt-1 text-[10px] text-slate-500">Ces informations apparaîtront sur le PDF de la facture. Les mentions de l’émetteur se configurent dans le fichier .env du backend.</p></div>
            <label className="block font-bold text-slate-700">Adresse du siège<textarea value={clientAdresse} onChange={e => setClientAdresse(e.target.value)} rows={2} maxLength={300} placeholder="Adresse complète du client" className="mt-1 w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-800"/></label>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="block font-bold text-slate-700">SIRET / identifiant<input value={clientSiret} onChange={e => setClientSiret(e.target.value)} maxLength={32} placeholder="Numéro d’identification" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-800"/></label>
              <label className="block font-bold text-slate-700">RCS / registre<input value={clientRcs} onChange={e => setClientRcs(e.target.value)} maxLength={120} placeholder="Ville et numéro d’immatriculation" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-800"/></label>
              <label className="block font-bold text-slate-700">TVA intracommunautaire<input value={clientTva} onChange={e => setClientTva(e.target.value)} maxLength={32} placeholder="Numéro de TVA" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-800"/></label>
            </div>
          </div>

          <div>
            <label className="block font-bold text-slate-700 uppercase mb-1">Montant Hors Taxes (Ar HT)</label>
            <input
              type="number"
              required
              min="1"
              value={montantHT}
              onChange={(e) => setMontantHT(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block font-bold text-slate-700 uppercase">TVA (%)
              <input type="number" min="0" max="100" step="0.01" required value={tvaTaux} onChange={e => setTvaTaux(e.target.value)} className="mt-1 w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm font-normal normal-case text-slate-800" />
            </label>
            <label className="block font-bold text-slate-700 uppercase">Date d’échéance *
              <input type="date" required value={dateEcheance} onChange={e => setDateEcheance(e.target.value)} className="mt-1 w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm font-normal normal-case text-slate-800" />
            </label>
          </div>

          <div className="p-3 bg-[#F4F5F3] rounded-xl text-slate-600">
            <div className="flex justify-between font-medium">
              <span>Montant HT :</span>
              <strong>{(parseFloat(montantHT) || 0).toLocaleString()} Ar</strong>
            </div>
            <div className="flex justify-between font-medium mt-1">
              <span>TVA ({Number(tvaTaux) || 0}%) :</span>
              <span>{(((parseFloat(montantHT) || 0) * (Number(tvaTaux) || 0)) / 100).toLocaleString()} Ar</span>
            </div>
            <div className="flex justify-between font-extrabold text-[#11162A] mt-2 pt-2 border-t border-slate-200 text-sm">
              <span>Total TTC :</span>
              <strong>{((parseFloat(montantHT) || 0) * (1 + (Number(tvaTaux) || 0) / 100)).toLocaleString()} Ar TTC</strong>
            </div>
          </div>

          {error && <div role="alert" className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{error}</div>}

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
