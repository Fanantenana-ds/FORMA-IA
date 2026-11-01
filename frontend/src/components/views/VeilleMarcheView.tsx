import React, { useEffect, useMemo, useState } from 'react';
import {
  Search,
  Sparkles,
  CheckCircle2,
  FileText,
  Building2,
  Check,
  Loader2,
  ExternalLink,
  AlertTriangle,
  CalendarClock,
  Globe2,
  Bot,
  Keyboard
} from 'lucide-react';
import { VeilleMarche, MenuSection } from '../../types';
import { apiService } from '../../services/api';
import { veilleCache } from '../../services/veilleCache';
import { describeVeilleError } from '../../services/veilleErrors';
import { isAlreadyAccepted } from '../../services/veilleMapping';
import type { DetectionResult } from '../../services/veilleMapping';
import { DetectionAutoPanel } from './DetectionAutoPanel';

interface VeilleMarcheViewProps {
  /** Marchés acceptés = opportunités enregistrées dans le backend. */
  veilles: VeilleMarche[];
  onNavigateToSection?: (section: MenuSection) => void;
  onSelectMarketForDoc?: (market: VeilleMarche) => void;
  /** Recharge les données de l'application après un enregistrement. */
  onRefreshData?: () => Promise<void> | void;
  /** Direction et Assistants : peuvent lancer la détection automatique et accepter des marchés. */
  canTriggerDetection?: boolean;
}

const matches = (v: VeilleMarche, term: string): boolean => {
  const t = term.trim().toLowerCase();
  if (!t) return true;
  return (
    v.titre.toLowerCase().includes(t) ||
    v.description.toLowerCase().includes(t) ||
    (v.clientCible?.toLowerCase().includes(t) ?? false) ||
    v.categorie.toLowerCase().includes(t)
  );
};

const scoreStyle = (score: number): string =>
  score >= 80
    ? 'bg-emerald-100 text-emerald-800'
    : score >= 60
    ? 'bg-blue-100 text-blue-800'
    : 'bg-amber-100 text-amber-800';

export const VeilleMarcheView: React.FC<VeilleMarcheViewProps> = ({
  veilles: acceptedList,
  onNavigateToSection,
  onSelectMarketForDoc,
  onRefreshData,
  canTriggerDetection = false
}) => {
  const cached = useMemo(() => veilleCache.get(), []);

  const [foundList, setFoundList] = useState<VeilleMarche[]>(cached?.markets ?? []);
  const [activeTab, setActiveTab] = useState<'trouves' | 'acceptes'>('trouves');
  const [mode, setMode] = useState<'manuel' | 'auto'>('manuel');
  const [foundOrigin, setFoundOrigin] = useState<'manuel' | 'auto'>('manuel');
  const [query, setQuery] = useState<string>(cached?.query ?? '');
  const [filter, setFilter] = useState('');

  const [isSearching, setIsSearching] = useState(false);
  const [searchNote, setSearchNote] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState<boolean>(cached !== null);

  // Mémorise la dernière recherche le temps de la session
  useEffect(() => {
    if (hasSearched) veilleCache.set({ query, markets: foundList });
  }, [foundList, query, hasSearched]);

  const trouvesList = foundList.filter((v) => matches(v, filter));
  const acceptesFiltered = acceptedList.filter((v) => matches(v, filter));

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 2 || isSearching) return;

    setIsSearching(true);
    setErrorMsg(null);
    setSearchNote(null);
    setActiveTab('trouves');
    try {
      const result = await apiService.searchMarkets(q);
      setFoundList(result.markets);
      setFoundOrigin('manuel');
      setHasSearched(true);
      if (result.status === 'degraded') {
        setSearchNote("L'analyse IA est momentanément indisponible : résultats limités.");
      } else if (result.markets.length === 0) {
        setSearchNote('Aucun marché pertinent trouvé pour cette recherche. Essayez des mots-clés plus larges.');
      } else if (result.notes) {
        setSearchNote(result.notes);
      }
    } catch (err) {
      setErrorMsg(describeVeilleError(err, 'search'));
    } finally {
      setIsSearching(false);
    }
  };

  const handleDetected = async (result: DetectionResult, saved: boolean) => {
    setErrorMsg(null);
    setSearchNote(null);
    setFoundList(result.markets);
    setFoundOrigin('auto');
    setHasSearched(true);
    setActiveTab('trouves');
    // Des opportunités ont pu être enregistrées par le serveur : on recharge la liste des acceptés
    if (saved && onRefreshData) await onRefreshData();
  };

  const handleAcceptMarket = async (market: VeilleMarche) => {
    setAcceptingId(market.id);
    setErrorMsg(null);
    try {
      const acceptance = await apiService.acceptMarket(market);
      setFoundList((prev) => prev.filter((m) => m.id !== market.id));
      if (onRefreshData) await onRefreshData();
      setActiveTab('acceptes');
      setSearchNote(acceptance.sessionError
        ? `Marché accepté, mais la session automatique n'a pas pu être créée : ${acceptance.sessionError}`
        : 'Marché accepté et session planifiée une semaine après l’acceptation.');
    } catch (err) {
      setErrorMsg(describeVeilleError(err, 'accept'));
    } finally {
      setAcceptingId(null);
    }
  };

  const handleOpenDocGenerator = (market: VeilleMarche) => {
    if (onSelectMarketForDoc) onSelectMarketForDoc(market);
    if (onNavigateToSection) onNavigateToSection('opportunites_crm');
  };

  const budgetCumule = acceptedList.reduce((acc, curr) => acc + (curr.budgetEstimeAr || 0), 0);

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
            Recherche d'appels d'offres et d'opportunités de formation à Madagascar, analysés et notés par l'IA.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1.5 rounded-xl text-xs font-bold shrink-0">
          <button
            onClick={() => setActiveTab('trouves')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'trouves' ? 'bg-white text-[#11162A] shadow-xs' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Search size={15} className="text-[#1B8F6E]" />
            <span>Marchés Trouvés ({foundList.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('acceptes')}
            className={`px-4 py-2.5 rounded-lg transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === 'acceptes' ? 'bg-[#1B8F6E] text-white shadow-xs' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <CheckCircle2 size={15} />
            <span>Marchés Acceptés ({acceptedList.length})</span>
          </button>
        </div>
      </div>

      {/* Choix du mode : recherche manuelle ou détection automatique */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => setMode('manuel')}
          className={`p-4 rounded-2xl border-2 text-left transition-all cursor-pointer flex items-start gap-3 ${
            mode === 'manuel'
              ? 'border-[#1B8F6E] bg-[#1B8F6E]/5'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
        >
          <Keyboard size={20} className={mode === 'manuel' ? 'text-[#1B8F6E]' : 'text-slate-400'} />
          <span>
            <span className="block text-sm font-extrabold text-[#11162A]">Recherche manuelle</span>
            <span className="block text-xs text-slate-500 mt-0.5">
              Saisissez vos mots-clés et lancez la recherche quand vous le souhaitez.
            </span>
          </span>
        </button>

        <button
          type="button"
          onClick={() => setMode('auto')}
          className={`p-4 rounded-2xl border-2 text-left transition-all cursor-pointer flex items-start gap-3 ${
            mode === 'auto'
              ? 'border-[#1B8F6E] bg-[#1B8F6E]/5'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
        >
          <Bot size={20} className={mode === 'auto' ? 'text-[#1B8F6E]' : 'text-slate-400'} />
          <span>
            <span className="block text-sm font-extrabold text-[#11162A]">Détection automatique</span>
            <span className="block text-xs text-slate-500 mt-0.5">
              Le serveur cherche seul selon le profil ALTIORA, à intervalle régulier ou à la demande.
            </span>
          </span>
        </button>
      </div>

      {mode === 'auto' && (
        <DetectionAutoPanel canTrigger={canTriggerDetection} onDetected={handleDetected} />
      )}

      {/* Recherche IA (manuelle) */}
      {mode === 'manuel' && (
      <form
        onSubmit={handleSearch}
        className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row gap-3"
      >
        <div className="relative flex-1">
          <Sparkles className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#1B8F6E]" size={16} />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            minLength={2}
            maxLength={500}
            placeholder="Que cherchez-vous ? ex : appel d'offres formation intelligence artificielle"
            className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
          />
        </div>
        <button
          type="submit"
          disabled={isSearching || query.trim().length < 2}
          className="px-5 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {isSearching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          <span>{isSearching ? 'Analyse en cours…' : 'Lancer la recherche IA'}</span>
        </button>
      </form>
      )}

      {isSearching && (
        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold flex items-center gap-2">
          <Loader2 size={14} className="animate-spin shrink-0" />
          Recherche sur le web puis analyse par l'IA : cela peut prendre quelques dizaines de secondes.
        </div>
      )}

      {errorMsg && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {searchNote && !errorMsg && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-semibold">
          {searchNote}
        </div>
      )}

      {/* KPI Highlight Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Résultats de la recherche</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{foundList.length}</div>
          <p className="text-xs text-[#1B8F6E] font-semibold mt-1">
            {foundList.filter((v) => v.validation === 'validated').length} jugés fiables par l'IA
          </p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Marchés acceptés</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{acceptedList.length}</div>
          <p className="text-xs text-emerald-600 font-semibold mt-1">Enregistrés dans la base</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Budget cumulé retenu</div>
          <div className="text-2xl font-extrabold text-[#11162A] mt-1">{budgetCumule.toLocaleString()} Ar</div>
          <p className="text-xs text-blue-600 font-semibold mt-1">Somme des budgets renseignés</p>
        </div>
      </div>

      {/* Filtre local */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrer la liste affichée par titre, organisme ou domaine..."
          className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E]"
        />
      </div>

      {/* LIST 1 : MARCHES TROUVES */}
      {activeTab === 'trouves' && (
        <div className="space-y-4">
          {foundList.length > 0 && (
            <p className="text-[11px] text-slate-500 font-medium">
              {foundOrigin === 'auto'
                ? 'Résultats du dernier passage de détection automatique.'
                : 'Résultats de votre dernière recherche manuelle.'}
            </p>
          )}
          {trouvesList.map((item) => {
            const alreadySaved = isAlreadyAccepted(item, acceptedList);
            return (
            <div
              key={item.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4 hover:border-[#1B8F6E]/40 transition-all"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-[#11162A] text-white rounded-md text-[11px] font-bold">
                    {item.categorie}
                  </span>
                  {item.clientCible && (
                    <span className="px-2.5 py-0.5 bg-slate-100 text-slate-700 rounded-md text-[11px] font-extrabold flex items-center gap-1">
                      <Building2 size={12} className="text-[#1B8F6E]" />
                      {item.clientCible}
                    </span>
                  )}
                  {item.portee && (
                    <span className="px-2.5 py-0.5 bg-slate-100 text-slate-600 rounded-md text-[11px] font-bold flex items-center gap-1">
                      <Globe2 size={12} />
                      {item.portee}
                    </span>
                  )}
                  {item.requeteDetection && (
                    <span
                      className="px-2.5 py-0.5 bg-blue-50 text-blue-700 rounded-md text-[11px] font-bold flex items-center gap-1 max-w-[260px]"
                      title={`Détecté via : ${item.requeteDetection}`}
                    >
                      <Bot size={12} className="shrink-0" />
                      <span className="truncate">{item.requeteDetection}</span>
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {typeof item.score === 'number' && (
                    <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-extrabold ${scoreStyle(item.score)}`}>
                      Score {item.score}/100
                    </span>
                  )}
                  <span
                    className={`px-2.5 py-0.5 rounded-md text-[11px] font-bold ${
                      item.validation === 'validated'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-amber-50 text-amber-700'
                    }`}
                  >
                    {item.validation === 'validated' ? 'Fiable' : 'À vérifier'}
                  </span>
                </div>
              </div>

              <div>
                <h3 className="text-base font-extrabold text-[#11162A]">{item.titre}</h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">{item.description}</p>
                {item.raison && (
                  <p className="text-[11px] text-slate-400 mt-1.5 italic">{item.raison}</p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs">
                <span className="flex items-center gap-1.5 text-slate-600">
                  <CalendarClock size={14} className="text-[#1B8F6E]" />
                  <span className="font-bold text-slate-800">Échéance :</span> {item.echeance || 'Non précisée'}
                </span>
                {item.sourceSite && (
                  <span className="text-slate-600">
                    <span className="font-bold text-slate-800">Source :</span> {item.sourceSite}
                  </span>
                )}
                {item.url && (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 font-bold text-[#1B8F6E] hover:underline"
                  >
                    <ExternalLink size={13} />
                    Consulter l'annonce
                  </a>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
                <span className="text-slate-500 font-medium">
                  Budget estimé :{' '}
                  <strong className="text-[#11162A] font-extrabold">
                    {item.budgetEstimeAr ? `${item.budgetEstimeAr.toLocaleString()} Ar` : 'Budget non précisé'}
                  </strong>
                </span>

                {alreadySaved ? (
                  <span className="px-3.5 py-2 bg-emerald-50 text-emerald-700 rounded-xl font-bold flex items-center gap-1.5">
                    <CheckCircle2 size={15} />
                    <span>Déjà enregistré</span>
                  </span>
                ) : (
                  <button
                    onClick={() => handleAcceptMarket(item)}
                    disabled={acceptingId !== null}
                    className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {acceptingId === item.id ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
                    <span>{acceptingId === item.id ? 'Enregistrement…' : 'Accepter ce marché'}</span>
                  </button>
                )}
              </div>
            </div>
            );
          })}

          {trouvesList.length === 0 && !isSearching && (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
              <Search size={32} className="mx-auto text-slate-300 mb-2" />
              <p className="font-bold text-xs text-slate-700">
                {foundList.length === 0
                  ? hasSearched
                    ? 'Aucun marché à afficher.'
                    : 'Lancez une recherche manuelle ou une détection automatique pour découvrir des marchés.'
                  : 'Aucun résultat ne correspond au filtre.'}
              </p>
            </div>
          )}
        </div>
      )}

      {/* LIST 2 : MARCHES ACCEPTES */}
      {activeTab === 'acceptes' && (
        <div className="space-y-4">
          {acceptesFiltered.map((item) => (
            <div
              key={item.id}
              className="bg-white p-5 rounded-2xl border-2 border-emerald-500/40 shadow-xs space-y-4 relative overflow-hidden"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 rounded-md text-[11px] font-extrabold flex items-center gap-1">
                    <CheckCircle2 size={13} />
                    Marché Accepté
                  </span>
                  <span className="px-2.5 py-0.5 bg-[#11162A] text-white rounded-md text-[11px] font-bold">
                    {item.categorie}
                  </span>
                </div>
                <span className="text-xs text-slate-400 font-medium">Enregistré le {item.dateAnalyse}</span>
              </div>

              <div>
                <h3 className="text-base font-extrabold text-[#11162A]">{item.titre}</h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed whitespace-pre-line line-clamp-4">
                  {item.description}
                </p>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                <div className="flex gap-6">
                  <div>
                    <span className="text-slate-400 font-semibold uppercase text-[10px] block">Montant</span>
                    <span className="text-base font-extrabold text-[#11162A]">
                      {item.budgetEstimeAr ? `${item.budgetEstimeAr.toLocaleString()} Ar` : 'Budget non précisé'}
                    </span>
                  </div>
                  {item.echeance && (
                    <div>
                      <span className="text-slate-400 font-semibold uppercase text-[10px] block">Échéance</span>
                      <span className="text-base font-extrabold text-[#11162A]">{item.echeance}</span>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleOpenDocGenerator(item)}
                  className="px-4 py-2.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-xl font-bold flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
                >
                  <FileText size={16} />
                  <span>Générer / Éditer TDR et OT →</span>
                </button>
              </div>
            </div>
          ))}

          {acceptesFiltered.length === 0 && (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center text-slate-500">
              <CheckCircle2 size={32} className="mx-auto text-slate-300 mb-2" />
              <p className="font-bold text-xs text-slate-700">
                {acceptedList.length === 0
                  ? "Aucun marché n'est encore accepté."
                  : 'Aucun résultat ne correspond au filtre.'}
              </p>
              {acceptedList.length === 0 && (
                <p className="text-[11px] text-slate-400 mt-1">
                  Lancez une recherche, puis cliquez sur « Accepter ce marché » pour l'enregistrer.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
