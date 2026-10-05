import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  BookOpen,
  CheckCircle2,
  FileText,
  Building2,
  DollarSign,
  ArrowRight,
  Filter,
  Check,
  Zap,
  Tag
} from 'lucide-react';
import { VeilleMarche, MenuSection } from '../../types';

interface VeilleMarcheViewProps {
  veilles: VeilleMarche[];
  onNavigateToSection?: (section: MenuSection) => void;
  onSelectMarketForDoc?: (market: VeilleMarche) => void;
}

export const VeilleMarcheView: React.FC<VeilleMarcheViewProps> = ({
  veilles: initialVeilles,
  onNavigateToSection,
  onSelectMarketForDoc
}) => {
  const [veillesList, setVeillesList] = useState<VeilleMarche[]>(initialVeilles);
  const [activeTab, setActiveTab] = useState<'trouves' | 'acceptes'>('trouves');
  const [searchTerm, setSearchTerm] = useState('');

  // Filtered lists
  const trouvesList = veillesList.filter(
    (v) => (v.statut === 'Trouvé' || !v.statut) &&
      (v.titre.toLowerCase().includes(searchTerm.toLowerCase()) ||
       v.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
       (v.clientCible && v.clientCible.toLowerCase().includes(searchTerm.toLowerCase())))
  );

  const acceptesList = veillesList.filter(
    (v) => v.statut === 'Accepté' &&
      (v.titre.toLowerCase().includes(searchTerm.toLowerCase()) ||
       v.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
       (v.clientCible && v.clientCible.toLowerCase().includes(searchTerm.toLowerCase())))
  );

  const handleAcceptMarket = (marketId: string) => {
    setVeillesList((prev) =>
      prev.map((v) => (v.id === marketId ? { ...v, statut: 'Accepté' as const } : v))
    );
  };

  const handleOpenDocGenerator = (market: VeilleMarche) => {
    if (onSelectMarketForDoc) {
      onSelectMarketForDoc(market);
    }
    if (onNavigateToSection) {
      onNavigateToSection('opportunites_crm');
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#1B8F6E]/10 text-[#1B8F6E]">
              Intelligence Artificielle & Veille
            </span>
            <span className="text-xs text-slate-400 font-medium">• Analyseur automatisé de marché</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Veille marché IA</h1>
          <p className="text-slate-600 text-xs mt-1">
            Détection proactive des marchés, propositions d'offres et génération associée des TDR et OT (Offre Technique).
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('trouves')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'trouves'
                ? 'bg-white text-[#11162A] shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Search size={15} className="text-[#1B8F6E]" />
            <span>Marchés Trouvés ({trouvesList.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('acceptes')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'acceptes'
                ? 'bg-[#1B8F6E] text-white shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <CheckCircle2 size={15} />
            <span>Marchés Acceptés ({acceptesList.length})</span>
          </button>
        </div>
      </div>

      {/* KPI Highlight Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Marchés Détectés IA</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{veillesList.length} Opportunités</div>
          <p className="text-xs text-[#1B8F6E] font-semibold mt-1">Génération TDR & OT activée</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Marchés Retenus / Acceptés</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{acceptesList.length} Gagnés</div>
          <p className="text-xs text-emerald-600 font-semibold mt-1">Prêts pour formalisation contractuelle</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Budget Cumulé Retenu</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">
            {acceptesList.reduce((acc, curr) => acc + (curr.budgetEstimeAr || 0), 0).toLocaleString()} Ar
          </div>
          <p className="text-xs text-blue-600 font-semibold mt-1">Financement entreprises & partenaires</p>
        </div>
      </div>

      {/* Search Input Bar */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filtrer les marchés par titre, client ou mots-clés..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
        />
      </div>

      {/* LIST 1 : MARCHES TROUVES */}
      {activeTab === 'trouves' && (
        <div className="space-y-4">
          {trouvesList.map((item) => (
            <div
              key={item.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4 hover:border-[#1B8F6E]/40 transition-all"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-[#11162A] text-white rounded-md text-[11px] font-bold">
                    {item.categorie}
                  </span>
                  {item.clientCible && (
                    <span className="px-2.5 py-0.5 bg-slate-100 text-slate-700 rounded-md text-[11px] font-extrabold flex items-center gap-1">
                      <Building2 size={12} className="text-[#1B8F6E]" />
                      {item.clientCible}
                    </span>
                  )}
                </div>
                <span className="text-xs text-slate-400 font-medium">Détecté le {item.dateAnalyse}</span>
              </div>

              <div>
                <h3 className="text-base font-extrabold text-[#11162A]">{item.titre}</h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">{item.description}</p>
              </div>

              {/* TDR & OT Preview Badges */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs">
                <div className="flex items-center gap-2">
                  <FileText size={15} className="text-[#1B8F6E] shrink-0" />
                  <div>
                    <span className="font-bold text-slate-800">TDR (Termes de Réf.) : </span>
                    <span className="text-slate-600">{item.tdrSummary || 'Pré-modèle disponible'}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Zap size={15} className="text-blue-600 shrink-0" />
                  <div>
                    <span className="font-bold text-slate-800">OT (Offre Technique) : </span>
                    <span className="text-slate-600">{item.otSummary || 'Programme & Formateur attribués'}</span>
                  </div>
                </div>
              </div>

              {/* Bottom Actions */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
                <div className="flex items-center gap-3">
                  <span className="text-slate-500 font-medium">
                    Budget Estimé :{' '}
                    <strong className="text-[#11162A] font-extrabold">
                      {(item.budgetEstimeAr || 8000000).toLocaleString()} Ar HT
                    </strong>
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAcceptMarket(item.id)}
                    className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Check size={15} />
                    <span>Accepter ce marché</span>
                  </button>

                  <button
                    onClick={() => handleOpenDocGenerator(item)}
                    className="px-3.5 py-2 bg-[#11162A] hover:bg-[#1B8F6E] text-white rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <span>Voir TDR & OT Prévus →</span>
                  </button>
                </div>
              </div>
            </div>
          ))}

          {trouvesList.length === 0 && (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
              <Search size={32} className="mx-auto text-slate-300 mb-2" />
              <p className="font-bold text-xs text-slate-700">Aucun marché trouvé ne correspond à la recherche.</p>
            </div>
          )}
        </div>
      )}

      {/* LIST 2 : MARCHES ACCEPTES */}
      {activeTab === 'acceptes' && (
        <div className="space-y-4">
          {acceptesList.map((item) => (
            <div
              key={item.id}
              className="bg-white p-5 rounded-2xl border-2 border-emerald-500/40 shadow-xs space-y-4 relative overflow-hidden"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 rounded-md text-[11px] font-extrabold flex items-center gap-1">
                    <CheckCircle2 size={13} />
                    Marché Accepté
                  </span>
                  {item.clientCible && (
                    <span className="px-2.5 py-0.5 bg-slate-100 text-slate-700 rounded-md text-[11px] font-extrabold flex items-center gap-1">
                      <Building2 size={12} className="text-[#1B8F6E]" />
                      {item.clientCible}
                    </span>
                  )}
                </div>
                <span className="text-xs text-slate-400 font-medium">Validé le {item.dateAnalyse}</span>
              </div>

              <div>
                <h3 className="text-base font-extrabold text-[#11162A]">{item.titre}</h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">{item.description}</p>
              </div>

              {/* TDR and OT Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 bg-emerald-50/50 rounded-xl border border-emerald-200 text-xs">
                <div>
                  <div className="font-extrabold text-emerald-900 flex items-center gap-1 mb-0.5">
                    <FileText size={14} className="text-emerald-700" />
                    <span>Termes de Référence (TDR)</span>
                  </div>
                  <p className="text-slate-700 text-[11px]">{item.tdrSummary}</p>
                </div>

                <div>
                  <div className="font-extrabold text-emerald-900 flex items-center gap-1 mb-0.5">
                    <Zap size={14} className="text-emerald-700" />
                    <span>Offre Technique (OT)</span>
                  </div>
                  <p className="text-slate-700 text-[11px]">{item.otSummary}</p>
                </div>
              </div>

              {/* Footer action button */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                <div>
                  <span className="text-slate-400 font-semibold uppercase text-[10px] block">Montant du marché</span>
                  <span className="text-base font-extrabold text-[#11162A]">
                    {(item.budgetEstimeAr || 12000000).toLocaleString()} Ar HT
                  </span>
                </div>

                <button
                  onClick={() => handleOpenDocGenerator(item)}
                  className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
                >
                  <FileText size={16} />
                  <span>Générer / Éditer TDR et OT (Format Word) →</span>
                </button>
              </div>
            </div>
          ))}

          {acceptesList.length === 0 && (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
              <CheckCircle2 size={32} className="mx-auto text-slate-300 mb-2" />
              <p className="font-bold text-xs text-slate-700">Aucun marché n'est encore marqué comme accepté.</p>
              <p className="text-[11px] text-slate-400 mt-1">
                Basculez sur l'onglet "Marchés Trouvés" et cliquez sur "Accepter ce marché".
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
