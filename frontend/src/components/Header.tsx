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
} from 'lucide-react';
import { UserRole, AuthUser, ROLE_LABELS } from '../types';
import { apiService } from '../services/api';

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
  onToggleSidebar: () => void;
  isSidebarOpen: boolean;
  onOpenAuthModal: (mode?: 'login' | 'register') => void;
  onLogout: () => void;
  onQuickNewSession: () => void;
  onQuickNewOpportunity: () => void;
  onQuickNewInvoice: () => void;
  onNavigateToFormateurs?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  authUser,
  onToggleSidebar,
  isSidebarOpen,
  onOpenAuthModal,
  onLogout,
  onQuickNewSession,
  onQuickNewOpportunity,
  onQuickNewInvoice,
  onNavigateToFormateurs,
}) => {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showBell, setShowBell] = useState(false);
  const [candidatures, setCandidatures] = useState<any[]>([]);
  const [nonTraites, setNonTraites] = useState(0);
  const [candidaturesError, setCandidaturesError] = useState(false);
  const [seenCandidatureIds, setSeenCandidatureIds] = useState<Set<string>>(() => new Set());
  const bellRef = useRef<HTMLDivElement>(null);
  const canSeeCandidatures = authUser?.role === 'Dir.' || authUser?.role === 'Assis.';
  const seenStorageKey = `formaia-seen-candidatures:${authUser?.id ?? 'anonymous'}`;

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

  // Fermer le dropdown Bell si clic extérieur
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setShowBell(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2.5 shadow-xs sm:px-6 sm:py-3.5">
      {/* Left Search Bar */}
      <div className="flex min-w-0 max-w-md flex-1 items-center gap-2 sm:gap-4">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Ouvrir ou fermer le menu de navigation"
          aria-controls="primary-navigation"
          aria-expanded={isSidebarOpen}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-[#11162A] shadow-sm transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B8F6E] md:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="relative min-w-0 w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="text"
            placeholder="Rechercher une session, opportunité, formateur..."
            className="w-full rounded-lg border border-slate-200 bg-[#F4F5F3] py-2 pl-9 pr-2 text-xs text-slate-800 transition-all placeholder:text-[10px] placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] sm:pr-4 sm:text-sm sm:placeholder:text-xs"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
        {/* Quick Add Dropdown / Buttons */}
        <div className="hidden lg:flex items-center gap-2">
          <button
            onClick={onQuickNewOpportunity}
            className="px-3 py-1.5 bg-[#1B8F6E]/10 hover:bg-[#1B8F6E]/20 text-[#1B8F6E] rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors border border-[#1B8F6E]/20"
          >
            <Plus size={14} />
            <span>Opportunité</span>
          </button>
          <button
            onClick={onQuickNewSession}
            className="px-3 py-1.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <Plus size={14} />
            <span>Session</span>
          </button>
          <button
            onClick={onQuickNewInvoice}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Plus size={14} />
            <span>Devis / Facture</span>
          </button>
        </div>

        <div className="mx-1 hidden h-6 w-px bg-slate-200 sm:block"></div>

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
                    className="w-full text-xs font-bold text-[#1B8F6E] hover:underline text-center"
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
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2.5 hover:opacity-80 transition-opacity p-1 rounded-xl hover:bg-slate-50"
              >
                <div className="w-8 h-8 rounded-full bg-[#1B8F6E] text-white font-extrabold text-xs flex items-center justify-center border border-white shadow-xs">
                  {getInitials(authUser.nom)}
                </div>
                <div className="hidden md:block text-left">
                  <div className="text-xs font-bold text-slate-800 leading-none flex items-center gap-1">
                    <span>{authUser.nom}</span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-[#1B8F6E]/10 text-[#1B8F6E] font-extrabold rounded">
                      {ROLE_LABELS[authUser.role]}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5 truncate max-w-[130px]">
                    {authUser.email}
                  </div>
                </div>
              </button>

              {/* User Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-slate-200 p-2 z-50 animate-in fade-in duration-150">
                  <div className="p-2 border-b border-slate-100">
                    <div className="font-bold text-xs text-[#11162A]">{authUser.nom}</div>
                    <div className="text-[11px] text-slate-500">{authUser.email}</div>
                    <div className="text-[10px] text-[#1B8F6E] font-bold mt-1">{ROLE_LABELS[authUser.role]}</div>
                  </div>

                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      onOpenAuthModal('login');
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 rounded-lg flex items-center gap-2 mt-1"
                  >
                    <User size={14} className="text-slate-400" />
                    <span>Changer de compte</span>
                  </button>

                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      onLogout();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 rounded-lg flex items-center gap-2 font-bold"
                  >
                    <LogOut size={14} />
                    <span>Se déconnecter</span>
                  </button>
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
                className="px-3 py-1.5 bg-[#1B8F6E] hover:bg-[#16785c] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs"
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
