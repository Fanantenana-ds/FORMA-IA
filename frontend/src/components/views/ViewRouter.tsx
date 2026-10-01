import React from 'react';
import { DashboardView } from './DashboardView';
import { VeilleMarcheView } from './VeilleMarcheView';
import { OpportunitesCrmView } from './OpportunitesCrmView';
import { FormateursStaffView } from './FormateursStaffView';
import { EvaluationCompetencesView } from './EvaluationCompetencesView';
import { SessionsGroupesView } from './SessionsGroupesView';
import { SuiviPresencesView } from './SuiviPresencesView';
import { FacturationDevisView } from './FacturationDevisView';
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
  DevisFacture,
  EvaluationFormateur
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
  onNavigateTo: (section: MenuSection) => void;
  onOpenNewOpportunity: () => void;
  onOpenNewSession: () => void;
  onOpenNewInvoice: () => void;
  onAddFormateur?: (formateur: Formateur) => void;
  onAddEvaluation?: (evaluation: EvaluationFormateur) => void;
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
  onNavigateTo,
  onOpenNewOpportunity,
  onOpenNewSession,
  onOpenNewInvoice,
  onAddFormateur,
  onAddEvaluation
}) => {
  switch (currentSection) {
    case 'tableau_de_bord':
      return (
        <DashboardView
          kpis={kpis}
          domainOpportunities={domainOpportunities}
          facturationStatuts={facturationStatuts}
          activites={activites}
          currentRole={currentRole}
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
        />
      );

    case 'opportunites_crm':
      return (
        <OpportunitesCrmView
          opportunites={opportunites}
          onOpenNewOpportunity={onOpenNewOpportunity}
        />
      );

    case 'formateurs_staff':
      return (
        <FormateursStaffView
          formateurs={formateurs}
          onAddFormateur={onAddFormateur}
          onAddEvaluation={onAddEvaluation}
        />
      );

    case 'evaluation_competences':
      return (
        <EvaluationCompetencesView
          formateurs={formateurs}
          onAddEvaluation={onAddEvaluation}
        />
      );

    case 'sessions_groupes':
      return (
        <SessionsGroupesView
          sessions={sessions}
          presences={presences}
          onOpenNewSession={onOpenNewSession}
        />
      );

    case 'suivi_presences':
      return <SuiviPresencesView presences={presences} sessions={sessions} />;

    case 'facturation_devis':
      return (
        <FacturationDevisView
          factures={factures}
          onOpenNewInvoice={onOpenNewInvoice}
        />
      );

    default:
      return (
        <DashboardView
          kpis={kpis}
          domainOpportunities={domainOpportunities}
          facturationStatuts={facturationStatuts}
          activites={activites}
          currentRole={currentRole}
          onRefresh={onRefreshData}
          onNavigateTo={onNavigateTo}
          onOpenNewOpportunity={onOpenNewOpportunity}
          onOpenNewSession={onOpenNewSession}
        />
      );
  }
};
