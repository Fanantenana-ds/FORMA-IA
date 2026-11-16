# FORMA-IA — configuration frontend

Le front conserve les composants et les styles fournis. Les données, formulaires et appels réseau utilisent maintenant les routes du backend FORMA-IA sous `/api/v1`.

## Configuration

1. Installer les dépendances avec `npm install`.
2. Copier `.env.example` en `.env.local`.
3. Régler `VITE_API_URL` sur l'adresse du backend, sans `/api/v1` à la fin.
4. Pour le développement local seulement, renseigner `VITE_IA_TOKEN` avec le jeton interne fourni par l'équipe backend.
5. Démarrer le front avec `npm run dev`.

Les routes IA du backend attendent un jeton interne distinct du JWT de connexion. Un jeton placé dans une application navigateur est lisible côté client ; la documentation backend indique qu'en production, les routes IA doivent accepter une authentification utilisateur ou passer par le serveur. Ne publiez pas le jeton interne dans le dépôt ou dans une version publique du front.

## Connexions mises à jour

- Connexion, inscription, profil, expiration de session et déconnexion avec le JWT.
- Les routes M1 de veille acceptent le JWT utilisateur du backend ; les autres routes IA protégées utilisent le jeton interne configuré pour le développement.
- Tableau de bord agrégé depuis `/dashboard/statistiques` et les listes accessibles au rôle connecté.
- Opportunités `/opportunites`, veille IA, formateurs `/rh/formateurs`, sessions `/sessions` et factures `/factures`.
- Création d'opportunités, de sessions et de factures avec les champs réellement acceptés par le backend.
- Mise à jour du statut et ajout de paiements sur une facture, export comptable CSV/XLSX/PDF.
- Espace IA : revue humaine, téléversement/indexation de supports, chat documentaire avec conservation du `conversation_id`, sources et suggestions.
- Écran complémentaire : projets, salles et candidats RH, lancement de la présélection CV et génération du syllabus/portfolio avec envoi dans la file de validation.
- Les erreurs HTTP (401, 403, 404, 422…) restent visibles dans l'interface ; les requêtes IA ont un délai adapté aux générations longues.

## Vérification de configuration

`VITE_API_URL` doit viser l'hôte FastAPI. Le backend doit autoriser l'origine du front dans `CORS_ORIGINS`. L'interface vérifie la disponibilité générale sur `/health`.

