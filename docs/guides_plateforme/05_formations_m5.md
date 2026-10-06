# Module M5 — Gestion des formations

## À quoi ça sert

Le module Gestion des formations pilote l'ensemble du cycle d'une session de formation, du début jusqu'à la clôture, grâce à six agents IA spécialisés. Chaque agent prend en charge une étape du processus et produit un livrable qui doit être validé par un responsable avant de passer à l'étape suivante.

Ce module est utilisé par les directeurs pédagogiques, les formateurs et les coordinateurs.

## Les six agents et leur rôle

| Agent | Nom | Ce qu'il fait |
|-------|-----|---------------|
| Agent 1 | Génération des formulaires | Crée les 4 formulaires de la session (inscription, test avant, test après, satisfaction) |
| Agent 2 | Analyse des niveaux | Compare les niveaux des participants avant et après la formation |
| Agent 3 | Analyse de satisfaction | Analyse les réponses au questionnaire de satisfaction |
| Agent 4 | Analyse des présences | Calcule les taux de présence et identifie les anomalies |
| Agent 5 | Génération des attestations | Crée les attestations PDF pour les participants éligibles |
| Agent 6 | Rapport final | Rédige le rapport de bilan de la formation |

## Comment utiliser le module étape par étape

**Avant la formation :**
1. Ouvrez le module Gestion des formations.
2. Renseignez les informations de la session (titre, domaine, niveau, dates, lieu, formateur, nombre de participants).
3. Cliquez sur « Générer les formulaires ». L'Agent 1 crée les 4 formulaires.
4. Validez le résultat dans la section Validation (voir guide HITL).
5. Les formulaires Google Forms réels sont créés après approbation.

**Pendant et après la formation :**
6. Analysez les niveaux des participants (Agent 2) — comparez les résultats avant/après.
7. Analysez la satisfaction (Agent 3) — à partir des réponses au questionnaire.
8. Analysez les présences (Agent 4) — calcul automatique sans intervention de l'IA.
9. Validez chaque analyse dans la section Validation.

**Clôture :**
10. Générez les attestations (Agent 5) — uniquement pour les participants éligibles selon l'Agent 4.
11. Générez le rapport final (Agent 6) — bilan complet de la formation.
12. Validez chaque livrable.

## Règle importante

Chaque étape produit une demande de validation humaine (review HITL). Il faut approuver ou rejeter avant de continuer. Aucune étape suivante ne peut démarrer sans approbation de l'étape précédente.

## Vérifier l'état des agents

Avant de lancer une opération, vérifiez que tous les agents sont disponibles dans la section « État des agents ». Un agent indisponible bloque l'étape correspondante.

## Si quelque chose ne fonctionne pas

- **Un agent est indisponible** : consultez l'état des agents — un service IA est peut-être en cours de redémarrage.
- **La génération de formulaires échoue** : vérifiez que les informations de session sont complètes.
- **Les attestations sont vides** : aucun participant n'est éligible selon l'analyse des présences — vérifiez les données de présence.
