import React from 'react';
import { Building2, Calendar, FileText, Sparkles, CheckCircle2 } from 'lucide-react';
import { AcceptedMarket } from '../../types/tdr';

interface AcceptedMarketsListProps {
  markets: AcceptedMarket[];
  selectedMarketId: string;
  onSelectMarket: (id: string) => void;
  onOpenNewOpportunity?: () => void;
}

export const AcceptedMarketsList: React.FC<AcceptedMarketsListProps> = ({
  markets,
  selectedMarketId,
  onSelectMarket,
  onOpenNewOpportunity
}) => {
  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <span className="text-[10px] font-extrabold text-[#1B8F6E] uppercase tracking-wider">
            Portefeuille CRM & Veille
          </span>
          <h2 className="text-base font-extrabold text-[#11162A]">Marchés & Projets Acceptés</h2>
        </div>
        {onOpenNewOpportunity && (
          <button
            onClick={onOpenNewOpportunity}
            className="px-3 py-1.5 bg-[#1B8F6E] text-white text-xs font-bold rounded-xl hover:bg-[#16785c] transition-colors"
          >
            + Opportunité
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {markets.map((m) => {
          const isSelected = m.id === selectedMarketId;
          return (
            <div
              key={m.id}
              onClick={() => onSelectMarket(m.id)}
              className={`p-4 rounded-xl border transition-all cursor-pointer space-y-2 relative ${
                isSelected
                  ? 'border-[#1B8F6E] bg-emerald-50/50 ring-2 ring-[#1B8F6E]/20'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800 flex items-center gap-1">
                  <CheckCircle2 size={12} />
                  {m.statut}
                </span>
                <span className="text-[11px] font-mono text-slate-400">{m.date}</span>
              </div>

              <h3 className="text-xs font-extrabold text-[#11162A] line-clamp-2">{m.titre}</h3>

              <div className="flex items-center gap-1.5 text-xs text-slate-600 font-semibold">
                <Building2 size={13} className="text-[#1B8F6E] shrink-0" />
                <span className="truncate">{m.client}</span>
              </div>

              <div className="pt-2 border-t border-slate-100/80 flex items-center justify-between text-xs">
                <span className="text-slate-400 font-medium text-[10px]">{m.duree}</span>
                <strong className="font-extrabold text-[#11162A]">{m.budgetAr.toLocaleString()} Ar</strong>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
