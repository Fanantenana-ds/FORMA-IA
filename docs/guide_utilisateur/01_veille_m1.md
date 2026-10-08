# M1 — Veille marché

## À quoi ça sert

Détecte des opportunités de formation (appels d'offres, demandes de formation) sur Internet, en analyse le contenu avec l'IA, et les enregistre dans FORMA-IA avec un score de pertinence.

Deux modes :
- **Mode 1 — Recherche** : vous saisissez une requête (ex. « formation en intelligence artificielle Madagascar »), le système cherche sur le web (Tavily), analyse les résultats et propose des opportunités.
- **Mode 2 — Détection automatique** : lance une série de requêtes prédéfinies (profil ALTIORA), sans saisie manuelle.

Vous pouvez aussi analyser directement un texte collé ou un PDF (appel d'offre déjà en votre possession), sans recherche web.

## Étapes d'utilisation

1. **Recherche par mots-clés** : `POST /ia/veille/rechercher` avec une requête. Le système ajoute automatiquement « Madagascar » si votre requête ne mentionne pas de zone géographique.
2. **Détection automatique** : `POST /ia/veille/detecter` (aucun corps requis) — lance le profil de requêtes ALTIORA. Vérifier l'état avec `GET /ia/veille/detecter/statut` (une seule détection à la fois : un second lancement pendant qu'une détection tourne est refusé).
3. **Analyser un texte déjà en main** : `POST /ia/veille/analyser-texte`.
4. **Analyser un PDF** : `POST /ia/veille/analyser-pdf` (fichier + source), 15 Mo maximum.
5. Les opportunités retenues (score ≥ seuil) sont automatiquement envoyées au Backend (sauf si vous désactivez `sync_backend`).

## Ce qui nécessite une validation

**Aucune validation humaine (HITL) n'est actuellement appliquée à ce module.** Les opportunités détectées sont envoyées au Backend automatiquement dès qu'elles dépassent le seuil de score, sans étape d'approbation manuelle avant enregistrement. C'est un écart par rapport au principe général de FORMA-IA (validation humaine avant toute diffusion externe) — signalé ici tel quel, pas résolu à ce jour.

## Erreurs fréquentes

- **Aucun résultat retourné** : la requête est peut-être trop spécifique, ou Tavily n'a rien trouvé pour ce sujet/cette zone.
- **Détection automatique refusée (409)** : une détection est déjà en cours — attendez qu'elle se termine (voir `/detecter/statut`).
- **Erreur 500 sur l'analyse PDF** : le PDF est peut-être scanné (image) sans texte exploitable, ou corrompu.
