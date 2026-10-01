import React, { useState, useEffect } from 'react';
import {
  FileText,
  Sparkles,
  Download,
  Search,
  BookOpen,
  Edit3,
  Eye,
  ArrowLeft,
  FileSpreadsheet
} from 'lucide-react';
import { OpportuniteCRM, VeilleMarche } from '../../types';
import {
  TdrDocModel,
  OtDocModel,
  DEFAULT_ACCEPTED_MARKETS,
  INITIAL_TDR_DATA,
  INITIAL_OT_DATA
} from '../../types/tdr';
import { exportDocumentToWord } from '../../utils/docxExport';
import { AcceptedMarketsList } from '../tdr/AcceptedMarketsList';
import { WordDocumentPreview } from '../tdr/WordDocumentPreview';
import { TdrFormEditor } from '../tdr/TdrFormEditor';
import { OtFormEditor } from '../tdr/OtFormEditor';

interface OpportunitesCrmViewProps {
  opportunites: OpportuniteCRM[];
  selectedMarketFromVeille?: VeilleMarche | null;
  onOpenNewOpportunity?: () => void;
}

export const OpportunitesCrmView: React.FC<OpportunitesCrmViewProps> = ({
  selectedMarketFromVeille,
  onOpenNewOpportunity
}) => {
  const acceptedMarkets = DEFAULT_ACCEPTED_MARKETS;

  const [selectedMarketId, setSelectedMarketId] = useState<string>(
    selectedMarketFromVeille ? 'mkt-vina' : acceptedMarkets[0].id
  );

  const activeMarket = acceptedMarkets.find((m) => m.id === selectedMarketId) || acceptedMarkets[0];

  const [docTab, setDocTab] = useState<'tdr' | 'ot'>('tdr');
  const [editorMode, setEditorMode] = useState<'preview' | 'edit'>('preview');

  const [tdrData, setTdrData] = useState<TdrDocModel>(INITIAL_TDR_DATA);
  const [otData, setOtData] = useState<OtDocModel>(INITIAL_OT_DATA);

  useEffect(() => {
    setTdrData((prev) => ({
      ...prev,
      projetTitre: activeMarket.titre,
      clientOrganisme: activeMarket.client
    }));
    setOtData((prev) => ({
      ...prev,
      clientOrganisme: activeMarket.client,
      intituleFormation: activeMarket.titre,
      dureeAtelier: activeMarket.duree,
      budgetTotalAr: activeMarket.budgetAr
    }));
  }, [selectedMarketId]);

  const handleExportWord = () => {
    exportDocumentToWord(docTab, tdrData, otData, activeMarket.client);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Banner Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded text-[11px] font-extrabold bg-blue-100 text-blue-800">
              Cabinet BPO & Projets Contractuels
            </span>
            <span className="text-xs text-slate-400 font-medium">• Générateur Word TDR & Offres Techniques</span>
          </div>
          <h1 className="text-2xl font-extrabold text-[#11162A]">Opportunités & Contrats CRM</h1>
          <p className="text-slate-600 text-xs mt-1">
            Édition dynamique des Termes de Référence (TDR ENI/ALTIORA) et des Offres Techniques exportables sous MS Word.
          </p>
        </div>

        {/* Export Button */}
        <button
          onClick={handleExportWord}
          className="px-5 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition-all cursor-pointer shrink-0"
        >
          <Download size={16} />
          <span>Exporter document Word (.doc)</span>
        </button>
      </div>

      {/* Accepted Markets Selector */}
      <AcceptedMarketsList
        markets={acceptedMarkets}
        selectedMarketId={selectedMarketId}
        onSelectMarket={setSelectedMarketId}
        onOpenNewOpportunity={onOpenNewOpportunity}
      />

      {/* Editor & Preview Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Tab 1: TDR vs OT */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-bold w-full md:w-auto">
          <button
            onClick={() => setDocTab('tdr')}
            className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              docTab === 'tdr' ? 'bg-[#11162A] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText size={15} className="text-amber-400" />
            <span>Termes de Référence (TDR ENI)</span>
          </button>

          <button
            onClick={() => setDocTab('ot')}
            className={`px-4 py-2 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              docTab === 'ot' ? 'bg-[#11162A] text-white shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <BookOpen size={15} className="text-emerald-400" />
            <span>Offre Technique & Budget (OT)</span>
          </button>
        </div>

        {/* View Mode: Preview vs Quick Edit */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-bold">
          <button
            onClick={() => setEditorMode('preview')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
              editorMode === 'preview' ? 'bg-white text-[#11162A] shadow-xs' : 'text-slate-500'
            }`}
          >
            <Eye size={14} />
            <span>Aperçu Document Imprimable</span>
          </button>

          <button
            onClick={() => setEditorMode('edit')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
              editorMode === 'edit' ? 'bg-white text-[#11162A] shadow-xs' : 'text-slate-500'
            }`}
          >
            <Edit3 size={14} />
            <span>Formulaire de modification</span>
          </button>
        </div>
      </div>

      {/* Main Content View */}
      {editorMode === 'preview' ? (
        <WordDocumentPreview
          docTab={docTab}
          tdrData={tdrData}
          setTdrData={setTdrData}
          otData={otData}
          setOtData={setOtData}
        />
      ) : docTab === 'tdr' ? (
        <TdrFormEditor tdrData={tdrData} setTdrData={setTdrData} />
      ) : (
        <OtFormEditor otData={otData} setOtData={setOtData} />
      )}
    </div>
  );
};
