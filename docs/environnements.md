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