# Suivi de consommation des tokens API — FORMA-IA

## État actuel

Le suivi de consommation est **techniquement implémenté côté provider Groq**
(`app/services/llm/groq_provider.py`) : chaque appel retourne un objet `usage` avec
`prompt_tokens`, `completion_tokens` et `total_tokens`, et le logue automatiquement
(visible dans les logs backend avec `tokens=<total>`).

Le provider Claude (`app/services/llm/claude_provider.py`) a la même logique prévue
dans le code, actuellement commentée — à réactiver quand l'intégration Claude sera
finalisée côté équipe IA.

L'interface commune (`llm_provider.py`) garantit que chaque provider retourne
cette structure `usage`, ce qui permettra un suivi uniforme quel que soit le
fournisseur utilisé.

## Suivi manuel (aujourd'hui)

En l'absence d'un tableau de bord dédié, la consommation peut être suivie en
consultant les logs backend :
```powershell
docker-compose logs backend | Select-String "tokens="
```

## Seuil d'alerte (Kit de pilotage)

Conformément au plan de management du projet, un seuil d'alerte est fixé à
**80 % du plafond mensuel de tokens**. Au-delà, les actions attendues sont :
optimisation des prompts, mise en place d'un cache, ou arbitrage du sponsor si
nécessaire.

## À construire (phase ultérieure)

- Un cumul persistant par module (M1 Veille, M2 TDR, M3 Offres, M5 Formations,
  M7 Facturation), par exemple via une table dédiée ou un export périodique des
  logs.
- Une alerte automatique quand le seuil de 80 % est atteint.
- La réactivation du suivi côté Claude une fois l'intégration finalisée.

Cette construction dépend du budget de tokens réel défini par ALTIORA, qui n'est
pas encore communiqué à l'équipe à ce stade du projet.
