import React from 'react';
import { DashboardView } from './DashboardView';
import { VeilleMarcheView } from './VeilleMarcheView';
import { OpportunitesCrmView } from './OpportunitesCrmView';
import { FormateursStaffView } from './FormateursStaffView';
import { EvaluationCompetencesView } from './EvaluationCompetencesView';
import { SessionsGroupesView } from './SessionsGroupesView';
import { SuiviPresencesView } from './SuiviPresencesView';
import { FacturationDevisView } from './FacturationDevisView';
import { EspaceIAView } from './EspaceIAView';
import { GestionUtilisateursView } from './GestionUtilisateursView';
import {
  MenuSection,
  UserRole,
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente,
  VeilleMarche,
  OpportuniteCRM,
  Formateur,
  Session,
  PresenceRecord,
  DevisFacture
} from '../../types';

interface ViewRouterProps {
  currentSection: MenuSection;
  currentRole: UserRole;
  kpis: KPIStats;
  domainOpportunities: DomainOpportunity[];
  facturationStatuts: FacturationStatut[];
  activites: ActiviteRecente[];
  veilles: VeilleMarche[];
  opportunites: OpportuniteCRM[];
  formateurs: Formateur[];
  sessions: Session[];
  presences: PresenceRecord[];
  factures: DevisFacture[];
  onRefreshData: () => void;
  dashboardLoading?: boolean;
  dashboardNotice?: string | null;
  onNavigateTo: (section: MenuSection) => void;
  onOpenNewOpportunity: () => void;
  onOpenNewSession: () => void;
  /** Seule la Direction peut créer, modifier ou supprimer des formateurs. */
  canManageFormateurs: boolean;
  onOpenNewInvoice: () => void;
}

export const ViewRouter: React.FC<ViewRouterProps> = ({
  currentSection,
  currentRole,
  kpis,
  domainOpportunities,
  facturationStatuts,
  activites,
  veilles,
  opportunites,
  formateurs,
  sessions,
  presences,
  factures,
  onRefreshData,
  dashboardLoading,
  dashboardNotice,
  onNavigateTo,
  onOpenNewOpportunity,
  onOpenNewSession,
  onOpenNewInvoice,
  canManageFormateurs
}) => {
  switch (currentSection) {
    case 'gestion_utilisateurs':
      return currentRole === 'Dir.' ? <GestionUtilisateursView /> : null;
    case 'tableau_de_bord':
      return (
        <DashboardView
          kpis={kpis}
          domainOpportunities={domainOpportunities}
          facturationStatuts={facturationStatuts}
          activites={activites}
          currentRole={currentRole}
          isLoading={dashboardLoading}
          notice={dashboardNotice}
          onRefresh={onRefreshData}
          onNavigateTo={onNavigateTo}
          onOpenNewOpportunity={onOpenNewOpportunity}
          onOpenNewSession={onOpenNewSession}
        />
      );

    case 'veille_marche':
      return (
        <VeilleMarcheView
          veilles={veilles}
          onNavigateToSection={onNavigateTo}
          onRefreshData={onRefreshData}
          canTriggerDetection={currentRole === 'Dir.' || currentRole === 'Assis.'}
        />
      );

    case 'opportunites_crm':
      return (
        <OpportunitesCrmView
          opportunites={opportunites}
          onOpenNewOpportunity={onOpenNewOpportunity}
          onRefreshData={onRefreshData}
          canDeleteOpportunities={currentRole === 'Dir.' || currentRole === 'Assis.'}
        />
      );

    case 'formateurs_staff':
      return (
        <FormateursStaffView
          formateurs={formateurs}
          sessions={sessions}
          canManage={canManageFormateurs}
          onRefreshData={onRefreshData}
        />
      );

    case 'evaluation_competences':
      return (
        <EvaluationCompetencesView
          formateurs={formateurs}
        />
      );

    case 'sessions_groupes':
      return (
        <SessionsGroupesView
          sessions={sessions}
          presences={presences}
          onOpenNewSession={onOpenNewSession}
          onRefreshData={onRefreshData}
          canDeleteSessions={currentRole === 'Dir.'}
          readOnly={currentRole === 'Form.'}
        />
      );

    case 'suivi_presences':
      return <SuiviPresencesView presences={presences} sessions={sessions} readOnly={currentRole === 'Form.'} />;

    case 'facturation_devis':
      return (
        <FacturationDevisView
          factures={factures}
          sessions={sessions}
          onOpenNewInvoice={onOpenNewInvoice}
          onRefreshData={onRefreshData}
        />
      );

    case 'espace_ia':
      return <EspaceIAView readOnly={currentRole === 'Form.'} trainerMode={currentRole === 'Form.'} />;

    default:
      return (
        <DashboardView
          kpis={kpis}
          domainOpportunities={domainOpportunities}
          facturationStatuts={facturationStatuts}
          activites={activites}
          currentRole={currentRole}
          isLoading={dashboardLoading}
          notice={dashboardNotice}
          onRefresh={onRefreshData}
          onNavigateTo={onNavigateTo}
          onOpenNewOpportunity={onOpenNewOpportunity}
          onOpenNewSession={onOpenNewSession}
        />
      );
  }
};
