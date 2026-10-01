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
  Server,
  Zap,
  CheckCircle2,
  AlertCircle,
  User,
  LogIn,
  UserPlus,
  LogOut
} from 'lucide-react';
import { MenuSection, UserRole, ApiConfig, AuthUser } from '../types';

interface SidebarProps {
  currentSection: MenuSection;
  onSelectSection: (section: MenuSection) => void;
  currentRole: UserRole;
  onChangeRole: (role: UserRole) => void;
  apiConfig: ApiConfig;
  onOpenApiModal: () => void;
  authUser?: AuthUser | null;
  onOpenAuthModal?: (mode?: 'login' | 'register') => void;
  onLogout?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentSection,
  onSelectSection,
  currentRole,
  onChangeRole,
  apiConfig,
  onOpenApiModal,
  authUser,
  onOpenAuthModal,
  onLogout
}) => {

  const navItem = (
    id: MenuSection,
    label: string,
    icon: React.ReactNode,
    badge?: string
  ) => {
    const isActive = currentSection === id;
    return (
      <button
        key={id}
        onClick={() => onSelectSection(id)}
        className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
          isActive
            ? 'bg-[#1B8F6E] text-white shadow-md shadow-[#1B8F6E]/20 font-semibold'
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
            className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
              isActive
                ? 'bg-white/20 text-white'
                : 'bg-[#1B8F6E]/20 text-[#2dd4bf]'
            }`}
          >
            {badge}
          </span>
        )}
      </button>
    );
  };

  return (
    <aside className="w-72 bg-[#11162A] text-white flex flex-col h-screen sticky top-0 border-r border-slate-800/60 shrink-0 select-none z-30">
      {/* Top Header Logo Section */}
      <div className="p-5 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-[#1B8F6E] flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-[#1B8F6E]/30 tracking-wider border border-white/10">
            FA
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="font-extrabold text-xl tracking-tight text-white">
                FORMA-IA
              </h1>
              <span className="inline-block w-2 h-2 rounded-full bg-[#1B8F6E] animate-pulse"></span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">
              Plateforme de gestion IA
            </p>
          </div>
        </div>

        {/* Role connecte section */}
        <div className="mt-5 pt-4 border-t border-slate-800/40">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase font-bold tracking-wider text-slate-400">
              Rôle connecté
            </span>
            <span className="text-xs text-[#2dd4bf] font-semibold bg-[#1B8F6E]/20 px-2 py-0.5 rounded">
              {currentRole === 'Dir.' ? 'Directeur' : currentRole === 'Form.' ? 'Formateur' : 'Assistant'}
            </span>
          </div>

          {/* Role Pills: Dir. / Form. / Assis. */}
          <div className="grid grid-cols-3 gap-1 bg-slate-900/80 p-1 rounded-lg border border-slate-800">
            {(['Dir.', 'Form.', 'Assis.'] as UserRole[]).map((role) => {
              const isSelected = currentRole === role;
              return (
                <button
                  key={role}
                  onClick={() => onChangeRole(role)}
                  className={`py-1.5 text-xs font-semibold rounded-md transition-all text-center ${
                    isSelected
                      ? 'bg-[#1B8F6E] text-white shadow'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                  title={
                    role === 'Dir.'
                      ? 'Rôle Directeur (Vue complète)'
                      : role === 'Form.'
                      ? 'Rôle Formateur (Pédagogie & Présences)'
                      : 'Rôle Assistant (Gestion & Support)'
                  }
                >
                  {role}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 px-3 py-4 overflow-y-auto space-y-6 custom-scrollbar">
        {/* PILOTAGE & VEILLE */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Pilotage & Veille
          </div>
          <div className="space-y-1">
            {navItem(
              'tableau_de_bord',
              'Tableau de bord',
              <LayoutDashboard size={18} />,
              'Vue Rôle'
            )}
            {navItem(
              'veille_marche',
              'Veille marché IA',
              <Search size={18} />,
              'IA'
            )}
            {navItem(
              'opportunites_crm',
              'Génération TDR et OT',
              <Zap size={18} />,
              'IA'
            )}
          </div>
        </div>

        {/* RESSOURCES HUMAINES */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Ressources Humaines
          </div>
          <div className="space-y-1">
            {navItem(
              'formateurs_staff',
              'Formateurs & Staff',
              <GraduationCap size={18} />
            )}
            {navItem(
              'evaluation_competences',
              'Évaluation Compétences',
              <Award size={18} />
            )}
          </div>
        </div>

        {/* FORMATION & FACTURATION */}
        <div>
          <div className="px-3 mb-2 text-[11px] font-bold tracking-wider uppercase text-slate-400">
            Formation & Gestion
          </div>
          <div className="space-y-1">
            {navItem(
              'sessions_groupes',
              'Sessions & Groupes',
              <CalendarDays size={18} />,
              '37'
            )}
            {navItem(
              'suivi_presences',
              'Suivi des présences',
              <UserCheck size={18} />,
              '91%'
            )}
            {navItem(
              'facturation_devis',
              'Facturation & Devis',
              <ReceiptText size={18} />
            )}
          </div>
        </div>
      </div>

      {/* Footer REST API connection Status Widget & Logout */}
      <div className="p-3.5 m-3 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-300">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5 font-semibold text-slate-200">
            <Server size={14} className="text-[#2dd4bf]" />
            <span>API REST</span>
          </div>
          <button
            onClick={onOpenApiModal}
            className="text-[10px] text-[#2dd4bf] hover:underline font-medium cursor-pointer"
          >
            Configurer
          </button>
        </div>
        <div className="text-[11px] font-mono text-slate-400 truncate mb-1">
          {apiConfig.baseUrl}
        </div>
        <div className="flex items-center justify-between pt-1 border-t border-slate-800 text-[11px]">
          <span className="text-slate-400">Statut :</span>
          {apiConfig.isConnected ? (
            <span className="flex items-center gap-1 text-emerald-400 font-medium">
              <CheckCircle2 size={12} /> Connecté
            </span>
          ) : (
            <span className="flex items-center gap-1 text-amber-400 font-medium" title="Serveur local 127.0.0.1 non détecté. Mode simulation actif.">
              <AlertCircle size={12} /> Simulation REST
            </span>
          )}
        </div>

        {onLogout && (
          <button
            onClick={onLogout}
            className="w-full mt-2.5 pt-2 border-t border-slate-800/80 text-left text-red-400 hover:text-red-300 font-bold flex items-center justify-between text-[11px] transition-colors cursor-pointer"
          >
            <span>Se déconnecter</span>
            <LogOut size={13} />
          </button>
        )}
      </div>
    </aside>
  );
};
