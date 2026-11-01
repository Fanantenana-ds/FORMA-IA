import React, { useEffect, useState } from 'react';
import { X, CalendarDays, Send } from 'lucide-react';
import { Formateur, Session, VeilleMarche } from '../../types';
import { defaultSessionDates } from '../../services/sessionDates';

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (session: Partial<Session>) => Promise<void>;
  acceptedMarkets: VeilleMarche[];
  formateurs: Formateur[];
}

export const NewSessionModal: React.FC<NewSessionModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  acceptedMarkets,
  formateurs
}) => {
  const [intitule, setIntitule] = useState('');
  const [client, setClient] = useState('');
  const [formateurId, setFormateurId] = useState('');
  const [selectedMarketId, setSelectedMarketId] = useState('');
  const [dates, setDates] = useState('');
  const [dateFin, setDateFin] = useState('');
  const [lieu, setLieu] = useState('');
  const [capacityMax, setCapacityMax] = useState('');
  const [formationCode, setFormationCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    const defaults = defaultSessionDates();
    let prefill: Record<string, any> = {};
    try { prefill = JSON.parse(sessionStorage.getItem('forma_ia_voice_prefill') ?? '{}'); sessionStorage.removeItem('forma_ia_voice_prefill'); } catch { /* préremplissage facultatif */ }
    setIntitule(String(prefill.titre ?? prefill.intitule ?? prefill.session ?? ''));
    setClient(String(prefill.client ?? prefill.organisation ?? ''));
    setFormateurId('');
    setSelectedMarketId('');
    setDates(String(prefill.date_debut ?? prefill.dates ?? defaults.dateDebut));
    setDateFin(String(prefill.date_fin ?? defaults.dateFin));
    setLieu(String(prefill.lieu ?? '')); setCapacityMax(String(prefill.nb_participants_max ?? '')); setFormationCode(String(prefill.formation_code ?? ''));
    setSubmitError('');
  }, [isOpen]);

  if (!isOpen) return null;

  const availableTrainers = formateurs.filter((trainer) => trainer.statut === 'Disponible');

  const handleMarketChange = (marketId: string) => {
    setSelectedMarketId(marketId);
    if (!marketId) {
      setIntitule('');
      setClient('');
      return;
    }
    const market = acceptedMarkets.find((item) => item.id === marketId);
    if (market) {
      setIntitule(market.titre);
      setClient(market.clientCible ?? '');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!intitule) return;

    setIsSubmitting(true);
    setSubmitError('');
    try {
      const trainer = availableTrainers.find((item) => item.id === formateurId);
      await onSubmit({
        intitule,
        client,
        formateurId,
        formateur: trainer ? [trainer.prenom, trainer.nom].filter(Boolean).join(' ') : '',
        dates,
        dateFin,
        lieu,
        capacityMax: capacityMax ? Number(capacityMax) : undefined,
        formationCode: formationCode.trim() || undefined,
        participantsInscrits: 0
      });
      onClose();
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'La création de la session a échoué.');
    } finally {
      setIsSubmitting(false);
    }
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
            <label className="block font-bold text-slate-700 uppercase mb-1">Partir d'un marché accepté (facultatif)</label>
            <select
              value={selectedMarketId}
              onChange={(e) => handleMarketChange(e.target.value)}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
            >
              <option value="">Saisie manuelle d'une formation</option>
              {acceptedMarkets.map((market) => (
                <option key={market.id} value={market.id}>{market.titre}</option>
              ))}
            </select>
          </div>

          <label className="block font-bold text-slate-700 uppercase">Code formation (facultatif)<input value={formationCode} onChange={e=>setFormationCode(e.target.value)} placeholder="Ex. IA-2026" className="mt-1 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-normal normal-case" /></label>

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
              <label className="block font-bold text-slate-700 uppercase mb-1">Client / organisme</label>
              <input
                type="text"
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="Nom du client"
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Formateur disponible (optionnel)</label>
              <select
                value={formateurId}
                onChange={(e) => setFormateurId(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              >
                <option value="">À définir</option>
                {availableTrainers.map((trainer) => (
                  <option key={trainer.id} value={trainer.id}>
                    {[trainer.prenom, trainer.nom].filter(Boolean).join(' ')}{trainer.recommandation === 'Oui' ? ' · Recommandé' : trainer.recommandation === 'Conditionnel' ? ' · À confirmer' : ''}{trainer.scoreMoyen != null ? ` · ${Math.round(trainer.scoreMoyen)}/100` : ''}{trainer.specialite ? ` · ${trainer.specialite}` : ''}
                  </option>
                ))}
              </select>
              {availableTrainers.length === 0 && (
                <p className="mt-1 text-[11px] text-slate-500">Aucun formateur disponible enregistré.</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block font-bold text-slate-700 uppercase">Lieu<input value={lieu} onChange={e => setLieu(e.target.value)} placeholder="Antananarivo / en ligne" className="mt-1 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-normal normal-case" /></label>
            <label className="block font-bold text-slate-700 uppercase">Capacité maximale<input type="number" min="1" max="500" value={capacityMax} onChange={e => setCapacityMax(e.target.value)} placeholder="30" className="mt-1 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-normal normal-case" /></label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Date de début *</label>
              <input
                type="date"
                required
                value={dates}
                onChange={(e) => setDates(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
            <div>
              <label className="block font-bold text-slate-700 uppercase mb-1">Date de fin (optionnelle)</label>
              <input
                type="date"
                value={dateFin}
                min={dates || undefined}
                onChange={(e) => setDateFin(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-sm text-slate-800"
              />
            </div>
          </div>

          {submitError && <p role="alert" className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{submitError}</p>}

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
