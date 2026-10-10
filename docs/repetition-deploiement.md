# Répétition de déploiement sur recette — S11

## Contexte

Répétition complète du cycle de déploiement sur l'environnement de recette
(`docker-compose.recette.yml`), en préparation du jalon J4 (16/10).

## Déroulé

1. Nettoyage complet (`down -v`) : suppression des conteneurs et volumes existants,
   pour repartir d'un état totalement vierge.
2. Rebuild complet (`up --build`) avec le fichier d'environnement dédié
   (`--env-file .env.recette`).
3. Vérification : backend (74 endpoints, `/api/docs`) et frontend accessibles
   sur les ports dédiés (8001, 3001).
4. Test de sauvegarde sur la base de recette (`scripts/backup_db_recette.ps1`) :
   réussi.

## Incident rencontré et corrigé

**Conflit de port** : le service de monitoring Uptime Kuma (port 3001) entrait en
conflit avec le frontend de recette (également configuré sur 3001), empêchant le
démarrage du frontend.

**Correction** : port d'Uptime Kuma déplacé de 3001 à 3002
(`docker-compose.monitoring.yml`). Les deux environnements (recette et monitoring)
peuvent désormais tourner simultanément sans conflit.

## Point d'attention à retenir

Cette commande précise est nécessaire pour l'environnement de recette, car
Docker Compose ne lit pas automatiquement `.env.recette` :
```powershell
docker-compose -f docker-compose.recette.yml --env-file .env.recette up --build
```
Documenté également dans `docs/environnements.md`.

## Conclusion

La répétition de déploiement est un succès : le cycle complet (build → démarrage
→ vérification → sauvegarde) fonctionne de bout en bout sur l'environnement de
recette, sans intervention manuelle cachée. Prêt pour la démonstration du jalon J4.