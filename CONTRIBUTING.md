# Convention de contribution — FORMA-IA

## Format des commits

Chaque commit doit commencer par un préfixe indiquant son type :

- feat: nouvelle fonctionnalité
- fix: correction de bug
- docs: documentation uniquement
- test: ajout ou modification de tests
- refactor: réécriture sans changement de comportement
- chore: tâches diverses (config, dépendances, nettoyage)

Exemple : feat: ajout de l'endpoint /opportunites

## Branches

- main : toujours déployable, jamais de push direct, protégée par pull request
- develop : branche d'intégration quotidienne
- feat/nom-de-la-tache : une branche par tâche, créée à partir de develop, fusionnée via pull request

## Revue de code

Toute fusion vers main ou develop nécessite une pull request relue par au moins un pair avant merge.
