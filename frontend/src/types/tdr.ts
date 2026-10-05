export interface TdrDocModel {
  projetCode: string;
  projetTitre: string;
  clientOrganisme: string;
  partenaireAcademic: string;
  anneeAcademique: string;
  dureePrestation: string;
  datesDebutFin: string;
  etudiantAssign: string;
  encadreurPro: string;
  encadreurAcademic: string;
  versionDate: string;
  
  // Section 1: Contexte
  presentationClient: string;
  positionnementProjet: string;
  justificationBesoin: string;
  
  // Section 2: Objectifs
  problematique: string;
  objectifGeneral: string;
  objectifsSMART: string[];
  resultatsAttendus: string[];
  
  // Section 3: Planning
  planningPhases: { phase: string; semaines: string; activites: string; livrable: string }[];
  
  // Section 4: Profil
  niveauRequis: string;
  competencesTech: string[];
  competencesComportement: string[];
  
  // Section 5: Conditions
  cadreGeneral: string;
  encadrementRythme: string;
  conditionsMaterielles: string;
  
  // Section 6: Livrables
  livrablesTable: { id: number; livrable: string; echeance: string; destinataire: string; validation: string }[];
  
  // Section 7: Grille d'évaluation
  grilleEvaluation: { critere: string; poids: string; evaluateur: string }[];
}

export interface OtDocModel {
  referenceOt: string;
  clientOrganisme: string;
  intituleFormation: string;
  formateurRef: string;
  dureeAtelier: string;
  methodologiePedago: string;
  programmeModules: { module: string; duree: string; description: string }[];
  budgetDetails: { designation: string; quantite: number; prixUnitaireAr: number; totalAr: number }[];
  budgetTotalAr: number;
  garantiesEtPropretie: string;
}

export interface AcceptedMarket {
  id: string;
  titre: string;
  client: string;
  domaine: string;
  budgetAr: number;
  duree: string;
  date: string;
  statut: string;
}

export const DEFAULT_ACCEPTED_MARKETS: AcceptedMarket[] = [
  {
    id: 'mkt-vina',
    titre: 'Projet VINA - Plateforme de suivi-évaluation augmentée par IA',
    client: 'ENI Madagascar × ALTIORA PREST',
    domaine: 'IA Générative & BPO',
    budgetAr: 12500000,
    duree: '4 mois (16 semaines)',
    date: '10/08/2026',
    statut: 'Accepté'
  },
  {
    id: 'mkt-telma',
    titre: 'Masterclass Agents Autonomes & Workflows Multi-Agents',
    client: 'TELMA Madagascar',
    domaine: 'Frameworks LangGraph & CrewAI',
    budgetAr: 8500000,
    duree: '3 jours (21h)',
    date: '08/08/2026',
    statut: 'Accepté'
  },
  {
    id: 'mkt-boa',
    titre: 'Audit & Conformité EU AI Act et Cyber-Sécurité Bancaire',
    client: 'Bank Of Africa Madagascar',
    domaine: 'Compliance & Guardrails RAG',
    budgetAr: 9200000,
    duree: '2 jours (14h)',
    date: '06/08/2026',
    statut: 'Accepté'
  }
];

export const INITIAL_TDR_DATA: TdrDocModel = {
  projetCode: 'VINA',
  projetTitre: 'Plateforme de gestion, de suivi et d’évaluation de projets augmentée par l’IA',
  clientOrganisme: 'ALTIORA PREST (Cabinet de conseil & formation)',
  partenaireAcademic: 'École Nationale d’Informatique (ENI) — Fianarantsoa, Madagascar',
  anneeAcademique: '2025–2026',
  dureePrestation: '4 mois (16 semaines consécutives)',
  datesDebutFin: 'Du 01/09/2026 au 31/12/2026',
  etudiantAssign: 'Hasina RAKOTOMANANA (Master 2 Génie Logiciel ENI)',
  encadreurPro: 'M. Principal Consultant IA (ALTIORA PREST)',
  encadreurAcademic: 'Prof. Titulaire Chaire IA (ENI Fianarantsoa)',
  versionDate: 'v1.2 — 10/08/2026',

  presentationClient:
    'ALTIORA PREST est une entreprise dynamique spécialisée dans les prestations intellectuelles, le conseil en transformation digitale et les services d’Externalisation des Processus Métier (BPO). Dans un contexte où la réactivité et la précision du suivi de projets sont primordiales, ALTIORA souhaite intégrer des briques d’Intelligence Artificielle à son système d’information.',

  positionnementProjet:
    'Le projet VINA vise à doter ALTIORA d’une plateforme web interne intégrant des assistants virtuels intelligents capables d’automatiser la collecte d’indicateurs, de générer des synthèses d’avancement et d’alerter en cas de déviation par rapport aux objectifs.',

  justificationBesoin:
    'Le suivi de projets complexes reposait jusqu’à présent sur des processus manuels chronophages. L’intégration d’agents IA permettra de réduire de 60% le temps de synthèse pour le comité de direction.',

  problematique:
    'Comment concevoir et déployer une plateforme logicielle moderne intégrant de l’IA générative et de la recherche vectorielle (RAG) pour automatiser le suivi-évaluation sans altérer la rigueur des données ?',

  objectifGeneral:
    'Concevoir, développer et déployer la plateforme VINA et formaliser une méthodologie reproductible d’intégration d’IA pour les projets du cabinet ALTIORA.',

  objectifsSMART: [
    'SMART 1 : Livrer un prototype fonctionnel d’assistant IA (FastAPI + Claude API) sous 12 semaines.',
    'SMART 2 : Automatiser à 80% la génération des comptes-rendus de réunions et rapports BPF.',
    'SMART 3 : Former au moins 10 collaborateurs d’ALTIORA à l’utilisation des agents IA d’ici fin 2026.'
  ],

  resultatsAttendus: [
    'Une plateforme web fonctionnelle (Frontend React + Backend Python FastAPI + PostgreSQL).',
    'Un module Assistant IA pour la génération automatique de rapports BPF et d’alertes.',
    'Un guide méthodologique d’intégration de l’IA dans les processus BPO.',
    'Le mémoire de stage de fin d’études conforme aux exigences académiques de l’ENI.'
  ],

  planningPhases: [
    {
      phase: 'Ph. 1 — Cadrage',
      semaines: 'S1–S2',
      activites: 'Étude de l’existant chez ALTIORA, spécifications fonctionnelles, revue de littérature IA',
      livrable: 'Rapport de cadrage + Architecture cible'
    },
    {
      phase: 'Ph. 2 — Conception',
      semaines: 'S3–S5',
      activites: 'Modélisation du cycle projet, maquettes UI/UX, catalogue de prompts RTFCE',
      livrable: 'Dossier de conception validé'
    },
    {
      phase: 'Ph. 3 — Réalisation',
      semaines: 'S6–S11',
      activites: 'Socle gestion & suivi (WBS, indicateurs) + Assistant IA rapports & alertes',
      livrable: 'Socle validé avec portefeuille pilote chargé'
    },
    {
      phase: 'Ph. 4 — Service',
      semaines: 'S12–S13',
      activites: 'Déploiement Docker, tableaux de bord, formation des utilisateurs et recette',
      livrable: 'Plateforme en service + documentation'
    },
    {
      phase: 'Ph. 5 — Mémoire',
      semaines: 'S14–S16',
      activites: 'Rédaction du mémoire (norme ENI) et préparation de la soutenance orale',
      livrable: 'Mémoire final + Soutenance ENI'
    }
  ],

  niveauRequis: 'Master Informatique — ENI Madagascar (Génie Logiciel / Systèmes d’Information)',

  competencesTech: [
    'Python 3.10+ (FastAPI, typage rigoureux, POO)',
    'SQL & Modélisation relationnelle (PostgreSQL)',
    'Notions d’intégration LLM (API Claude Anthropic, LangChain / RAG)',
    'Visualisation de données et tableaux de bord web',
    'Git & Notions de conteneurisation Docker'
  ],

  competencesComportement: [
    'Rigueur méthodologique et écoute des utilisateurs',
    'Autonomie, respect des délais et rédaction académique',
    'Sens de l’éthique de l’IA (l’IA assiste, l’humain décide)'
  ],

  cadreGeneral: 'Durée : 4 mois (16 semaines consécutives) en présentiel chez ALTIORA Antananarivo.',

  encadrementRythme: 'Réunion de suivi hebdomadaire + Comité pilote bimensuel direction.',

  conditionsMaterielles: 'Poste de travail fourni, accès aux API Claude, connexion internet professionnelle.',

  livrablesTable: [
    {
      id: 1,
      livrable: 'Rapport d’étonnement + Plan de travail détaillé',
      echeance: 'Fin S2',
      destinataire: 'ALTIORA',
      validation: 'Encadreur pro'
    },
    {
      id: 2,
      livrable: 'Dossier de conception technique et fonctionnelle',
      echeance: 'Fin S5',
      destinataire: 'ALTIORA',
      validation: 'Comité pilote'
    },
    {
      id: 3,
      livrable: 'Plateforme VINA déployée avec assistant IA',
      echeance: 'Fin S13',
      destinataire: 'ALTIORA + ENI',
      validation: 'Recette finale'
    },
    {
      id: 4,
      livrable: 'Mémoire de stage conforme norme ENI',
      echeance: 'Fin S15',
      destinataire: 'Jury ENI',
      validation: 'Encadreur académique'
    }
  ],

  grilleEvaluation: [
    { critere: 'Qualité du livrable technique & Assistant IA', poids: '35%', evaluateur: 'ALTIORA' },
    { critere: 'Qualité du mémoire académique (normes ENI)', poids: '30%', evaluateur: 'Jury ENI' },
    { critere: 'Soutenance orale (clarté & réponses aux questions)', poids: '20%', evaluateur: 'Jury ENI' },
    { critere: 'Comportement professionnel & assiduité', poids: '15%', evaluateur: 'ALTIORA' }
  ]
};

export const INITIAL_OT_DATA: OtDocModel = {
  referenceOt: 'OT-2026-FORMAIA-089',
  clientOrganisme: 'ENI Madagascar × ALTIORA PREST',
  intituleFormation: 'Projet VINA - Plateforme de suivi-évaluation augmentée par IA',
  formateurRef: 'Dr. Hasina R. (PhD IA & RAG Senior Consultant)',
  dureeAtelier: '4 mois (16 semaines)',
  methodologiePedago: '75% Pratique appliquée sur environnement Cloud / 25% Théorie et études de cas réels',

  programmeModules: [
    {
      module: 'Module 1 : Fondations des LLMs & Prompt Engineering Avancé',
      duree: 'Jour 1 (7h)',
      description: 'Concepts clés, architectures Transformers, techniques de chain-of-thought et prompt engineering systématique.'
    },
    {
      module: 'Module 2 : Orchestration Multi-Agents & RAG Entreprise',
      duree: 'Jour 2 (7h)',
      description: 'Mise en place de bases vectorielles, gestion de mémoire et orchestration d’agents autonomes avec LangChain.'
    },
    {
      module: 'Module 3 : Sécurisation, Guardrails & Déploiement REST API',
      duree: 'Jour 3 (7h)',
      description: 'Sécurité des données, filtrage des PII, monitoring des requêtes et atelier de déploiement d’un cas d’usage réel.'
    }
  ],

  budgetDetails: [
    { designation: 'Honoraires d’ingénierie pédagogique et conception sur mesure', quantite: 1, prixUnitaireAr: 2500000, totalAr: 2500000 },
    { designation: 'Animation de la Masterclass (Formateur Senior Expert IA)', quantite: 3, prixUnitaireAr: 2000000, totalAr: 6000000 },
    { designation: 'Fourniture des environnements Sandbox Cloud & Notebooks', quantite: 15, prixUnitaireAr: 200000, totalAr: 3000000 },
    { designation: 'Documentation, attestation de réussite et suivi post-formation', quantite: 1, prixUnitaireAr: 1000000, totalAr: 1000000 }
  ],

  budgetTotalAr: 12500000,

  garantiesEtPropretie:
    'Garantie d’accompagnement de 30 jours post-formation. Propriété intellectuelle des codes sources et scripts développés pendant l’atelier transférée au client.'
};
