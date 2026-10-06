# INTERFACES MANQUANTES — FORMA-IA
## Diagnostic réel : Backend vs Frontend

> **Pour qui ?** Le développeur frontend, pour savoir exactement ce qu'il reste à faire.  
> **Méthode :** Lecture directe du code backend (19 fichiers endpoints) et du code frontend (34 fichiers .tsx + api.ts).  
> **Dernière mise à jour :** 2026-10-06

---

## ÉTAT RÉEL DU FRONTEND AUJOURD'HUI

Le frontend a **8 vues dans le menu**, **1 fichier `api.ts`** avec 12 méthodes, et **aucune authentification réelle**.

### Ce qui existe vraiment dans `api.ts`
| Méthode | Ce qu'elle fait réellement |
|---|---|
| `checkHealth()` | Ping `/health` — la seule vraie vérification |
| `getSessions()` | Appel réel `GET /sessions` (avec fallback mock si échec) |
| `createSession()` | Crée une session locale en dur, puis tente POST — le corps envoyé est construit localement, pas depuis un formulaire réel |
| `getOpportunites()` | Appel réel `GET /opportunites` (avec fallback mock) |
| `createOpportunite()` | Même problème : corps construit localement |
| `getFormateurs()` | Appel réel `GET /rh/formateurs` (avec fallback mock) |
| `getFactures()` | Appel réel `GET /factures` (avec fallback mock) |
| `createFacture()` | Corps construit localement, tente POST |
| `getKPIs()` | Appel dashboard — données réelles si connecté |
| `getPresences()` | **Retourne directement les mocks** — aucun appel API |
| `getVeilles()` | **Retourne directement les mocks** — aucun appel API |
| `getRecentActivities()` | **Retourne directement les mocks** — aucun appel API |

### Problème transversal sur TOUS les appels
Le `request()` dans `api.ts` **n'envoie jamais le token JWT**. Résultat : toutes les routes protégées retournent HTTP 401 et l'API bascule automatiquement sur le mode mock. Même quand le backend est démarré, le frontend affiche des données fictives.

---

## PARTIE 1 — CE QUI EST CASSÉ DANS L'EXISTANT

### 1.1 — Authentification (`AuthPage.tsx` + `api.ts`)

**Problème :** Il n'existe pas de méthode `login()` dans `api.ts`. `AuthPage.tsx` utilise une fonction `quickDemoLogin()` qui simule une connexion sans jamais contacter le backend. Aucun token JWT n'est jamais obtenu ni stocké.

**Ce qui est prêt côté backend :**
- `POST /auth/login` → reçoit email + mot de passe, retourne un token JWT
- `POST /auth/register` → créer un compte
- `POST /auth/logout` → invalider la session
- `GET /auth/me` → lire son propre profil
- `GET /auth/users` → lister tous les comptes (admin)
- `PATCH /auth/users/{id}` → modifier un compte
- `DELETE /auth/users/{id}` → supprimer un compte

**Ce qui manque dans le frontend :**
- La méthode `login(email, password)` dans `api.ts`, qui appelle `POST /auth/login` et stocke le token reçu
- L'ajout du header `Authorization: Bearer {token}` sur toutes les requêtes dans `request()`
- La gestion de l'expiration du token (redirection vers login si HTTP 401)
- Le branchement de `AuthPage.tsx` sur cette vraie méthode au lieu de `quickDemoLogin()`
- Un écran de profil utilisateur qui appelle `GET /auth/me`
- Une page de gestion des comptes (admin) qui appelle les routes `/auth/users`

---

### 1.2 — `VeilleMarcheView.tsx`

**Problème :** `getVeilles()` dans `api.ts` retourne directement des données mockées (pas d'appel réseau du tout). Même si le backend est connecté, on voit toujours les données fictives.

**Ce qui est prêt côté backend :**
- `GET /opportunites` → lister toutes les opportunités détectées
- `PUT /opportunites/{id}` → modifier le statut d'une opportunité
- `DELETE /opportunites/{id}` → supprimer
- `POST /ia/veille/rechercher` → déclencher une recherche IA (retourne un `review_id` à valider)
- `POST /ia/veille/detecter` → détection automatique de marchés (retourne un `review_id`)
- `POST /ia/veille/synchroniser-backend` → après validation, crée l'opportunité en base

**Ce qui manque dans le frontend :**
- Remplacer `getVeilles()` par un vrai appel `GET /opportunites`
- Le bouton "Rechercher avec l'IA" qui déclenche `POST /ia/veille/rechercher` et redirige vers la vue de validation HITL
- L'affichage de l'analyse d'une opportunité : `POST /{opportunite_id}/analyse` (analyse IA ponctuelle sans HITL)

---

### 1.3 — `OpportunitesCrmView.tsx` (vue TDR et OT)

**Problème :** La liste des marchés est une constante `DEFAULT_ACCEPTED_MARKETS` codée en dur dans le fichier. `getOpportunites()` retourne ces données fictives même quand le backend répond.

**Ce qui est prêt côté backend :**
- `GET /opportunites` → liste réelle depuis la base
- `POST /opportunites` → créer une opportunité manuellement
- `PUT /opportunites/{id}` → remplacer
- `DELETE /opportunites/{id}` → supprimer
- `GET /ia/tdr/from-opportunite/{id}` → pré-remplir le formulaire TDR depuis une opportunité existante
- `POST /ia/tdr/generer` → générer un TDR complet (retourne `review_id`)
- `POST /ia/tdr/synchroniser` → après validation, sauvegarde le TDR
- `GET /ia/tdr/download/{filename}` → télécharger le fichier DOCX du TDR généré
- `POST /offres` → créer une offre manuellement
- `GET /offres` → lister les offres
- `POST /ia/offres/generer-complet` → générer une offre complète technique + financière (retourne `review_id`)
- `POST /ia/offres/regenerer` → régénérer avec feedback après rejet
- `POST /ia/offres/synchroniser` → après validation, sauvegarde l'offre

**Ce qui manque dans le frontend :**
- Charger les opportunités réelles depuis le backend au lieu de la constante
- Le composant `TdrFormEditor.tsx` existe (formulaire de saisie TDR) mais n'est relié à aucun appel API
- Le bouton "Générer le TDR" qui appelle `POST /ia/tdr/generer` et redirige vers la validation
- Le bouton "Générer l'offre" (technique + financière) qui appelle `POST /ia/offres/generer-complet`
- Le téléchargement du DOCX après validation
- L'affichage de la liste des offres générées

---

### 1.4 — `FormateursStaffView.tsx`

**Problème :** Le bouton "Ajouter un formateur" appelle `onAddFormateur(created)` — un callback qui met à jour l'état local de `App.tsx`. Aucun appel POST n'est envoyé au backend. La modification et la suppression n'existent pas du tout.

**Ce qui est prêt côté backend :**
- `POST /rh/formateurs` → créer un formateur
- `PATCH /rh/formateurs/{id}` → modifier
- `DELETE /rh/formateurs/{id}` → supprimer
- `POST /rh/candidats` → créer un dossier candidat
- `GET /rh/candidats` → lister les candidats
- `PATCH /rh/candidats/{id}` → modifier un candidat
- `DELETE /rh/candidats/{id}` → supprimer
- `POST /rh/candidats/{id}/entretiens` → créer un entretien
- `GET /rh/candidats/{id}/entretiens` → lister les entretiens d'un candidat
- `PATCH /rh/entretiens/{id}` → modifier un entretien
- `DELETE /rh/entretiens/{id}` → supprimer
- `POST /ia/rh/preselection` → analyser un CV (retourne `review_id`)
- `POST /ia/rh/entretien/compte-rendu` → rédiger un compte-rendu d'entretien (retourne `review_id`)
- `POST /ia/rh/rediger-email` → rédiger un email RH (retourne `review_id`)
- `POST /ia/rh/generer-contrat` → générer un contrat formateur (retourne `review_id`)
- `POST /ia/rh/evaluer-formateur` → évaluer un formateur post-session (retourne `review_id`)
- `POST /ia/rh/synchroniser/candidat` → après validation, crée le candidat en base
- `POST /ia/rh/synchroniser/entretien-cr` → après validation, sauvegarde le compte-rendu
- `POST /ia/rh/synchroniser/evaluation` → après validation, met à jour le profil formateur

**Ce qui manque dans le frontend :**
- Les appels POST/PATCH/DELETE pour créer, modifier, supprimer un formateur
- Toute la gestion des candidats (dossiers, entretiens) — il n'existe aucun écran pour ça
- Le bouton "Analyser un CV" pour présélectionner un profil formateur
- Le bouton "Rédiger le compte-rendu" d'entretien
- Le bouton "Générer le contrat" formateur
- L'évaluation post-session d'un formateur (actuellement `EvaluationCompetencesView.tsx` n'appelle rien)

---

### 1.5 — `EvaluationCompetencesView.tsx`

**Problème :** La vue affiche des données statiques codées en dur (`competencesData`). Le bouton "Ajouter une évaluation" appelle `onAddEvaluation` (callback local). Rien n'est persisté.

**Ce qui est prêt côté backend :**
- `POST /ia/rh/evaluer-formateur` → évaluation IA d'un formateur post-session
- `POST /ia/rh/synchroniser/evaluation` → synchroniser l'évaluation approuvée

**Ce qui manque dans le frontend :**
- Charger les évaluations réelles depuis la base (actuellement impossible car il n'existe pas de route GET dédiée — à vérifier avec le backend)
- Le bouton "Évaluer avec l'IA" qui appelle l'agent d'évaluation post-session

---

### 1.6 — `SessionsGroupesView.tsx`

**Problème :** `getSessions()` fait un vrai appel API mais sans token — il tombe toujours en mode mock. Le bouton "Ajouter un participant" met à jour un tableau React local. Rien n'est envoyé au backend.

**Ce qui est prêt côté backend :**
- `GET /sessions` → lister les sessions
- `POST /sessions` → créer une session
- `GET /sessions/{id}` → lire une session
- `PATCH /sessions/{id}` → modifier
- `DELETE /sessions/{id}` → supprimer
- `GET /sessions/{id}/seances` → lister les séances d'une session
- `POST /sessions/{id}/seances` → ajouter une séance
- `PATCH /seances/{id}` → modifier une séance
- `DELETE /seances/{id}` → supprimer une séance
- `POST /sessions/{id}/inscrire` → inscrire un participant
- `DELETE /sessions/{id}/inscrire/{pid}` → désinscrire
- `GET /sessions/{id}/participants` → lister les participants inscrits
- `POST /ia/formations/generate-forms` → générer les 4 formulaires d'évaluation (inscription, test avant, test après, satisfaction) — retourne `review_id`
- `POST /ia/formations/creer-formulaires` → après validation, créer les formulaires réels sur Google Forms → retourne les 4 liens Google
- `POST /ia/formations/sync-responses` → récupérer les réponses des participants depuis Google Forms
- `POST /ia/formations/analyze-levels` → analyser les niveaux test avant/après — retourne `review_id`
- `POST /ia/formations/analyze-satisfaction` → analyser la satisfaction — retourne `review_id`
- `POST /ia/formations/analyze-presences` → analyser les présences/inscriptions — retourne `review_id`
- `POST /ia/formations/generate-attestations` → générer les attestations de formation — retourne `review_id`
- `POST /ia/formations/generate-report` → générer le rapport de formation complet — retourne `review_id`
- `POST /ia/formations/regenerate-forms` → régénérer les formulaires avec feedback après rejet

**Ce qui manque dans le frontend :**
- Toute la gestion des séances (créer, modifier, supprimer)
- La gestion des inscriptions participants avec appels API réels
- Le bouton "Générer les formulaires" qui lance le cycle M5 complet (le plus complexe)
- L'affichage des 4 liens Google Forms à distribuer aux participants
- Le bouton "Récupérer les réponses" après la formation
- Les boutons d'analyse (niveaux, satisfaction, présences)
- La génération des attestations
- La génération du rapport de formation complet

---

### 1.7 — `SuiviPresencesView.tsx`

**Problème :** `getPresences()` retourne directement des mocks (aucun appel réseau). Marquer présent/absent modifie un état React local. Rien n'est sauvegardé.

**Ce qui est prêt côté backend :**
- `GET /seances/{id}/presences` → lister les présences d'une séance
- `POST /seances/{id}/presences` → enregistrer une présence
- `PATCH /seances/presences/{id}` → corriger (modifier présent/absent, ajouter motif d'absence)

**Ce qui manque dans le frontend :**
- Sélectionner une séance spécifique pour afficher ses présences
- Charger les présences réelles depuis le backend
- Enregistrer chaque marquage présent/absent via POST
- Modifier une présence déjà enregistrée (corriger une erreur)

---

### 1.8 — `FacturationDevisView.tsx`

**Problème :** `getFactures()` et `createFacture()` font des appels réels mais sans token JWT — ils basculent sur les mocks. La modification du statut, l'enregistrement d'un paiement, la relance et l'export n'existent pas du tout.

**Ce qui est prêt côté backend :**
- `GET /factures` → lister
- `POST /factures` → créer
- `GET /factures/{id}` → lire une facture
- `PATCH /factures/{id}` → modifier le statut, les montants
- `DELETE /factures/{id}` → supprimer
- `POST /factures/{id}/paiements` → enregistrer un paiement
- `POST /factures/{id}/relance` → créer une relance manuelle
- `GET /factures/{id}/relances` → historique des relances
- `POST /ia/facturation/relances/generer` → générer une relance IA (niveau 1/2/3 selon le retard) — retourne `review_id`
- `POST /ia/facturation/relances/synchroniser` → après validation, enregistre la relance
- `POST /ia/facturation/calculer-montants` → calculer HT/TVA/TTC/remise automatiquement
- `GET /exports` → export comptable au format CSV, XLSX ou PDF

**Ce qui manque dans le frontend :**
- Modifier le statut d'une facture (Envoyée → Payée, etc.)
- Enregistrer un paiement avec montant, date, mode de paiement
- Voir l'historique des relances d'une facture
- Bouton "Générer une relance IA" avec les 3 niveaux de ton (rappel, ferme, contentieux)
- Calcul automatique des montants (HT → TVA → TTC → remise)
- Export comptable en 1 clic (CSV / XLSX / PDF)

---

## PARTIE 2 — VUES ENTIÈREMENT ABSENTES

Ces fonctionnalités sont complètes côté backend. Il n'existe aucun fichier `.tsx` correspondant.

---

### 2.1 — Gestion des supports de cours (`SupportsFormationView`)

Le backend peut recevoir des fichiers PDF, DOCX, PPTX, XLSX — les indexer pour le RAG — et générer des résumés DOCX. Il n'existe aucune interface pour ça.

**Ce qui est prêt côté backend :**
- `POST /documents/upload` → uploader un support (PDF, DOCX, PPTX, XLSX, TXT, MD — max 100 Mo) avec son code de formation et son module pédagogique
- `GET /documents/rag/supports` → lister tous les supports avec leur statut d'indexation (en attente / en cours / indexé / erreur)
- `DELETE /documents/rag/supports/{hash}` → supprimer un support et ses vecteurs RAG
- `POST /ia/rag/indexer-document` → lancer l'indexation d'un support dans la base vectorielle
- `GET /ia/rag/statut/{hash}` → vérifier le statut d'indexation d'un document
- `GET /documents/rag/supports/resume-formation` → télécharger en un clic un DOCX qui résume tous les supports d'une formation, groupés par module pédagogique
- `GET /documents/rag/supports/bilan-formations` → télécharger un DOCX bilan de toutes les formations sur une période (réservé Direction)
- `GET /documents` → lister les documents validés
- `GET /documents/{id}` → lire un document
- `GET /documents/{id}/export` → télécharger un document
- `DELETE /documents/{id}` → supprimer

**Ce qui manque dans le frontend :**
- Un formulaire d'upload avec les champs : fichier, code formation, module pédagogique (optionnel), type de collection
- Une liste des supports uploadés avec leur statut d'indexation en temps réel (icône ✅ indexé / ⏳ en cours / ❌ erreur)
- Un regroupement visuel par module pédagogique dans l'affichage
- Un bouton "Télécharger le résumé DOCX" de la formation (1 clic → fichier prêt)
- Une vue Direction "Bilan des formations" avec sélection de période et téléchargement DOCX
- La suppression d'un support avec confirmation

---

### 2.2 — Chat avec les documents RAG (`RagChatView`)

Le backend a un agent de chat contextuel qui répond aux questions en se basant sur les supports indexés. Il n'existe aucune interface de chat dans le frontend.

**Ce qui est prêt côté backend :**
- `POST /ia/rag/chat` → poser une question, reçoit une réponse avec les sources (fichier + page)
- `GET /ia/rag/formations` → lister les formations qui ont des supports indexés
- `GET /ia/rag/health` → vérifier que le module RAG est opérationnel
- `POST /ia/rag/rechercher` → recherche vectorielle pure (sans génération de réponse)

**Ce qui manque dans le frontend :**
- Une interface de chat (type messagerie) où le formateur ou la Direction peut poser des questions sur le contenu des formations
- L'affichage des sources citées dans la réponse (nom du fichier, numéro de page)
- Un indicateur de santé du RAG (combien de documents sont indexés, le module est-il prêt)

---

### 2.3 — Génération de syllabus (`SyllabusView`)

Le backend peut générer automatiquement un syllabus de formation à partir des supports indexés, avec les durées calculées en Python. Il n'existe aucune interface pour ça.

**Ce qui est prêt côté backend :**
- `POST /ia/rag/syllabus` → générer le syllabus (contenu + durées calculées depuis les supports) — retourne `review_id`
- `POST /ia/rag/syllabus/{review_id}/exporter` → après validation, télécharger le DOCX du syllabus
- `POST /ia/rag/generer-questions` → générer des questions de révision à partir des supports (usage interne, pas de HITL)

**Ce qui manque dans le frontend :**
- Un bouton "Générer le syllabus" à partir d'une formation (avec ses supports déjà indexés)
- L'affichage du syllabus généré pour validation avant export
- Le téléchargement du DOCX final

---

### 2.4 — Portfolio des formations (`PortfolioView`)

Le backend peut générer un portfolio complet qui agrège toutes les formations réalisées, avec les métriques et les thèmes couverts.

**Ce qui est prêt côté backend :**
- `POST /ia/rag/portfolio` → générer le portfolio (synthèse de toutes les formations) — retourne `review_id`
- `POST /ia/rag/portfolio/{review_id}/exporter` → après validation, télécharger le DOCX

**Ce qui manque dans le frontend :**
- Un bouton "Générer le portfolio" (usage Direction principalement)
- L'affichage du contenu généré pour validation
- Le téléchargement du DOCX final

---

### 2.5 — Projets, salles et préparation logistique (`PreparationView`)

Tout ce qui concerne la logistique d'une formation (réserver une salle, créer un emploi du temps, calculer le budget) est absent du frontend.

**Ce qui est prêt côté backend :**
- `POST /projets` → créer un projet de formation
- `GET /projets` → lister les projets
- `PATCH /projets/{id}` → modifier (statut, dates, client)
- `DELETE /projets/{id}` → supprimer (supprime aussi l'EDT et le budget)
- `POST /projets/{id}/edt` → ajouter une séance à l'emploi du temps
- `GET /projets/{id}/edt` → voir l'EDT complet
- `DELETE /projets/{id}/edt/{edt_id}` → supprimer une séance de l'EDT
- `POST /projets/{id}/budget` → créer ou remplacer le budget prévisionnel
- `GET /projets/{id}/budget` → voir le budget
- `POST /salles` → créer une salle
- `GET /salles` → lister les salles disponibles
- `PUT /salles/{id}` / `PATCH /salles/{id}` → modifier
- `DELETE /salles/{id}` → supprimer
- `POST /ia/preparation/calculer-budget` → calcul automatique du budget (Python pur, pas de LLM)
- `POST /ia/preparation/generer-edt` → générer l'emploi du temps avec un LLM
- `POST /ia/preparation/generer-complet` → budget + EDT en une seule opération — retourne `review_id`
- `POST /ia/preparation/regenerer` → régénérer après rejet
- `POST /ia/preparation/synchroniser` → après validation, créer la session et l'EDT en base
- `POST /preparation/ingest-ia-edt` → ingérer un EDT généré par l'IA dans un projet existant

**Ce qui manque dans le frontend :**
- La gestion des salles (créer, lister, modifier, supprimer)
- La gestion des projets (créer, voir l'EDT, voir le budget)
- Le bouton "Générer la préparation complète" qui calcule budget + EDT en automatique
- La visualisation de l'EDT sous forme de calendrier ou tableau
- La visualisation du budget prévisionnel

---

### 2.6 — Validation humaine des contenus IA (`HitlReviewView`)

C'est la vue la plus critique. Tous les agents IA retournent un `review_id` — sans cette vue, aucun contenu généré ne peut être validé, donc rien de ce que fait l'IA n'est sauvegardé.

**Ce qui est prêt côté backend :**
- `GET /ia/formations/pending-reviews` → lister tous les contenus IA en attente (filtrables par agent)
- `GET /ia/formations/reviews/{id}` → lire le contenu généré dans son détail
- `GET /ia/formations/reviews/stats` → statistiques (combien en attente, combien approuvés, etc.)
- `POST /ia/formations/reviews/{id}/approve` → approuver (avec commentaire optionnel)
- `POST /ia/formations/reviews/{id}/reject` → rejeter avec un feedback (minimum 10 caractères) — l'agent peut régénérer avec ce feedback

**Ce qui manque dans le frontend :**
- La liste de tous les contenus en attente avec le nom de l'agent et la date de création
- L'affichage du contenu généré (TDR, offre, formulaires, relance...) dans un format lisible
- Les boutons Approuver / Rejeter avec champ feedback
- Un badge dans le menu indiquant combien de contenus attendent validation
- Après approbation, l'appel à la route `/synchroniser` du module concerné

---

### 2.7 — Gestion des candidats RH (`CandidatsView`)

Il n'existe aucune vue pour la gestion des dossiers candidats, bien que le backend dispose d'un CRUD complet et de 3 agents IA RH.

**Ce qui est prêt côté backend :**
- `POST /rh/candidats` → créer un dossier candidat
- `GET /rh/candidats` → lister
- `PATCH /rh/candidats/{id}` → modifier
- `DELETE /rh/candidats/{id}` → supprimer
- `POST /rh/candidats/{id}/entretiens` → créer un entretien
- `GET /rh/candidats/{id}/entretiens` → historique des entretiens
- `PATCH /rh/entretiens/{id}` → modifier
- `DELETE /rh/entretiens/{id}` → supprimer
- `POST /ia/rh/preselection` → analyser un CV texte et scorer le profil par rapport aux critères du poste — retourne `review_id`
- `POST /ia/rh/entretien/compte-rendu` → rédiger automatiquement un compte-rendu d'entretien — retourne `review_id`
- `POST /ia/rh/rediger-email` → rédiger un email de convocation, refus ou proposition — retourne `review_id`
- `POST /ia/rh/generer-contrat` → générer un contrat de prestation formateur — retourne `review_id`

**Ce qui manque dans le frontend :**
- La liste des candidats avec leur statut de recrutement
- La fiche d'un candidat (informations + historique des entretiens)
- Le bouton "Analyser le CV" pour présélectionner un profil
- Le bouton "Rédiger le compte-rendu" après un entretien
- Le bouton "Générer le contrat" pour un formateur retenu
- Le bouton "Rédiger l'email" (convocation, refus, proposition)

---

## PARTIE 3 — ÉLÉMENTS TRANSVERSAUX ABSENTS PARTOUT

Ces éléments ne sont liés à aucune vue particulière mais manquent dans toute l'application.

### 3.1 — Gestion des utilisateurs / comptes

Il n'existe aucun écran pour créer, modifier ou supprimer des comptes utilisateurs. Le backend a un CRUD complet sous `/auth/users` (accessible uniquement en tant qu'admin). Le profil de l'utilisateur connecté (`GET /auth/me`) n'est jamais affiché.

### 3.2 — Barre de santé de l'API

Chaque module IA a une route `/health` dédiée. Ces informations ne sont jamais affichées dans le frontend. L'utilisateur ne sait pas si les modules RAG, M5, M3, M7, PREP, M4 sont opérationnels.

| Route health | Module |
|---|---|
| `GET /ia/rag/health` | Chat RAG + Syllabus + Portfolio |
| `GET /ia/formations/health` | Formulaires M5 + attestations |
| `GET /ia/offres/health` | Génération TDR + offres |
| `GET /ia/preparation/health` | EDT + budget |
| `GET /ia/facturation/health` | Relances factures |
| `GET /ia/rh/health` | Présélection CV + contrats |

### 3.3 — Menu incomplet dans `Sidebar.tsx`

Les sections suivantes existent dans le backend mais n'ont aucun item dans le menu :

| Section | Ce qui manque |
|---|---|
| Supports de cours | Entrée de menu (formateurs + direction) |
| Chat IA / RAG | Entrée de menu (formateurs pour poser des questions) |
| Syllabus | Entrée de menu (formateurs) |
| Portfolio | Entrée de menu (direction) |
| Préparation logistique | Entrée de menu (projets, salles, EDT, budget) |
| Validation IA (HITL) | Entrée de menu avec badge de compteur (critique) |
| Candidats RH | Entrée de menu (direction, assistant) |
| Bilan formations | Entrée de menu direction |

### 3.4 — Types TypeScript manquants

Le fichier `types/index.ts` (ou équivalent) ne contient pas les types pour : `Support`, `Projet`, `Salle`, `Edt`, `Budget`, `Review`, `Candidat`, `Entretien`, `Syllabus`, `Portfolio`. Sans ces types, les vues à créer devront travailler avec `any` ou définir leurs types localement.

---

## RÉSUMÉ DES PRIORITÉS

| Priorité | Quoi | Pourquoi c'est bloquant |
|---|---|---|
| 1 | **Auth réelle + token JWT** | Sans ça, 100% des données sont des mocks |
| 2 | **`HitlReviewView`** | Sans ça, aucun contenu IA ne peut être utilisé |
| 3 | **Brancher les 8 vues existantes** sur les vraies données | Les données affichées sont fictives |
| 4 | **`SupportsFormationView`** | Le RAG ne peut pas être alimenté |
| 5 | **Chat RAG** | La fonctionnalité phare de l'IA n'est pas accessible |
| 6 | **`SyllabusView`** | Génération de contenu pédagogique bloquée |
| 7 | **`PreparationView`** | Logistique inaccessible |
| 8 | **`CandidatsView`** | Gestion RH incomplète |
| 9 | **`PortfolioView`** | Bilan général inaccessible |
| 10 | **Menu + types TypeScript** | Ergonomie et cohérence globale |

---

*Voir `GUIDE_INTEGRATION_FRONTEND.md` pour le détail des formats de requêtes, les corps JSON attendus et les exemples de code pour chaque route.*
