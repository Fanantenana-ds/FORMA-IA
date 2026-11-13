import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Search,
  Bell,
  Plus,
  User,
  LogIn,
  UserPlus,
  LogOut,
  UserCheck,
  AlertCircle,
  Menu,
  ArrowUpRight,
  Settings,
} from 'lucide-react';
import { UserRole, AuthUser, MenuSection, ROLE_LABELS } from '../types';
import { apiService } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';

/** Initiales (2 max) à partir du nom complet. */
const getInitials = (name: string): string =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('');

const scoreColor = (score: number | null) =>
  score === null ? 'text-slate-400' : score >= 70 ? 'text-emerald-600' : score >= 45 ? 'text-amber-600' : 'text-red-600';

interface HeaderProps {
  authUser: AuthUser | null;
  avatarUrl: string | null;
  searchItems: HeaderSearchItem[];
  onNavigate: (section: MenuSection) => void;
  onToggleSidebar: () => void;
  isSidebarOpen: boolean;
  onOpenAuthModal: (mode?: 'login' | 'register') => void;
  onLogout: () => void;
  onQuickNewSession: () => void;
  onQuickNewOpportunity: () => void;
  onQuickNewInvoice: () => void;
  onNavigateToFormateurs?: () => void;
}

export interface HeaderSearchItem {
  id: string;
  title: string;
  description: string;
  searchText: string;
  section: MenuSection;
  sectionLabel: string;
}

export const Header: React.FC<HeaderProps> = ({
  authUser,
  avatarUrl,
  searchItems,
  onNavigate,
  onToggleSidebar,
  isSidebarOpen,
  onOpenAuthModal,
  onLogout,
  onQuickNewSession,
  onQuickNewOpportunity,
  onQuickNewInvoice,
  onNavigateToFormateurs,
}) => {
  const { t } = useLanguage();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [activeSearchIndex, setActiveSearchIndex] = useState(0);
  const [showBell, setShowBell] = useState(false);
  const [candidatures, setCandidatures] = useState<any[]>([]);
  const [nonTraites, setNonTraites] = useState(0);
  const [candidaturesError, setCandidaturesError] = useState(false);
  const [seenCandidatureIds, setSeenCandidatureIds] = useState<Set<string>>(() => new Set());
  const bellRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const quickActionsRef = useRef<HTMLDivElement>(null);
  const canSeeCandidatures = authUser?.role === 'Dir.' || authUser?.role === 'Assis.';
  const canCreateOpportunity = authUser?.role === 'Dir.' || authUser?.role === 'Assis.';
  const canCreateSession = authUser?.role === 'Dir.';
  const canCreateInvoice = authUser?.role === 'Dir.' || authUser?.role === 'Compt.';
  const hasQuickActions = canCreateOpportunity || canCreateSession || canCreateInvoice;
  const seenStorageKey = `formaia-seen-candidatures:${authUser?.id ?? 'anonymous'}`;
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase('fr');
  const filteredSearchItems = normalizedQuery.length >= 2
    ? searchItems.filter(item => `${item.title} ${item.description} ${item.searchText}`.toLocaleLowerCase('fr').includes(normalizedQuery)).slice(0, 8)
    : [];

  const selectSearchItem = (item: HeaderSearchItem) => {
    setSearchQuery(item.title);
    setShowSearchResults(false);
    onNavigate(item.section);
  };

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(seenStorageKey) ?? '[]');
      setSeenCandidatureIds(new Set(Array.isArray(saved) ? saved.map(String) : []));
    } catch {
      setSeenCandidatureIds(new Set());
    }
  }, [seenStorageKey]);

  const markCandidaturesSeen = useCallback((rows: any[]) => {
    if (!rows.length) return;
    setSeenCandidatureIds(previous => {
      const next = new Set(previous);
      rows.forEach(row => { if (row.id != null) next.add(String(row.id)); });
      const bounded = [...next].slice(-200);
      try { localStorage.setItem(seenStorageKey, JSON.stringify(bounded)); } catch { /* Le badge reste fonctionnel pendant cette session. */ }
      return new Set(bounded);
    });
  }, [seenStorageKey]);

  const unreadCount = candidatures.filter(row => !seenCandidatureIds.has(String(row.id))).length;

  const fetchCandidatures = useCallback(async () => {
    if (!canSeeCandidatures) {
      setCandidatures([]);
      setNonTraites(0);
      setCandidaturesError(false);
      return;
    }
    try {
      const data = await apiService.getRecentCandidatures(48);
      if (!data.success) throw new Error('Chargement indisponible');
      setCandidatures(data.candidatures ?? []);
      setNonTraites(data.non_traites ?? 0);
      setCandidaturesError(false);
    } catch {
      setCandidaturesError(true);
    }
  }, [canSeeCandidatures]);

  useEffect(() => {
    void fetchCandidatures();
    const interval = setInterval(() => void fetchCandidatures(), 60_000);
    return () => clearInterval(interval);
  }, [fetchCandidatures]);

  useEffect(() => {
    if (showBell) markCandidaturesSeen(candidatures);
  }, [showBell, candidatures, markCandidaturesSeen]);

  // Fermer les menus si clic extérieur.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setShowBell(false);
      }
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearchResults(false);
      if (quickActionsRef.current && !quickActionsRef.current.contains(e.target as Node)) setShowQuickActions(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2.5 shadow-xs sm:px-6 sm:py-3.5">
      {/* Recherche dans les données déjà chargées pour le rôle connecté */}
      <div className="flex min-w-0 max-w-xl flex-1 items-center gap-2 sm:gap-4">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Ouvrir ou fermer le menu de navigation"
          aria-controls="primary-navigation"
          aria-expanded={isSidebarOpen}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-[#11162A] shadow-sm transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0B1F4D] md:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="relative min-w-0 w-full" ref={searchRef}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="text"
            role="combobox"
            aria-label="Rechercher dans FORMA-IA"
            aria-expanded={showSearchResults}
            aria-controls={showSearchResults ? 'header-search-results' : undefined}
            aria-activedescendant={filteredSearchItems[activeSearchIndex] ? `header-search-option-${activeSearchIndex}` : undefined}
            aria-autocomplete="list"
            autoComplete="off"
            value={searchQuery}
            onFocus={() => setShowSearchResults(true)}
            onChange={event => { setSearchQuery(event.target.value); setActiveSearchIndex(0); setShowSearchResults(true); }}
            onKeyDown={event => {
              if (event.key === 'Escape') setShowSearchResults(false);
              if (event.key === 'ArrowDown' && filteredSearchItems.length) {
                event.preventDefault();
                setActiveSearchIndex(index => Math.min(index + 1, filteredSearchItems.length - 1));
              }
              if (event.key === 'ArrowUp' && filteredSearchItems.length) {
                event.preventDefault();
                setActiveSearchIndex(index => Math.max(index - 1, 0));
              }
              if (event.key === 'Enter' && filteredSearchItems[activeSearchIndex]) {
                event.preventDefault();
                selectSearchItem(filteredSearchItems[activeSearchIndex]);
              }
            }}
            placeholder="Rechercher une session, une opportunité…"
            className="w-full rounded-xl border border-slate-200 bg-[#F4F5F3] py-2.5 pl-9 pr-3 text-xs text-slate-800 transition-all placeholder:text-[10px] placeholder:text-slate-400 focus:border-[#0B1F4D] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]/20 sm:pr-4 sm:text-sm sm:placeholder:text-xs"
          />
          {showSearchResults && (
            <div id="header-search-results" role="listbox" aria-label="Résultats de recherche" className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
              {normalizedQuery.length < 2 ? (
                <p className="px-4 py-3 text-xs text-slate-500">Saisissez au moins 2 caractères pour chercher dans les données disponibles.</p>
              ) : filteredSearchItems.length === 0 ? (
                <p className="px-4 py-3 text-xs text-slate-500">Aucun résultat dans les données actuellement chargées.</p>
              ) : (
                <>
                  <p className="border-b border-slate-100 px-4 py-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">Résultats disponibles</p>
                  {filteredSearchItems.map((item, index) => (
                    <button
                      key={item.id}
                      id={`header-search-option-${index}`}
                      type="button"
                      role="option"
                      aria-selected={index === activeSearchIndex}
                      onMouseEnter={() => setActiveSearchIndex(index)}
                      onClick={() => selectSearchItem(item)}
                      className={`flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors ${index === activeSearchIndex ? 'bg-emerald-50' : 'hover:bg-slate-50'}`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-bold text-slate-800">{item.title}</span>
                        <span className="mt-0.5 block truncate text-[10px] text-slate-500">{item.description || 'Aucune information complémentaire'}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1 text-[10px] font-semibold text-[#0B1F4D]">{item.sectionLabel}<ArrowUpRight size={12} /></span>
                    </button>
                  ))}
                  <p className="border-t border-slate-100 px-4 py-2 text-[10px] text-slate-400">Recherche parmi les données déjà chargées pour votre rôle.</p>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
        {/* Quick Add Dropdown / Buttons */}
        {hasQuickActions && <>
        <div className="hidden lg:flex items-center gap-2">
          {canCreateOpportunity && <button
            onClick={onQuickNewOpportunity}
            type="button"
            className="px-3 py-1.5 bg-brand-gold/10 hover:bg-brand-gold/20 text-brand-navy rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors border border-brand-gold/40"
          >
            <Plus size={14} />
            <span>Opportunité</span>
          </button>}
          {canCreateSession && <button
            onClick={onQuickNewSession}
            type="button"
            className="px-3 py-1.5 bg-brand-navy hover:bg-brand-darkNavy text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <Plus size={14} />
            <span>Session</span>
          </button>}
          {canCreateInvoice && <button
            onClick={onQuickNewInvoice}
            type="button"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Plus size={14} />
            <span>Devis / Facture</span>
          </button>}
        </div>

        <div className="mx-1 hidden h-6 w-px bg-slate-200 sm:block"></div>
        <div className="relative lg:hidden" ref={quickActionsRef}>
          <button
            type="button"
            onClick={() => setShowQuickActions(open => !open)}
            aria-label="Ouvrir les actions rapides"
            aria-expanded={showQuickActions}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-brand-gold/50 bg-brand-gold/10 text-brand-navy transition hover:bg-brand-gold/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold"
          >
            <Plus size={18} />
          </button>
          {showQuickActions && <div className="absolute right-0 top-full z-40 mt-2 w-56 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
            <p className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-400">Actions rapides</p>
            {canCreateOpportunity && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewOpportunity(); }} className="w-full rounded-xl px-3 py-2.5 text-left text-xs font-semibold text-slate-700 transition hover:bg-emerald-50">Créer une opportunité</button>}
            {canCreateSession && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewSession(); }} className="w-full rounded-xl px-3 py-2.5 text-left text-xs font-semibold text-slate-700 transition hover:bg-emerald-50">Créer une session</button>}
            {canCreateInvoice && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewInvoice(); }} className="w-full rounded-xl px-3 py-2.5 text-left text-xs font-semibold text-slate-700 transition hover:bg-emerald-50">Créer un devis / une facture</button>}
          </div>}
        </div>
        </>}


        {/* Notifications CV */}
        {canSeeCandidatures && <div className="relative" ref={bellRef}>
          <button
            type="button"
            onClick={() => {
              const opening = !showBell;
              setShowBell(opening);
              if (opening) markCandidaturesSeen(candidatures);
            }}
            className="relative p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            title={unreadCount > 0 ? `${unreadCount} nouvelle(s) candidature(s)` : 'Candidatures récentes'}
            aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} nouvelle(s) candidature(s)` : 'Notifications, candidatures récentes'}
            aria-expanded={showBell}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[9px] font-extrabold rounded-full flex items-center justify-center leading-none">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {showBell && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-200 z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <span className="font-extrabold text-xs text-[#11162A]">Candidatures récentes</span>
                {nonTraites > 0 && (
                  <span className="text-[10px] font-bold text-white bg-red-500 px-1.5 py-0.5 rounded-full">{nonTraites} à traiter</span>
                )}
              </div>
              {candidaturesError ? (
                <div className="px-4 py-6 text-center text-xs text-amber-700">Impossible de charger les candidatures. Réessayez dans quelques instants.</div>
              ) : candidatures.length === 0 ? (
                <div className="px-4 py-6 text-center text-xs text-slate-400">Aucune candidature dans les 48 dernières heures.</div>
              ) : (
                <ul className="max-h-72 overflow-y-auto divide-y divide-slate-100">
                  {candidatures.map(c => (
                    <li key={c.id} className="px-4 py-3 hover:bg-slate-50 transition-colors">
                      <div className="flex items-start gap-2">
                        <div className={`mt-0.5 rounded-full p-1 ${c.a_traiter ? 'bg-amber-100' : 'bg-emerald-100'}`}>
                          {c.a_traiter ? <AlertCircle size={12} className="text-amber-600" /> : <UserCheck size={12} className="text-emerald-600" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-xs font-bold text-slate-800 truncate">{c.prenom} {c.nom}</span>
                            <span className={`text-xs font-extrabold ${scoreColor(c.score_preselection)}`}>
                              {c.score_preselection !== null ? `${c.score_preselection}/100` : '—'}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500 truncate">{c.poste_vise}</div>
                          {c.date_soumission && (
                            <div className="text-[10px] text-slate-400 mt-0.5">
                              {new Date(c.date_soumission).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </div>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {onNavigateToFormateurs && (
                <div className="px-4 py-2.5 border-t border-slate-100">
                  <button
                    onClick={() => { setShowBell(false); onNavigateToFormateurs(); }}
                    className="w-full text-xs font-bold text-[#0B1F4D] hover:underline text-center"
                  >
                    Voir toutes les candidatures →
                  </button>
                </div>
              )}
            </div>
          )}
        </div>}

        {/* User Info / Auth Controls */}
        <div className="relative border-l border-slate-200 pl-1 sm:pl-2">
          {authUser ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowUserMenu(!showUserMenu)}
                aria-label={`Ouvrir le menu du compte ${authUser.nom}`}
                aria-expanded={showUserMenu}
                className="flex items-center gap-2.5 hover:opacity-80 transition-opacity p-1 rounded-xl hover:bg-slate-50"
              >
                <div className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border-2 border-white bg-brand-navy text-xs font-extrabold text-white shadow-sm ring-1 ring-slate-200">
                  {avatarUrl ? <img src={avatarUrl} alt="" className="h-full w-full object-cover" /> : getInitials(authUser.nom)}
                </div>
                <span className="hidden md:inline-block text-[10px] px-1.5 py-0.5 bg-brand-gold/15 text-brand-navy font-extrabold rounded">
                  {ROLE_LABELS[authUser.role]}
                </span>
              </button>

              {/* User Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200 p-2 z-50 animate-in fade-in duration-150">
                  {/* Profil résumé */}
                  <div className="p-2 border-b border-slate-100 mb-1">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-navy text-xs font-extrabold text-white">
                        {avatarUrl ? <img src={avatarUrl} alt="" className="h-full w-full object-cover" /> : getInitials(authUser.nom)}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-xs text-[#11162A] truncate">{authUser.nom}</div>
                        <div className="text-[10px] text-slate-500 truncate">{authUser.email}</div>
                        <div className="text-[10px] text-brand-goldDark font-bold">{ROLE_LABELS[authUser.role]}</div>
                      </div>
                    </div>
                  </div>

                  {/* Mon profil */}
                  <button
                    type="button"
                    onClick={() => { setShowUserMenu(false); onNavigate('mon_profil'); }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-semibold text-slate-700 transition-colors hover:bg-emerald-50 hover:text-[#0B1F4D]"
                  >
                    <User size={14} className="text-[#0B1F4D]" />
                    <span>{t('nav.profil')}</span>
                  </button>

                  {/* Paramètres */}
                  <button
                    type="button"
                    onClick={() => { setShowUserMenu(false); onNavigate('parametres'); }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50 hover:text-[#0B1F4D]"
                  >
                    <Settings size={14} className="text-slate-500" />
                    <span>{t('nav.parametres')}</span>
                  </button>

                  <div className="mt-2 border-t border-slate-100 pt-1">
                    <button
                      type="button"
                      onClick={() => { setShowUserMenu(false); onOpenAuthModal('login'); }}
                      className="w-full text-left px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 rounded-lg flex items-center gap-2"
                    >
                      <User size={14} className="text-slate-400" />
                      <span>{t('nav.changer_compte')}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => { setShowUserMenu(false); onLogout(); }}
                      className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 rounded-lg flex items-center gap-2 font-bold"
                    >
                      <LogOut size={14} />
                      <span>{t('nav.deconnexion')}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onOpenAuthModal('login')}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors"
              >
                <LogIn size={14} />
                <span>Connexion</span>
              </button>
              <button
                onClick={() => onOpenAuthModal('register')}
                className="px-3 py-1.5 bg-brand-navy hover:bg-brand-darkNavy text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <UserPlus size={14} />
                <span className="hidden sm:inline">Inscription</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
