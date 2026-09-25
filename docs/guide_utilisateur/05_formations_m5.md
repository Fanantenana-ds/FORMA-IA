# M5 — Gestion des formations (6 agents)

## À quoi ça sert

Accompagne le déroulement d'une formation en cours, du démarrage (formulaires) à la clôture (rapport), via 6 agents indépendants :

| Agent | Rôle |
|---|---|
| 1 — FormGenerator | Génère 4 formulaires (inscription, test avant, test après, satisfaction) |
| 2 — LevelAnalyzer | Analyse la progression des participants (niveau avant/après) |
| 3 — SatisfactionAnalyzer | Analyse les réponses au questionnaire de satisfaction |
| 4 — PresenceAnalyzer | Détecte les anomalies de présence (Python pur, sans IA) |
| 5 — AttestationGenerator | Génère les attestations PDF (voir le [guide M6](06_attestations_m6.md) dédié) |
| 6 — ReportGenerator | Rédige le rapport final de formation |

## Étapes d'utilisation

1. **`POST /ia/formations/generate-forms`** : génère les 4 formulaires à partir des informations de session (titre, domaine, niveau, dates, lieu, formateur, effectif). Crée un review HITL.
   - Si le résultat doit être ajusté : `POST /ia/formations/regenerate-forms` avec `session_info`, `previous_generation` et un `feedback` (10 caractères minimum).
2. **Pendant/après la formation** :
   - `POST /ia/formations/analyze-levels` : nécessite `session_info`, `participants`, `corrige` (grille de correction). Crée un review HITL.
   - `POST /ia/formations/analyze-satisfaction` : nécessite `session_info`, `responses`. Crée un review HITL.
   - `POST /ia/formations/analyze-presences` : nécessite `session_info`, `participants`, `presences`. **Analyse 100 % Python, sans appel IA.** Crée un review HITL.
3. **En clôture** :
   - `POST /ia/formations/generate-attestations` : voir le [guide M6](06_attestations_m6.md).
   - `POST /ia/formations/generate-report` : rapport final, nécessite `session_data` complet.
4. **Voir l'état des agents** : `GET /ia/formations/agents` (indique lesquels sont réellement disponibles — un agent peut être indisponible si son service n'a pas pu s'initialiser).

## Ce qui nécessite une validation

**Validation HITL obligatoire pour les 6 agents** (chacun crée son propre review, indépendamment des autres). Voir le [guide de validation HITL](08_validation_hitl.md) pour approuver/rejeter — les reviews de M5 apparaissent avec `agent_id` = `agent_1_forms`, `agent_2_levels`, `agent_3_satisfaction`, `agent_4_presences`, `agent_5_attestations` ou `agent_6_report`.

## Erreurs fréquentes

- **Agent indisponible (503)** : le service correspondant n'a pas pu s'initialiser au démarrage (vérifier `/ia/formations/agents` et `/ia/formations/health`).
- **422 « Réponse IA invalide »** : la réponse du LLM n'a pas pu être validée par le schéma attendu.
- **Feedback trop court sur une régénération** : minimum 10 caractères exigé, pour forcer un feedback réellement utile.
