# Architecture infrastructure — FORMA-IA

## Vue d'ensemble des conteneurs

Le projet repose sur 3 conteneurs Docker orchestrés par un seul `docker-compose.yml` à la racine :

| Service | Technologie | Port | Rôle |
| --- | --- | --- | --- |
| `db` | PostgreSQL 15 | 5432 | Stockage des données (opportunités, sessions, utilisateurs) |
| `backend` | FastAPI (Python 3.10) | 8000 | API REST, logique métier, appels à l'API Claude |
| `frontend` | React JS (Node 20, Vite) | 5173 | Interface utilisateur (Direction, Formateur, Assistant) |

## Communication entre services

Le frontend React appelle l'API backend en HTTP (`http://localhost:8000` en développement).
Le backend communique avec PostgreSQL via SQLAlchemy, en utilisant la variable `DATABASE_URL`.
Le CORS est activé côté backend pour autoriser les requêtes venant du frontend (origine `http://localhost:5173`).

## Développement local

En développement, chaque conteneur monte le code source en volume (`./backend:/app`, `./frontend:/app`),
ce qui permet un rechargement à chaud : toute modification de code est reflétée immédiatement
sans reconstruire les images (`--reload` pour FastAPI, mode dev natif pour Vite).

## Environnements

Trois environnements sont définis pour le projet : développement, recette et production.
Le détail complet (usage, données, configuration) est documenté dans
[`environnements.md`](./environnements.md).

Les variables sensibles (clé API Anthropic, identifiants de base de données) sont gérées
via des fichiers `.env` locaux, jamais versionnés. Le fichier `.env.example` à la racine
sert de modèle pour connaître les variables nécessaires.

## Intégration continue (CI)

À chaque `push` ou `pull request` sur les branches `main` et `develop`, GitHub Actions
exécute automatiquement deux jobs en parallèle (`.github/workflows/ci.yml`) :

- **`backend-checks`** : installation des dépendances Python, lint avec `ruff`,
  exécution des tests avec `pytest`, et mesure de la couverture de code
  (seuil minimum : 70 %, conformément au Kit de pilotage du projet).
- **`frontend-checks`** : installation des dépendances Node, lint et tests du code React.

## Conventions de contribution

Toute fusion de code vers `main` ou `develop` doit en principe passer par une pull request
relue par au moins un pair, comme documenté dans `CONTRIBUTING.md`.
La branche `main` reste toujours déployable ; le développement quotidien se fait sur `develop`
et des branches `feat/nom-de-la-tache`.

*Note : la protection technique de branche (blocage des push directs) n'est pas active sur
le plan GitHub gratuit avec un dépôt privé ; la règle est donc appliquée par discipline d'équipe.*

## Outils prévus (à venir)

Les outils suivants sont planifiés pour les phases de déploiement et de test de charge,
conformément au Kit de pilotage :

- **Locust** (S12) : test de charge simulant 10 utilisateurs simultanés, exigence du CDC.
- **Uptime Kuma** (S13) : supervision de la disponibilité de la production (objectif 99 %).
- **Bitwarden** : partage sécurisé des identifiants d'environnement de production entre
  les membres de l'équipe.

## Schéma d'architecture

```
Utilisateur
    |
    v
Frontend React (port 5173)
    |  appels HTTP (CORS active)
    v
Backend FastAPI (port 8000)
    |  SQLAlchemy
    v
PostgreSQL (port 5432)

A chaque push : GitHub Actions (CI) valide backend + frontend en parallele.
```