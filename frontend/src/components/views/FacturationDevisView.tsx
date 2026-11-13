import React, { useState } from 'react';
import { ReceiptText, Plus, Download, Search, ChevronDown, CreditCard, History, X, Check, Loader2, Sparkles } from 'lucide-react';
import { DevisFacture, MenuSection, Session } from '../../types';
import { apiService } from '../../services/api';

interface FacturationDevisViewProps {
  factures: DevisFacture[];
  sessions: Session[];
  onOpenNewInvoice: () => void;
  onRefreshData?: () => Promise<void> | void;
  onNavigateToSection?: (section: MenuSection) => void;
}

export const FacturationDevisView: React.FC<FacturationDevisViewProps> = ({
  factures,
  sessions,
  onOpenNewInvoice,
  onRefreshData,
  onNavigateToSection
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [paymentTarget, setPaymentTarget] = useState<DevisFacture | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [paymentMode, setPaymentMode] = useState('VIREMENT');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reminderHistory, setReminderHistory] = useState<Record<string, any[]>>({});
  const [historyBusyId, setHistoryBusyId] = useState<string | null>(null);
  const [reminderPreview, setReminderPreview] = useState<any | null>(null);
  const exportFile = async (format: 'csv' | 'excel' | 'pdf') => {
    try {
      const blob = await apiService.exportAccounting(format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `export-comptable.${format === 'excel' ? 'xlsx' : format}`; link.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof Error ? e.message : 'Export impossible.'); }
  };
  const downloadInvoice = async (item: DevisFacture) => {
    setBusyId(item.id); setError('');
    try {
      const blob = await apiService.downloadInvoicePdf(item.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `${item.numero.replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof Error ? e.message : 'Le téléchargement de la facture a échoué.'); }
    finally { setBusyId(null); }
  };
  const addPayment = async (item: DevisFacture) => {
    setPaymentTarget(item); setPaymentAmount(String(item.montantRestantDu ?? item.montantTTC)); setPaymentDate(new Date().toISOString().slice(0, 10)); setError('');
  };
  const savePayment = async (event: React.FormEvent) => {
    event.preventDefault(); if (!paymentTarget) return;
    const amount = Number(paymentAmount); const remaining = paymentTarget.montantRestantDu ?? paymentTarget.montantTTC;
    if (!Number.isFinite(amount) || amount <= 0 || amount > remaining) { setError(`Le paiement doit être positif et ne pas dépasser le solde de ${remaining.toLocaleString('fr-FR')} Ar.`); return; }
    setBusyId(paymentTarget.id); setError('');
    try { await apiService.saveInvoicePayment(paymentTarget.id, { montant: amount, date: paymentDate, mode: paymentMode }); setPaymentTarget(null); await onRefreshData?.(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Paiement impossible.'); }
    finally { setBusyId(null); }
  };
  const generateReminder = async (item: DevisFacture) => {
    setBusyId(item.id); setError(''); setNotice('');
    try {
      const result = await apiService.generateInvoiceReminder(item.id);
      if (result.data?.necessaire === false || result.necessaire === false) { setNotice(result.message ?? result.data?.raison ?? 'Aucune relance nécessaire.'); return; }
      const reviewId = result.review_id ?? result.data?._review_id ?? result._review_id;
      if (!reviewId) throw new Error(result.message ?? 'Le backend n’a pas retourné l’identifiant de validation.');
      const reviewResult = await apiService.getReview(String(reviewId));
      const review = reviewResult.review ?? reviewResult.data ?? reviewResult;
      setReminderPreview({ invoice: item, review: { ...review, review_id: review.review_id ?? reviewId } });
    } catch (e) { setError(e instanceof Error ? e.message : 'La relance IA n’a pas pu être générée.'); }
    finally { setBusyId(null); }
  };

  const toggleDetails = async (item: DevisFacture) => {
    if (expandedId === item.id) { setExpandedId(null); return; }
    setExpandedId(item.id);
    if (reminderHistory[item.id]) return;
    setHistoryBusyId(item.id);
    try { const history = await apiService.getInvoiceReminders(item.id); setReminderHistory(prev => ({ ...prev, [item.id]: history })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Impossible de charger l’historique des relances.'); }
    finally { setHistoryBusyId(null); }
  };

  const openReminderReview = () => {
    const id = reminderPreview?.review?.review_id ?? reminderPreview?.review?.id;
    if (!id) return;
    try { sessionStorage.setItem('formaia-review-focus', String(id)); } catch { /* stockage indisponible */ }
    setReminderPreview(null);
    onNavigateToSection?.('espace_ia');
  };

  const filtered = factures.filter(
    (f) =>
      f.client.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.numero.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPaye = factures.reduce((sum, invoice) => sum + (invoice.montantPaye ?? (invoice.statut === 'Payé' ? invoice.montantTTC : 0)), 0);
  const totalEnAttente = factures.filter(invoice => invoice.statut !== 'Annulée').reduce((sum, invoice) => sum + (invoice.montantRestantDu ?? Math.max(0, invoice.montantTTC - (invoice.montantPaye ?? 0))), 0);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-gold/15 text-brand-navy">
              M7 — Facturation IA
            </span>
            <span className="text-xs text-slate-400">· Devis · Règlements · Relances IA automatiques</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Facturation & Devis</h1>
          <p className="text-slate-600 text-xs mt-1">
            Calculez les montants par IA, générez les relances automatiquement et suivez les règlements.
          </p>
        </div>

        <div className="flex gap-2 flex-wrap">
        <button
          onClick={onOpenNewInvoice}
          className="px-4 py-2.5 bg-[#0B1F4D] hover:bg-[#06132F] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors shrink-0"
        >
          <Plus size={16} />
          <span>Créer un devis ou une facture</span>
        </button>
        <div className="flex gap-1.5">{(['csv','excel','pdf'] as const).map(format => <button key={format} onClick={() => exportFile(format)} className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-[11px] font-bold">{format.toUpperCase()}</button>)}</div>
        </div>
      </div>

      {error && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{error}</div>}
      {notice && <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">{notice}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <div className="text-xs font-bold text-slate-500 uppercase">Paiements reçus (TTC)</div>
          <div className="text-2xl font-extrabold text-emerald-600 mt-1">{totalPaye.toLocaleString()} Ar</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <div className="text-xs font-bold text-slate-500 uppercase">Montant restant dû</div>
          <div className="text-2xl font-extrabold text-amber-600 mt-1">{totalEnAttente.toLocaleString()} Ar</div>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Rechercher par client ou numéro de facture/devis..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
        />
      </div>

      <div className="space-y-3">
        {filtered.map(item => {
          const paid = item.montantPaye ?? (item.statut === 'Payé' ? item.montantTTC : 0);
          const remaining = item.montantRestantDu ?? Math.max(0, item.montantTTC - paid);
          const statusStyle: Record<string, string> = {
            'Brouillon': 'bg-slate-100 text-slate-700 border-slate-200',
            'Envoyé': 'bg-blue-50 text-blue-700 border-blue-200',
            'En attente': 'bg-blue-50 text-blue-700 border-blue-200',
            'Partiellement payé': 'bg-amber-50 text-amber-800 border-amber-200',
            'En retard': 'bg-orange-50 text-orange-800 border-orange-200',
            'Payé': 'bg-emerald-50 text-emerald-700 border-emerald-200',
            'Annulée': 'bg-slate-100 text-slate-500 border-slate-200',
          };
          const session = sessions.find(value => value.id === item.sessionId);
          const payments = item.paiements ?? [];
          return <article key={item.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
            <div className="grid gap-4 p-4 lg:grid-cols-[1.2fr_1fr_0.8fr_1fr_auto] lg:items-center">
              <div><div className="font-mono text-sm font-extrabold text-[#11162A]">{item.numero}</div><div className="mt-1 text-[11px] text-slate-500">{item.type}{session ? ` · ${session.titre}` : ''}</div></div>
              <div><div className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Client</div><div className="mt-1 font-bold text-slate-800">{item.client}</div></div>
              <div><div className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Total TTC</div><div className="mt-1 font-extrabold text-[#11162A]">{item.montantTTC.toLocaleString('fr-FR')} Ar</div></div>
              <div><span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-bold ${statusStyle[item.statut] ?? statusStyle['Envoyé']}`}>{item.statut}</span><div className="mt-1 text-[11px] text-slate-500">{item.dateEcheance ? `Échéance : ${new Date(item.dateEcheance).toLocaleDateString('fr-FR')}` : 'Échéance non renseignée'}</div><div className="mt-1 text-[11px] font-semibold text-slate-600">Reçu {paid.toLocaleString('fr-FR')} Ar · dû <span className={remaining > 0 ? 'text-orange-700' : 'text-emerald-700'}>{remaining.toLocaleString('fr-FR')} Ar</span></div></div>
              <div className="flex flex-wrap items-center gap-1.5 lg:justify-end">
                <button onClick={() => toggleDetails(item)} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50"><History size={14}/>Historique<ChevronDown size={13} className={expandedId === item.id ? 'rotate-180' : ''}/></button>
                {remaining > 0 && item.statut !== 'Annulée' && <button onClick={() => addPayment(item)} disabled={busyId === item.id} className="inline-flex items-center gap-1 rounded-lg bg-[#0B1F4D] px-2.5 py-2 text-[11px] font-bold text-white disabled:opacity-50"><CreditCard size={14}/>Paiement</button>}
                {item.statut === 'En retard' && <button onClick={() => generateReminder(item)} disabled={busyId === item.id} className="inline-flex items-center gap-1 rounded-lg bg-indigo-50 px-2.5 py-2 text-[11px] font-bold text-indigo-700 disabled:opacity-50">{busyId === item.id ? <Loader2 size={14} className="animate-spin"/> : <Sparkles size={14}/>}Relance IA</button>}
                <button onClick={() => downloadInvoice(item)} disabled={busyId === item.id} className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-[#0B1F4D] hover:text-[#0B1F4D] disabled:opacity-50" title={`Télécharger la facture ${item.numero} en PDF`}>{busyId === item.id ? <Loader2 size={15} className="animate-spin"/> : <Download size={15}/>}</button>
              </div>
            </div>
            {expandedId === item.id && <div className="grid gap-4 border-t border-slate-100 bg-slate-50/70 p-4 md:grid-cols-2">
              <section><h3 className="mb-2 flex items-center gap-2 text-xs font-extrabold text-[#11162A]"><CreditCard size={14}/>Paiements partiels</h3>{payments.length ? <div className="space-y-2">{payments.map((payment: any, index: number) => <div key={payment.id ?? index} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"><span className="text-slate-600">{payment.date ? new Date(payment.date).toLocaleDateString('fr-FR') : 'Date non renseignée'} · {payment.mode ?? 'Mode non précisé'}</span><strong className="text-emerald-700">{Number(payment.montant ?? 0).toLocaleString('fr-FR')} Ar</strong></div>)}</div> : <p className="text-xs text-slate-500">Aucun paiement enregistré.</p>}</section>
              <section><h3 className="mb-2 flex items-center gap-2 text-xs font-extrabold text-[#11162A]"><History size={14}/>Historique des relances IA</h3>{historyBusyId === item.id ? <Loader2 size={16} className="animate-spin text-slate-400"/> : reminderHistory[item.id]?.length ? <div className="space-y-2">{reminderHistory[item.id].map((entry: any, index: number) => <div key={entry.id ?? index} className="rounded-lg border border-slate-200 bg-white p-3 text-xs"><div className="flex justify-between gap-2"><strong>{entry.niveau ?? entry.type ?? 'Relance'}</strong><span className="text-slate-500">{entry.date ? new Date(entry.date).toLocaleDateString('fr-FR') : ''}</span></div><p className="mt-1 whitespace-pre-wrap text-slate-600">{entry.texte ?? entry.contenu ?? entry.message ?? 'Relance validée'}</p></div>)}</div> : <p className="text-xs text-slate-500">Aucune relance enregistrée.</p>}</section>
            </div>}
          </article>;
        })}
        {filtered.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><ReceiptText size={28} className="mx-auto text-slate-300"/><p className="mt-3 text-sm font-bold text-slate-600">Aucune facture trouvée</p><p className="mt-1 text-xs text-slate-400">Créez une facture ou modifiez votre recherche.</p></div>}
      </div>

      {paymentTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="payment-title"><form onSubmit={savePayment} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between"><div><h2 id="payment-title" className="text-lg font-extrabold text-[#11162A]">Enregistrer un paiement</h2><p className="mt-1 text-xs text-slate-500">Facture {paymentTarget.numero} · solde {(paymentTarget.montantRestantDu ?? paymentTarget.montantTTC).toLocaleString('fr-FR')} Ar</p></div><button type="button" onClick={() => setPaymentTarget(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button></div>
        <label className="block text-xs font-bold text-slate-600">Montant payé (Ar)<input type="number" min="1" max={paymentTarget.montantRestantDu ?? paymentTarget.montantTTC} step="0.01" required value={paymentAmount} onChange={e => setPaymentAmount(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800"/></label>
        <div className="grid grid-cols-2 gap-3"><label className="block text-xs font-bold text-slate-600">Date<input type="date" required value={paymentDate} onChange={e => setPaymentDate(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800"/></label><label className="block text-xs font-bold text-slate-600">Mode<select value={paymentMode} onChange={e => setPaymentMode(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800"><option>VIREMENT</option><option>ESPECES</option><option>CHEQUE</option><option>MOBILE_MONEY</option><option>AUTRE</option></select></label></div>
        {error && <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700">{error}</p>}<button disabled={busyId === paymentTarget.id} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0B1F4D] px-4 py-3 text-xs font-bold text-white disabled:opacity-50">{busyId === paymentTarget.id ? <Loader2 size={15} className="animate-spin"/> : <Check size={15}/>}Enregistrer le paiement</button>
      </form></div>}

      {reminderPreview && <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="reminder-title"><div className="my-auto w-full max-w-2xl space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between"><div><span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold uppercase text-indigo-700"><Sparkles size={12}/>Validation humaine M7</span><h2 id="reminder-title" className="mt-2 text-xl font-extrabold text-[#11162A]">Aperçu de la relance</h2><p className="mt-1 text-xs text-slate-500">{reminderPreview.invoice.numero} · {reminderPreview.invoice.client}</p></div><button type="button" onClick={() => setReminderPreview(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button></div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4"><div className="mb-2 flex flex-wrap gap-2"><span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-indigo-700">{reminderPreview.review.niveau ?? 'Relance'}</span>{reminderPreview.review.objet && <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{reminderPreview.review.objet}</span>}</div><div className="max-h-[45vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{reminderPreview.review.texte ?? reminderPreview.review.contenu ?? JSON.stringify(reminderPreview.review, null, 2)}</div></div>
        <div className="flex justify-end"><button type="button" onClick={openReminderReview} className="rounded-xl bg-[#0B1F4D] px-4 py-2.5 text-xs font-bold text-white">Vérifier et valider dans l’Espace IA</button></div>
      </div></div>}
    </div>
  );
};
