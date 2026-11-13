import React, { useState } from 'react';
import {
  LayoutDashboard,
  Search,
  GraduationCap,
  Award,
  CalendarDays,
  UserCheck,
  ReceiptText,
  Zap,
  LogOut,
  BrainCircuit,
  UserCog,
  X,
  Workflow,
  ChevronLeft,
  ChevronRight,
  Settings2,
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
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

/** Numéros affichés dans le pipeline M1→M7. */
const PIPELINE_STEPS: { id: MenuSection; label: string; icon: React.ReactNode; step?: string; urgent?: boolean }[] = [
  { id: 'tableau_de_bord',   label: 'Tableau de bord',           icon: <LayoutDashboard size={18} /> },
  { id: 'veille_marche',     label: 'Veille & Détection',         icon: <Search size={18} />,       step: 'M1' },
  { id: 'opportunites_crm',  label: 'Opportunités · TDR · Offres',icon: <Zap size={18} />,          step: 'M2–M3' },
  { id: 'dossiers_formation',label: 'Dossiers de formation',      icon: <Workflow size={18} /> },
  { id: 'formateurs_staff',  label: 'Formateurs & Staff',         icon: <GraduationCap size={18} />,step: 'M4' },
  { id: 'sessions_groupes',  label: 'Sessions & Présences',       icon: <CalendarDays size={18} />, step: 'M4–M5' },
  { id: 'espace_ia',         label: 'Espace IA · Validations',    icon: <BrainCircuit size={18} />, step: 'IA' },
  { id: 'facturation_devis', label: 'Facturation & Devis',        icon: <ReceiptText size={18} />,  step: 'M7' },
];

const ADMIN_STEPS: { id: MenuSection; label: string; icon: React.ReactNode }[] = [
  { id: 'suivi_presences',       label: 'Suivi des présences',    icon: <UserCheck size={18} /> },
  { id: 'evaluation_competences',label: 'Évaluation Compétences', icon: <Award size={18} /> },
  { id: 'gestion_utilisateurs',  label: 'Gestion utilisateurs',   icon: <UserCog size={18} /> },
];

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onSelectSection,
  isOpen,
  onClose,
  currentRole,
  authUser,
  onLogout,
  pendingReviewCount = 0,
  collapsed = false,
  onToggleCollapse,
}) => {
  const [adminOpen, setAdminOpen] = useState(false);

  const navBtn = (
    id: MenuSection,
    label: string,
    icon: React.ReactNode,
    badge?: string,
    urgent = false,
  ) => {
    if (!canAccessSection(currentRole, id)) return null;
    const isActive = currentSection === id;
    return (
      <button
        key={id}
        type="button"
        title={collapsed ? label : undefined}
        onClick={() => { onSelectSection(id); onClose(); }}
        aria-current={isActive ? 'page' : undefined}
        className={`group w-full flex items-center gap-3 rounded-xl transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-offset-1 focus-visible:ring-offset-brand-darkNavy
          ${collapsed ? 'justify-center px-2 py-2.5' : 'justify-between px-3 py-2.5'}
          ${isActive
            ? 'bg-gradient-to-r from-brand-gold to-amber-400 text-brand-darkNavy shadow-lg shadow-brand-gold/25 font-semibold'
            : 'text-slate-400 hover:text-white hover:bg-white/8'
          }`}
      >
        {/* icon */}
        <span className={`shrink-0 transition-colors ${isActive ? 'text-brand-darkNavy' : 'text-slate-400 group-hover:text-white'}`}>
          {icon}
        </span>

        {/* label */}
        {!collapsed && (
          <span className="flex-1 truncate text-sm text-left leading-tight">{label}</span>
        )}

        {/* badge */}
        {!collapsed && badge && (
          <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-md font-bold tracking-wide
            ${urgent
              ? (isActive ? 'bg-brand-darkNavy/20 text-brand-darkNavy' : 'bg-red-500 text-white animate-pulse')
              : (isActive ? 'bg-brand-darkNavy/15 text-brand-darkNavy' : 'bg-white/10 text-slate-300')
            }`}
          >
            {badge}
          </span>
        )}

        {/* dot badge when collapsed + urgent */}
        {collapsed && urgent && badge && (
          <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-red-500 ring-2 ring-brand-darkNavy" />
        )}
      </button>
    );
  };

  const pipelineItems = PIPELINE_STEPS.filter(s => canAccessSection(currentRole, s.id));
  const adminItems = ADMIN_STEPS.filter(s => canAccessSection(currentRole, s.id));

  return (
    <aside
      id="primary-navigation"
      aria-label="Navigation principale"
      aria-hidden={!isOpen}
      inert={!isOpen}
      className={`fixed inset-y-0 left-0 z-40 flex h-[100dvh] shrink-0 select-none flex-col
        border-r border-white/[0.06] bg-[#0A1628] text-white shadow-2xl
        transition-all duration-300 ease-in-out
        md:sticky md:top-0 md:z-30 md:h-screen md:translate-x-0 md:shadow-none
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        ${collapsed ? 'w-[68px]' : 'w-[260px]'}
      `}
    >
      {/* ── Header ── */}
      <div className={`relative border-b border-white/[0.07] ${collapsed ? 'px-2 py-4' : 'px-4 py-4'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3 items-center'}`}>
          <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-lg shadow-black/30 ring-1 ring-white/30 p-1">
            <img src="/logo_altiora_prest.png" alt="ALTIORA PREST" className="h-full w-full object-contain" />
          </div>

          {!collapsed && (
            <div className="min-w-0 flex-1 flex flex-col items-center justify-center gap-0.5">
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-[23px] tracking-tight leading-none">
                  <span className="text-white">FORMA</span><span className="text-brand-gold">-IA</span>
                </h1>
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="text-[10px] font-medium text-emerald-400/80 leading-tight">
                Plateforme de Gestion de Formation
              </p>
            </div>
          )}

          {/* Fermer mobile */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer le menu"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white transition-colors md:hidden"
          >
            <X size={17} />
          </button>
        </div>

        {/* Rôle & utilisateur */}
        {!collapsed && authUser && (
          <div className="mt-3 pt-3 border-t border-white/[0.07] flex items-center gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-gold to-amber-500 text-brand-darkNavy text-[12px] font-extrabold uppercase shadow-sm">
              {authUser.nom.charAt(0)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-bold text-white leading-tight">
                {authUser.nom.length > 20 ? authUser.nom.split(' ').map((w: string) => w.charAt(0).toUpperCase() + '.').join(' ') : authUser.nom}
              </div>
              <div className="text-[10px] text-slate-400 font-medium">{ROLE_LABELS[currentRole]}</div>
            </div>
          </div>
        )}

        {/* Bouton réduction desktop */}
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Développer la barre latérale' : 'Réduire la barre latérale'}
            className={`hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2
              h-6 w-6 items-center justify-center rounded-full
              border border-white/15 bg-[#0A1628] text-slate-400
              shadow-md transition-all hover:bg-brand-gold hover:text-brand-darkNavy hover:border-brand-gold`}
          >
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        )}
      </div>

      {/* ── Navigation ── */}
      <div className={`flex-1 overflow-y-auto py-3 custom-scrollbar ${collapsed ? 'px-2' : 'px-2'}`}>

        {/* Label section */}
        {!collapsed && (
          <div className="mb-2 px-2">
            <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-slate-600">
              Pipeline formation
            </span>
          </div>
        )}

        {/* Entrées pipeline */}
        <div className="space-y-0.5">
          {pipelineItems.map((step) => {
            const isEspaceIA = step.id === 'espace_ia';
            const badge = isEspaceIA
              ? (pendingReviewCount > 0 ? `${pendingReviewCount} à valider` : step.step)
              : step.step;
            const urgent = isEspaceIA && pendingReviewCount > 0;
            return (
              <div key={step.id} className="relative">
                {navBtn(step.id, step.label, step.icon, badge, urgent)}
              </div>
            );
          })}
        </div>

        {/* Section admin secondaire */}
        {adminItems.length > 0 && (
          <div className="mt-4">
            {!collapsed ? (
              <>
                <button
                  type="button"
                  onClick={() => setAdminOpen(o => !o)}
                  className="flex w-full items-center gap-2 px-2 py-1.5 group"
                >
                  <div className="flex-1 h-px bg-white/[0.07]" />
                  <span className="flex items-center gap-1 text-[10px] font-bold tracking-[0.1em] uppercase text-slate-600 group-hover:text-slate-400 transition-colors whitespace-nowrap">
                    <Settings2 size={10} />
                    Administration
                    <ChevronRight size={10} className={`transition-transform ${adminOpen ? 'rotate-90' : ''}`} />
                  </span>
                  <div className="flex-1 h-px bg-white/[0.07]" />
                </button>
                {adminOpen && (
                  <div className="mt-0.5 space-y-0.5">
                    {adminItems.map(s => navBtn(s.id, s.label, s.icon))}
                  </div>
                )}
              </>
            ) : (
              <div className="mt-2 pt-2 border-t border-white/[0.07] space-y-0.5">
                {adminItems.map(s =>
                  canAccessSection(currentRole, s.id)
                    ? navBtn(s.id, s.label, s.icon)
                    : null
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Pied de page ── */}
      {onLogout && (
        <div className={`border-t border-white/[0.07] p-2`}>
          <button
            type="button"
            onClick={onLogout}
            title={collapsed ? 'Se déconnecter' : undefined}
            className={`flex w-full items-center rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-500
              transition-colors hover:bg-red-500/10 hover:text-red-400
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400
              ${collapsed ? 'justify-center' : 'justify-between gap-3'}`}
          >
            {!collapsed && <span>Se déconnecter</span>}
            <LogOut size={15} />
          </button>
        </div>
      )}
    </aside>
  );
};
