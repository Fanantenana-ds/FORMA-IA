/**
 * FORMA-IA Frontend Application
 * Communicates with REST API at http://127.0.0.1:8000
 */

import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { AuthPage } from './components/AuthPage';
import { ViewRouter } from './components/views/ViewRouter';
import { ModalManager } from './components/modals/ModalManager';

import {
  MenuSection,
  UserRole,
  ApiConfig,
  AuthUser,
  KPIStats,
  DomainOpportunity,
  FacturationStatut,
  ActiviteRecente,
  Session,
  OpportuniteCRM,
  Formateur,
  PresenceRecord,
  DevisFacture,
  VeilleMarche,
  EvaluationFormateur
} from './types';

import { apiService } from './services/api';

export default function App() {
  // Auth State (unauthenticated by default when opening platform or when logged out)
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('forma_ia_auth_user');
      if (saved) {
        try { return JSON.parse(saved); } catch (e) { return null; }
      }
    }
    return null;
  });

  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  // Navigation & Role State
  const [currentSection, setCurrentSection] = useState<MenuSection>('tableau_de_bord');
  const [currentRole, setCurrentRole] = useState<UserRole>(authUser ? authUser.role : 'Dir.');

  const handleOpenAuthModal = (mode: 'login' | 'register' = 'login') => {
    setAuthModalMode(mode);
    setAuthUser(null); // Return to auth screen
  };

  const handleLoginSuccess = (user: AuthUser) => {
    setAuthUser(user);
    setCurrentRole(user.role);
    if (typeof window !== 'undefined') {
      localStorage.setItem('forma_ia_auth_user', JSON.stringify(user));
    }
    showToast(`Bienvenue ${user.prenom} ${user.nom} (${user.role === 'Dir.' ? 'Directeur' : user.role === 'Form.' ? 'Formateur' : 'Assistant'}) !`);
  };

  const handleLogout = () => {
    setAuthUser(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('forma_ia_auth_user');
    }
    showToast('Déconnexion effectuée avec succès.');
  };

  // API Config State
  const [apiConfig, setApiConfig] = useState<ApiConfig>(apiService.getConfig());
  const [isApiModalOpen, setIsApiModalOpen] = useState<boolean>(false);

  // Data States
  const [kpis, setKpis] = useState<KPIStats>({
    sessionsRealisees: 37,
    participantsFormes: 412,
    tauxPresenceMoyen: 91,
    opportunitesDetectees: 54
  });
  const [domainOpportunities, setDomainOpportunities] = useState<DomainOpportunity[]>([]);
  const [facturationStatuts, setFacturationStatuts] = useState<FacturationStatut[]>([]);
  const [activites, setActivites] = useState<ActiviteRecente[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [opportunites, setOpportunites] = useState<OpportuniteCRM[]>([]);
  const [formateurs, setFormateurs] = useState<Formateur[]>([]);
  const [presences, setPresences] = useState<PresenceRecord[]>([]);
  const [factures, setFactures] = useState<DevisFacture[]>([]);
  const [veilles, setVeilles] = useState<VeilleMarche[]>([]);

  // Modals state
  const [isNewOppModalOpen, setIsNewOppModalOpen] = useState<boolean>(false);
  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState<boolean>(false);
  const [isNewInvoiceModalOpen, setIsNewInvoiceModalOpen] = useState<boolean>(false);

  // Toast feedback
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  // Subscribe to API config changes & check connection health
  useEffect(() => {
    const unsubscribe = apiService.subscribe((cfg) => {
      setApiConfig(cfg);
    });

    // Check backend health on initial load
    apiService.checkHealth();

    return () => unsubscribe();
  }, []);

  // Fetch initial data from REST API (with mock fallback)
  const loadAllData = async () => {
    try {
      const [
        kpiData,
        domainsData,
        factData,
        actData,
        sessData,
        oppData,
        trainData,
        presData,
        facData,
        vData
      ] = await Promise.all([
        apiService.getKPIs(),
        apiService.getDomainOpportunities(),
        apiService.getFacturationStatuts(),
        apiService.getRecentActivities(),
        apiService.getSessions(),
        apiService.getOpportunites(),
        apiService.getFormateurs(),
        apiService.getPresences(),
        apiService.getFactures(),
        apiService.getVeilles()
      ]);

      setKpis(kpiData);
      setDomainOpportunities(domainsData);
      setFacturationStatuts(factData);
      setActivites(actData);
      setSessions(sessData);
      setOpportunites(oppData);
      setFormateurs(trainData);
      setPresences(presData);
      setFactures(facData);
      setVeilles(vData);
    } catch (err) {
      console.error('Erreur chargement données FORMA-IA:', err);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  // Form submission handlers via REST API
  const handleCreateOpportunity = async (oppData: Partial<OpportuniteCRM>) => {
    const newOpp = await apiService.createOpportunite(oppData);
    setOpportunites(prev => [newOpp, ...prev]);
    setKpis(prev => ({
      ...prev,
      opportunitesDetectees: prev.opportunitesDetectees + 1
    }));
    
    // Add activity log
    const newAct: ActiviteRecente = {
      id: `act-${Date.now()}`,
      titre: `Nouvelle opportunité : ${newOpp.entreprise}`,
      description: `Créée pour le domaine ${newOpp.domaineIA} - Budget estimé : ${newOpp.montantEstime.toLocaleString()} Ar`,
      horodateur: "À l'instant",
      type: 'opportunite',
      statutTag: 'Nouveau',
      utilisateur: `${currentRole === 'Dir.' ? 'Directeur' : 'Utilisateur'}`
    };
    setActivites(prev => [newAct, ...prev]);
    showToast(`Opportunité pour ${newOpp.entreprise} enregistrée via REST API !`);
  };

  const handleCreateSession = async (sessData: Partial<Session>) => {
    const newSess = await apiService.createSession(sessData);
    setSessions(prev => [newSess, ...prev]);
    setKpis(prev => ({
      ...prev,
      sessionsRealisees: prev.sessionsRealisees + 1
    }));

    const newAct: ActiviteRecente = {
      id: `act-${Date.now()}`,
      titre: `Nouvelle session créée : ${newSess.intitule}`,
      description: `Format ${newSess.lieu} - Formateur : ${newSess.formateur}`,
      horodateur: "À l'instant",
      type: 'session',
      statutTag: 'Planifiée',
      utilisateur: `${currentRole === 'Dir.' ? 'Directeur' : 'Utilisateur'}`
    };
    setActivites(prev => [newAct, ...prev]);
    showToast(`Session "${newSess.intitule}" créée avec succès !`);
  };

  const handleCreateInvoice = async (facData: Partial<DevisFacture>) => {
    const newFac = await apiService.createFacture(facData);
    setFactures(prev => [newFac, ...prev]);

    const newAct: ActiviteRecente = {
      id: `act-${Date.now()}`,
      titre: `${newFac.type} ${newFac.numero} émis`,
      description: `Client : ${newFac.client} - Montant : ${newFac.montantTTC.toLocaleString()} Ar TTC`,
      horodateur: "À l'instant",
      type: 'facture',
      statutTag: newFac.statut,
      utilisateur: `${currentRole === 'Dir.' ? 'Directeur' : 'Utilisateur'}`
    };
    setActivites(prev => [newAct, ...prev]);
    showToast(`${newFac.type} ${newFac.numero} généré (${newFac.montantTTC.toLocaleString()} Ar TTC) !`);
  };

  const handleAddFormateur = (newFormateur: Formateur) => {
    setFormateurs(prev => [newFormateur, ...prev]);
    const newAct: ActiviteRecente = {
      id: `act-${Date.now()}`,
      titre: `Nouveau formateur ajouté`,
      description: `${newFormateur.nom} - ${newFormateur.specialites.join(', ')}`,
      horodateur: "À l'instant",
      type: 'session',
      statutTag: newFormateur.statut,
      utilisateur: `${currentRole === 'Dir.' ? 'Directeur' : 'Utilisateur'}`
    };
    setActivites(prev => [newAct, ...prev]);
    showToast(`Formateur "${newFormateur.nom}" ajouté avec succès !`);
  };

  const handleAddEvaluation = (newEval: EvaluationFormateur) => {
    setFormateurs(prev =>
      prev.map(f => {
        if (f.id === newEval.formateurId) {
          const currentEvals = f.evaluations || [];
          const updatedEvals = [newEval, ...currentEvals];
          const newAvgSatisfaction = Number(
            (updatedEvals.reduce((acc, e) => acc + e.noteMoyenne, 0) / updatedEvals.length).toFixed(2)
          );
          return {
            ...f,
            tauxSatisfaction: newAvgSatisfaction,
            evaluations: updatedEvals
          };
        }
        return f;
      })
    );
    showToast(`Évaluation ajoutée avec succès (${newEval.noteMoyenne}/5) !`);
  };

  if (!authUser) {
    return <AuthPage onLoginSuccess={handleLoginSuccess} initialMode={authModalMode} />;
  }

  return (
    <div className="flex min-h-screen bg-[#F4F5F3] font-sans text-slate-800 antialiased selection:bg-[#1B8F6E] selection:text-white">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-4 right-4 z-50 bg-[#11162A] text-white px-4 py-3 rounded-xl shadow-2xl border border-[#1B8F6E] flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[#1B8F6E] animate-ping"></span>
          <span className="text-xs font-semibold">{toastMessage}</span>
        </div>
      )}

      {/* Sidebar Menu Lateral */}
      <Sidebar
        currentSection={currentSection}
        onSelectSection={setCurrentSection}
        currentRole={currentRole}
        onChangeRole={(role) => {
          setCurrentRole(role);
          showToast(`Rôle basculé sur : ${role === 'Dir.' ? 'Directeur' : role === 'Form.' ? 'Formateur' : 'Assistant'}`);
        }}
        apiConfig={apiConfig}
        onOpenApiModal={() => setIsApiModalOpen(true)}
        authUser={authUser}
        onOpenAuthModal={handleOpenAuthModal}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          currentRole={currentRole}
          apiConfig={apiConfig}
          authUser={authUser}
          onOpenAuthModal={handleOpenAuthModal}
          onLogout={handleLogout}
          onOpenApiModal={() => setIsApiModalOpen(true)}
          onQuickNewOpportunity={() => setIsNewOppModalOpen(true)}
          onQuickNewSession={() => setIsNewSessionModalOpen(true)}
          onQuickNewInvoice={() => setIsNewInvoiceModalOpen(true)}
        />

        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto overflow-y-auto">
          <ViewRouter
            currentSection={currentSection}
            currentRole={currentRole}
            kpis={kpis}
            domainOpportunities={domainOpportunities}
            facturationStatuts={facturationStatuts}
            activites={activites}
            veilles={veilles}
            opportunites={opportunites}
            formateurs={formateurs}
            sessions={sessions}
            presences={presences}
            factures={factures}
            onRefreshData={loadAllData}
            onNavigateTo={setCurrentSection}
            onOpenNewOpportunity={() => setIsNewOppModalOpen(true)}
            onOpenNewSession={() => setIsNewSessionModalOpen(true)}
            onOpenNewInvoice={() => setIsNewInvoiceModalOpen(true)}
            onAddFormateur={handleAddFormateur}
            onAddEvaluation={handleAddEvaluation}
          />
        </main>
      </div>

      {/* Global Modals Manager */}
      <ModalManager
        apiConfig={apiConfig}
        isApiModalOpen={isApiModalOpen}
        onCloseApiModal={() => setIsApiModalOpen(false)}
        isNewOppModalOpen={isNewOppModalOpen}
        onCloseNewOppModal={() => setIsNewOppModalOpen(false)}
        onCreateOpportunity={handleCreateOpportunity}
        isNewSessionModalOpen={isNewSessionModalOpen}
        onCloseNewSessionModal={() => setIsNewSessionModalOpen(false)}
        onCreateSession={handleCreateSession}
        isNewInvoiceModalOpen={isNewInvoiceModalOpen}
        onCloseNewInvoiceModal={() => setIsNewInvoiceModalOpen(false)}
        onCreateInvoice={handleCreateInvoice}
      />
    </div>
  );
}
