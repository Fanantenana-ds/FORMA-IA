import React from 'react';
import {
  LayoutDashboard,
  Search,
  Users2,
  GraduationCap,
  Award,
  CalendarDays,
  UserCheck,
  ReceiptText,
  Zap,
  LogIn,
  UserPlus,
  LogOut,
  BrainCircuit,
  UserCog,
  X,
  Workflow
} from 'lucide-react';
import { MenuSection, UserRole, AuthUser, ROLE_LABELS, canAccessSection } from '../types';

interface SidebarProps {
  currentSection: MenuSection;
  onSelectSection: (section: MenuSection) => void;
  isOpen: boolean;
  onClose: () => void;
  currentRole: UserRole;
  authUser?: AuthUser | null;
  onOpenAuthModal?: (mode?: 'login' | 'register') => void;
  onLogout?: () => void;
  pendingReviewCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onSelectSection,
  isOpen,
  onClose,
  currentRole,
  authUser,
  onOpenAuthModal,
  onLogout,
  pendingReviewCount = 0
}) => {

  const navItem = (
    id: MenuSection,
    label: string,
    icon: React.ReactNode,
    badge?: string,
    urgent = false
  ) => {
    if (!canAccessSection(currentRole, id)) return null;
    const isActive = currentSection === id;
    return (
      <button
        key={id}
        type="button"
        onClick={() => { onSelectSection(id); onClose(); }}
        aria-current={isActive ? 'page' : undefined}
        className={`w-full min-h-11 flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-2 focus-visible:ring-offset-brand-darkNavy ${
          isActive
            ? 'bg-brand-gold text-brand-darkNavy shadow-md shadow-brand-gold/20 font-semibold'
            : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
        }`}
      >
        <div className="flex items-center gap-3">
          <span className={isActive ? 'text-white' : 'text-slate-400'}>
            {icon}
          </span>
          <span className="truncate">{label}</span>
        </div>
        {badge && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-semibold ${urgent ? (isActive ? 'bg-white text-red-700' : 'bg-red-500/20 text-red-300') : isActive
                ? 'bg-brand-darkNavy/10 text-brand-darkNavy'
                : 'bg-brand-gold/15 text-brand-goldLight'
            }`}
          >
            {badge}
          </span>
        )}
      </button>
    );
  };

  return (
    <aside
      id="primary-navigation"
      aria-label="Navigation principale"
      aria-hidden={!isOpen}
      inert={!isOpen}
      className={`fixed inset-y-0 left-0 z-40 flex h-[100dvh] w-72 shrink-0 select-none flex-col border-r border-slate-800/60 bg-brand-darkNavy text-white shadow-2xl transition-transform duration-300 ease-in-out md:sticky md:top-0 md:z-30 md:h-screen md:translate-x-0 md:shadow-none ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
    >
      {/* Top Header Logo Section */}
      <div className="p-5 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/70 bg-white p-1 shadow-lg shadow-black/10">
            <img src="/logo_altiora_prest.png" alt="ALTIORA PREST" className="h-full w-full object-contain" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <h1 className="font-extrabold text-xl tracking-tight text-white">
                FORMA-IA
              </h1>
              <span className="inline-block w-2 h-2 rounded-full bg-brand-gold animate-pulse"></span>
            </div>
            <p className="text-[11px] font-semibold text-emerald-300">
              Plateforme de gestion de Formation avec IA
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Fermer le menu" className="rounded-lg p-2 text-slate-300 transition-colors hover:bg-slate-800 hover:text-white md:hidden">
            <X size={19} />
          </button>
        </div>

        {/* Role connecte section */}
        <div className="mt-5 pt-4 border-t border-slate-800/40">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-bold tracking-wider text-slate-400">
              Rôle connecté
            </span>
            <span className="text-xs text-brand-goldLight font-semibold bg-brand-gold/15 px-2 py-0.5 rounded">
              {ROLE_LABELS[currentRole]}
            </span>
          </div>
          {authUser && (
            <div className="text-xs text-slate-300 truncate" title={authUser.email}>
              {authUser.nom}
            </div>
          )}
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 px-3 py-4 overflow-y-auto space-y-6 custom-scrollbar">
        {/* PILOTAGE & VEILLE */}
        {currentRole !== 'Form.' && <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Pilotage & Veille
          </div>
          <div className="space-y-1">
            {navItem('dossiers_formation', 'Dossiers de formation', <Workflow size={18} />)}
            {navItem('tableau_de_bord', 'Tableau de bord', <LayoutDashboard size={18} />, 'Vue Rôle')}
            {navItem('veille_marche', 'Veille marché IA', <Search size={18} />, 'IA')}
            {navItem('opportunites_crm', 'Génération TDR et OT', <Zap size={18} />, 'IA')}
          </div>
        </div>}

        {/* RESSOURCES HUMAINES */}
        {currentRole !== 'Form.' && <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Ressources Humaines
          </div>
          <div className="space-y-1">
            {navItem('formateurs_staff', 'Formateurs & Staff', <GraduationCap size={18} />)}
            {navItem('evaluation_competences', 'Évaluation Compétences', <Award size={18} />)}
          </div>
        </div>}

        {/* FORMATION & GESTION */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Formation & Gestion
          </div>
          <div className="space-y-1">
            {navItem('sessions_groupes', 'Sessions & Groupes', <CalendarDays size={18} />)}
            {navItem('suivi_presences', 'Suivi des présences', <UserCheck size={18} />)}
            {navItem('facturation_devis', 'Facturation & Devis', <ReceiptText size={18} />)}
            {navItem('espace_ia', 'Espace IA & Documents', <BrainCircuit size={18} />, pendingReviewCount ? `${pendingReviewCount} à valider` : 'IA', pendingReviewCount > 0)}
            {navItem('gestion_utilisateurs', 'Gestion des utilisateurs', <UserCog size={18} />)}
          </div>
        </div>
      </div>

      {/* Déconnexion */}
      {onLogout && (
        <div className="mt-auto border-t border-slate-800/80 p-3">
          <button
            type="button"
            onClick={onLogout}
            className="flex min-h-10 w-full cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-bold text-red-300 transition-colors hover:bg-red-400/10 hover:text-red-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
          >
            <span>Se déconnecter</span>
            <LogOut size={15} />
          </button>
        </div>
      )}
    </aside>
  );
};
