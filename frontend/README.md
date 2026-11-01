# FORMA-IA — Frontend

Interface React (Vite + TypeScript + Tailwind) de la plateforme FORMA-IA.

## Démarrage

```bash
npm install
cp .env.example .env     # puis adaptez VITE_API_URL
npm run dev              # http://localhost:3000
```

## Configuration

| Variable        | Rôle                                                        | Exemple                 |
|-----------------|-------------------------------------------------------------|-------------------------|
| `VITE_API_URL`  | URL de base du backend (sans slash final, sans `/api/v1`)   | `http://127.0.0.1:8000` |

Le backend doit autoriser l'origine du frontend (`CORS_ORIGINS`, par défaut `http://localhost:3000`).
Après toute modification du `.env`, redémarrez `npm run dev`.

## Authentification (étape 1)

| Action        | Appel backend                                   |
|---------------|-------------------------------------------------|
| Inscription   | `POST /api/v1/auth/register` puis connexion auto |
| Connexion     | `POST /api/v1/auth/login` puis `GET /api/v1/auth/me` |
| Session       | `GET /api/v1/auth/me` au chargement de la page  |
| Déconnexion   | `POST /api/v1/auth/logout` (révoque le jeton)   |

- Le jeton JWT est conservé dans `localStorage` (clé `forma_ia_token`) et envoyé en `Authorization: Bearer`.
- Un `401` sur une requête authentifiée ramène automatiquement à l'accueil.
- Rôles backend → interface : `DIRECTION` → Directeur, `FORMATEUR` → Formateur, `ASSISTANT` → Assistant, `COMPTABLE` → Comptable.
- Le backend ne stocke qu'un seul champ `nom` : le formulaire d'inscription demande donc un « nom complet ».

## Organisation

- `src/config/env.ts` : lecture de `VITE_API_URL`
- `src/services/api.ts` : client REST (jeton, erreurs, authentification)
- `src/components/AuthPage.tsx` : connexion / inscription

## Reste à brancher

Les listes (sessions, opportunités, formateurs, présences, factures, veille, KPI du tableau de bord) n'ont plus de données
de démonstration : elles restent vides tant que leurs routes ne sont pas raccordées au backend (`src/services/api.ts`,
section « Données métier »).

## Dépannage

- **`OPTIONS /api/v1/auth/... 400 Bad Request`** dans les logs du backend : problème CORS. Ajoutez l'adresse exacte du front
  (`http://localhost:3000`, `http://127.0.0.1:3000`...) à `CORS_ORIGINS` dans le `.env` du backend, puis redémarrez-le.
- **« Accès refusé aux routes IA »** dans la Veille marché : le backend doit accepter le JWT sur `/api/v1/ia/*`
  (voir `backend_patch/LISEZMOI.md`).

## Veille marché

Deux modes, au choix en haut de la page « Veille marché IA » :

| Mode | Fonctionnement | Routes |
|------|----------------|--------|
| **Recherche manuelle** | barre de mots-clés + bouton « Lancer la recherche IA » | `POST /api/v1/ia/veille/rechercher` |
| **Détection automatique** | le serveur lance ses recherches prédéfinies (profil ALTIORA), à intervalle régulier ou sur demande via « Lancer la détection maintenant » | `GET /ia/veille/detecter/statut`, `GET /ia/veille/quota`, `POST /ia/veille/detecter` |

- Les deux modes remplissent la liste « Marchés trouvés » (score, fiabilité, organisme, échéance, lien source).
- « Accepter ce marché » enregistre l'opportunité (`POST /api/v1/opportunites`, rôles Direction et Assistant) ; les marchés
  acceptés proviennent de `GET /api/v1/opportunites`. Un marché déjà enregistré est signalé « Déjà enregistré ».
- Détection automatique : la case « Enregistrer automatiquement les nouvelles opportunités » (cochée par défaut) fait
  enregistrer les nouveautés par le serveur ; décochée, le passage est un simple aperçu. Le panneau affiche l'état de la
  planification, les requêtes configurées, le dernier passage et le quota mensuel de recherche web.
- Le déclenchement manuel est proposé à la Direction et aux Assistants.
- Côté serveur : `VEILLE_AUTO_ENABLED`, `VEILLE_AUTO_INTERVAL_HOURS`, `VEILLE_AUTO_QUERIES` (planification) et
  `BACKEND_SYNC_ENABLED` (enregistrement automatique) pilotent ce mode.

## Formateurs (M4 RH)

La page « Formateurs & Staff » est un CRUD complet sur `/api/v1/rh/formateurs` :

| Action | Route | Rôles |
|--------|-------|-------|
| Lister | `GET /rh/formateurs` | tout utilisateur connecté |
| Créer | `POST /rh/formateurs` | Direction |
| Modifier (y compris le statut) | `PATCH /rh/formateurs/{id}` | Direction |
| Supprimer (avec confirmation) | `DELETE /rh/formateurs/{id}` | Direction |

- Champs : nom (obligatoire), prénom, email, téléphone, adresse, spécialités (texte libre, séparées par des virgules),
  tarif journalier, statut (`Disponible` = DISPONIBLE, `En session` = OCCUPE, `Indisponible` = INACTIF), notes internes.
- Le statut ne se fixe pas à la création côté backend : le front applique un second appel si un autre statut que « Disponible » est choisi.
- Score, sessions et recommandation sont calculés par l'évaluation IA post-session (`/ia/rh/formateur/evaluer` puis
  `/synchroniser/evaluation`) : ils sont affichés mais pas modifiables ici. Le score est un **score global sur 100**.
- Pour vider un champ texte, le front envoie une chaîne vide (le backend ignore les `null`). Le tarif ne peut pas être vidé :
  vide, il reste inchangé.
- La suppression retire aussi les dossiers de candidature rattachés au formateur (cascade côté backend).
- La page « Évaluation & Compétences » affiche les résultats d'évaluation (score, recommandation, synthèse) ; les avis
  individuels d'apprenants ne sont pas encore stockés côté serveur.

## Tableau de bord

`getDashboard(role)` (`src/services/api.ts`) rassemble les données, la mise en forme est dans `src/services/dashboardMapping.ts` :

| Bloc affiché                         | Source                                                                 |
|--------------------------------------|------------------------------------------------------------------------|
| Sessions, participants, taux de présence, opportunités, documents, CA, impayés, relances | `GET /api/v1/dashboard/statistiques` (**Direction uniquement**) |
| Opportunités par domaine (nombre et budget) | `GET /api/v1/opportunites`                                      |
| Facturation par statut (factures annulées exclues) | `GET /api/v1/factures`                                   |
| Activité récente (10 derniers éléments créés) | opportunités, sessions, factures, documents                  |

Pour les autres rôles, les indicateurs sont recalculés à partir de ces listes (mêmes définitions que le backend) ;
le nombre de participants et le taux de présence global restent réservés à la Direction et s'affichent « — ».
Il n'y a plus de sélecteur de période : le backend fournit des totaux globaux, sans filtre par date.
