# Journalisation — FORMA-IA

## Configuration

Le backend utilise le module `logging` standard de Python, configuré dans `app/main.py` :

- **Format** : `<horodatage> | <niveau> | <module> | <message>`
- **Niveau** : configurable via la variable d'environnement `LOG_LEVEL` (`settings.LOG_LEVEL`)

## Middleware HTTP (`LoggingMiddleware`)

Chaque requête HTTP est journalisée automatiquement avec :
- Méthode et chemin appelés
- Adresse IP du client
- Durée de traitement précise (mesurée avec `time.perf_counter()`)
- Code de statut, avec un indicateur visuel selon la catégorie (succès, redirection,
  erreur client, erreur serveur)
- En cas d'exception : la durée écoulée avant l'échec et le détail de l'erreur

La durée de traitement est également renvoyée dans l'en-tête HTTP `X-Process-Time`
de chaque réponse, exploitable par un outil de supervision externe.

Les endpoints techniques (santé) peuvent être exclus des logs verbeux via la variable
`VERBOSE_SKIP_HEALTH`, pour ne pas polluer les journaux avec les sondes de monitoring.

## Consulter les logs

**En développement / recette (local)** :
```powershell
docker-compose logs backend --tail 50
docker-compose logs backend -f    # suivi en temps réel
```

**En production** (prévu S12-S13) : les mêmes logs seront collectés, et la disponibilité
sera supervisée en continu via Uptime Kuma (voir section Monitoring).

## Sécurité des logs

Les logs ne doivent jamais contenir de secrets (clés API, mots de passe, tokens).
Les variables sensibles sont exclusivement gérées via les fichiers `.env` (jamais
affichées dans les logs applicatifs) — voir `docs/environnements.md`.

## Monitoring (POC)

Un environnement de supervision basé sur Uptime Kuma est en cours de préparation
(voir `docker-compose.monitoring.yml`), en anticipation du déploiement final (S13),
où il surveillera la disponibilité de la plateforme (objectif CDC : 99 %).