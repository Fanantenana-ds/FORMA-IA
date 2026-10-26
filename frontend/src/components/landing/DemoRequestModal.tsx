import React, { useEffect, useState } from 'react';

interface DemoRequestModalProps {
  open: boolean;
  onClose: () => void;
}

const MODULE_OPTIONS = [
  "Veille marché & Appels d'offres",
  'Génération de TDR',
  'Offres technique & financière',
  'Planification & Budget',
  'Émargement QR & Attestations',
  'Base documentaire RAG',
];
const DEFAULT_SELECTED = ["Veille marché & Appels d'offres", 'Génération de TDR', 'Base documentaire RAG'];

const INPUT_CLS =
  'w-full px-3.5 py-2.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-gold focus:border-brand-gold text-slate-800 bg-white placeholder-slate-400';
const LABEL_CLS = 'block text-xs font-semibold text-brand-darkNavy uppercase tracking-wider mb-1.5';

export const DemoRequestModal: React.FC<DemoRequestModalProps> = ({ open, onClose }) => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [org, setOrg] = useState('');
  const [size, setSize] = useState('50-200');
  const [notes, setNotes] = useState('');
  const [modules, setModules] = useState<string[]>(DEFAULT_SELECTED);
  const [submitted, setSubmitted] = useState(false);

  // Verrouille le scroll + Échap pour fermer
  useEffect(() => {
    if (!open) return;
    document.body.classList.add('overflow-hidden');
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.classList.remove('overflow-hidden');
      window.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const toggleModule = (m: string) =>
    setModules((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  const handleClose = () => {
    onClose();
    // Réinitialise le formulaire après la fermeture d'une confirmation
    if (submitted) {
      setSubmitted(false);
      setFirstName(''); setLastName(''); setEmail(''); setPhone(''); setOrg(''); setNotes('');
      setSize('50-200');
      setModules(DEFAULT_SELECTED);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="demo-modal-title"
      className="fixed inset-0 z-[60] flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
    >
      <div className="fixed inset-0 bg-brand-darkNavy/80 backdrop-blur-md transition-opacity duration-300" onClick={handleClose} />

      <div className="relative bg-white rounded-2xl shadow-2xl border border-slate-200/80 max-w-2xl w-full max-h-[92vh] overflow-y-auto z-10 my-auto text-left">
        {/* Header */}
        <div className="bg-linear-to-r from-brand-navy via-[#0A183D] to-brand-darkNavy px-6 sm:px-8 pt-7 pb-6 text-white relative rounded-t-2xl border-b border-brand-gold/20">
          <div className="absolute -right-10 -top-10 w-44 h-44 bg-brand-gold/20 rounded-full blur-2xl pointer-events-none" />
          <button
            type="button"
            aria-label="Fermer"
            onClick={handleClose}
            className="absolute top-4 right-4 text-slate-300 hover:text-white bg-white/10 hover:bg-white/20 p-2 rounded-full transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
          </button>
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-gold/15 border border-brand-gold/30 text-brand-gold text-[11px] font-bold uppercase tracking-wider mb-2.5">
            <span>✨ DÉMO PERSONNALISÉE</span>
          </div>
          <h3 id="demo-modal-title" className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Découvrez la puissance de FORMA-IA
          </h3>
          <p className="mt-2 text-xs sm:text-sm text-slate-300 leading-relaxed">
            Planifiez une présentation guidée de 30 minutes adaptée aux besoins de votre cabinet ou institution à Madagascar et en Afrique.
          </p>
        </div>

        <div className="p-6 sm:p-8">
          {!submitted ? (
            <form className="space-y-5" onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-firstname">Prénom *</label>
                  <input id="demo-firstname" required type="text" placeholder="Ex. Andry" className={INPUT_CLS} value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                </div>
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-lastname">Nom de famille *</label>
                  <input id="demo-lastname" required type="text" placeholder="Ex. RAKOTO" className={INPUT_CLS} value={lastName} onChange={(e) => setLastName(e.target.value)} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-email">Email professionnel *</label>
                  <input id="demo-email" required type="email" placeholder="contact@organisme.mg" className={INPUT_CLS} value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-phone">Téléphone / WhatsApp *</label>
                  <input id="demo-phone" required type="tel" placeholder="+261 34 00 000 00" className={INPUT_CLS} value={phone} onChange={(e) => setPhone(e.target.value)} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-org">Organisation / Cabinet / Entreprise *</label>
                  <input id="demo-org" required type="text" placeholder="Nom de votre structure" className={INPUT_CLS} value={org} onChange={(e) => setOrg(e.target.value)} />
                </div>
                <div>
                  <label className={LABEL_CLS} htmlFor="demo-size">Volume annuel d'apprenants</label>
                  <select id="demo-size" className={INPUT_CLS} value={size} onChange={(e) => setSize(e.target.value)}>
                    <option value="1-50">&lt; 50 apprenants / an</option>
                    <option value="50-200">50 - 200 apprenants / an</option>
                    <option value="200-500">200 - 500 apprenants / an</option>
                    <option value="500+">Plus de 500 apprenants / an</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-brand-darkNavy uppercase tracking-wider mb-2">
                  Modules prioritaires à explorer lors de la démo
                </label>
                <div className="flex flex-wrap gap-2">
                  {MODULE_OPTIONS.map((m) => {
                    const selected = modules.includes(m);
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => toggleModule(m)}
                        aria-pressed={selected}
                        className={`text-xs font-medium px-3 py-1.5 rounded-full border transition flex items-center space-x-1.5 ${
                          selected
                            ? 'border-brand-gold bg-brand-gold/15 text-brand-darkNavy'
                            : 'border-slate-200 bg-slate-50 text-gray-700 hover:border-brand-gold'
                        }`}
                      >
                        <span className={selected ? 'font-bold' : undefined}>{selected ? '✓' : '+'}</span>
                        <span>{m}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className={LABEL_CLS} htmlFor="demo-notes">Vos objectifs ou questions spécifiques (facultatif)</label>
                <textarea
                  id="demo-notes"
                  rows={2}
                  placeholder="Ex. Nous souhaitons automatiser l'élaboration de nos TDR et la délivrance des attestations QR..."
                  className={INPUT_CLS}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-3.5 px-6 rounded-xl font-bold text-base text-brand-darkNavy bg-linear-to-r from-brand-gold via-amber-400 to-brand-goldDark shadow-lg shadow-brand-gold/30 hover:brightness-110 transform hover:-translate-y-0.5 transition flex items-center justify-center space-x-2"
                >
                  <span>Confirmer ma demande de démo</span>
                  <svg className="w-5 h-5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M13 7l5 5m0 0l-5 5m5-5H6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                  </svg>
                </button>
                <p className="text-[11px] text-center text-gray-500 mt-2.5 flex items-center justify-center space-x-1">
                  <svg className="w-3.5 h-3.5 text-brand-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                  </svg>
                  <span>Données confidentielles. Aucun engagement commercial requis.</span>
                </p>
              </div>
            </form>
          ) : (
            <div className="py-8 px-4 text-center space-y-5">
              <div className="w-16 h-16 rounded-full bg-emerald-500/10 border-2 border-emerald-500 text-emerald-600 mx-auto flex items-center justify-center shadow-lg">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
                </svg>
              </div>
              <div className="space-y-2">
                <h4 className="text-2xl font-black text-brand-darkNavy">Demande bien reçue !</h4>
                <p className="text-sm text-gray-600 max-w-md mx-auto leading-relaxed">
                  Merci <strong className="text-brand-darkNavy">{firstName} {lastName}</strong>. Votre demande de démo personnalisée pour{' '}
                  <strong className="text-brand-darkNavy">{org || 'votre organisation'}</strong> a été transmise avec succès.
                </p>
                <p className="text-xs text-brand-goldDark font-semibold">
                  Un conseiller ALTIORA PREST vous contactera sous 24h ouvrées pour caler votre créneau de démonstration.
                </p>
              </div>
              <div className="pt-4">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-6 py-2.5 rounded-lg text-sm font-bold bg-brand-navy text-white hover:bg-brand-darkNavy transition shadow-md"
                >
                  Fermer la fenêtre
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
