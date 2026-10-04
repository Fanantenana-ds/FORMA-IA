# Intégration API Google — FORMA-IA

## État actuel

Le module M5 (Formations) prévoit la génération automatique de 4 formulaires
Google Forms par session (inscription, avant-formation, après-formation,
satisfaction), visible dans les modèles (`app/models/formation.py`) et schémas
(`app/schemas/formation_ia.py`).

**Aucun client Google n'est encore implémenté** côté backend (contrairement à
Tavily, voir `app/clients/tavily_client.py`) — cette intégration reste à construire
par l'équipe IA/Backend.

## Ce qui sera nécessaire (à anticiper)

Quand l'intégration sera développée, les éléments suivants devront être ajoutés :
- Un compte de service Google Cloud avec les API Forms et Sheets activées
- Un fichier de credentials (JSON) ou des variables d'environnement dédiées
  (ex. `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_PROJECT_ID`)
- Une vérification des quotas de l'API Google Forms (limites par défaut : environ
  60 requêtes/minute par utilisateur — à confirmer selon le compte utilisé)
- Un suivi de consommation, sur le même principe que `docs/suivi-tokens.md`

## Responsabilité

Cette tâche technique revient à l'Intégrateur IA / Développeur Backend. Le DevOps
prépare la gestion des secrets associés (`.env`) une fois le besoin concret connu.