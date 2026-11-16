import React from 'react';
import { Building2, CheckCircle2, Loader2, Trophy, Trash2 } from 'lucide-react';
import { AcceptedMarket } from '../../types/tdr';

interface AcceptedMarketsListProps {
  markets: AcceptedMarket[];
  selectedMarketId: string;
  onSelectMarket: (id: string) => void;
  onOpenNewOpportunity?: () => void;
  onDeleteMarket?: (id: string, title: string) => void;
  canDeleteMarkets?: boolean;
  onMarkWon?: (id: string) => Promise<void>;
  markingWonId?: string;
}

export const AcceptedMarketsList: React.FC<AcceptedMarketsListProps> = ({
  markets,
  selectedMarketId,
  onSelectMarket,
  onOpenNewOpportunity,
  onDeleteMarket,
  canDeleteMarkets = false,
  onMarkWon,
  markingWonId = ''
}) => {
  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div>
          <span className="text-[10px] font-extrabold text-[#0B1F4D] uppercase tracking-wider">
            Portefeuille CRM & Veille
          </span>
          <h2 className="text-base font-extrabold text-[#11162A]">Opportunités enregistrées</h2>
        </div>
        {onOpenNewOpportunity && (
          <button
            onClick={onOpenNewOpportunity}
            className="px-3 py-1.5 bg-[#0B1F4D] text-white text-xs font-bold rounded-xl hover:bg-[#06132F] transition-colors"
          >
            + Opportunité
          </button>
        )}
      </div>

      {markets.length === 0 && (
        <p className="text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200/80">
          Aucune opportunité enregistrée pour le moment.
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {markets.map((m) => {
          const isSelected = m.id === selectedMarketId;
          return (
            <div
              key={m.id}
              onClick={() => onSelectMarket(m.id)}
              className={`p-4 rounded-xl border transition-all cursor-pointer space-y-2 relative ${
                isSelected
                  ? 'border-[#0B1F4D] bg-emerald-50/50 ring-2 ring-[#0B1F4D]/20'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold flex items-center gap-1 ${m.statut === 'Gagnée' ? 'bg-yellow-100 text-yellow-800' : 'bg-emerald-100 text-emerald-800'}`}>
                  {m.statut === 'Gagnée' ? <Trophy size={12}/> : <CheckCircle2 size={12} />}
                  {m.statut}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-mono text-slate-400">{m.date}</span>
                  {onMarkWon && m.statut !== 'Gagnée' && (
                    <button
                      type="button"
                      title="Marquer comme gagnée"
                      disabled={markingWonId === m.id}
                      onClick={(event) => { event.stopPropagation(); void onMarkWon(m.id); }}
                      className="rounded-lg p-1.5 text-amber-500 hover:bg-yellow-50 hover:text-yellow-700 disabled:opacity-50"
                    >
                      {markingWonId === m.id ? <Loader2 size={14} className="animate-spin"/> : <Trophy size={14}/>}
                    </button>
                  )}
                  {canDeleteMarkets && onDeleteMarket && <button type="button" title="Supprimer cette opportunité acceptée" aria-label={`Supprimer ${m.titre}`} onClick={(event) => { event.stopPropagation(); onDeleteMarket(m.id, m.titre); }} className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={14} /></button>}
                </div>
              </div>

              <h3 className="text-xs font-extrabold text-[#11162A] line-clamp-2">{m.titre}</h3>

              <div className="flex items-center gap-1.5 text-xs text-slate-600 font-semibold">
                <Building2 size={13} className="text-[#0B1F4D] shrink-0" />
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
