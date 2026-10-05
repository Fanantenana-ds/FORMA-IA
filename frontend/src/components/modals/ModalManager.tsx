import React from 'react';
import { ApiStatusModal } from '../ApiStatusModal';
import { NewOpportunityModal } from './NewOpportunityModal';
import { NewSessionModal } from './NewSessionModal';
import { NewInvoiceModal } from './NewInvoiceModal';
import { ApiConfig, OpportuniteCRM, Session, DevisFacture } from '../../types';

interface ModalManagerProps {
  apiConfig: ApiConfig;
  isApiModalOpen: boolean;
  onCloseApiModal: () => void;

  isNewOppModalOpen: boolean;
  onCloseNewOppModal: () => void;
  onCreateOpportunity: (opp: Omit<OpportuniteCRM, 'id' | 'dateCreation'>) => void;

  isNewSessionModalOpen: boolean;
  onCloseNewSessionModal: () => void;
  onCreateSession: (session: Omit<Session, 'id'>) => void;

  isNewInvoiceModalOpen: boolean;
  onCloseNewInvoiceModal: () => void;
  onCreateInvoice: (invoice: Omit<DevisFacture, 'id' | 'dateEmission'>) => void;
}

export const ModalManager: React.FC<ModalManagerProps> = ({
  apiConfig,
  isApiModalOpen,
  onCloseApiModal,
  isNewOppModalOpen,
  onCloseNewOppModal,
  onCreateOpportunity,
  isNewSessionModalOpen,
  onCloseNewSessionModal,
  onCreateSession,
  isNewInvoiceModalOpen,
  onCloseNewInvoiceModal,
  onCreateInvoice
}) => {
  return (
    <>
      <ApiStatusModal
        isOpen={isApiModalOpen}
        onClose={onCloseApiModal}
        apiConfig={apiConfig}
      />

      <NewOpportunityModal
        isOpen={isNewOppModalOpen}
        onClose={onCloseNewOppModal}
        onSubmit={onCreateOpportunity}
      />

      <NewSessionModal
        isOpen={isNewSessionModalOpen}
        onClose={onCloseNewSessionModal}
        onSubmit={onCreateSession}
      />

      <NewInvoiceModal
        isOpen={isNewInvoiceModalOpen}
        onClose={onCloseNewInvoiceModal}
        onSubmit={onCreateInvoice}
      />
    </>
  );
};
