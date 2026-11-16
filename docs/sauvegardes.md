# Sauvegardes — FORMA-IA

## Ce qui est sauvegardé

- **Base de données PostgreSQL** : toutes les tables (opportunités, sessions, documents, utilisateurs, factures).
- **Fichiers générés** : documents Word/PDF (TDR, offres, attestations), stockés dans le volume Docker `generated_files` (`/app/exports` dans le conteneur).

## Sauvegarde manuelle (aujourd'hui)

Lancer depuis la racine du projet, avec Docker actif :
```powershell
.\scripts\backup_db.ps1
```
Le fichier est créé dans `backups/forma_ia_<date>.sql` (non versionné, exclu du dépôt Git).

## Restauration

En cas de besoin, restaurer un dump dans la base :
```powershell
docker exec -i altiora-forma-ia-db-1 psql -U forma_user -d forma_ia < backups\forma_ia_<date>.sql
```
⚠️ Cette commande écrase les données existantes — à utiliser avec précaution, idéalement sur une base vide ou de test.

## Fréquence prévue en production

Conformément au Kit de pilotage du projet : sauvegarde quotidienne automatisée de la base de recette/production (S12-S13), avec un test de restauration effectué au moins une fois avant la mise en production finale (S12).

## Fichiers générés

Le volume Docker `generated_files` persiste les documents générés entre les redémarrages de conteneurs en développement. En production, une stratégie de sauvegarde équivalente (snapshot de volume ou export régulier) sera mise en place à l'étape de déploiement (S12-S13).