# M6 — Attestations de formation

## À quoi ça sert

Génère les attestations de formation (JSON puis PDF) pour les participants **éligibles** d'une session — l'éligibilité (généralement basée sur le taux de présence) est déterminée en amont, par l'Agent 4 (M5, `analyze-presences`).

## Étapes d'utilisation

1. Avoir au préalable la liste des `eligible_participants` (typiquement issue du résultat de `POST /ia/formations/analyze-presences`, champ `eligibles_attestation`).
2. **`POST /ia/formations/generate-attestations`** avec `session_data` (informations complètes de la session) et `eligible_participants`.
   - **Si la liste des éligibles est vide**, la route renvoie directement un résultat vide (`total_eligible: 0`) **sans appeler l'agent ni créer de review** — ce n'est pas une erreur.
   - Sinon, l'agent génère les attestations (contenu + numéro unique par attestation) et crée un review HITL.
3. Une fois approuvées, les attestations PDF sont produites par le Backend (`POST /documents/attestations/{session_id}` côté synchronisation M5, non documenté ici en détail — voir la synchronisation Backend du module M5).

## Ce qui nécessite une validation

**Validation HITL obligatoire** (`agent_id = agent_5_attestations`) avant que les attestations ne soient considérées comme définitives — voir le [guide HITL](08_validation_hitl.md).

## Erreurs fréquentes

- **Aucune attestation générée alors que des participants sont éligibles** : vérifier que `eligible_participants` n'est pas vide et correspond bien au format attendu par l'agent.
- **503 Agent 5 indisponible** : le service de génération d'attestations n'a pas pu s'initialiser — vérifier `GET /ia/formations/agents`.
- **Numéro d'attestation en doublon** : à signaler, ce cas n'est pas géré explicitement dans le code consulté pour ce guide — vérifier avant diffusion.
