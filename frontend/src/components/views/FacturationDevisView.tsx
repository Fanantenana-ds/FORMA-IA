import React, { useState, useMemo } from 'react';
import { ReceiptText, Plus, Download, Search, ChevronDown, CreditCard, History, X, Check, Loader2, Sparkles, AlertTriangle, ArrowUpDown, Eye } from 'lucide-react';
import { PageHeader } from '../PageHeader';
import { DevisFacture, MenuSection, Session } from '../../types';
import { apiService } from '../../services/api';
import { ConfirmDialog, useConfirmDialog } from '../ConfirmDialog';

interface FacturationDevisViewProps {
  factures: DevisFacture[];
  sessions: Session[];
  onOpenNewInvoice: () => void;
  onRefreshData?: () => Promise<void> | void;
  onNavigateToSection?: (section: MenuSection) => void;
}

type StatusFilter = 'Toutes' | 'Envoyé' | 'Partiellement payé' | 'En retard' | 'Payé' | 'Annulée';
type SortKey = 'date' | 'montant' | 'echeance';

export const FacturationDevisView: React.FC<FacturationDevisViewProps> = ({
  factures,
  sessions,
  onOpenNewInvoice,
  onRefreshData,
  onNavigateToSection
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('Toutes');
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reminderBusyId, setReminderBusyId] = useState<string | null>(null);
  const [paymentTarget, setPaymentTarget] = useState<DevisFacture | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [paymentMode, setPaymentMode] = useState('VIREMENT');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reminderHistory, setReminderHistory] = useState<Record<string, any[]>>({});
  const [historyBusyId, setHistoryBusyId] = useState<string | null>(null);
  const [reminderPreview, setReminderPreview] = useState<any | null>(null);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewBusyId, setPdfPreviewBusyId] = useState<string | null>(null);
  const { confirm, dialogProps } = useConfirmDialog();

  const exportFile = async (format: 'csv' | 'excel' | 'pdf') => {
    try {
      const blob = await apiService.exportAccounting(format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `export-comptable.${format === 'excel' ? 'xlsx' : format}`; link.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof Error ? e.message : 'Export impossible.'); }
  };

  const previewInvoice = async (item: DevisFacture) => {
    setPdfPreviewBusyId(item.id); setError('');
    try {
      const blob = await apiService.downloadInvoicePdf(item.id);
      const url = URL.createObjectURL(blob);
      setPdfPreviewUrl(url);
    } catch (e) { setError(e instanceof Error ? e.message : "L'aperçu de la facture a échoué."); }
    finally { setPdfPreviewBusyId(null); }
  };

  const closePdfPreview = () => {
    if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewUrl(null);
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

  const emitInvoice = async (item: DevisFacture) => {
    setBusyId(item.id); setError('');
    try {
      await apiService.updateFactureStatus(item.id, 'Envoyé');
      await onRefreshData?.();
      setNotice(`Facture ${item.numero} émise.`);
    } catch (e) { setError(e instanceof Error ? e.message : "L'émission a échoué."); }
    finally { setBusyId(null); }
  };

  const cancelInvoice = async (item: DevisFacture) => {
    const ok = await confirm({
      title: "Annuler la facture",
      message: `La facture ${item.numero} (${item.client}) sera marquée comme annulée. Cette action est irréversible.`,
      confirmLabel: 'Annuler la facture',
      variant: 'danger',
    });
    if (!ok) return;
    setBusyId(item.id); setError('');
    try {
      await apiService.updateFactureStatus(item.id, 'Annulée');
      await onRefreshData?.();
      setNotice(`Facture ${item.numero} annulée.`);
    } catch (e) { setError(e instanceof Error ? e.message : "L'annulation a échoué."); }
    finally { setBusyId(null); }
  };

  const generateReminder = async (item: DevisFacture) => {
    setReminderBusyId(item.id); setError(''); setNotice('');
    try {
      const result = await apiService.generateInvoiceReminder(item.id);
      if (result.data?.necessaire === false || result.necessaire === false) { setNotice(result.message ?? result.data?.raison ?? 'Aucune relance nécessaire.'); return; }
      const reviewId = result.review_id ?? result.data?._review_id ?? result._review_id;
      if (!reviewId) throw new Error(result.message ?? "Le backend n'a pas retourné l'identifiant de validation.");
      const reviewResult = await apiService.getReview(String(reviewId));
      const review = reviewResult.review ?? reviewResult.data ?? reviewResult;
      setReminderPreview({ invoice: item, review: { ...review, review_id: review.review_id ?? reviewId } });
    } catch (e) { setError(e instanceof Error ? e.message : "La relance IA n'a pas pu être générée."); }
    finally { setReminderBusyId(null); }
  };

  const toggleDetails = async (item: DevisFacture) => {
    if (expandedId === item.id) { setExpandedId(null); return; }
    setExpandedId(item.id);
    if (reminderHistory[item.id]) return;
    setHistoryBusyId(item.id);
    try { const history = await apiService.getInvoiceReminders(item.id); setReminderHistory(prev => ({ ...prev, [item.id]: history })); }
    catch (e) { setError(e instanceof Error ? e.message : "Impossible de charger l'historique des relances."); }
    finally { setHistoryBusyId(null); }
  };

  const openReminderReview = () => {
    const id = reminderPreview?.review?.review_id ?? reminderPreview?.review?.id;
    if (!id) return;
    try { sessionStorage.setItem('formaia-review-focus', String(id)); } catch { /* stockage indisponible */ }
    setReminderPreview(null);
    onNavigateToSection?.('espace_ia');
  };

  // KPIs
  const totalPaye = factures.reduce((sum, f) => sum + (f.montantPaye ?? (f.statut === 'Payé' ? f.montantTTC : 0)), 0);
  const totalDu = factures.filter(f => f.statut !== 'Annulée').reduce((sum, f) => sum + (f.montantRestantDu ?? Math.max(0, f.montantTTC - (f.montantPaye ?? 0))), 0);
  const retardCount = factures.filter(f => f.statut === 'En retard').length;
  const retardMontant = factures.filter(f => f.statut === 'En retard').reduce((sum, f) => sum + (f.montantRestantDu ?? f.montantTTC), 0);

  // Status filter counts
  const statusCounts: Record<StatusFilter, number> = useMemo(() => ({
    'Toutes': factures.length,
    'Envoyé': factures.filter(f => f.statut === 'Envoyé').length,
    'Partiellement payé': factures.filter(f => f.statut === 'Partiellement payé').length,
    'En retard': factures.filter(f => f.statut === 'En retard').length,
    'Payé': factures.filter(f => f.statut === 'Payé').length,
    'Annulée': factures.filter(f => f.statut === 'Annulée').length,
  }), [factures]);

  const filtered = useMemo(() => {
    let list = factures.filter(f =>
      (f.client.toLowerCase().includes(searchTerm.toLowerCase()) || f.numero.toLowerCase().includes(searchTerm.toLowerCase())) &&
      (statusFilter === 'Toutes' || f.statut === statusFilter)
    );
    if (sortKey === 'montant') list = [...list].sort((a, b) => b.montantTTC - a.montantTTC);
    else if (sortKey === 'echeance') list = [...list].sort((a, b) => (a.dateEcheance ?? '').localeCompare(b.dateEcheance ?? ''));
    else list = [...list].sort((a, b) => (b.dateEmission ?? '').localeCompare(a.dateEmission ?? ''));
    return list;
  }, [factures, searchTerm, statusFilter, sortKey]);

  const statusChips: { key: StatusFilter; label: string; active: string; inactive: string }[] = [
    { key: 'Toutes', label: 'Toutes', active: 'bg-[#11162A] text-white', inactive: 'bg-white text-slate-600 border-slate-200' },
    { key: 'Envoyé', label: 'Émises', active: 'bg-blue-700 text-white', inactive: 'bg-white text-blue-700 border-blue-200' },
    { key: 'Partiellement payé', label: 'Partielles', active: 'bg-amber-600 text-white', inactive: 'bg-white text-amber-700 border-amber-200' },
    { key: 'En retard', label: 'En retard', active: 'bg-orange-600 text-white', inactive: 'bg-white text-orange-700 border-orange-200' },
    { key: 'Payé', label: 'Payées', active: 'bg-emerald-700 text-white', inactive: 'bg-white text-emerald-700 border-emerald-200' },
    { key: 'Annulée', label: 'Annulées', active: 'bg-slate-600 text-white', inactive: 'bg-white text-slate-500 border-slate-200' },
  ];

  const statusStyle: Record<string, string> = {
    'Brouillon': 'bg-slate-100 text-slate-700 border-slate-200',
    'Envoyé': 'bg-blue-50 text-blue-700 border-blue-200',
    'En attente': 'bg-blue-50 text-blue-700 border-blue-200',
    'Partiellement payé': 'bg-amber-50 text-amber-800 border-amber-200',
    'En retard': 'bg-orange-50 text-orange-800 border-orange-200',
    'Payé': 'bg-emerald-50 text-emerald-700 border-emerald-200',
    'Annulée': 'bg-slate-100 text-slate-500 border-slate-200',
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <ConfirmDialog {...dialogProps} />
      <PageHeader
        icon={<ReceiptText size={22} />}
        badge="M7 — Facturation IA"
        title="Facturation & Devis"
        subtitle="Calculez les montants par IA, générez les relances automatiquement et suivez les règlements."
        actions={
          <div className="flex items-center gap-2">
            <button onClick={onOpenNewInvoice} className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25 transition-colors cursor-pointer">
              <Plus size={14} /><span>Nouveau devis / facture</span>
            </button>
            <div className="flex gap-1">{(['csv','excel','pdf'] as const).map(format => <button key={format} onClick={() => exportFile(format)} className="px-2.5 py-1.5 rounded-lg border border-white/15 bg-white/10 text-white/70 text-[10px] font-bold hover:bg-white/20">{format.toUpperCase()}</button>)}</div>
          </div>
        }
      />

      {error && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold">{error}</div>}
      {notice && <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">{notice}</div>}

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Encaissé */}
        <div className="relative overflow-hidden rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-5 shadow-sm">
          <div className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-100">
            <Check size={16} className="text-emerald-700"/>
          </div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-emerald-700">Encaissé TTC</div>
          <div className="mt-2 text-3xl font-black tabular-nums text-emerald-800">{totalPaye.toLocaleString('fr-FR')} <span className="text-lg font-bold">Ar</span></div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-600">
            <span className="font-bold">{factures.filter(f => f.statut === 'Payé').length}</span> facture{factures.filter(f => f.statut === 'Payé').length > 1 ? 's' : ''} soldée{factures.filter(f => f.statut === 'Payé').length > 1 ? 's' : ''}
          </div>
          {(totalPaye + totalDu) > 0 && (
            <div className="mt-3">
              <div className="mb-1 flex justify-between text-[10px] text-emerald-600">
                <span>Taux de recouvrement</span>
                <strong>{Math.round(totalPaye / (totalPaye + totalDu) * 100)} %</strong>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-emerald-100">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{width: `${Math.round(totalPaye / (totalPaye + totalDu) * 100)}%`}}/>
              </div>
            </div>
          )}
        </div>
        {/* Restant dû */}
        <div className="relative overflow-hidden rounded-2xl border border-amber-100 bg-gradient-to-br from-amber-50 to-white p-5 shadow-sm">
          <div className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-xl bg-amber-100">
            <CreditCard size={16} className="text-amber-700"/>
          </div>
          <div className="text-[10px] font-extrabold uppercase tracking-widest text-amber-700">Reste à encaisser</div>
          <div className="mt-2 text-3xl font-black tabular-nums text-amber-800">{totalDu.toLocaleString('fr-FR')} <span className="text-lg font-bold">Ar</span></div>
          <div className="mt-2 text-[11px] text-amber-600">
            <span className="font-bold">{factures.filter(f => f.statut !== 'Payé' && f.statut !== 'Annulée').length}</span> facture{factures.filter(f => f.statut !== 'Payé' && f.statut !== 'Annulée').length > 1 ? 's' : ''} en cours
          </div>
          <div className="mt-3 text-[10px] text-amber-500">Paiements partiels · virement · mobile money</div>
        </div>
        {/* En retard */}
        <div className={`relative overflow-hidden rounded-2xl border p-5 shadow-sm ${retardCount > 0 ? 'border-orange-200 bg-gradient-to-br from-orange-50 to-white' : 'border-slate-100 bg-gradient-to-br from-slate-50 to-white'}`}>
          <div className={`absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-xl ${retardCount > 0 ? 'bg-orange-100' : 'bg-slate-100'}`}>
            <AlertTriangle size={16} className={retardCount > 0 ? 'text-orange-700' : 'text-slate-400'}/>
          </div>
          <div className={`text-[10px] font-extrabold uppercase tracking-widest ${retardCount > 0 ? 'text-orange-700' : 'text-slate-400'}`}>Factures en retard</div>
          <div className={`mt-2 text-3xl font-black tabular-nums ${retardCount > 0 ? 'text-orange-800' : 'text-slate-300'}`}>{retardCount}</div>
          <div className={`mt-2 text-[11px] font-semibold ${retardCount > 0 ? 'text-orange-700' : 'text-slate-400'}`}>
            {retardCount > 0 ? `${retardMontant.toLocaleString('fr-FR')} Ar à recouvrer — relance IA disponible` : 'Aucun impayé en retard'}
          </div>
          {retardCount > 0 && <div className="mt-3 inline-flex items-center gap-1 rounded-full bg-orange-100 px-2.5 py-1 text-[10px] font-bold text-orange-700"><AlertTriangle size={10}/>Action requise</div>}
        </div>
      </div>

      {/* Filtres par statut */}
      <div className="flex flex-wrap gap-2 items-center">
        {statusChips.map(chip => (
          <button
            key={chip.key}
            onClick={() => setStatusFilter(chip.key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-bold border transition-all ${statusFilter === chip.key ? chip.active : chip.inactive}`}
          >
            {chip.label}
            <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-extrabold ${statusFilter === chip.key ? 'bg-white/20' : 'bg-slate-100 text-slate-500'}`}>
              {statusCounts[chip.key]}
            </span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1.5">
          <ArrowUpDown size={13} className="text-slate-400 shrink-0" />
          <select value={sortKey} onChange={e => setSortKey(e.target.value as SortKey)} className="text-[11px] font-semibold text-slate-600 bg-white border border-slate-200 rounded-lg px-2 py-1.5 outline-none">
            <option value="date">Date d'émission</option>
            <option value="montant">Montant</option>
            <option value="echeance">Date d'échéance</option>
          </select>
        </div>
      </div>

      {/* Barre de recherche */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Rechercher par client ou numéro de facture..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]"
        />
      </div>

      {/* Liste des factures */}
      <div className="space-y-3">
        {filtered.map(item => {
          const paid = item.montantPaye ?? (item.statut === 'Payé' ? item.montantTTC : 0);
          const remaining = item.montantRestantDu ?? Math.max(0, item.montantTTC - paid);
          const session = sessions.find(value => value.id === item.sessionId);
          const payments = item.paiements ?? [];
          const canEmit = item.statut === 'Brouillon';
          const canPay = remaining > 0 && item.statut !== 'Annulée' && item.statut !== 'Brouillon';
          const canRemind = item.statut === 'En retard' || item.statut === 'Partiellement payé';
          const canCancel = item.statut !== 'Payé' && item.statut !== 'Annulée';
          const isBusy = busyId === item.id;
          const isReminderBusy = reminderBusyId === item.id;

          const paidPct = item.montantTTC > 0 ? Math.round((paid / item.montantTTC) * 100) : 0;
          const isOverdue = item.statut === 'En retard';

          return (
            <article key={item.id} className={`overflow-hidden rounded-2xl border bg-white shadow-sm transition-shadow hover:shadow-md ${isOverdue ? 'border-orange-200' : 'border-slate-200'}`}>
              {/* Header de la facture */}
              <div className="flex flex-col gap-4 p-5 md:flex-row md:items-start md:justify-between">
                {/* Colonne gauche : identité */}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-extrabold tracking-tight text-[#11162A]">{item.numero}</span>
                    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[10px] font-extrabold ${statusStyle[item.statut] ?? statusStyle['Envoyé']}`}>{item.statut}</span>
                    {isOverdue && <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold text-orange-700"><AlertTriangle size={10}/>Retard</span>}
                  </div>
                  <div className="mt-1 text-sm font-bold text-slate-800">{item.client}</div>
                  <div className="text-[11px] text-slate-400">{item.type ?? 'Facture'}{session ? <> · <button type="button" onClick={() => onNavigateToSection?.('sessions_groupes')} className="text-[#0B1F4D] underline decoration-dotted hover:text-blue-700">{session.titre}</button></> : ''}</div>
                  <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-500">
                    <span>Émise : <strong>{item.dateEmission ?? '—'}</strong></span>
                    <span>Échéance : <strong className={isOverdue ? 'text-orange-700' : ''}>{item.dateEcheance ? new Date(item.dateEcheance).toLocaleDateString('fr-FR') : '—'}</strong></span>
                  </div>
                </div>

                {/* Colonne droite : montant + barre de paiement */}
                <div className="flex shrink-0 flex-col gap-2 md:min-w-56 md:items-end">
                  <div className="text-right">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Total TTC</div>
                    <div className="text-2xl font-black tabular-nums text-[#11162A]">{item.montantTTC.toLocaleString('fr-FR')} <span className="text-sm font-bold">Ar</span></div>
                  </div>
                  {/* Barre de paiement */}
                  <div className="w-full md:w-56">
                    <div className="mb-1 flex justify-between text-[10px]">
                      <span className="text-emerald-700 font-semibold">Reçu : {paid.toLocaleString('fr-FR')} Ar</span>
                      <span className={`font-bold ${remaining > 0 ? 'text-orange-700' : 'text-emerald-700'}`}>{paidPct}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div className={`h-full rounded-full transition-all ${paidPct === 100 ? 'bg-emerald-500' : isOverdue ? 'bg-orange-500' : 'bg-[#0B1F4D]'}`} style={{width: `${paidPct}%`}}/>
                    </div>
                    <div className={`mt-1 text-[10px] font-bold ${remaining > 0 ? 'text-orange-700' : 'text-emerald-700'}`}>
                      {remaining > 0 ? `${remaining.toLocaleString('fr-FR')} Ar restant` : 'Soldée ✓'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Barre d'actions */}
              <div className={`flex flex-wrap items-center gap-2 border-t px-5 py-3 ${isOverdue ? 'border-orange-100 bg-orange-50/40' : 'border-slate-100 bg-slate-50/50'}`}>
                <button onClick={() => toggleDetails(item)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-100">
                  <History size={13}/>Tracabilité<ChevronDown size={12} className={expandedId === item.id ? 'rotate-180 transition-transform' : 'transition-transform'}/>
                </button>
                {canEmit && (
                  <button onClick={() => emitInvoice(item)} disabled={isBusy} className="inline-flex items-center gap-1.5 rounded-lg bg-blue-700 px-3 py-2 text-[11px] font-bold text-white hover:bg-blue-800 disabled:opacity-50">
                    <Check size={13}/>Émettre la facture
                  </button>
                )}
                {canPay && (
                  <button onClick={() => addPayment(item)} disabled={isBusy} className="inline-flex items-center gap-1.5 rounded-lg bg-[#0B1F4D] px-3 py-2 text-[11px] font-bold text-white hover:bg-slate-800 disabled:opacity-50">
                    <CreditCard size={13}/>Enregistrer un paiement
                  </button>
                )}
                {canRemind && (
                  <button onClick={() => generateReminder(item)} disabled={isBusy || isReminderBusy} className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-[11px] font-bold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50">
                    {isReminderBusy ? <Loader2 size={13} className="animate-spin"/> : <Sparkles size={13}/>}
                    {isReminderBusy ? 'Rédaction…' : 'Relance IA'}
                  </button>
                )}
                <div className="ml-auto flex items-center gap-1.5">
                  <button onClick={() => previewInvoice(item)} disabled={isBusy || pdfPreviewBusyId === item.id} className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:border-[#0B1F4D] hover:text-[#0B1F4D] disabled:opacity-50" title="Aperçu PDF">
                    {pdfPreviewBusyId === item.id ? <Loader2 size={14} className="animate-spin"/> : <Eye size={14}/>}
                  </button>
                  <button onClick={() => downloadInvoice(item)} disabled={isBusy} className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:border-[#0B1F4D] hover:text-[#0B1F4D] disabled:opacity-50" title="Télécharger PDF">
                    {isBusy ? <Loader2 size={14} className="animate-spin"/> : <Download size={14}/>}
                  </button>
                  {canCancel && (
                    <button onClick={() => cancelInvoice(item)} disabled={isBusy} className="rounded-lg border border-red-200 bg-white p-2 text-red-400 hover:border-red-500 hover:text-red-600 disabled:opacity-50" title="Annuler">
                      <X size={14}/>
                    </button>
                  )}
                </div>
              </div>

              {isReminderBusy && (
                <div className="border-t border-indigo-100 bg-indigo-50/60 px-5 py-3 space-y-1.5">
                  <div className="flex items-center gap-2 text-[11px] font-semibold text-indigo-800">
                    <Loader2 size={12} className="animate-spin shrink-0"/>
                    <span>L'IA rédige la lettre de relance — 10 à 20 secondes…</span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-indigo-200">
                    <div className="h-full bg-indigo-600 rounded-full animate-pulse" style={{width: '55%'}}/>
                  </div>
                </div>
              )}

              {/* Tracabilité étendue */}
              {expandedId === item.id && (
                <div className="border-t border-slate-100 bg-slate-50/60 p-5">
                  <h3 className="mb-4 text-xs font-extrabold uppercase tracking-widest text-slate-500">Traçabilité financière</h3>
                  <div className="grid gap-5 md:grid-cols-2">
                    {/* Timeline des paiements */}
                    <section>
                      <div className="mb-3 flex items-center gap-2 text-xs font-extrabold text-[#11162A]">
                        <CreditCard size={13}/>Encaissements
                        <span className="ml-auto font-mono text-[11px] text-emerald-700">{paid.toLocaleString('fr-FR')} Ar / {item.montantTTC.toLocaleString('fr-FR')} Ar</span>
                      </div>
                      {payments.length ? (
                        <div className="relative space-y-0">
                          {payments.map((payment: any, index: number) => (
                            <div key={payment.id ?? index} className="flex gap-3">
                              <div className="flex flex-col items-center">
                                <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500 ring-2 ring-emerald-100"/>
                                {index < payments.length - 1 && <div className="mt-1 w-px flex-1 bg-slate-200"/>}
                              </div>
                              <div className="mb-3 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-[11px] font-semibold text-slate-700">
                                    {payment.date ? new Date(payment.date).toLocaleDateString('fr-FR') : 'Date non renseignée'}
                                  </span>
                                  <strong className="text-sm font-extrabold text-emerald-700">+{Number(payment.montant ?? 0).toLocaleString('fr-FR')} Ar</strong>
                                </div>
                                <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">{payment.mode ?? 'Mode non précisé'}</div>
                              </div>
                            </div>
                          ))}
                          {remaining > 0 && (
                            <div className="flex gap-3">
                              <div className="flex flex-col items-center">
                                <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-2 ${isOverdue ? 'bg-orange-400 ring-orange-100' : 'bg-slate-300 ring-slate-100'}`}/>
                              </div>
                              <div className={`mb-1 flex-1 rounded-lg border px-3 py-2 text-[11px] font-semibold ${isOverdue ? 'border-orange-200 bg-orange-50 text-orange-700' : 'border-dashed border-slate-200 bg-slate-50 text-slate-500'}`}>
                                Solde restant : {remaining.toLocaleString('fr-FR')} Ar
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-4 text-center text-xs text-slate-400">
                          Aucun encaissement enregistré
                        </div>
                      )}
                    </section>

                    {/* Historique des relances */}
                    <section>
                      <div className="mb-3 flex items-center gap-2 text-xs font-extrabold text-[#11162A]">
                        <Sparkles size={13} className="text-indigo-600"/>Relances IA
                      </div>
                      {historyBusyId === item.id ? (
                        <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin"/>Chargement…</div>
                      ) : reminderHistory[item.id]?.length ? (
                        <div className="space-y-2">
                          {reminderHistory[item.id].map((entry: any, index: number) => (
                            <div key={entry.id ?? index} className="rounded-lg border border-indigo-100 bg-white p-3 text-xs">
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-extrabold text-indigo-700">Niveau {entry.niveau ?? entry.type ?? '?'}</span>
                                <span className="text-[10px] text-slate-400">{entry.date_creation ? new Date(entry.date_creation).toLocaleDateString('fr-FR') : ''}</span>
                              </div>
                              {entry.objet && <p className="font-semibold text-slate-700">{entry.objet}</p>}
                              <p className="mt-1 text-slate-500 line-clamp-2">{entry.texte ?? entry.contenu ?? entry.message ?? 'Relance validée'}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-4 text-center text-xs text-slate-400">
                          Aucune relance émise
                        </div>
                      )}
                    </section>
                  </div>
                </div>
              )}
            </article>
          );
        })}
        {filtered.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <ReceiptText size={28} className="mx-auto text-slate-300"/>
            <p className="mt-3 text-sm font-bold text-slate-600">Aucune facture trouvée</p>
            <p className="mt-1 text-xs text-slate-400">{statusFilter !== 'Toutes' ? `Aucune facture avec le statut "${statusFilter}".` : 'Créez une facture ou modifiez votre recherche.'}</p>
          </div>
        )}
      </div>

      {/* Modal paiement */}
      {paymentTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="payment-title">
          <form onSubmit={savePayment} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 id="payment-title" className="text-lg font-extrabold text-[#11162A]">Enregistrer un paiement</h2>
                <p className="mt-1 text-xs text-slate-500">Facture {paymentTarget.numero} · solde {(paymentTarget.montantRestantDu ?? paymentTarget.montantTTC).toLocaleString('fr-FR')} Ar</p>
              </div>
              <button type="button" onClick={() => setPaymentTarget(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button>
            </div>
            <label className="block text-xs font-bold text-slate-600">Montant payé (Ar)
              <input type="number" min="1" max={paymentTarget.montantRestantDu ?? paymentTarget.montantTTC} step="0.01" required value={paymentAmount} onChange={e => setPaymentAmount(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800"/>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs font-bold text-slate-600">Date
                <input type="date" required value={paymentDate} onChange={e => setPaymentDate(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800"/>
              </label>
              <label className="block text-xs font-bold text-slate-600">Mode
                <select value={paymentMode} onChange={e => setPaymentMode(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-800">
                  <option>VIREMENT</option><option>ESPECES</option><option>CHEQUE</option><option>MOBILE_MONEY</option><option>AUTRE</option>
                </select>
              </label>
            </div>
            {error && <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700">{error}</p>}
            <button disabled={busyId === paymentTarget.id} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#0B1F4D] px-4 py-3 text-xs font-bold text-white disabled:opacity-50">
              {busyId === paymentTarget.id ? <Loader2 size={15} className="animate-spin"/> : <Check size={15}/>}Enregistrer le paiement
            </button>
          </form>
        </div>
      )}

      {/* Modal aperçu PDF facture */}
      {pdfPreviewUrl && (
        <div className="fixed inset-0 z-50 flex flex-col bg-slate-950/80" role="dialog" aria-modal="true" aria-label="Aperçu de la facture">
          <div className="flex items-center justify-between bg-[#11162A] px-4 py-3">
            <span className="text-xs font-bold text-white">Aperçu de la facture</span>
            <div className="flex items-center gap-2">
              <a href={pdfPreviewUrl} download="facture.pdf" className="rounded-lg border border-white/20 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-white/10">
                <Download size={13} className="inline mr-1"/>Télécharger
              </a>
              <button type="button" onClick={closePdfPreview} className="rounded-lg p-2 text-white/70 hover:bg-white/10"><X size={16}/></button>
            </div>
          </div>
          <iframe src={pdfPreviewUrl} className="flex-1 w-full border-0" title="Aperçu PDF"/>
        </div>
      )}

      {/* Modal aperçu relance */}
      {reminderPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="reminder-title">
          <div className="my-auto w-full max-w-2xl space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between">
              <div>
                <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold uppercase text-indigo-700"><Sparkles size={12}/>Validation humaine M7</span>
                <h2 id="reminder-title" className="mt-2 text-xl font-extrabold text-[#11162A]">Aperçu de la relance</h2>
                <p className="mt-1 text-xs text-slate-500">{reminderPreview.invoice.numero} · {reminderPreview.invoice.client}</p>
              </div>
              <button type="button" onClick={() => setReminderPreview(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X size={18}/></button>
            </div>
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4">
              <div className="mb-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-indigo-700">Niveau {reminderPreview.review.niveau ?? '?'}</span>
                {reminderPreview.review.objet && <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600">{reminderPreview.review.objet}</span>}
              </div>
              <div className="max-h-[45vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{reminderPreview.review.texte ?? reminderPreview.review.contenu ?? JSON.stringify(reminderPreview.review, null, 2)}</div>
            </div>
            <div className="flex justify-end">
              <button type="button" onClick={openReminderReview} className="rounded-xl bg-[#0B1F4D] px-4 py-2.5 text-xs font-bold text-white">
                Vérifier et valider dans l'Espace IA
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
