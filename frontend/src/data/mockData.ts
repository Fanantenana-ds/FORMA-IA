import {
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
} from '../types';

export const initialKPIs: KPIStats = {
  sessionsRealisees: 37,
  participantsFormes: 412,
  tauxPresenceMoyen: 91,
  opportunitesDetectees: 54
};

export const initialDomainOpportunities: DomainOpportunity[] = [
  { domaine: 'IA Générative & LLMs', nombre: 18, valeurEstimee: 105000, croissance: 34, couleur: '#1B8F6E' },
  { domaine: 'Cybersécurité & IA', nombre: 12, valeurEstimee: 72000, croissance: 22, couleur: '#2563EB' },
  { domaine: 'Prompt Engineering Business', nombre: 10, valeurEstimee: 48000, croissance: 15, couleur: '#D97706' },
  { domaine: 'Machine Learning & MLOps', nombre: 8, valeurEstimee: 39000, croissance: 11, couleur: '#8B5CF6' },
  { domaine: 'Gouvernance & Compliance IA (EU AI Act)', nombre: 6, valeurEstimee: 36000, croissance: 28, couleur: '#EC4899' }
];

export const initialFacturationStatuts: FacturationStatut[] = [
  { statut: 'Payé', montant: 185000, nombreFactures: 42, pourcentage: 58, couleur: '#10B981' },
  { statut: 'En attente', montant: 65000, nombreFactures: 14, pourcentage: 21, couleur: '#F59E0B' },
  { statut: 'Devis envoyé', montant: 45000, nombreFactures: 9, pourcentage: 14, couleur: '#3B82F6' },
  { statut: 'En retard', montant: 22000, nombreFactures: 4, pourcentage: 7, couleur: '#EF4444' }
];

export const initialActivites: ActiviteRecente[] = [
  {
    id: 'act-1',
    titre: 'Session "IA Générative pour Managers" clôturée',
    description: '32 participants évalués - Taux de satisfaction : 98%',
    horodateur: 'Il y a 15 min',
    type: 'session',
    statutTag: 'Complétée',
    utilisateur: 'Claire Dupont (Formateur)'
  },
  {
    id: 'act-2',
    titre: 'Nouvelle opportunité qualifiée : Thales Digital',
    description: 'Demande sur-mesure : Formation "Compliance EU AI Act" pour 45 ingénieurs',
    horodateur: 'Il y a 1 heure',
    type: 'opportunite',
    statutTag: 'Devis prêt (28 000 Ar)',
    utilisateur: 'Moteur Veille IA'
  },
  {
    id: 'act-3',
    titre: 'Émargement numérique validé - Groupe IA-Dev #2026-B',
    description: 'Presence confirmée à 100% (18/18 apprenants) via l’application',
    horodateur: 'Il y a 2 heures',
    type: 'presence',
    statutTag: 'Présence 100%',
    utilisateur: 'Marc Vasseur'
  },
  {
    id: 'act-4',
    titre: 'Facture #FAC-2026-089 réglée',
    description: 'Paiement reçu de Banque Populaire (12 500 Ar HT)',
    horodateur: 'Il y a 3 heures',
    type: 'facture',
    statutTag: 'Payée',
    utilisateur: 'Système Comptable'
  },
  {
    id: 'act-5',
    titre: 'Signalement Veille : Nouvelle norme de certification QUALIOPI IA',
    description: 'Ajout de 3 critères requis pour l’usage de modèles génératifs en atelier',
    horodateur: 'Hier à 17:30',
    type: 'veille',
    statutTag: 'Action requise',
    utilisateur: 'IA Veilleur'
  }
];

export const initialSessions: Session[] = [
  {
    id: 'sess-101',
    code: 'FORMA-IA-2026-01',
    intitule: 'Masterclass IA Générative & Agentic Workflows',
    domaine: 'IA Générative & LLMs',
    formateur: 'Dr. Alex Moreau',
    dates: '12 - 14 Août 2026',
    participantsInscrits: 18,
    capacityMax: 20,
    tauxPresence: 95,
    statut: 'En cours',
    lieu: 'Présentiel',
    prixUnitaire: 1450
  },
  {
    id: 'sess-102',
    code: 'FORMA-IA-2026-02',
    intitule: 'Sécuriser les architectures IA & RAG entreprise',
    domaine: 'Cybersécurité & IA',
    formateur: 'Sophie Bernard',
    dates: '18 - 20 Août 2026',
    participantsInscrits: 15,
    capacityMax: 15,
    tauxPresence: 90,
    statut: 'Planifiée',
    lieu: 'Distanciel',
    prixUnitaire: 1600
  },
  {
    id: 'sess-103',
    code: 'FORMA-IA-2026-03',
    intitule: 'Conformité EU AI Act pour Directeurs Juridiques & IT',
    domaine: 'Gouvernance & Compliance',
    formateur: 'Maître Jean-Luc Roch',
    dates: '25 Août 2026',
    participantsInscrits: 24,
    capacityMax: 30,
    tauxPresence: 88,
    statut: 'Planifiée',
    lieu: 'Hybride',
    prixUnitaire: 950
  },
  {
    id: 'sess-104',
    code: 'FORMA-IA-2026-04',
    intitule: 'Prompt Engineering Avancé pour Équipes Marketing',
    domaine: 'Prompt Engineering',
    formateur: 'Claire Dupont',
    dates: '01 - 02 Août 2026',
    participantsInscrits: 22,
    capacityMax: 22,
    tauxPresence: 96,
    statut: 'Terminée',
    lieu: 'Distanciel',
    prixUnitaire: 1200
  },
  {
    id: 'sess-105',
    code: 'FORMA-IA-2026-05',
    intitule: 'Déploiement LLM Open-Source en Environnement Cloud Privé',
    domaine: 'Machine Learning & MLOps',
    formateur: 'Karim Benali',
    dates: '02 - 04 Sept. 2026',
    participantsInscrits: 12,
    capacityMax: 16,
    tauxPresence: 0,
    statut: 'Planifiée',
    lieu: 'Présentiel',
    prixUnitaire: 1800
  }
];

export const initialOpportunites: OpportuniteCRM[] = [
  {
    id: 'opp-201',
    entreprise: 'Airbus Defence & Space',
    contactName: 'Lucie Marchand',
    contactEmail: 'l.marchand@airbus.com',
    domaineIA: 'LLM Ops & Sécurité',
    besoinFormation: 'Formation sur-mesure de 60 ingénieurs sur la sécurisation des prompts et modèles RAG',
    participantsEstimes: 60,
    montantEstime: 48000,
    etape: 'Devis transmis',
    probabilite: 80,
    dateDetection: '04/08/2026'
  },
  {
    id: 'opp-202',
    entreprise: 'Société Générale Tech',
    contactName: 'Antoine Laurent',
    contactEmail: 'a.laurent@socgen.com',
    domaineIA: 'Gouvernance & EU AI Act',
    besoinFormation: 'Mise en conformité des modèles d’évaluation du risque de crédit',
    participantsEstimes: 25,
    montantEstime: 32000,
    etape: 'Contact qualifié',
    probabilite: 60,
    dateDetection: '06/08/2026'
  },
  {
    id: 'opp-203',
    entreprise: 'Decathlon Digital',
    contactName: 'Camille Leroy',
    contactEmail: 'c.leroy@decathlon.com',
    domaineIA: 'IA Générative pour le Design & Product Management',
    besoinFormation: 'Accélération des processus créatifs et prototypage IA',
    participantsEstimes: 40,
    montantEstime: 26000,
    etape: 'Détectée par IA',
    probabilite: 40,
    dateDetection: '08/08/2026'
  },
  {
    id: 'opp-204',
    entreprise: 'L’Oréal Luxe Innovation',
    contactName: 'Nathalie Fournier',
    contactEmail: 'n.fournier@loreal.com',
    domaineIA: 'Automatisations Workflow IA (N8N / LangChain)',
    besoinFormation: 'Automatisation des analyses consommateurs et création de contenus marketing',
    participantsEstimes: 30,
    montantEstime: 38000,
    etape: 'Gagnée',
    probabilite: 100,
    dateDetection: '28/07/2026'
  }
];

export const initialFormateurs: Formateur[] = [
  {
    id: 'form-1',
    nom: 'Dr. Alex Moreau',
    specialites: ['IA Générative', 'Transformers', 'LangChain', 'Python'],
    statut: 'En session',
    tauxSatisfaction: 4.95,
    tarifJournalier: 1200,
    email: 'a.moreau@forma-ia.fr',
    telephone: '+33 6 12 34 56 78',
    sessionsCompteur: 24,
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150',
    evaluations: [
      {
        id: 'eval-1',
        formateurId: 'form-1',
        apprenantNom: 'Hasina Rakoto',
        entreprise: 'TELMA Madagascar',
        date: '08/08/2026',
        notePedagogie: 5,
        noteMaitriseTech: 5,
        noteSupports: 5,
        notePonctualite: 5,
        noteMoyenne: 5.0,
        commentaire: 'Excellente pédagogie sur la mise en place des agents avec LangChain et FastAPI. Explication très claire des mécanismes d\'attention.',
        recommande: true
      },
      {
        id: 'eval-2',
        formateurId: 'form-1',
        apprenantNom: 'Élodie Roux',
        entreprise: 'BNP Paribas',
        date: '02/08/2026',
        notePedagogie: 5,
        noteMaitriseTech: 5,
        noteSupports: 4,
        notePonctualite: 5,
        noteMoyenne: 4.8,
        commentaire: 'Excellente maîtrise technique. Les exercices pratiques sur les Transformers et RAG étaient très enrichissants.',
        recommande: true
      }
    ]
  },
  {
    id: 'form-2',
    nom: 'Sophie Bernard',
    specialites: ['Cybersécurité IA', 'RAG Security', 'Pentest LLM'],
    statut: 'Disponible',
    tauxSatisfaction: 4.88,
    tarifJournalier: 1350,
    email: 's.bernard@forma-ia.fr',
    telephone: '+33 6 98 76 54 32',
    sessionsCompteur: 18,
    avatarUrl: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&q=80&w=150',
    evaluations: [
      {
        id: 'eval-3',
        formateurId: 'form-2',
        apprenantNom: 'Mialy Andria',
        entreprise: 'Bank Of Africa',
        date: '06/08/2026',
        notePedagogie: 5,
        noteMaitriseTech: 5,
        noteSupports: 5,
        notePonctualite: 4,
        noteMoyenne: 4.8,
        commentaire: 'Exposé d\'une grande précision sur la sécurité des bases vectorielles et le filtrage des fuites de PII dans les architectures RAG bancaires.',
        recommande: true
      }
    ]
  },
  {
    id: 'form-3',
    nom: 'Claire Dupont',
    specialites: ['Prompt Engineering', 'GenAI Business', 'No-Code IA'],
    statut: 'Disponible',
    tauxSatisfaction: 4.92,
    tarifJournalier: 950,
    email: 'c.dupont@forma-ia.fr',
    telephone: '+33 6 45 67 89 10',
    sessionsCompteur: 31,
    avatarUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&q=80&w=150',
    evaluations: [
      {
        id: 'eval-4',
        formateurId: 'form-3',
        apprenantNom: 'Nathalie Fournier',
        entreprise: 'L\'Oréal Digital',
        date: '28/07/2026',
        notePedagogie: 5,
        noteMaitriseTech: 5,
        noteSupports: 5,
        notePonctualite: 5,
        noteMoyenne: 5.0,
        commentaire: 'Atelier de prompt engineering sur mesure pour les équipes marketing. Résultats immédiats constatés.',
        recommande: true
      }
    ]
  },
  {
    id: 'form-4',
    nom: 'Karim Benali',
    specialites: ['MLOps', 'PyTorch', 'Kubernetes', 'Fine-Tuning Llama'],
    statut: 'En session',
    tauxSatisfaction: 4.91,
    tarifJournalier: 1400,
    email: 'k.benali@forma-ia.fr',
    telephone: '+33 6 23 45 67 89',
    sessionsCompteur: 15,
    avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=150',
    evaluations: [
      {
        id: 'eval-5',
        formateurId: 'form-4',
        apprenantNom: 'Julien Mercier',
        entreprise: 'Orange Business',
        date: '20/07/2026',
        notePedagogie: 5,
        noteMaitriseTech: 5,
        noteSupports: 4,
        notePonctualite: 5,
        noteMoyenne: 4.8,
        commentaire: 'Excellente session MLOps. Déploiement Kubernetes de modèles Llama 3 très instructif.',
        recommande: true
      }
    ]
  }
];

export const initialPresences: PresenceRecord[] = [
  {
    id: 'pres-1',
    sessionId: 'sess-101',
    sessionTitle: 'Masterclass IA Générative & Agentic Workflows',
    apprenantNom: 'Thomas Girard',
    entreprise: 'Capgemini Tech',
    date: '10/08/2026',
    statut: 'Présent',
    heureEmargement: '08:58'
  },
  {
    id: 'pres-2',
    sessionId: 'sess-101',
    sessionTitle: 'Masterclass IA Générative & Agentic Workflows',
    apprenantNom: 'Élodie Roux',
    entreprise: 'BNP Paribas',
    date: '10/08/2026',
    statut: 'Présent',
    heureEmargement: '09:02'
  },
  {
    id: 'pres-3',
    sessionId: 'sess-101',
    sessionTitle: 'Masterclass IA Générative & Agentic Workflows',
    apprenantNom: 'Julien Mercier',
    entreprise: 'Orange Business',
    date: '10/08/2026',
    statut: 'Retard',
    heureEmargement: '09:24'
  },
  {
    id: 'pres-4',
    sessionId: 'sess-101',
    sessionTitle: 'Masterclass IA Générative & Agentic Workflows',
    apprenantNom: 'Marion Lambert',
    entreprise: 'SNCF Réseau',
    date: '10/08/2026',
    statut: 'Absent',
    heureEmargement: undefined
  },
  {
    id: 'pres-5',
    sessionId: 'sess-101',
    sessionTitle: 'Masterclass IA Générative & Agentic Workflows',
    apprenantNom: 'Hasina Rakoto',
    entreprise: 'TELMA Madagascar',
    date: '10/08/2026',
    statut: 'Présent',
    heureEmargement: '08:55'
  },
  {
    id: 'pres-6',
    sessionId: 'sess-102',
    sessionTitle: 'Sécuriser les architectures IA & RAG entreprise',
    apprenantNom: 'Arnaud Dejean',
    entreprise: 'Airbus Defence',
    date: '18/08/2026',
    statut: 'Présent',
    heureEmargement: '09:00'
  },
  {
    id: 'pres-7',
    sessionId: 'sess-102',
    sessionTitle: 'Sécuriser les architectures IA & RAG entreprise',
    apprenantNom: 'Clara Vasseur',
    entreprise: 'Thales Cyber',
    date: '18/08/2026',
    statut: 'Absent',
    heureEmargement: undefined
  },
  {
    id: 'pres-8',
    sessionId: 'sess-103',
    sessionTitle: 'Conformité EU AI Act pour Directeurs Juridiques & IT',
    apprenantNom: 'Mialy Andria',
    entreprise: 'Bank Of Africa',
    date: '25/08/2026',
    statut: 'Présent',
    heureEmargement: '08:45'
  }
];

export const initialFactures: DevisFacture[] = [
  {
    id: 'fac-1',
    numero: 'FAC-2026-089',
    type: 'Facture',
    client: 'Banque Populaire',
    montantHT: 12500,
    montantTTC: 15000,
    dateEmission: '01/08/2026',
    dateEcheance: '31/08/2026',
    statut: 'Payé'
  },
  {
    id: 'fac-2',
    numero: 'DEV-2026-114',
    type: 'Devis',
    client: 'Airbus Defence & Space',
    montantHT: 48000,
    montantTTC: 57600,
    dateEmission: '04/08/2026',
    dateEcheance: '18/08/2026',
    statut: 'Envoyé'
  },
  {
    id: 'fac-3',
    numero: 'FAC-2026-085',
    type: 'Facture',
    client: 'Thales Group',
    montantHT: 18000,
    montantTTC: 21600,
    dateEmission: '15/07/2026',
    dateEcheance: '15/08/2026',
    statut: 'En attente'
  },
  {
    id: 'fac-4',
    numero: 'FAC-2026-072',
    type: 'Facture',
    client: 'Sopra Steria',
    montantHT: 9500,
    montantTTC: 11400,
    dateEmission: '10/06/2026',
    dateEcheance: '10/07/2026',
    statut: 'En retard'
  }
];

export const initialVeilles: VeilleMarche[] = [
  {
    id: 'veil-1',
    titre: 'Projet VINA - Plateforme de suivi-évaluation augmentée par IA',
    categorie: 'IA Générative & BPO',
    description: 'Conception et déploiement d’une plateforme unifiée de gestion, suivi et évaluation de projets augmentée par IA (API Claude, RAG, cadres logiques).',
    impactOrganisme: 'Majeur',
    demandeClient: 'Projet retenu - Financement validé',
    dateAnalyse: '10/08/2026',
    motsCles: ['VINA', 'ALTIORA', 'ENI', 'RAG', 'Suivi-Évaluation'],
    statut: 'Accepté',
    clientCible: 'ENI Madagascar × ALTIORA PREST',
    budgetEstimeAr: 12500000,
    tdrSummary: 'Stage & Prestation 4 mois (16 semaines) - Master Informatique ENI',
    otSummary: 'Offre technique avec modèle FastAPI, orchestration Claude/LangChain & PostgreSQL'
  },
  {
    id: 'veil-2',
    titre: 'Masterclass Agents Autonomes & Workflows Multi-Agents (CrewAI, LangGraph)',
    categorie: 'Technologie IA',
    description: 'Formation intensive et atelier d’implémentation d’agents autonomes avec garde-fous de sécurité pour équipes bancaires et télécoms.',
    impactOrganisme: 'Majeur',
    demandeClient: 'Offre acceptée par la direction technique',
    dateAnalyse: '08/08/2026',
    motsCles: ['Agents IA', 'CrewAI', 'LangGraph', 'Autonomie'],
    statut: 'Accepté',
    clientCible: 'TELMA Madagascar',
    budgetEstimeAr: 8500000,
    tdrSummary: 'TDR validé pour 15 participants - Durée 3 jours',
    otSummary: 'Offre Pédagogique & Technique certifiée FORMA-IA'
  },
  {
    id: 'veil-3',
    titre: 'Audit & Conformité EU AI Act et Cyber-Sécurité des Données Bancaires',
    categorie: 'Réglementation & Normes',
    description: 'Obligation de formation des Risk Managers et DPO aux risques de fuite de données et filtrage PII dans les architectures RAG.',
    impactOrganisme: 'Majeur',
    demandeClient: 'Appel d’offres gagné',
    dateAnalyse: '06/08/2026',
    motsCles: ['EU AI Act', 'Compliance', 'Audit IA', 'Risk Management'],
    statut: 'Accepté',
    clientCible: 'Bank Of Africa Madagascar',
    budgetEstimeAr: 9200000,
    tdrSummary: 'TDR Sécurisation des LLMs bancaires',
    otSummary: 'OT Module Risk & Guardrails'
  },
  {
    id: 'veil-4',
    titre: 'Digitalisation des Services Publics par l’IA Générative',
    categorie: 'Secteur Public & ONG',
    description: 'Détection d’opportunité d’automatisation du traitement des requêtes citoyennes et rédaction automatique de rapports administratifs.',
    impactOrganisme: 'Majeur',
    demandeClient: 'Marché identifié en phase de prospection',
    dateAnalyse: '04/08/2026',
    motsCles: ['Gouvernance', 'Secteur Public', 'Rapports IA'],
    statut: 'Trouvé',
    clientCible: 'Ministère du Développement Numérique',
    budgetEstimeAr: 15000000,
    tdrSummary: 'TDR Cadrage gouvernance numérique',
    otSummary: 'Offre Technique en attente de soumission'
  },
  {
    id: 'veil-5',
    titre: 'Acculturation & Prompt Engineering pour Directeurs Financiers',
    categorie: 'Financement Formation',
    description: 'Programme sur mesure pour l’analyse prédictive et la synthèse intelligente de business plans via assistants IA personnalisés.',
    impactOrganisme: 'Moyen',
    demandeClient: 'En cours d’évaluation client',
    dateAnalyse: '02/08/2026',
    motsCles: ['Finance', 'Business Plan', 'Prompting'],
    statut: 'Trouvé',
    clientCible: 'Groupe AXIAN',
    budgetEstimeAr: 6800000,
    tdrSummary: 'TDR Formation Cadres Dirigeants',
    otSummary: 'OT Module Finance Augmentée'
  }
];
