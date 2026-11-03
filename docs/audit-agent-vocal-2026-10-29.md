# Agent vocal : état vérifié le 29 octobre 2026

Audit sur `main`, dépôt déjà modifié : 15 fichiers suivis modifiés et 11 fichiers non suivis au début de la reprise. Aucun commit, reset, installation ou changement de configuration sensible.

## Contrat et limites

`POST /api/v1/ia/vocal/commande` utilise le jeton interne IA. Le service vocal appelle `ChatOrchestrator.traiter_message` pour les questions documentaires et transmet l'identifiant de conversation. `texte_affiche` conserve la réponse complète, `texte_a_lire` est une courte extraction nettoyée ; `reponse_vocale` reste compatible. Ce n'est pas une synthèse sémantique supplémentaire par LLM.

La liste blanche contrôle les actions proposées par le LLM. Une faible confiance ou des paramètres manquants empêche la navigation. La confiance est déclarée par le modèle, pas une probabilité calibrée.

Les commandes métier ne sont pas exécutées par ce service. Les créations/générations sont signalées `integration_requise`. Aucun succès métier n'est annoncé. Arrêter interrompt le microphone, la lecture et l'attente HTTP côté React ; ce n'est pas une annulation de transaction serveur.

## Onze intentions

| Intention | Traitement vocal actuel | Cible existante / préconditions pour raccordement |
| --- | --- | --- |
| veille_marche | Navigation React vers la veille, pas de lancement automatique | Routes veille IA ; paramètres de recherche et mode explicite |
| generer_tdr | Non raccordé, aucune génération | Orchestrateur TDR ; opportunité identifiée, schéma métier, HITL |
| generer_offre | Non raccordé | Routes offres IA ; TDR/contexte validé, paramètres financiers, HITL |
| creer_seance | Non raccordé ; ne crée pas une session à la place | POST /sessions/{session_id}/seances ; session existante, données SeanceCreate, JWT et rôle DIRECTION/FORMATEUR |
| generer_attestation | Non raccordé | Module formation/attestation ; participant, session, éligibilité et validation métier |
| relance_facture | Non raccordé | Routes facturation IA ; facture identifiée, contexte, validation avant synchronisation/envoi |
| question_rag | C3 réel appelé ; sources et conversation restituées | Question, conversation facultative ; corpus indexé, Voyage et Groq selon parcours |
| afficher_opportunites | Navigation uniquement | Écran veille ; données à charger par son service |
| afficher_sessions | Navigation uniquement, aucune liste inventée | GET /sessions avec JWT utilisateur et filtres |
| afficher_validations | Non raccordé au panneau vocal | Intégration écran HITL et droits utilisateur à établir |
| hors_perimetre | Réponse sans action | Aucune cible métier |

Ces préconditions sont des points d'intégration, pas un schéma complet validé pour chaque module. Les salutations et annulations simples sont locales et sans LLM.

## Dépendances restantes

Le frontend général utilise encore `/api/sessions` et un secours de données simulées. Le backend réel expose `/api/v1/sessions` protégé par JWT. Raccorder les écritures nécessite le contexte utilisateur et les validations métier ; le jeton IA ne doit pas les remplacer. Aucun backend CRUD, modèle ou mécanisme JWT n'a été modifié.

C3 contient déjà des réponses de secours sans sources. Le vocal masque les réponses documentaires non sourcées pour les types concernés, y compris l'aide plateforme, et demande un support pertinent. Le guide local C3 n'est pas une preuve documentaire ; il ne sera pas présenté comme une réponse sourcée. C3 lui-même est conservé.

## Vérification manuelle indispensable

Avec le backend et le frontend déjà lancés : autoriser le microphone, choisir une voix française, dicter puis envoyer une question documentaire. Vérifier réponse complète, sources et voix courte. Tester une seconde question, Arrêter, refus de permission et backend indisponible. « Crée une séance Python jeudi » doit demander des précisions ou annoncer le raccordement manquant, sans annoncer une création. « Ouvre les sessions » doit ouvrir l'écran sans inventer de planning.

Les tests locaux utilisent des doublures : ils ne prouvent pas la qualité du vrai corpus ALTIORA, l'accès Groq/Voyage, les permissions d'un navigateur ni une exécution métier de bout en bout.

## Résultats exécutés

- Vocal : 18 tests réussis (`test_routeur_vocal`, `test_assistant_vocal_service`, `test_vocal_ia_endpoint`, pytest avec `--noconftest --no-cov`).
- C3 : 15 tests réussis (`test_rag_chat_orchestrator`, mêmes options, doubles et fichiers temporaires).
- Frontend : `npm run lint` (TypeScript) et `npm run build` réussis. Vite signale un bundle supérieur à 500 ko.
- Ruff : indisponible dans le venv (`No module named ruff`), aucune installation.
- Avertissement Pydantic sur la configuration de classes existantes. Couverture non mesurée.
