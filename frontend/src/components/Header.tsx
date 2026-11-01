import React, { useState } from 'react';
import {
  Search,
  Bell,
  Plus,
  User,
  LogIn,
  UserPlus,
  LogOut,
} from 'lucide-react';
import { UserRole, AuthUser, ROLE_LABELS } from '../types';

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
  onOpenAuthModal: (mode?: 'login' | 'register') => void;
  onLogout: () => void;
  onQuickNewSession: () => void;
  onQuickNewOpportunity: () => void;
  onQuickNewInvoice: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  authUser,
  onOpenAuthModal,
  onLogout,
  onQuickNewSession,
  onQuickNewOpportunity,
  onQuickNewInvoice
}) => {
  const [showUserMenu, setShowUserMenu] = useState(false);
  return (
    <header className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between sticky top-0 z-20 shadow-xs">
      {/* Left Search Bar */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <input
            type="text"
            placeholder="Rechercher une session, opportunité, formateur..."
            className="w-full pl-9 pr-4 py-2 bg-[#F4F5F3] border border-slate-200 rounded-lg text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1B8F6E] focus:bg-white transition-all"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
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

        <div className="h-6 w-px bg-slate-200 mx-1"></div>

        {/* Notifications */}
        <button className="relative p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors">
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#1B8F6E] rounded-full"></span>
        </button>

        {/* User Info / Auth Controls */}
        <div className="relative pl-2 border-l border-slate-200">
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
