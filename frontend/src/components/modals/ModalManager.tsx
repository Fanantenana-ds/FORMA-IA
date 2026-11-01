import React from 'react';
import { NewOpportunityModal } from './NewOpportunityModal';
import { NewSessionModal } from './NewSessionModal';
import { NewInvoiceModal } from './NewInvoiceModal';
import { Formateur, OpportuniteCRM, Session, VeilleMarche, DevisFacture } from '../../types';

interface ModalManagerProps {
  isNewOppModalOpen: boolean;
  onCloseNewOppModal: () => void;
  onCreateOpportunity: (opp: Partial<OpportuniteCRM>) => Promise<void>;

  isNewSessionModalOpen: boolean;
  onCloseNewSessionModal: () => void;
  onCreateSession: (session: Partial<Session>) => Promise<void>;
  acceptedMarkets: VeilleMarche[];
  formateurs: Formateur[];

  isNewInvoiceModalOpen: boolean;
  onCloseNewInvoiceModal: () => void;
  onCreateInvoice: (invoice: Partial<DevisFacture>) => Promise<void>;
  sessions: Session[];
}

export const ModalManager: React.FC<ModalManagerProps> = ({
  isNewOppModalOpen,
  onCloseNewOppModal,
  onCreateOpportunity,
  isNewSessionModalOpen,
  onCloseNewSessionModal,
  onCreateSession,
  acceptedMarkets,
  formateurs,
  isNewInvoiceModalOpen,
  onCloseNewInvoiceModal,
  onCreateInvoice,
  sessions
}) => {
  return (
    <>
      <NewOpportunityModal
        isOpen={isNewOppModalOpen}
        onClose={onCloseNewOppModal}
        onSubmit={onCreateOpportunity}
      />

      <NewSessionModal
        isOpen={isNewSessionModalOpen}
        onClose={onCloseNewSessionModal}
        onSubmit={onCreateSession}
        acceptedMarkets={acceptedMarkets}
        formateurs={formateurs}
      />

      <NewInvoiceModal
        isOpen={isNewInvoiceModalOpen}
        onClose={onCloseNewInvoiceModal}
        onSubmit={onCreateInvoice}
        sessions={sessions}
      />
    </>
  );
};
