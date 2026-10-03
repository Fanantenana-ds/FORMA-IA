# Environnements — FORMA-IA

## Dev
Machine locale de chaque étudiant. Lancé via `docker-compose up --build`.
Données fictives uniquement.

## Recette
Environnement de démonstration utilisé pour les jalons de validation (J3, J4, J5).
Données fictives, reflète la configuration de production.

## Production
Déploiement final (S12–S13). Données réelles, limitées au strict nécessaire.
Aucune donnée personnelle réelle ne doit exister en dehors de cet environnement
(exigence de protection des données du CDC).

## Gestion des secrets
Les variables sensibles (clé API Anthropic, mots de passe de base de données)
sont stockées uniquement dans des fichiers `.env` locaux, jamais commités.
Le fichier `.env.example` sert de modèle pour savoir quelles variables créer.

## Lancer les environnements

### Développement
```powershell
docker-compose up --build
```
Accès : backend `localhost:8000`, frontend `localhost:3000`, base `localhost:5432`.
Le code est monté en volume : toute modification se reflète immédiatement (rechargement à chaud).

### Recette
```powershell
docker-compose -f docker-compose.recette.yml up --build
```
Accès : backend `localhost:8001`, frontend `localhost:3001`, base `localhost:5433`.
Le code est figé dans l'image au moment du build — aucune modification locale n'est
reflétée automatiquement. Base de données séparée (`forma_ia_recette`), jamais mélangée
avec les données de développement quotidien.

Cet environnement sert aux démonstrations des jalons (J3, J4, J5) avec l'encadreur
professionnel et la direction ALTIORA.