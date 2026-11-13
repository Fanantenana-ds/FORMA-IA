import React, { useEffect, useRef, useState } from 'react';
import {
  Search,
  Plus,
  User,
  LogIn,
  UserPlus,
  LogOut,
  Menu,
  ArrowUpRight,
  Settings,
  CalendarDays,
} from 'lucide-react';
import { UserRole, AuthUser, MenuSection, ROLE_LABELS } from '../types';
import { useLanguage } from '../contexts/LanguageContext';

/** Initiales (2 max) à partir du nom complet. */
const getInitials = (name: string): string =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join('');


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
  currentSection?: MenuSection;
}

export interface HeaderSearchItem {
  id: string;
  title: string;
  description: string;
  searchText: string;
  section: MenuSection;
  sectionLabel: string;
}

const SECTION_LABELS: Partial<Record<MenuSection, string>> = {
  tableau_de_bord:      'Tableau de bord',
  veille_marche:        'Veille & Détection · M1',
  opportunites_crm:     'Opportunités · TDR · Offres · M2–M3',
  dossiers_formation:   'Dossiers de formation',
  formateurs_staff:     'Formateurs & Staff · M4',
  sessions_groupes:     'Sessions & Présences · M4–M5',
  espace_ia:            'Espace IA · Validations',
  facturation_devis:    'Facturation & Devis · M7',
  suivi_presences:      'Suivi des présences',
  evaluation_competences: 'Évaluation des compétences',
  gestion_utilisateurs: 'Gestion des utilisateurs',
  mon_profil:           'Mon profil',
  parametres:           'Paramètres',
};

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
  currentSection,
}) => {
  const { t } = useLanguage();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [activeSearchIndex, setActiveSearchIndex] = useState(0);
  const [now, setNow] = useState(new Date());
  const searchRef = useRef<HTMLDivElement>(null);
  const quickActionsRef = useRef<HTMLDivElement>(null);
  const canCreateOpportunity = authUser?.role === 'Dir.' || authUser?.role === 'Assis.';
  const canCreateSession = authUser?.role === 'Dir.';
  const canCreateInvoice = authUser?.role === 'Dir.' || authUser?.role === 'Compt.';
  const hasQuickActions = canCreateOpportunity || canCreateSession || canCreateInvoice;
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase('fr');
  const filteredSearchItems = normalizedQuery.length >= 2
    ? searchItems.filter(item => `${item.title} ${item.description} ${item.searchText}`.toLocaleLowerCase('fr').includes(normalizedQuery)).slice(0, 8)
    : [];

  const sectionLabel = currentSection ? SECTION_LABELS[currentSection] : undefined;

  const selectSearchItem = (item: HeaderSearchItem) => {
    setSearchQuery(item.title);
    setShowSearchResults(false);
    onNavigate(item.section);
  };

  // Horloge live
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  // Fermer menus au clic extérieur
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearchResults(false);
      if (quickActionsRef.current && !quickActionsRef.current.contains(e.target as Node)) setShowQuickActions(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header className="sticky top-0 z-20 flex h-[60px] items-center justify-between gap-3 border-b border-slate-100 bg-white/95 backdrop-blur-sm px-4 shadow-[0_1px_12px_rgba(0,0,0,0.06)] sm:px-6">

      {/* ── Gauche : burger + recherche ── */}
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {/* Burger mobile */}
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Ouvrir ou fermer le menu"
          aria-controls="primary-navigation"
          aria-expanded={isSidebarOpen}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 md:hidden"
        >
          <Menu size={18} />
        </button>

        {/* Fil d'Ariane section active */}
        {sectionLabel && (
          <div className="hidden md:flex items-center gap-1.5 shrink-0">
            <span className="text-slate-300 text-sm">/</span>
            <span className="text-xs font-semibold text-slate-600 whitespace-nowrap">{sectionLabel}</span>
          </div>
        )}

        {/* Barre de recherche */}
        <div className="relative min-w-0 w-full max-w-sm" ref={searchRef}>
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={15} />
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
            onChange={e => { setSearchQuery(e.target.value); setActiveSearchIndex(0); setShowSearchResults(true); }}
            onKeyDown={e => {
              if (e.key === 'Escape') setShowSearchResults(false);
              if (e.key === 'ArrowDown' && filteredSearchItems.length) { e.preventDefault(); setActiveSearchIndex(i => Math.min(i + 1, filteredSearchItems.length - 1)); }
              if (e.key === 'ArrowUp' && filteredSearchItems.length) { e.preventDefault(); setActiveSearchIndex(i => Math.max(i - 1, 0)); }
              if (e.key === 'Enter' && filteredSearchItems[activeSearchIndex]) { e.preventDefault(); selectSearchItem(filteredSearchItems[activeSearchIndex]); }
            }}
            placeholder="Rechercher session, opportunité, facture…"
            className="h-9 w-full rounded-full border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm text-slate-800 placeholder:text-slate-400 placeholder:text-xs transition-all focus:border-[#0B1F4D]/40 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B1F4D]/10"
          />
          {showSearchResults && (
            <div id="header-search-results" role="listbox" aria-label="Résultats" className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
              {normalizedQuery.length < 2 ? (
                <p className="px-4 py-3 text-xs text-slate-400">Saisissez au moins 2 caractères…</p>
              ) : filteredSearchItems.length === 0 ? (
                <p className="px-4 py-3 text-xs text-slate-400">Aucun résultat.</p>
              ) : (
                <>
                  <p className="border-b border-slate-100 px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">Résultats</p>
                  {filteredSearchItems.map((item, index) => (
                    <button key={item.id} id={`header-search-option-${index}`} type="button" role="option" aria-selected={index === activeSearchIndex}
                      onMouseEnter={() => setActiveSearchIndex(index)} onClick={() => selectSearchItem(item)}
                      className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors ${index === activeSearchIndex ? 'bg-slate-50' : 'hover:bg-slate-50'}`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-semibold text-slate-800">{item.title}</span>
                        <span className="block truncate text-[10px] text-slate-400">{item.description}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                        {item.sectionLabel} <ArrowUpRight size={10} />
                      </span>
                    </button>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Droite : actions rapides + cloche + profil ── */}
      <div className="flex shrink-0 items-center gap-2">

        {/* Boutons actions rapides — desktop */}
        {hasQuickActions && (
          <>
            <div className="hidden lg:flex items-center gap-1.5">
              {canCreateOpportunity && (
                <button onClick={onQuickNewOpportunity} type="button"
                  className="flex h-8 items-center gap-1.5 rounded-full border border-brand-gold/50 bg-brand-gold/8 px-3.5 text-xs font-semibold text-[#7A5C00] transition hover:bg-brand-gold/15 hover:border-brand-gold/70"
                >
                  <Plus size={13} strokeWidth={2.5} />
                  Opportunité
                </button>
              )}
              {canCreateSession && (
                <button onClick={onQuickNewSession} type="button"
                  className="flex h-8 items-center gap-1.5 rounded-full bg-[#0B1F4D] px-3.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#06132F]"
                >
                  <Plus size={13} strokeWidth={2.5} />
                  Session
                </button>
              )}
              {canCreateInvoice && (
                <button onClick={onQuickNewInvoice} type="button"
                  className="flex h-8 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 hover:border-slate-300"
                >
                  <Plus size={13} strokeWidth={2.5} />
                  Devis / Facture
                </button>
              )}
            </div>

            {/* Menu rapide mobile */}
            <div className="relative lg:hidden" ref={quickActionsRef}>
              <button type="button" onClick={() => setShowQuickActions(o => !o)} aria-label="Actions rapides" aria-expanded={showQuickActions}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-brand-gold/40 bg-brand-gold/10 text-[#7A5C00] transition hover:bg-brand-gold/20"
              >
                <Plus size={17} />
              </button>
              {showQuickActions && (
                <div className="absolute right-0 top-full z-40 mt-2 w-52 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-2xl">
                  <p className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-slate-400">Actions rapides</p>
                  {canCreateOpportunity && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewOpportunity(); }} className="w-full rounded-xl px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50">+ Opportunité</button>}
                  {canCreateSession && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewSession(); }} className="w-full rounded-xl px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50">+ Session</button>}
                  {canCreateInvoice && <button type="button" onClick={() => { setShowQuickActions(false); onQuickNewInvoice(); }} className="w-full rounded-xl px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50">+ Devis / Facture</button>}
                </div>
              )}
            </div>
          </>
        )}

        {/* Date du jour */}
        <div className="hidden lg:flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5">
          <CalendarDays size={13} className="text-slate-400 shrink-0" />
          <span className="text-[11px] font-semibold text-slate-600 whitespace-nowrap">
            {now.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
          </span>
        </div>

        {/* Séparateur */}
        <div className="h-5 w-px bg-slate-200" />

        {/* Profil utilisateur */}
        {authUser ? (
          <div className="relative">
            <button type="button" onClick={() => setShowUserMenu(!showUserMenu)}
              aria-label={`Menu du compte — ${authUser.nom}`} aria-expanded={showUserMenu}
              className="flex items-center gap-2.5 rounded-full border border-slate-200 bg-white pl-1 pr-3 py-1 shadow-sm transition hover:bg-slate-50"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-[#0B1F4D] to-[#1a3a7a] text-[11px] font-extrabold text-white ring-1 ring-white">
                {avatarUrl ? <img src={avatarUrl} alt="" className="h-full w-full object-cover" /> : getInitials(authUser.nom)}
              </div>
              <span className="hidden text-xs font-semibold text-slate-700 md:inline">{ROLE_LABELS[authUser.role]}</span>
            </button>

            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl z-50 animate-in fade-in duration-150">
                <div className="bg-gradient-to-br from-[#0B1F4D] to-[#1a3a7a] px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white/20 text-sm font-extrabold text-white ring-2 ring-white/30">
                      {avatarUrl ? <img src={avatarUrl} alt="" className="h-full w-full object-cover" /> : getInitials(authUser.nom)}
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-white">{authUser.nom}</div>
                      <div className="truncate text-[10px] text-white/60">{authUser.email}</div>
                      <div className="mt-0.5 inline-block rounded-md bg-brand-gold/25 px-1.5 py-0.5 text-[10px] font-bold text-brand-gold">{ROLE_LABELS[authUser.role]}</div>
                    </div>
                  </div>
                </div>
                <div className="p-1.5">
                  <button type="button" onClick={() => { setShowUserMenu(false); onNavigate('mon_profil'); }}
                    className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <User size={14} className="text-[#0B1F4D]" /> {t('nav.profil')}
                  </button>
                  <button type="button" onClick={() => { setShowUserMenu(false); onNavigate('parametres'); }}
                    className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <Settings size={14} className="text-slate-400" /> {t('nav.parametres')}
                  </button>
                  <div className="my-1 h-px bg-slate-100" />
                  <button type="button" onClick={() => { setShowUserMenu(false); onLogout(); }}
                    className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-bold text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut size={14} /> {t('nav.deconnexion')}
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button onClick={() => onOpenAuthModal('login')} className="flex h-8 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50">
              <LogIn size={13} /> Connexion
            </button>
            <button onClick={() => onOpenAuthModal('register')} className="flex h-8 items-center gap-1.5 rounded-full bg-[#0B1F4D] px-3.5 text-xs font-semibold text-white shadow-sm transition hover:bg-[#06132F]">
              <UserPlus size={13} /> <span className="hidden sm:inline">Inscription</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
