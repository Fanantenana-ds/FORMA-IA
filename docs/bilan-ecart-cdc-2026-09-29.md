# FORMA-IA — Bilan d’avancement par rapport au CDC

**Date de l’analyse :** 29 septembre 2026  
**Référence :** CDC FORMA-IA fusionné V1.0/V2.0 fourni pour cette analyse  
**Périmètre observé :** backend FastAPI, frontend React, routes, services, orchestrateurs, modèles/schémas, prompts, tests et configuration visibles dans le dépôt.

> Le CDC fourni se présente comme un document de fusion de travail qui reste à faire valider par l’encadreur. Les priorités et points encore ouverts dans ce document (notamment C3/RAG) ne sont donc pas considérés comme arbitrés. Cette analyse décrit le code présent ; elle ne vaut ni recette fonctionnelle, ni audit de production.

## Conclusion exécutive

**Le backend couvre désormais une grande partie du pipeline métier et plusieurs fonctionnalités déclarées « non développées » dans l’état initial du CDC ont du code réel. Le produit n’est toutefois pas utilisable de bout en bout conformément au CDC : le frontend React est encore principalement une interface de démonstration, avec des données simulées et des appels incompatibles avec l’API FastAPI.**

En particulier, le frontend utilise des chemins `/api/...` quand le backend expose principalement `/api/v1/...`, n’envoie pas le JWT attendu par les routes CRUD, et ne passe pas la clé requise par plusieurs routes IA. L’écran de connexion fabrique un profil local sans appeler `/auth/login`; les opérations en échec peuvent retourner des objets de démonstration comme si elles avaient réussi. Ainsi, les écrans ne prouvent pas la persistance des données.

**État global : backend fonctionnellement avancé, intégration et acceptation de la plateforme encore partielles.** Une présence de routes, services ou tests ne suffit pas à valider les seuils de performance, de précision, de disponibilité ou le fonctionnement réel des intégrations externes.

## État par module

| Module / priorité CDC | Ce qui existe dans le code | Écart restant pour le CDC |
|---|---|---|
| **M1 — Veille (MUST)** | Routes de veille, recherche Tavily, analyse/classification/scoring, orchestration et mécanisme de validation/synchronisation humaine côté backend. | La vue React ne consomme pas ces routes. Les seuils de précision et d’extraction ainsi que le scénario complet ne sont pas établis par les vérifications exécutées ici. |
| **M2 — TDR (MUST)** | Génération et téléchargement de documents, orchestrateur et synchronisation après approbation HITL. | L’éditeur React produit ses documents à partir de modèles locaux et ne pilote pas le workflow IA du backend. Les routes TDR n’appliquent pas visiblement la dépendance d’authentification utilisée par les autres API. |
| **M3 — Offres (MUST)** | Génération technique/financière, calculs, orchestration HITL, synchronisation après approbation et CRUD `/offres`. | L’écran CRM affiche des marchés prédéfinis et édite des documents localement ; il ne consomme pas le module M3. |
| **Préparation (MUST)** | Calcul de budget, génération d’EDT, HITL, synchronisation, et CRUD backend pour projets, salles, EDT et budget. | Aucun écran frontend dédié ni parcours de validation/synchronisation n’est raccordé. |
| **M5 — Formations (MUST)** | CRUD sessions/séances/participants/présences, agents IA, routes d’intégration Google Forms et synchronisations protégées par HITL. | Les vues de session et de présence ne raccordent pas ces workflows au backend. L’exécution réelle de Google Forms dépend d’une configuration externe non vérifiée ici. |
| **M6 — Attestations (MUST)** | Génération backend d’attestations à partir d’une session, agents de génération et route de synchronisation après HITL. | Aucun parcours frontend relié ne permet de démontrer la génération en lot, l’archivage et le téléchargement conformes aux critères de recette. |
| **M7 — Facturation (MUST V2)** | CRUD factures/paiements, calculs, génération de relances IA, HITL, persistance des relances approuvées et export comptable. | La vue React ne dialogue pas avec ces routes et ne permet pas de vérifier l’émission, les paiements ou les relances de bout en bout. |
| **M8a — Dashboard (MUST)** | Le backend fournit `/api/v1/dashboard/statistiques`. | Le frontend attend plusieurs anciennes routes `/api/dashboard/...` et des structures distinctes ; les statistiques backend ne sont donc pas branchées telles quelles. |
| **C3 — RAG (SHOULD / arbitrage CDC ouvert)** | Upload, indexation, embeddings, recherche, chat, portfolio, syllabus et questions sont représentés dans les services et routes backend. | Aucune vue RAG n’apparaît dans le routeur React. La priorité finale de C3 reste à arbitrer dans le CDC. La conformité fonctionnelle sur le corpus métier réel n’est pas démontrée. |
| **M4 — RH (COULD/bonus)** | CRUD backend formateurs/candidats/entretiens et services/routes IA RH. | Le frontend a des vues formateurs/évaluations, mais pas le parcours candidats/entretiens ; les vues présentes gardent des changements en état local et ne sont pas reliées au CRUD RH. |

## Frontend : écart principal à traiter

Les écrans React présents couvrent dashboard, veille, CRM/TDR-offre, formateurs, évaluations, sessions, présences et facturation. Il manque notamment des vues dédiées à la préparation, aux offres M3, au HITL, au RAG et au recrutement RH.

Les preuves concrètes de désynchronisation sont :

- le backend monte les routes métier sous `/api/v1`; le client appelle par exemple `/api/sessions`, `/api/opportunities`, `/api/invoices` et `/api/market-watch`;
- le contrôle frontend `/api/health` ne correspond pas au `/health` du backend ;
- le dashboard backend expose `/api/v1/dashboard/statistiques`, alors que l’interface attend quatre endpoints de dashboard différents ;
- le client REST ne joint aucun jeton d’authentification et ne transmet pas la clé d’API exigée par plusieurs routes IA ;
- la connexion et l’inscription de `AuthPage` ne font pas d’appel backend ; l’identité est créée côté navigateur et conservée dans `localStorage`. Des boutons de connexion démo et un sélecteur de rôle sont présents ;
- en cas d’échec HTTP, le service API peut retourner des données de remplacement et l’interface affiche ensuite une confirmation de création. Cela masque l’absence de persistance réelle.

**Conséquence :** ne pas présenter les écrans actuels comme une interface de production reliée aux données du backend. Ils constituent une maquette avancée à intégrer.

## Architecture et exigences transverses

- **Provider Abstraction : partielle.** L’interface commune et le provider Groq existent. `ClaudeProvider` reste un placeholder qui n’est jamais disponible ; si `LLM_PROVIDER=claude`, la factory peut retomber sur Groq. La migration réelle vers Claude demandée par le CDC n’est pas démontrée.
- **HITL : présent côté backend, pas livré dans l’interface.** Les reviews sont conservées dans un fichier JSON local, pas dans le stockage PostgreSQL. Le parcours humain n’est pas accessible depuis les vues React et ce stockage devra être évalué pour un déploiement multi-instance.
- **Authentification/RBAC : discordance.** Le backend a des routes JWT et des dépendances par rôle, mais le frontend ne s’authentifie pas auprès de lui. Certaines routes IA utilisent une clé API plutôt qu’un JWT ; les routes TDR n’affichent pas de dépendance d’authentification. La couverture homogène des règles du CDC doit être validée et sécurisée avant exposition.
- **Stack frontend :** React, Vite et TypeScript sont présents. Aucun store Zustand ni routage applicatif dédié n’a été relevé dans le frontend inspecté.
- **RAG :** les commentaires de dépendances indiquent que LangChain et les splitters LangChain ont été retirés au profit d’une implémentation spécifique. C’est une déviation à faire valider vis-à-vis de la stack prescrite par le CDC.
- **Intégrations externes :** une intégration Google Forms existe dans le code ; la configuration et les appels réels n’ont pas été vérifiés. Aucun envoi SMTP effectif n’a été établi par cette analyse.
- **Déploiement :** aucun Dockerfile, fichier docker-compose ou workflow CI n’a été trouvé dans l’arborescence examinée. TLS, montée en charge, disponibilité et déploiement cloud/serveur ne sont donc pas prouvés par le dépôt analysé.
- **Mesures d’acceptation :** la présence de scripts/benchmarks ne démontre pas à elle seule les exigences CDC de précision (>85 %), d’extraction (>90 %), de latence (<3 s), de 10 utilisateurs simultanés, d’uptime (99 %) ou de couverture globale (≥70 %). Ces résultats doivent être mesurés et documentés sur des jeux et environnements convenus.

## Vérifications exécutées

- `npm.cmd run lint` : réussi (TypeScript).
- `npm.cmd run build` : réussi ; Vite signale un bundle JavaScript principal de **796,04 kB** après minification (avertissement de découpage).
- Tests backend ciblés, avec `--noconftest` : **102 réussis, 2 échoués** parmi les quatre fichiers lancés. Les deux échecs concernent les routes de synchronisation Offres et Préparation : réponse **401** là où les tests attendaient respectivement **422** et **200**. Le contrat d’authentification et les fixtures de ces tests doivent être réalignés.
- Exécution complète de pytest non concluante : la collecte échoue sur une connexion PostgreSQL locale refusée ; une collecte depuis la racine rencontre également un script d’extraction qui attend un modèle DOCX absent (`app/templates/tdr/template_tdr_formation.docx`). Cela ne permet pas de conclure sur le résultat global ni sur la couverture.
- Aucun appel réel à Tavily, Google, Groq/Claude, aucune recette E2E navigateur/API et aucune mesure de production n’ont été effectués dans cette analyse.

## Ordre recommandé pour converger vers la recette

1. **Raccorder l’interface au contrat backend réel** : base `/api/v1`, chemins/schémas exacts et opérations par module ; supprimer les succès simulés pour les opérations d’écriture et présenter explicitement les erreurs API.
2. **Unifier l’authentification** : login/register backend, gestion du JWT, en-têtes attendus pour les routes IA et suppression des rôles de démonstration dans le parcours de production.
3. **Livrer les parcours manquants** : HITL, M3, préparation, RAG et fonctions nécessaires M5/M6/M7 ; vérifier les rôles sur chaque écran et chaque route.
4. **Rendre les validations reproductibles** : fixture DOCX, base de test isolée, tests CI sans dépendance implicite à une base locale, correction des deux divergences observées et mesure de couverture.
5. **Faire la recette CDC** : corpus annoté d’au moins 100 documents, métriques IA, latence et charge, flux complet de chaque MUST, intégrations externes et disponibilité.
6. **Arbitrer et documenter les écarts** : activation réelle de Claude, déviation LangChain, priorisation C3, stockage HITL, Docker/CI/TLS et éventuel SMTP avec l’encadreur.

## Mise à jour — 3 octobre 2026

Cette mise à jour complète le bilan du 29 septembre ; elle ne remplace pas la recette complète du frontend et du CDC.

### Ce qui avance

- Le backend a reçu de nouveaux changements CRUD et tests, dont un chantier Préparation : modèles/schémas pour les ressources de préparation, services budget/EDT et ingestion d’un EDT lié à un projet.
- Le backend expose déjà une part importante des services métier décrits dans le bilan initial ; l’écart prioritaire demeure l’intégration réelle de l’interface React, de l’authentification et des parcours humains (HITL).
- La branche locale est en avance d’un commit et en retard de neuf commits sur `origin/main`. Les changements locaux sont nombreux, majoritairement staged, avec aussi une modification unstaged de `requirements.txt` : ils ne sont pas encore un état intégré et vérifié.

### Ce qui bloque encore

- Les tests `tests/test_preparation.py` et `tests/test_dashboard.py` donnent **7 réussites et 5 échecs**. Les cinq échecs sont des réponses HTTP **401** (« token interne manquant ») sur les tests Préparation IA ; le contrat d’authentification et les fixtures de tests doivent être réalignés.
- Dans les changements locaux, la route d’ingestion d’EDT est déclarée `/{projet_id}/edt/ingest-ia}` avec une accolade fermante en trop. Corriger le chemin et ajouter un test qui appelle cette route.
- Les conclusions du 29 septembre sur le frontend restent à revalider : aucun élément récent ne démontre que les routes, le JWT, les données simulées ou les vues manquantes ont été corrigés.
- Le corpus de référence, les critères de performance, la recette E2E et les intégrations externes réelles restent à prouver comme indiqué dans le bilan initial.

### Prochaines actions recommandées

1. Corriger la route d’ingestion EDT et les tests/authentifications Préparation ; relancer les suites ciblées.
2. Stabiliser et intégrer les changements locaux avec les neuf commits distants, après revue des modifications déjà présentes.
3. Raccorder le frontend au contrat API réel (routes `/api/v1`, authentification JWT/clé IA, erreurs visibles, aucune réussite simulée), puis livrer les parcours HITL et modules manquants.
4. Reprendre la recette du CDC : corpus annoté, métriques, tests E2E, sécurité des rôles, intégrations et déploiement.

## Verdict

**Le projet est nettement au-delà d’un simple prototype backend, mais le livrable complet du CDC n’est pas encore démontré. Le blocage prioritaire est l’intégration frontend–backend/authentification ; viennent ensuite les parcours UI manquants et la preuve mesurée des critères d’acceptation.**
