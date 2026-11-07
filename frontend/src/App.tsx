/**
 * FORMA-IA Frontend Application
 * Communique avec le backend REST défini par VITE_API_URL (voir .env).
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header, type HeaderSearchItem } from './components/Header';
import { AuthPage } from './components/AuthPage';
import { LandingPage } from './components/landing/LandingPage';
import { PublicRegistrationPage } from './components/PublicRegistrationPage';
import { ViewRouter } from './components/views/ViewRouter';
import { ModalManager } from './components/modals/ModalManager';
import { VocalAssistant } from './components/VocalAssistant';

import {
  MenuSection,
  UserRole,
  canAccessSection,
  ROLE_LABELS,
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
  VeilleMarche
} from './types';

import { apiService, tokenStore, ApiError } from './services/api';
import { veilleCache } from './services/veilleCache';
import { IS_API_CONFIGURED } from './config/env';
import { prepareProfileAvatar, profileAvatarDataUrl } from './services/profileAvatar';

const EMPTY_KPIS: KPIStats = {
  sessionsRealisees: 0,
  participantsFormes: 0,
  tauxPresenceMoyen: 0,
  opportunitesDetectees: 0
};

const errorMessage = (err: unknown): string =>
  err instanceof ApiError || err instanceof Error ? err.message : 'Une erreur est survenue.';

export default function App() {
  // Auth : l'utilisateur est toujours relu depuis le backend (GET /auth/me), jamais stocké en local.
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [profileAvatar, setProfileAvatar] = useState<{ userId: string; dataUrl: string } | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState<boolean>(() => tokenStore.get() !== null);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  // Page d'accueil publique : visible tant que l'utilisateur n'a pas demandé l'écran de connexion
  const [showAuthPage, setShowAuthPage] = useState<boolean>(false);

  // Navigation
  const [currentSection, setCurrentSection] = useState<MenuSection>('tableau_de_bord');
  const [previousSection, setPreviousSection] = useState<MenuSection>('tableau_de_bord');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isDesktopViewport, setIsDesktopViewport] = useState(() => window.matchMedia('(min-width: 768px)').matches);
  const currentRole: UserRole = authUser?.role ?? 'Dir.';

  const avatarUrl = profileAvatar && profileAvatar.userId === authUser?.id ? profileAvatar.dataUrl : null;

  const navigateToSection = useCallback((section: MenuSection) => {
    if (section === 'mon_profil' && currentSection !== 'mon_profil') setPreviousSection(currentSection);
    setCurrentSection(section);
  }, [currentSection]);

  useEffect(() => {
    const desktopQuery = window.matchMedia('(min-width: 768px)');
    const updateViewport = (event: MediaQueryListEvent) => {
      setIsDesktopViewport(event.matches);
      if (event.matches) setIsMobileSidebarOpen(false);
    };
    desktopQuery.addEventListener('change', updateViewport);
    return () => desktopQuery.removeEventListener('change', updateViewport);
  }, []);

  useEffect(() => {
    if (!isMobileSidebarOpen) return;
    const mobileQuery = window.matchMedia('(max-width: 767px)');
    if (!mobileQuery.matches) {
      setIsMobileSidebarOpen(false);
      return;
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsMobileSidebarOpen(false);
    };
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (!event.matches) setIsMobileSidebarOpen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', closeOnEscape);
    mobileQuery.addEventListener('change', closeOnDesktop);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', closeOnEscape);
      mobileQuery.removeEventListener('change', closeOnDesktop);
    };
  }, [isMobileSidebarOpen]);

  useEffect(() => {
    if (!authUser || canAccessSection(authUser.role, currentSection)) return;
    setCurrentSection(authUser.role === 'Form.' ? 'sessions_groupes' : authUser.role === 'Assis.' ? 'opportunites_crm' : 'tableau_de_bord');
  }, [authUser, currentSection]);

  // Data States
  const [kpis, setKpis] = useState<KPIStats>(EMPTY_KPIS);
  const [domainOpportunities, setDomainOpportunities] = useState<DomainOpportunity[]>([]);
  const [facturationStatuts, setFacturationStatuts] = useState<FacturationStatut[]>([]);
  const [activites, setActivites] = useState<ActiviteRecente[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [opportunites, setOpportunites] = useState<OpportuniteCRM[]>([]);
  const [formateurs, setFormateurs] = useState<Formateur[]>([]);
  const [presences, setPresences] = useState<PresenceRecord[]>([]);
  const [factures, setFactures] = useState<DevisFacture[]>([]);
  const [veilles, setVeilles] = useState<VeilleMarche[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState<boolean>(false);
  const [dashboardNotice, setDashboardNotice] = useState<string | null>(null);

  // Modals state
  const [isNewOppModalOpen, setIsNewOppModalOpen] = useState<boolean>(false);
  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState<boolean>(false);
  const [isNewInvoiceModalOpen, setIsNewInvoiceModalOpen] = useState<boolean>(false);
  const [invoiceSessionId, setInvoiceSessionId] = useState('');
  const openInvoiceModal = (sessionId?: string) => {
    setInvoiceSessionId(sessionId ?? '');
    setIsNewInvoiceModalOpen(true);
  };

  // Toast feedback
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [pendingReviewCount, setPendingReviewCount] = useState(0);

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  }, []);

  useEffect(() => {
    if (!authUser) {
      setProfileAvatar(null);
      return;
    }
    let active = true;
    setProfileAvatar(null);
    apiService.getProfilePhoto()
      .then(async photo => {
        if (!active || !photo) return;
        const dataUrl = await profileAvatarDataUrl(photo);
        if (active) setProfileAvatar({ userId: authUser.id, dataUrl });
      })
      .catch(err => { if (active) showToast(`Photo de profil indisponible : ${errorMessage(err)}`); });
    return () => { active = false; };
  }, [authUser?.id, showToast]);

  const resetData = useCallback(() => {
    setKpis(EMPTY_KPIS);
    setDomainOpportunities([]);
    setFacturationStatuts([]);
    setActivites([]);
    setSessions([]);
    setOpportunites([]);
    setFormateurs([]);
    setPresences([]);
    setFactures([]);
    setVeilles([]);
    setDashboardNotice(null);
  }, []);

  // Fin de session locale (déconnexion, jeton expiré...)
  const endSession = useCallback(() => {
    veilleCache.clear();
    setAuthUser(null);
    setShowAuthPage(false);
    setCurrentSection('tableau_de_bord');
    resetData();
  }, [resetData]);

  const handleOpenAuthModal = async (mode: 'login' | 'register' = 'login') => {
    setAuthModalMode(mode);
    if (authUser) {
      // « Changer de compte » : on révoque d'abord la session en cours
      try { await apiService.logout(); } catch { tokenStore.clear(); }
      endSession();
    }
    setShowAuthPage(true);
  };

  const handleLoginSuccess = (user: AuthUser) => {
    setAuthUser(user);
    setShowAuthPage(false);
    setCurrentSection('tableau_de_bord');
    showToast(`Bienvenue ${user.nom} (${ROLE_LABELS[user.role]}) !`);
  };

  const handleUpdateProfile = async (updates: Pick<AuthUser, 'nom' | 'email'>) => {
    const updatedUser = await apiService.updateOwnProfile(updates);
    setAuthUser(updatedUser);
  };

  const handleUploadProfileAvatar = async (file: File): Promise<void> => {
    if (!authUser) throw new Error('Connectez-vous pour modifier votre photo de profil.');
    const photo = await prepareProfileAvatar(file);
    await apiService.uploadProfilePhoto(photo);
    const dataUrl = await profileAvatarDataUrl(photo);
    setProfileAvatar({ userId: authUser.id, dataUrl });
  };

  const handleDeleteProfileAvatar = async () => {
    await apiService.deleteProfilePhoto();
    setProfileAvatar(null);
  };

  const handleLogout = async () => {
    try { await apiService.logout(); } catch { /* la session locale se termine même si l'API est indisponible */ }
    finally { tokenStore.clear(); endSession(); showToast('Déconnexion effectuée avec succès.'); }
  };

  // Jeton rejeté par le backend (expiré, révoqué, invalide) -> retour à l'accueil
  useEffect(() => {
    const unsubscribe = apiService.onUnauthorized(() => {
      tokenStore.clear();
      endSession();
      showToast('Votre session a expiré. Veuillez vous reconnecter.');
    });
    return () => unsubscribe();
  }, [endSession, showToast]);

  // Restauration de la session au chargement : on interroge GET /auth/me
  useEffect(() => {
    // Nettoyage des anciennes clés de la version « démo »
    try {
      localStorage.removeItem('forma_ia_auth_user');
      localStorage.removeItem('forma_ia_api_url');
    } catch {
      /* stockage indisponible */
    }

    if (!IS_API_CONFIGURED || !tokenStore.get()) {
      setIsCheckingSession(false);
      return;
    }

    let cancelled = false;
    apiService
      .fetchCurrentUser()
      .then((user) => {
        if (!cancelled) setAuthUser(user);
      })
      .catch((err) => {
        // 401 : déjà géré par onUnauthorized. Autre erreur (serveur injoignable...) : on informe.
        if (!cancelled && !(err instanceof ApiError && err.status === 401)) {
          showToast(errorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) setIsCheckingSession(false);
      });

    return () => {
      cancelled = true;
    };
  }, [showToast]);

  // Chargement des données depuis l'API (uniquement une fois connecté).
  // Un échec sur une ressource laisse simplement son état vide.
  const userRole = authUser?.role;

  const loadDashboard = useCallback(async (role: UserRole) => {
    setDashboardLoading(true);
    try {
      const data = await apiService.getDashboard(role);
      setKpis(data.kpis);
      setDomainOpportunities(data.domainOpportunities);
      setFacturationStatuts(data.facturationStatuts);
      setActivites(data.activites);
      setDashboardNotice(
        data.partial
          ? "Certaines données n'ont pas pu être chargées : les indicateurs affichés peuvent être incomplets."
          : null
      );
    } catch (err) {
      setDashboardNotice(`Impossible de charger le tableau de bord : ${errorMessage(err)}`);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  const loadAllData = useCallback(async () => {
    const isTrainer = userRole === 'Form.';
    const dashboardPromise = userRole && userRole !== 'Assis.' && userRole !== 'Form.' ? loadDashboard(userRole) : Promise.resolve();
    const resources = await Promise.allSettled([
      isTrainer ? Promise.resolve([]) : apiService.getFormateurs(),
      userRole === 'Dir.' ? apiService.getVeilles() : Promise.resolve([]),
      apiService.getSessions(),
      isTrainer ? Promise.resolve([]) : apiService.getOpportunites(),
      isTrainer ? Promise.resolve([]) : apiService.getFactures()
    ]);
    const [trainR, veilleR, sessionsR, opportunitiesR, invoicesR] = resources;
    if (trainR.status === 'fulfilled') setFormateurs(trainR.value as Formateur[]);
    if (veilleR.status === 'fulfilled') setVeilles(veilleR.value as VeilleMarche[]);
    if (sessionsR.status === 'fulfilled') setSessions(sessionsR.value);
    if (opportunitiesR.status === 'fulfilled') setOpportunites(opportunitiesR.value as OpportuniteCRM[]);
    if (invoicesR.status === 'fulfilled') setFactures(invoicesR.value as DevisFacture[]);
    const failedResources = resources.filter(result => result.status === 'rejected');
    if (failedResources.length) showToast(`${failedResources.length} ressource(s) n'ont pas pu être chargées. Vérifiez les droits et la connexion API.`);

    await dashboardPromise;
  }, [userRole, loadDashboard, showToast]);

  useEffect(() => {
    if (authUser) {
      loadAllData();
    }
  }, [authUser, loadAllData]);

  useEffect(() => {
    if (!authUser || authUser.role === 'Form.' || authUser.role === 'Assis.') { setPendingReviewCount(0); return; }
    let active = true;
    const refreshCount = async () => {
      const [backend, rag] = await Promise.allSettled([apiService.getPendingReviews(), apiService.getRagReviews()]);
      if (!active) return;
      const ids = new Set<string>();
      if (backend.status === 'fulfilled') (backend.value.reviews ?? []).forEach((r: any) => ids.add(String(r.review_id ?? r.id)));
      if (rag.status === 'fulfilled') (Array.isArray(rag.value.data) ? rag.value.data : []).forEach((r: any) => ids.add(String(r.review_id ?? r.id)));
      setPendingReviewCount(ids.size);
    };
    void refreshCount();
    const timer = window.setInterval(() => void refreshCount(), 45000);
    return () => { active = false; window.clearInterval(timer); };
  }, [authUser]);

  // Form submission handlers via REST API
  const handleCreateOpportunity = async (oppData: Partial<OpportuniteCRM>) => {
    try {
      const newOpp = await apiService.createOpportunite(oppData);
      setOpportunites((prev) => [newOpp, ...prev]);
      await loadDashboard(currentRole);
      showToast(`Opportunité pour ${newOpp.entreprise} enregistrée !`);
    } catch (err) {
      showToast(`Échec de l'enregistrement de l'opportunité : ${errorMessage(err)}`);
      throw err;
    }
  };

  const handleCreateSession = async (sessData: Partial<Session>) => {
    try {
      const newSess = await apiService.createSession(sessData);
      setSessions((prev) => [newSess, ...prev]);
      await loadDashboard(currentRole);
      showToast(`Session "${newSess.intitule}" créée avec succès !`);
    } catch (err) {
      showToast(`Échec de la création de la session : ${errorMessage(err)}`);
      throw err;
    }
  };

  const handleCreateInvoice = async (facData: Partial<DevisFacture>) => {
    try {
      const newFac = await apiService.createFacture(facData);
      setFactures((prev) => [newFac, ...prev]);
      await loadDashboard(currentRole);
      showToast(`${newFac.type} ${newFac.numero} généré (${newFac.montantTTC.toLocaleString()} Ar TTC) !`);
    } catch (err) {
      showToast(`Échec de l'émission du document : ${errorMessage(err)}`);
      throw err;
    }
  };

  // En production, VITE_API_URL doit être renseigné ; en développement, le proxy Vite utilise localhost.
  if (!IS_API_CONFIGURED) {
    return (
      <div className="min-h-screen bg-[#11162A] flex items-center justify-center p-6 font-sans">
        <div className="bg-white rounded-2xl max-w-lg w-full p-8 shadow-2xl border border-slate-100">
          <h1 className="text-xl font-extrabold text-[#11162A] mb-2">Configuration manquante</h1>
          <p className="text-sm text-slate-600 leading-relaxed">
            L'adresse du backend n'est pas définie. Créez un fichier <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-xs">.env</code> à la
            racine du projet (modèle : <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-xs">.env.example</code>) avec :
          </p>
          <pre className="mt-3 p-3 bg-slate-900 text-emerald-300 rounded-xl text-xs font-mono overflow-x-auto">VITE_API_URL=http://127.0.0.1:8000</pre>
          <p className="text-xs text-slate-500 mt-3">Puis redémarrez le serveur de développement.</p>
        </div>
      </div>
    );
  }

  const publicRegistrationToken = window.location.pathname.match(/^\/inscription-publique\/([^/]+)\/?$/)?.[1];
  if (publicRegistrationToken) return <PublicRegistrationPage token={decodeURIComponent(publicRegistrationToken)} />;

  // Vérification de la session en cours (évite un flash de la page d'accueil)
  if (isCheckingSession) {
    return (
      <div className="min-h-screen bg-[#11162A] flex items-center justify-center font-sans">
        <div className="flex items-center gap-3 text-slate-200 text-sm font-semibold">
          <span className="w-3 h-3 rounded-full bg-[#1B8F6E] animate-ping"></span>
          Vérification de la session…
        </div>
      </div>
    );
  }

  if (!authUser) {
    if (!showAuthPage) {
      return <LandingPage onLogin={() => handleOpenAuthModal('login')} />;
    }
    return (
      <AuthPage
        onLoginSuccess={handleLoginSuccess}
        initialMode={authModalMode}
        onBackToHome={() => setShowAuthPage(false)}
      />
    );
  }

  const searchItems: HeaderSearchItem[] = [
    ...(canAccessSection(currentRole, 'sessions_groupes') ? sessions.map(session => ({
      id: `session-${session.id}`,
      title: session.intitule,
      description: [session.client, session.formateur, session.dates].filter(Boolean).join(' · '),
      searchText: [session.intitule, session.code, session.formationCode, session.client, session.formateur, session.domaine, session.dates].filter(Boolean).join(' '),
      section: 'sessions_groupes' as const,
      sectionLabel: 'Session'
    })) : []),
    ...(canAccessSection(currentRole, 'opportunites_crm') ? opportunites.map(opportunity => ({
      id: `opportunity-${opportunity.id}`,
      title: opportunity.entreprise,
      description: [opportunity.besoinFormation, opportunity.etape].filter(Boolean).join(' · '),
      searchText: [opportunity.entreprise, opportunity.contactName, opportunity.contactEmail, opportunity.domaineIA, opportunity.besoinFormation, opportunity.etape].filter(Boolean).join(' '),
      section: 'opportunites_crm' as const,
      sectionLabel: 'Opportunité'
    })) : []),
    ...(canAccessSection(currentRole, 'formateurs_staff') ? formateurs.map(trainer => ({
      id: `trainer-${trainer.id}`,
      title: [trainer.prenom, trainer.nom].filter(Boolean).join(' '),
      description: [trainer.specialite, trainer.email].filter(Boolean).join(' · '),
      searchText: [trainer.prenom, trainer.nom, trainer.specialite, trainer.email, trainer.telephone].filter(Boolean).join(' '),
      section: 'formateurs_staff' as const,
      sectionLabel: 'Formateur'
    })) : []),
    ...(canAccessSection(currentRole, 'facturation_devis') ? factures.map(invoice => ({
      id: `invoice-${invoice.id}`,
      title: `${invoice.type} ${invoice.numero}`,
      description: [invoice.client, invoice.statut, `${invoice.montantTTC.toLocaleString()} Ar TTC`].filter(Boolean).join(' · '),
      searchText: [invoice.type, invoice.numero, invoice.client, invoice.statut].filter(Boolean).join(' '),
      section: 'facturation_devis' as const,
      sectionLabel: 'Facturation'
    })) : []),
    ...(canAccessSection(currentRole, 'veille_marche') ? veilles.map(veille => ({
      id: `veille-${veille.id}`,
      title: veille.titre,
      description: [veille.categorie, veille.impactOrganisme].filter(Boolean).join(' · '),
      searchText: [veille.titre, veille.categorie, veille.description, veille.demandeClient, ...veille.motsCles].filter(Boolean).join(' '),
      section: 'veille_marche' as const,
      sectionLabel: 'Veille marché'
    })) : [])
  ];

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
      {isMobileSidebarOpen && (
        <button
          type="button"
          aria-label="Fermer le menu de navigation"
          onClick={() => setIsMobileSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-slate-950/55 backdrop-blur-[1px] transition-opacity md:hidden"
        />
      )}
      <Sidebar
        currentSection={currentSection}
        isOpen={isDesktopViewport || isMobileSidebarOpen}
        onClose={() => setIsMobileSidebarOpen(false)}
        onSelectSection={(section) => { navigateToSection(section); setIsMobileSidebarOpen(false); }}
        currentRole={currentRole}
        authUser={authUser}
        onOpenAuthModal={handleOpenAuthModal}
        onLogout={handleLogout}
        pendingReviewCount={pendingReviewCount}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          authUser={authUser}
          avatarUrl={avatarUrl}
          searchItems={searchItems}
          onNavigate={navigateToSection}
          isSidebarOpen={isMobileSidebarOpen}
          onToggleSidebar={() => setIsMobileSidebarOpen((open) => !open)}
          onOpenAuthModal={handleOpenAuthModal}
          onLogout={handleLogout}
          onQuickNewOpportunity={() => setIsNewOppModalOpen(true)}
          onQuickNewSession={() => setIsNewSessionModalOpen(true)}
          onQuickNewInvoice={() => openInvoiceModal()}
          onNavigateToFormateurs={() => navigateToSection('formateurs_staff')}
        />

        <main className="flex-1 w-full max-w-[1600px] 2xl:max-w-[1760px] mx-auto p-3 sm:p-6 lg:p-7 2xl:px-9 overflow-y-auto">
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
            dashboardLoading={dashboardLoading}
            dashboardNotice={dashboardNotice}
            onNavigateTo={navigateToSection}
            onOpenNewOpportunity={() => setIsNewOppModalOpen(true)}
            onOpenNewSession={() => setIsNewSessionModalOpen(true)}
            onOpenNewInvoice={openInvoiceModal}
            canManageFormateurs={currentRole === 'Dir.'}
            authUser={authUser}
            avatarUrl={avatarUrl}
            onUploadAvatar={handleUploadProfileAvatar}
            onDeleteAvatar={handleDeleteProfileAvatar}
            onUpdateUser={handleUpdateProfile}
            onBackFromProfile={() => navigateToSection(previousSection)}
          />
        </main>
      </div>

      {/* Global Modals Manager */}
      <ModalManager
        isNewOppModalOpen={isNewOppModalOpen}
        onCloseNewOppModal={() => setIsNewOppModalOpen(false)}
        onCreateOpportunity={handleCreateOpportunity}
        isNewSessionModalOpen={isNewSessionModalOpen}
        onCloseNewSessionModal={() => setIsNewSessionModalOpen(false)}
        onCreateSession={handleCreateSession}
        acceptedMarkets={veilles}
        formateurs={formateurs}
        isNewInvoiceModalOpen={isNewInvoiceModalOpen}
        onCloseNewInvoiceModal={() => { setIsNewInvoiceModalOpen(false); setInvoiceSessionId(''); }}
        onCreateInvoice={handleCreateInvoice}
        sessions={sessions}
        invoiceSessionId={invoiceSessionId}
      />
      <VocalAssistant
        currentRole={currentRole}
        currentSection={currentSection}
        sessions={sessions}
        onNavigate={navigateToSection}
        onCreateSession={() => setIsNewSessionModalOpen(true)}
        onCreateOpportunity={() => setIsNewOppModalOpen(true)}
        onCreateInvoice={() => openInvoiceModal()}
      />
    </div>
  );
}
