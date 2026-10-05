# Observabilité — FORMA-IA

## Mesure de latence

Chaque requête HTTP est chronométrée automatiquement par le `LoggingMiddleware`
(`app/main.py`), avec une précision à la milliseconde (`time.perf_counter()`).

La durée de traitement est :
- Loguée pour chaque requête (succès comme erreur)
- Renvoyée au client dans l'en-tête de réponse `X-Process-Time`, consultable par
  tout outil externe (navigateur, Postman, futur système de supervision)

Cible du CDC : latence inférieure à 3 secondes par requête.

## Consulter la latence

**Dans les logs** :
```powershell
docker-compose logs backend | Select-String "ERREUR après"
```
(affiche les requêtes en erreur avec leur durée — les requêtes réussies sont
loguées avec la même information mais sans ce filtre)

**Dans le navigateur** : onglet Réseau (F12), colonne "Temps", ou en inspectant
l'en-tête `X-Process-Time` de chaque réponse.

## Supervision de disponibilité

Un moniteur Uptime Kuma (voir `docker-compose.monitoring.yml` et
`docs/journalisation.md`) vérifie la disponibilité du backend via l'endpoint
`/health`, avec mesure du temps de réponse à chaque vérification.

Objectif CDC : disponibilité de 99 % en production (S12-S13).

## Suivi de consommation des tokens

Voir `docs/suivi-tokens.md` pour le détail du suivi de consommation de l'API LLM
(Claude/Groq), lié au budget de tokens défini par le Kit de pilotage.