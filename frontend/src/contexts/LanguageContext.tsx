import React, { createContext, useCallback, useContext, useState } from 'react';

// ── Langues supportées ───────────────────────────────────────────────────────
export type Lang = 'fr' | 'en' | 'mg';

export const LANG_LABELS: Record<Lang, string> = {
  fr: '🇫🇷 Français',
  en: '🇬🇧 English',
  mg: '🇲🇬 Malagasy',
};

// ── Traductions ──────────────────────────────────────────────────────────────
export const translations: Record<Lang, Record<string, string>> = {
  fr: {
    // Navigation
    'nav.dashboard':       'Tableau de bord',
    'nav.veille':          'Veille marché',
    'nav.opportunites':    'Opportunités CRM',
    'nav.formateurs':      'Formateurs & Staff',
    'nav.competences':     'Évaluation compétences',
    'nav.sessions':        'Sessions & Groupes',
    'nav.presences':       'Suivi des présences',
    'nav.facturation':     'Facturation & Devis',
    'nav.dossiers':        'Dossiers formation',
    'nav.espace_ia':       'Espace IA',
    'nav.utilisateurs':    'Gestion utilisateurs',
    'nav.profil':          'Mon profil',
    'nav.parametres':      'Paramètres',
    'nav.deconnexion':     'Se déconnecter',
    'nav.changer_compte':  'Changer de compte',
    // Header
    'header.search':       'Rechercher une session, une opportunité…',
    'header.notifications':'Candidatures récentes',
    'header.a_traiter':    'à traiter',
    'header.aucune_cand':  'Aucune candidature dans les 48 dernières heures.',
    'header.voir_toutes':  'Voir toutes les candidatures →',
    // Paramètres
    'settings.title':      'Paramètres',
    'settings.llm':        'Configuration LLM',
    'settings.langue':     'Langue de l\'interface',
    'settings.langue_desc':'La langue s\'applique immédiatement à toute la plateforme.',
    // Général
    'common.annuler':      'Annuler',
    'common.enregistrer':  'Enregistrer',
    'common.confirmer':    'Confirmer',
    'common.chargement':   'Chargement…',
    'common.erreur':       'Une erreur est survenue.',
    'common.succes':       'Opération réussie.',
    'common.recherche':    'Recherche',
    'common.aucun_resultat':'Aucun résultat',
    'common.creer':        'Créer',
    'common.modifier':     'Modifier',
    'common.supprimer':    'Supprimer',
    'common.fermer':       'Fermer',
    'common.retour':       'Retour',
    'common.voir':         'Voir',
    'common.telecharger':  'Télécharger',
    // Actions rapides
    'quick.opportunite':   'Opportunité',
    'quick.session':       'Session',
    'quick.devis':         'Devis / Facture',
    'quick.actions':       'Actions rapides',
    'quick.creer_opp':     'Créer une opportunité',
    'quick.creer_session': 'Créer une session',
    'quick.creer_devis':   'Créer un devis / une facture',
    // Résultats recherche
    'search.min_chars':    'Saisissez au moins 2 caractères pour chercher dans les données disponibles.',
    'search.aucun':        'Aucun résultat dans les données actuellement chargées.',
    'search.disponibles':  'Résultats disponibles',
    'search.info':         'Recherche parmi les données déjà chargées pour votre rôle.',
  },

  en: {
    // Navigation
    'nav.dashboard':       'Dashboard',
    'nav.veille':          'Market Watch',
    'nav.opportunites':    'CRM Opportunities',
    'nav.formateurs':      'Trainers & Staff',
    'nav.competences':     'Skills Assessment',
    'nav.sessions':        'Sessions & Groups',
    'nav.presences':       'Attendance Tracking',
    'nav.facturation':     'Billing & Quotes',
    'nav.dossiers':        'Training Files',
    'nav.espace_ia':       'AI Workspace',
    'nav.utilisateurs':    'User Management',
    'nav.profil':          'My Profile',
    'nav.parametres':      'Settings',
    'nav.deconnexion':     'Sign out',
    'nav.changer_compte':  'Switch account',
    // Header
    'header.search':       'Search for a session, an opportunity…',
    'header.notifications':'Recent applications',
    'header.a_traiter':    'to process',
    'header.aucune_cand':  'No applications in the last 48 hours.',
    'header.voir_toutes':  'View all applications →',
    // Paramètres
    'settings.title':      'Settings',
    'settings.llm':        'LLM Configuration',
    'settings.langue':     'Interface language',
    'settings.langue_desc':'Language applies immediately across the entire platform.',
    // Général
    'common.annuler':      'Cancel',
    'common.enregistrer':  'Save',
    'common.confirmer':    'Confirm',
    'common.chargement':   'Loading…',
    'common.erreur':       'An error occurred.',
    'common.succes':       'Operation successful.',
    'common.recherche':    'Search',
    'common.aucun_resultat':'No results',
    'common.creer':        'Create',
    'common.modifier':     'Edit',
    'common.supprimer':    'Delete',
    'common.fermer':       'Close',
    'common.retour':       'Back',
    'common.voir':         'View',
    'common.telecharger':  'Download',
    // Actions rapides
    'quick.opportunite':   'Opportunity',
    'quick.session':       'Session',
    'quick.devis':         'Quote / Invoice',
    'quick.actions':       'Quick actions',
    'quick.creer_opp':     'Create an opportunity',
    'quick.creer_session': 'Create a session',
    'quick.creer_devis':   'Create a quote / invoice',
    // Résultats recherche
    'search.min_chars':    'Type at least 2 characters to search the loaded data.',
    'search.aucun':        'No results in the currently loaded data.',
    'search.disponibles':  'Available results',
    'search.info':         'Searching within data already loaded for your role.',
  },

  mg: {
    // Navigation
    'nav.dashboard':       'Fitsarana',
    'nav.veille':          'Fanaraha-maso tsena',
    'nav.opportunites':    'Tombontsoa CRM',
    'nav.formateurs':      'Mpampiofana & Staff',
    'nav.competences':     'Fanombanana fahaiza-manao',
    'nav.sessions':        'Fiatrehan-drenin-kazo',
    'nav.presences':       'Fanaraha-maso fanatrehana',
    'nav.facturation':     'Faktiora & Fanatanterahana',
    'nav.dossiers':        'Antontan-taratasy fiofanana',
    'nav.espace_ia':       'Eran-toerana AI',
    'nav.utilisateurs':    'Fitantanam-mpampiasa',
    'nav.profil':          'Mombamomba ahy',
    'nav.parametres':      'Fikirana',
    'nav.deconnexion':     'Mivoaka',
    'nav.changer_compte':  'Manova kaonty',
    // Header
    'header.search':       'Hikaroka fivoriana, tombontsoa…',
    'header.notifications':'Fangatahana nampidirina',
    'header.a_traiter':    'hodinihina',
    'header.aucune_cand':  'Tsy misy fangatahana ao anatin\'ny 48 ora lasa.',
    'header.voir_toutes':  'Hijery fangatahana rehetra →',
    // Paramètres
    'settings.title':      'Fikirana',
    'settings.llm':        'Fikirana LLM',
    'settings.langue':     'Fiteny fampiasana',
    'settings.langue_desc':'Ny fiteny dia mihatra avy hatrany amin\'ny sehatra manontolo.',
    // Général
    'common.annuler':      'Hanafoana',
    'common.enregistrer':  'Hitahiry',
    'common.confirmer':    'Hanamafy',
    'common.chargement':   'Miampy…',
    'common.erreur':       'Nisy fahadisoana.',
    'common.succes':       'Vita soamantsara.',
    'common.recherche':    'Fikarohana',
    'common.aucun_resultat':'Tsy misy valiny',
    'common.creer':        'Hamorona',
    'common.modifier':     'Hanova',
    'common.supprimer':    'Hamafa',
    'common.fermer':       'Hanidy',
    'common.retour':       'Hiverina',
    'common.voir':         'Hijery',
    'common.telecharger':  'Hisintona',
    // Actions rapides
    'quick.opportunite':   'Tombontsoa',
    'quick.session':       'Fivoriana',
    'quick.devis':         'Fanatanterahana / Faktiora',
    'quick.actions':       'Hetsika haingana',
    'quick.creer_opp':     'Hamorona tombontsoa',
    'quick.creer_session': 'Hamorona fivoriana',
    'quick.creer_devis':   'Hamorona fanatanterahana',
    // Résultats recherche
    'search.min_chars':    'Soraty litera 2 farafahakeliny hikaroka.',
    'search.aucun':        'Tsy misy valiny amin\'ny angona efa nampidirana.',
    'search.disponibles':  'Valiny misy',
    'search.info':         'Fikarohana amin\'ny angona efa nampidirana ho an\'ny andraikitrao.',
  },
};

// ── Context ──────────────────────────────────────────────────────────────────
interface LanguageContextType {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, fallback?: string) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  lang: 'fr',
  setLang: () => {},
  t: (key) => key,
});

const STORAGE_KEY = 'formaia-lang';

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Lang | null;
      return saved && saved in LANG_LABELS ? saved : 'fr';
    } catch {
      return 'fr';
    }
  });

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* ignore */ }
    // Mettre à jour l'attribut lang du document HTML
    document.documentElement.lang = l;
  }, []);

  const t = useCallback((key: string, fallback?: string): string => {
    return translations[lang]?.[key] ?? translations['fr']?.[key] ?? fallback ?? key;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
