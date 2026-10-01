import React, { useState } from 'react';
import { ReceiptText, Plus, FileText, CheckCircle2, AlertCircle, Clock, Download, Search } from 'lucide-react';
import { DevisFacture } from '../../types';

interface FacturationDevisViewProps {
  factures: DevisFacture[];
  onOpenNewInvoice: () => void;
}

export const FacturationDevisView: React.FC<FacturationDevisViewProps> = ({
  factures,
  onOpenNewInvoice
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = factures.filter(
    (f) =>
      f.client.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.numero.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPaye = factures.filter(f => f.statut === 'Payé').reduce((sum, f) => sum + f.montantTTC, 0);
  const totalEnAttente = factures.filter(f => f.statut === 'En attente' || f.statut === 'Envoyé').reduce((sum, f) => sum + f.montantTTC, 0);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800">
              Gestion Financière
            </span>
            <span className="text-xs text-slate-400">• Facturation automatisée</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Facturation & Devis</h1>
          <p className="text-slate-600 text-xs mt-1">
            Émission et suivi des devis de formation, factures d'acompte et règlements clients.
          </p>
        </div>

        <button
          onClick={onOpenNewInvoice}
          className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors shrink-0"
        >
          <Plus size={16} />
          <span>Créer Devis / Facture</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <div className="text-xs font-bold text-slate-500 uppercase">Encaissements validés (TTC)</div>
          <div className="text-2xl font-extrabold text-emerald-600 mt-1">{totalPaye.toLocaleString()} Ar</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200">
          <div className="text-xs font-bold text-slate-500 uppercase">Facturation à encaisser (TTC)</div>
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
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
        />
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 bg-[#F4F5F3] border-b border-slate-200 font-bold text-xs text-slate-600 uppercase tracking-wider grid grid-cols-12 gap-2">
          <div className="col-span-3">N° & Type</div>
          <div className="col-span-4">Client</div>
          <div className="col-span-2">Montant TTC</div>
          <div className="col-span-3 text-right">Statut & Échéance</div>
        </div>

        <div className="divide-y divide-slate-100">
          {filtered.map((item) => (
            <div key={item.id} className="p-4 grid grid-cols-12 gap-2 items-center text-xs hover:bg-slate-50 transition-colors">
              <div className="col-span-3">
                <div className="font-mono font-bold text-[#11162A] text-sm">{item.numero}</div>
                <div className="text-slate-400">{item.type}</div>
              </div>

              <div className="col-span-4 font-bold text-slate-800 text-sm">
                {item.client}
              </div>

              <div className="col-span-2 font-extrabold text-[#11162A] text-sm">
                {item.montantTTC.toLocaleString()} Ar
              </div>

              <div className="col-span-3 text-right flex items-center justify-end gap-2">
                <span
                  className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                    item.statut === 'Payé'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : item.statut === 'En attente' || item.statut === 'Envoyé'
                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : 'bg-red-50 text-red-700 border border-red-200'
                  }`}
                >
                  {item.statut}
                </span>
                <button className="p-1 text-slate-400 hover:text-slate-700" title="Télécharger PDF">
                  <Download size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
