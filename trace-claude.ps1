<#
.SYNOPSIS
    Journal des modifications faites par Claude Code dans le projet FORMA-IA.

.DESCRIPTION
    Chaque fois que Claude Code CREE, MODIFIE ou SUPPRIME un fichier de ce projet,
    une entrée est ajoutee dans la liste $Journal ci-dessous (avant la ligne
    "FIN DU JOURNAL"), avec une explication en francais.

    Ce script ne modifie rien : il affiche seulement le journal.

.PARAMETER Fichier
    Filtre : ne montre que les entrees dont le fichier contient ce texte.

.PARAMETER Action
    Filtre : CREE, MODIFIE ou SUPPRIME.

.PARAMETER Detail
    Affiche l'explication complete de chaque entree (sinon : tableau resume).

.EXAMPLE
    .\trace-claude.ps1
    .\trace-claude.ps1 -Detail
    .\trace-claude.ps1 -Fichier tdr_sync -Detail
    .\trace-claude.ps1 -Action MODIFIE
#>
param(
    [string]$Fichier = "",
    [string]$Action = "",
    [switch]$Detail
)

$Journal = @(
    # ------------------------------------------------------------------
    # 2026-09-21 — Sync IA -> Backend : recreation des 6 fichiers manquants
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/base_sync.py"
        Explication = "Socle commun de la synchronisation IA -> Backend (decrit par claude.md §11 mais absent du depot). Gere : lecture du .env a chaque appel, token fixe ou login automatique (POST /auth/login), re-login + 1 nouvelle tentative sur HTTP 401, skip gracieux si l'endpoint Backend est absent (404/405), verification par GET apres un POST, resultat standard, utilitaires is_valid_uuid et truncate. Ne journalise jamais le token, le mot de passe ni les payloads. Le compte de service doit avoir le role DIRECTION." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/facture_calculator_service.py"
        Explication = "Calculs de facturation en Python pur (sans LLM) pour le futur POST /ia/facturation/calculer-montants (CDC). Ordre : HT -> TVA -> TTC -> remise calculee sur le TTC -> net, memes conventions que la grille M3 (TVA 20 %, remise 5 % des 15 participants). Fournit aussi ht_apres_remise (montant HT a envoyer au Backend, dont le TTC est recalcule cote Backend) et calculer_reste_du() pour les relances. HYPOTHESE A VALIDER : type_client (participant / entreprise) est valide mais sans effet sur le prix, le CDC ne definit aucune regle." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/facture_sync.py"
        Explication = "Sync M7. sync_facture_to_backend() : POST /factures (client tronque a 50 caracteres, montant HT > 0, TVA, echeance) puis GET de controle. fetch_facture() : GET /factures/{id} (statut, TTC, paiements) pour preparer une relance. A appeler seulement APRES validation HITL : cote Backend une facture creee est immediatement EMISE." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/offre_sync.py"
        Explication = "Sync M3. sync_offre_to_backend() : POST /documents/offre (opportunite_id UUID + montant) puis GET de controle ; extract_montant() lit le net a payer dans le resultat de l'orchestrateur. LIMITE DU CONTRAT BACKEND : la trame technique et la grille financiere generees par l'IA ne sont PAS transmises (OffreRequest n'a pas de champ contenu). A demander au binome Backend (champ contenu ou routes /offres du CDC)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/preparation_sync.py"
        Explication = "Sync Preparation. Les routes du CDC (/projets, /edt, /budget) n'existent pas cote Backend (aucune table). L'EDT est donc enregistre avec les routes reelles : POST /sessions puis 1 seance par jour d'EDT. date_fin toujours envoyee (NOT NULL en base), titre/client limites a 50 caracteres, theme a 100, duree a 25. Le BUDGET n'est PAS persiste (signale dans le resultat : budget.skipped). A appeler apres validation HITL (chaque appel cree une nouvelle session)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/formation_sync.py"
        Explication = "Sync M5 volontairement legere : fetch_session() (GET /sessions/{id}, permet un contrat par session_id comme dans le CDC), sync_presences_to_backend() (presences, par exemple Google Forms, enums PRESENT / ABSENT / EXCUSE et MANUEL / GOOGLE_FORMS), sync_attestations_to_backend() (POST /documents/attestations/{session_id}, le Backend cree lui-meme les attestations). Les agents M5 stabilises et formation_orchestrator ne sont PAS modifies." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Fichiers existants qui ne correspondaient pas au contrat Backend
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/tdr_sync.py"
        Explication = "Aligne sur base_sync : login duplique supprime, re-login sur 401, GET de controle. CORRECTIONS : (1) format_export « WORD » -> « DOCX » (l'enum Backend est PDF | DOCX, « WORD » donnait HTTP 422) ; (2) ajout de la cle success, que tdr_orchestrator lisait alors qu'elle n'existait pas (elle valait toujours None) ; (3) ajout de skipped et verified. La fonction publique sync_tdr_to_backend et les cles historiques (enabled, sent, document_id, error) sont conservees. CONSTAT : POST /documents n'existe pas cote Backend (route retiree par le commit « suppression /documents/tdr ») : la sync est donc ignoree proprement (skipped) tant que le Backend n'expose pas de route de creation de TDR." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/opportunity_sync.py"
        Explication = "Aligne sur base_sync : avant, seul un token fixe etait utilise (un JWT expire vite, la sync s'arretait) ; maintenant login automatique + re-login sur 401. CORRECTION : source « VEILLE_IA » (valeur inexistante, HTTP 422 sur chaque opportunite) -> « URL » si un lien existe, sinon « TEXTE » (enum Backend : TEXTE | PDF | URL). Constantes et client httpx dupliques supprimes. Le retour reste {enabled, sent, failed}." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/opportunity_fetcher.py"
        Explication = "Login duplique supprime ; les 2 lectures (GET /opportunites/{id} et liste) passent par base_sync (re-login sur 401). Fonctions et valeurs de retour inchangees (routes_tdr continue de fonctionner, import verifie). Petite correction : fetch_opportunites_list accepte aussi une liste JSON directe (avant, l'appel .get() sur une liste levait une erreur avalee et renvoyait une liste vide)." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Tests et journal
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_backend_sync.py"
        Explication = "28 tests pytest de toute la sync (faux transport HTTP, AUCUN reseau, AUCUNE base de donnees, AUCUN LLM, aucun vrai identifiant). Resultat : 28 passed. Commande : venv\Scripts\python.exe -m pytest tests/unit/test_backend_sync.py --noconftest -q  (--noconftest car tests/conftest.py importe app.main, ce qui ouvre la base PostgreSQL)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "trace-claude.ps1"
        Explication = "Ce journal. Claude Code y ajoute une entree pour chaque fichier qu'il cree, modifie ou supprime dans votre projet." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Dependances BACKEND (demandees explicitement par le responsable IA)
    # ATTENTION : ces 3 fichiers sont dans le perimetre Backend (claude.md §14).
    # Modifications AJOUTEES et RETROCOMPATIBLES, a faire relire par le binome Backend.
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/endpoints/document.py"
        Explication = "BACKEND. Ajout de la route POST /documents/tdr (roles DIRECTION et ASSISTANT, reponse 201 DocumentResponse). Cette route existait avant : le commit « suppression /documents/tdr » l'avait retiree, alors que les tests du Backend (tests/test_document.py) l'attendent encore (401 sans token, 403 pour COMPTABLE, 201 pour ASSISTANT). Elle appelle DocumentService.generer_tdr(), qui existait deja. Aucune autre route modifiee." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/schemas/document.py"
        Explication = "BACKEND. TDRRequest : ajout de 2 champs OPTIONNELS, contenu (texte du TDR redige par l'IA, max 500 000 caracteres) et format_export (PDF ou DOCX). OffreRequest : ajout du champ OPTIONNEL contenu (offre technique + financiere redigee par l'IA, max 500 000 caracteres). Les anciennes requetes (sans ces champs) fonctionnent exactement comme avant. Aucune colonne ni migration : Document.contenu et Document.format_export existaient deja." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/document_service.py"
        Explication = "BACKEND. generer_tdr() : utilise brief.contenu et brief.format_export s'ils sont fournis (sinon texte par defaut inchange) ; renvoie 404 « Opportunite introuvable » si opportunite_id est inconnu (avant : erreur de cle etrangere, donc HTTP 500). generer_offre() : utilise data.contenu s'il est fourni, sinon le texte par defaut inchange." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/tdr_sync.py"
        Explication = "Cible desormais POST /documents/tdr (la route existe de nouveau) avec GET de controle sur /documents/{id}. Payload rendu robuste : client vide -> « Client », objectifs vides -> « Non precise » (le Backend refuse les chaines vides : HTTP 422), opportunite_id envoye seulement si c'est un UUID valide. Commentaire d'en-tete mis a jour." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/offre_sync.py"
        Explication = "La limite « le contenu IA n'est pas transmis » est levee. sync_offre_to_backend() accepte maintenant contenu (tronque a 500 000 caracteres, omis s'il est vide). Nouvelle fonction build_contenu() : transforme l'offre technique + financiere en TEXTE LISIBLE (libelles francais accentues, cles internes _review_id / metadata / success ignorees) car l'export Word/PDF du Backend imprime contenu tel quel ; un bloc JSON serait illisible dans le document du client." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_documents_route.py"
        Explication = "12 tests des routes Backend POST /documents/tdr et POST /documents/offre : 401, 403, 201, contenu IA conserve, texte par defaut conserve, opportunite inconnue (404), champs vides (422), contenu trop long (422), payload exact de tdr_sync accepte. Application FastAPI minimale + base SQLite EN MEMOIRE : aucune connexion a PostgreSQL. Commande : venv\Scripts\python.exe -m pytest tests/unit/test_documents_route.py --noconftest -q" }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/unit/test_backend_sync.py"
        Explication = "Tests ajoutes pour la nouvelle route TDR (chemin /documents/tdr + GET de controle), le nettoyage du payload TDR, l'envoi et la troncature du contenu de l'offre, et build_contenu() (texte lisible, libelles accentues, cles internes exclues). Total actuel avec test_documents_route.py : 44 tests passes." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Verification sur la vraie base PostgreSQL « formaia » (decision du responsable IA)
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/router.py"
        Explication = "BACKEND, 1 ligne : ajout de api_router.include_router(document.router). Cette ligne avait DISPARU au commit daa5cd5 (16/09, feat M3) : le module document etait importe mais jamais monte, donc TOUTES les routes /documents/... (tdr, offre, attestations, export, valider, lecture) repondaient 404 dans l'application reelle. Constat en lancant les tests Backend sur la vraie base : 17 echecs sur 21 (assert 404 == 401). Apres correction : 18 reussis sur 21. Effet voulu : ces routes deviennent joignables. Mes tests SQLite du tour precedent ne l'avaient pas vu car ils montaient le router a la main." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/unit/test_documents_route.py"
        Explication = "Ajout d'un test garde-fou (test_le_router_de_l_application_monte_les_routes_documents) : verifie que api_router de l'application monte bien /documents/tdr, /offre, /attestations, /{id}, /valider, /export. Verifie aussi que ce test aurait echoue avec l'ancien router.py (ni /documents/tdr ni /documents/offre montes). Total : 13 tests dans ce fichier, 45 avec test_backend_sync.py." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "DONNEES"; Fichier = "base PostgreSQL formaia (tables documents, opportunites, sessions)"
        Explication = "Les tests Backend existants (tests/test_document.py, test_offre.py, test_document_export.py, test_attestation.py) ECRIVENT dans la vraie base et ne nettoient pas. Mesure en lecture seule avant/apres mes 2 executions : documents 0 -> 9 (+9), opportunites 2 -> 6 (+4), sessions 5 -> 9 (+4). Aucune ligne supprimee ni modifiee par Claude Code. Ce sont des lignes de test (ex. client « Todisoa Olivier », « Appel d'offre formation Kubernetes »). Nettoyage possible sur demande, apres relecture de la liste." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Correction des 3 echecs + nettoyage des lignes de test dans « formaia »
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "DONNEES"; Fichier = "base PostgreSQL formaia (tables documents, opportunites, sessions)"
        Explication = "NETTOYAGE des lignes de test creees par mes 2 executions des tests Backend. SUPPRIME (ids exacts, 1 seule transaction) : 9 documents, 4 opportunites (contenu « Appel d'offre formation Kubernetes / DevOps », source TEXTE), 4 sessions (« Formation Kubernetes » et « Formation Ansible »). Controles avant suppression : nombres exacts, aucune seance / inscription / historique lie, aucun document reel lie. Controle apres : retour EXACT a l'etat initial sur les 12 tables (documents 0, opportunites 2, sessions 5, ...). Les 2 opportunites reelles (veille DevelopA, 16/09) et les 5 sessions reelles (« Introduction a l'IA », 17/09) n'ont pas ete touchees. Une premiere tentative a ete annulee automatiquement (erreur d'affichage sans rapport, avant le commit) : rien n'a ete perdu. SAUVEGARDE JSON des 17 lignes supprimees : C:\Users\FLAMIX\AppData\Local\Temp\claude\c--PROJET-FANA-FORMA-IA\37f75a3f-8dfa-41da-88dc-a4d5947152e2\scratchpad\sauvegarde_lignes_test.json (dossier temporaire : la copier ailleurs si vous voulez la garder)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/formation_service.py"
        Explication = "BACKEND, 3 lignes. ajouter_seance() : si duree n'est pas fournie, elle vaut « Non precisee ». Cause des echecs de test_attestation (flux_complet et idempotent) : Seance.duree est NOT NULL en base alors que SeanceCreate la declare optionnelle, donc creer une seance sans duree provoquait une erreur 500 (NotNullViolation). Correction dans le service : AUCUN changement de schema, de modele ni de migration, la base n'est pas modifiee. NON corrige (meme famille, pas demande) : Seance.theme et Session.date_fin sont aussi NOT NULL en base et optionnels dans les schemas." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/conftest.py"
        Explication = "TESTS BACKEND. Nouvelle fixture db_isolee : chaque test tourne dans une transaction ANNULEE a la fin (sessions en SAVEPOINT : les db.commit() des services fonctionnent mais ne sont jamais valides pour de bon). Effet 1 : plus aucune ligne de test dans formaia (avant, chaque execution ajoutait documents, opportunites, sessions). Effet 2 : un utilisateur factice REEL est cree dans la transaction, ce qui corrige test_valider_document_role_autorise (violation de cle etrangere documents.valide_par -> users.id). Les fixtures client, client_authenticated et client_role l'utilisent ; les tests qui n'utilisent aucune de ces fixtures (unit/test_m1, unit/test_tdr, mes tests) ne sont pas concernes. Le contenu des fixtures et des tests existants est inchange." }

    # ------------------------------------------------------------------
    # 2026-09-21 — /regenerer repare (M3 + Preparation) et sync Backend APRES approbation HITL
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/orchestrator/offre_orchestrator.py"
        Explication = "M3. (1) generate_complete() memorise les donnees d'entree dans le review (cle _inputs : tdr_data, session_info, options) : c'etait la CAUSE du bug, regenerate() cherchait tdr_data dans un review qui ne le contenait pas et echouait toujours (HTTP 422). (2) regenerate() lit _inputs (repli sur les anciennes cles), copie les options au lieu de modifier le review, et donne un message clair si l'on rejette un review individuel au lieu du review global agent_m3_complete. (3) Le feedback est transmis a l'offre technique et a l'offre financiere. (4) Nouvelle methode synchroniser_backend(review_id, opportunite_id, force) : n'accepte qu'un review APPROUVE de agent_m3_complete, un seul envoi par review, appelle offre_sync avec le texte de l'offre et le net a payer." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/orchestrator/preparation_orchestrator.py"
        Explication = "PREPARATION. (1) generate_complete() memorise offre_data, projet_info, ressources et options dans le review (_inputs) : sans cela regenerate() repartait avec des dictionnaires VIDES et des valeurs par defaut, sans erreur. (2) regenerate() lit _inputs ; refuse un review d'un autre agent et un review ancien sans entrees memorisees (message : relancer /generer-complet). (3) Le feedback est transmis a l'EDT. (4) CORRECTION au passage : les dates par defaut valaient 2026-10-{15+i}, soit des dates invalides comme 2026-10-32 au-dela de 17 jours (le Backend les aurait refusees) ; elles partent maintenant du 15/10/2026 avec un vrai calcul de date. (5) Nouvelle methode synchroniser_backend(review_id, formateur_id, force) : review APPROUVE de agent_preparation uniquement, un seul envoi par review, cree une session + une seance par jour ; le budget n'est pas persiste (aucune route Backend)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/offres/offre_technique_service.py"
        Explication = "generate() accepte feedback (parametre optionnel a la fin, appels existants inchanges). Le feedback est ajoute au prompt du LLM dans un bloc « CORRECTIONS DEMANDEES PAR LE REVISEUR HUMAIN ». Si le generateur retombe sur le gabarit Python, le feedback ne peut pas etre applique : metadata.feedback_applied vaut False (honnete, pas de faux effet)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/offres/offre_financiere_service.py"
        Explication = "Le feedback (options.feedback) est ajoute au prompt du LLM pour le TEXTE de l'offre ; les montants restent ceux du calcul Python (regle de securite existante : le LLM ne doit pas inventer de chiffres). metadata.feedback_applied indique s'il a pu etre applique (False avec le gabarit de secours)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/preparation/edt_generator_service.py"
        Explication = "generate() accepte feedback (parametre optionnel a la fin). Pris en compte seulement avec EDT_USE_LLM=true ; par defaut le LLM est desactive et l'EDT vient d'un gabarit Python : la regeneration donne alors le meme planning et metadata.feedback_applied vaut False. C'est une limite connue, signalee dans les donnees au lieu d'etre cachee." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/backend_sync/review_sync.py"
        Explication = "Garde-fous de la sync APRES approbation HITL, communs a M3 et Preparation. load_approved_review() refuse un review introuvable, non approuve (pending / rejected) ou d'un autre agent. sync_once() n'envoie qu'UNE fois par review (chaque envoi cree une nouvelle ressource cote Backend) grace a un registre data/backend_sync_registry.json (dossier data/ ignore par git) ; force=True renvoie volontairement. Le registre est separe : hitl_helper.py n'est PAS modifie. describe_sync() fabrique le message lisible." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/endpoints/offre_ia.py"
        Explication = "Nouvelle route POST /ia/offres/synchroniser {review_id, opportunite_id?, force?}. Renvoie 422 tant que le review n'est pas approuve. Routes existantes inchangees." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/endpoints/preparation_ia.py"
        Explication = "Nouvelle route POST /ia/preparation/synchroniser {review_id, formateur_id?, force?}. Renvoie 422 tant que le review n'est pas approuve ; le budget est signale comme non persiste (data.backend_sync.budget.skipped). Routes existantes inchangees." }

    # ------------------------------------------------------------------
    # 2026-09-21 — Les 3 echecs de tests restants (perimetre BACKEND, demande explicite)
    # ------------------------------------------------------------------
    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/api/v1/endpoints/analyse.py"
        Explication = "BACKEND. Route POST /opportunites/{id}/analyse RESTAUREE a l'identique depuis l'historique git (version du commit e3cfb2d^, avant sa suppression le 14/09 par « feat(M5) »). Verifie : contenu identique, seul le retour a la ligne final differe. Elle utilise AnalyseService, AnalyseResult et HistoriqueAnalyse qui existaient toujours. ATTENTION : elle renvoie toujours le resultat temporaire de l'origine (score_pertinence = 0.0) ; brancher le scoring IA de M1 est une etape distincte, non faite." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/router.py"
        Explication = "BACKEND. Import et montage de analyse.router (api_router.include_router(analyse.router)), comme avant le commit e3cfb2d." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/test_analyse.py"
        Explication = "BACKEND (tests). test_analyse_avec_auth_et_opportunite_existante utilisait un UUID code en dur (16c6314c...) qui n'existe que dans la base d'un developpeur : il echouait partout ailleurs. Le test cree maintenant sa propre opportunite (annulee a la fin par db_isolee), lance l'analyse, puis verifie que le statut passe a ANALYSEE. Les 2 autres tests sont inchanges." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/test_dashboard.py"
        Explication = "BACKEND (tests). test_get_statistiques_role_autorise exigeait chiffre_affaires_facture == 0.0, ce qui supposait une base SANS facture (formaia en contient 3). Les egalites sont remplacees par >= 0.0 et le calcul est verifie par un NOUVEAU test relatif : on cree une facture de 1000 et le chiffre d'affaires facture doit augmenter de 1000, quel que soit le contenu de la base. Pas de suppression de donnees reelles." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_regenerer_et_sync_m3_prep.py"
        Explication = "19 tests : /regenerer M3 et Preparation (entrees retrouvees, feedback transmis et feedback_applied honnete, review non rejete / individuel / d'un autre agent / ancien), dates par defaut valides sur 20 jours, sync refusee si review non approuve ou rejete, envoi unique + force, opportunite_id lu dans les entrees ou absent, sync desactivee, session + seances + budget signale, et les 2 nouvelles routes via FastAPI. Isolation totale : store HITL et registre dans un dossier temporaire, LLM coupe, faux Backend, aucune base." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/unit/test_documents_route.py"
        Explication = "Ajout d'un 2e test garde-fou : verifie que l'application monte /opportunites/{id}/analyse, /ia/offres/synchroniser et /ia/preparation/synchroniser (meme famille de bug que router.py perdu le 16/09 et analyse.py perdu le 14/09)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/veille/opportunity_analysis_service.py"
        Explication = "M1 / route d'analyse. Service OpportuniteAnalyseIAService : (1) extraction LLM OPTIONNELLE de l'objet, du budget, de l'echeance et de l'organisme (LLMAnalysisService, ANALYSE_USE_LLM=true par defaut, delai ANALYSE_LLM_TIMEOUT=30 s), (2) classification du domaine (ClassificationService, le domaine saisi par l'utilisateur prime), (3) score 0-100 (ScoringService) divise par 100 car le contrat Backend attend 0.0 a 1.0. N'utilise PAS le pipeline complet de M1 (sa sync Backend recreerait l'opportunite en doublon). Sans cle Groq, en cas d'erreur ou de delai depasse : scoring Python seul, la route ne plante jamais a cause du LLM. Les valeurs deja saisies (objet, budget, echeance, domaine) ne sont jamais ecrasees. Le budget est passe au scoring en entier : '5000000.0' etait lu 50 000 000 (x10)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/endpoints/analyse.py"
        Explication = "BACKEND (demande explicite : brancher le scoring M1). Le dictionnaire resultat_ia code en dur (score 0.0, 'Analyse temporaire') est remplace par l'appel a OpportuniteAnalyseIAService, conformement a docs/contrat-integration-ia.md. Ajout : opportunite.score_pertinence est desormais renseigne (AnalyseService ne le faisait pas : la route renvoyait donc toujours 0.0 meme avec un vrai score). La reponse est construite depuis le resultat IA. L'historique (historique_analyses) et le statut ANALYSEE restent geres par AnalyseService, non modifie. Les champs saisis de l'opportunite (objet, budget, domaine) ne sont pas modifies." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/opportunity_sync.py"
        Explication = "Correction de _parse_budget : '5M Ar' etait lu 5.0 au lieu de 5 000 000 (la regex \bM\b exigeait une frontiere de mot entre le chiffre et le M ; le docstring promettait pourtant 5M Ar -> 5000000.0). Bug present dans le commit HEAD : les budgets de ce format etaient envoyes au Backend et scores 1 000 000 fois trop petits. Nouvelle regle : M ou K colle (ou separe d'un espace) a un chiffre, sans lettre ni chiffre derriere ('150 m2' et '5 MGA' ne sont pas des millions)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/conftest.py"
        Explication = "BACKEND (tests). Ajout d'une fixture automatique _analyse_sans_llm (ANALYSE_USE_LLM=false) : aucun test ne consomme le quota Groq par accident maintenant que la route d'analyse peut appeler le LLM. Les tests qui veulent l'extraction LLM la reactivent avec un faux LLM." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_analyse_ia.py"
        Explication = "20 tests du service d'analyse IA, sans base ni reseau : echelle 0-1, contenu IA > contenu bureautique, budget float non gonfle, echeance expiree penalisee, domaine/objet/budget/echeance saisis conserves, titre derive de la 1re ligne et tronque a 255, LLM coupe = aucun appel, LLM complete les champs manquants sans ecraser les saisis, LLM en erreur / vide / trop lent / impossible a construire = scoring Python seul, appel depuis une boucle asyncio deja active. Garde-fou : le Backend n'est JAMAIS appele (pas de doublon d'opportunite)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/test_analyse.py"
        Explication = "BACKEND (tests). 7 tests AJOUTES (les 3 existants sont inchanges) sur la vraie route avec la base formaia isolee : score reel entre 0 et 1 (avant : toujours 0.0), score persiste sur l'opportunite ET dans historique_analyses, champs saisis non modifies, contenu pertinent > hors sujet, domaine saisi respecte, extraction LLM (faux LLM), LLM en panne = 200 quand meme. Le Backend est piege : un appel a base_sync.backend_request ferait echouer le test." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "tests/unit/test_backend_sync.py"
        Explication = "Ajout d'un test parametre (10 cas) sur _parse_budget : 5M, 60M, 1,5M, 5 M, 500K, 2 millions, 15 000 000, Non precise, et les cas qui ne doivent PAS etre multiplies (150 m2, 5 MGA). Les cas '5M' echouaient avant la correction." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/veille/auto_detection_service.py"
        Explication = "M1 MODE 2 (detection automatique, sans requete saisie). Contient : le profil de 5 requetes ALTIORA par defaut (formation IA, data science, DevOps/cloud, dev web/mobile, recrutement formateur/consultant IA-data), modifiable via VEILLE_AUTO_QUERIES ; le verrou anti-chevauchement (une seule detection a la fois, sinon HTTP 409) ; l'etat de la derniere execution (data/veille_auto_state.json, ecrit meme en cas d'echec) ; la planification optionnelle, DESACTIVEE par defaut (VEILLE_AUTO_ENABLED=false) car chaque passage consomme du quota Tavily + Groq. La planification tient compte des redemarrages et des passages manuels (prochain passage = derniere execution + VEILLE_AUTO_INTERVAL_HOURS, defaut 24 h). Score minimum conserve : VEILLE_AUTO_MIN_SCORE (defaut 40)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/orchestrator/veille_orchestrator.py"
        Explication = "M1. (1) analyser_opportunites et _finalize_opportunities recoivent sync_backend (defaut True : le MODE 1 recherche est inchange). (2) Nouvelle methode detecter_automatiquement : lance les requetes l'une apres l'autre (quotas), sans sync par requete, fusionne, dedoublonne (URL/titre), trie par score, applique min_score et limite, puis synchronise UNE fois vers le Backend sans doublons. Une requete en echec n'arrete pas les suivantes ; statut success / partial / degraded." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/services/backend_sync/opportunity_sync.py"
        Explication = "Nouvelle fonction sync_new_opportunities_to_backend : lit GET /opportunites puis n'envoie QUE les opportunites absentes (meme titre normalise, ou meme URL deja presente dans un contenu). Sans elle, chaque passage automatique recreerait les memes annonces dans le Backend. Si la liste du Backend est illisible, RIEN n'est envoye (cle 'error'). sync_opportunities_to_backend (mode 1) est inchangee." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/api/v1/routes_veille.py"
        Explication = "M1. Nouvelles routes : POST /ia/veille/detecter (mode 2, corps optionnel min_score / limit / sync_backend=false pour un apercu sans envoi ; 409 si deja en cours ; 500 sans detail interne) et GET /ia/veille/detecter/statut (configuration, en cours, derniere execution). Ajout d'un titre Swagger 'Mode 1' sur /ia/veille/rechercher, dont le comportement ne change pas." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/main.py"
        Explication = "Demarrage : appelle demarrer_planification (ne fait RIEN tant que VEILLE_AUTO_ENABLED n'est pas true). Ajout d'un evenement shutdown qui arrete proprement la tache planifiee. Import de l'orchestrateur de veille partage avec les routes." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_veille_auto.py"
        Explication = "37 tests, sans reseau ni base : configuration, orchestrateur (sync unique finale, fusion/doublons/seuil/limite, requete en echec, tout en echec, apercu), mode 1 inchange (sync par defaut), sync sans doublons (titre, URL, format de reponse, Backend illisible, desactivee, DEUXIEME PASSAGE IDENTIQUE = 0 creation), verrou et etat, calcul des echeances de planification (jamais execute / recent / en retard / etat illisible), creation-arret de la tache, boucle, routes (200, parametres, 422, 409, 500 sans detail, statut) et garde-fou : les deux modes sont montes dans l'application reelle." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "requirements.txt"
        Explication = "Ajout de 'pandas>=2.2,<3'. Probleme : level_analyzer_service.py (Agent 2) et satisfaction_analyzer_service.py (Agent 3) font 'import pandas' mais pandas n'etait declare nulle part : jamais installe dans le venv, donc scripts/test_agent2.py plante (ModuleNotFoundError) et le package M5 affiche '4/7 agents actifs'. Audit de tous les imports de app/ et scripts/ : pandas est le SEUL paquet manquant bloquant (docx2pdf est un repli optionnel, reportlab le remplace). Version en fourchette faute d'avoir pu la resoudre depuis mon environnement (PyPI inaccessible : Read timed out) : apres 'pip install pandas', figer la version exacte avec 'pip freeze'. Installation a faire dans le terminal de l'utilisateur." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "requirements.txt"
        Explication = "Suite : la fourchette 'pandas>=2.2,<3' est remplacee par les versions EXACTES installees (fichier au format pip freeze, transitives comprises) : numpy==2.5.3, pandas==2.3.3, python-dateutil==2.9.0.post0, pytz==2026.3.post1, tzdata==2026.4 (six deja present). Installation faite dans le venv avec 'pip install pandas' + --default-timeout 180 --retries 10 : la connexion (~20 ko/s) depassait le delai par defaut de pip (15 s), ce qui faisait echouer 'Read timed out'. 'pip check' : aucune dependance cassee ; aucune version deja figee n'a change." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "DONNEES"; Fichier = "data/hitl_reviews.json + outputs/agent2_test_output.json, agent3_test_output.json"
        Explication = "Lancement de scripts/test_agent2.py et test_agent3.py (appels Groq reels, demandes par l'utilisateur) : creent les reviews HITL-A2L-0002 et HITL-A3S-0003 (statut pending_review, a cote de HITL-A1F-0001 de l'utilisateur) et deux fichiers de sortie. Dossiers ignores par Git. Resultats : M5 passe a 6/7 agents actifs ; scores de l'Agent 2 recalcules a la main (avant 55, apres 90) = identiques." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_m5_agents_2_3.py"
        Explication = "M5 Agents 2 (niveaux) et 3 (satisfaction) : 36 tests + 2 xfail, faux LLM, store HITL dans un dossier temporaire, aucun appel Groq. Avant : couverts seulement par des scripts manuels sans assertion qui ecrivent dans le VRAI store HITL (15 reviews de test s'y trouvaient). Verifie : valeurs de reference recalculees a la main (55->90, notes 4.33/4.83/4.17/3.83/4.33, 83 %), seuils de niveau 40/70, normalisation ap_->av_, lecture des recommandations, notes vides, le LLM ne peut PAS changer les chiffres calcules (tentative de reecriture testee), plafonds 3/3/5, cles alternatives, echec/JSON invalide/reponse tronquee -> gabarit Python, review HITL. Les 2 xfail(strict) documentent des DEFAUTS CONNUS du gabarit de repli de l'Agent 2, non corriges (agent stabilise) : '+-10.0' pour une progression negative, et 'module avance' recommande meme avec 0 % d'avances (len(pourcentage) > 0 toujours vrai)." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "app/services/ia_health.py"
        Explication = "Controle de sante global des modules IA (M5, M3, Preparation). Les packages chargent leurs agents avec try/except ImportError : un paquet manquant (pandas) desactivait les Agents 2 et 3 sans erreur, et les routes /ia/*/health repondaient 'success: true' avec 4/7 agents. collecter() renvoie healthy / degraded et liste les agents requis manquants ; l'Agent 7 (RAG V2, non implemente) est optionnel. journaliser_au_demarrage() ecrit une ligne ERROR quand un agent requis manque." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "MODIFIE"; Fichier = "app/main.py"
        Explication = "Nouvelle route GET /health/ia (HTTP 200 toujours ; champ status healthy/degraded + manquants) et appel de ia_health.journaliser_au_demarrage() au demarrage. /health et les routes /ia/*/health existantes sont inchangees. NB : un commentaire de la ligne 12 ('tsy miova' -> 'Modeles') a ete retouche par l'utilisateur, conserve tel quel." }

    [pscustomobject]@{ Date = "2026-09-21"; Action = "CREE"; Fichier = "tests/unit/test_ia_health.py"
        Explication = "11 tests : tous les agents requis charges dans cet environnement (GARDE-FOU D'INSTALLATION : echoue avec 'Agents indisponibles : M5 - Agent 2..., Agent 3...' si pandas manque, verifie en simulant son absence), M5 = 6/7, agent requis manquant = degraded, Agent 7 absent = pas une degradation, M3/Preparation, route /health/ia (sain, degrade en HTTP 200), /health inchange, alerte ERROR au demarrage seulement si degrade." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "scripts/verifier_sync.py"
        Explication = "Script LECTURE SEULE demande par l'utilisateur pour consulter lui-meme la base reelle (formaia) et verifier que les opportunites detectees par M1 y sont bien synchronisees. Reutilise app.database.engine (aucun mot de passe a ressaisir). Usage : python scripts/verifier_sync.py [N] [--recherche mot]. Verifie sur la vraie base : 3 opportunites, dont celle creee lors du test de synchro de ce jour (id 39131c2a...)." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "app/prompts/m7/relance.yaml"
        Explication = "M7 (demande explicite de l'utilisateur, choisi plutot que le RAG bloque par le CDC #4.3 tant que M7 n'est pas fini). Prompt RTFCE pour la redaction des relances de facture, 3 niveaux (1 rappel courtois / 2 relance ferme / 3 mise en demeure formelle). Regle stricte : ne jamais recalculer le montant, la date ou le numero de facture (deja calcules en Python), ne jamais inventer de coordonnees bancaires ni de delai legal precis." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "app/services/facturation/relance_generator_service.py + __init__.py"
        Explication = "Agent M7 — RelanceGeneratorService, meme architecture que les Agents 2/3 du M5 : Python calcule (jours de retard, niveau 1/2/3), le LLM redige, repli par gabarit Python si le LLM est indisponible ou renvoie une reponse inexploitable (jamais d'echec). Seuils d'escalade (16j -> niveau 2, 31j -> niveau 3) : HYPOTHESE, le CDC ne fixe aucun bareme — a valider avec la direction avant un usage reel sur de vrais clients. Teste avec un vrai appel Groq sur les 3 niveaux : ton et ecriture corrects, mais le LLM invente un delai generique ('10 jours' au niveau 2) absent du prompt — pas une donnee fabriquee sur le dossier (montant/date/numero, repris tels quels), mais un ecart a signaler." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "app/orchestrator/facturation_orchestrator.py"
        Explication = "Orchestrateur M7. generer_relance(facture_id) : lit la facture via facture_sync.fetch_facture (deja existant), calcule le reste du via FactureCalculatorService.calculer_reste_du (deja existant), calcule jours de retard + niveau, fait rediger la relance par l'Agent M7, cree un review HITL (criticite 'critical' : contenu adresse a un vrai client — AUCUN envoi sans validation humaine). Retourne necessaire=False sans appeler le LLM ni creer de review si la facture est deja soldee ou si l'echeance n'est pas depassee. PAS de route /synchroniser (contrairement a M3/Preparation) : le Backend n'a aucune route pour stocker ou envoyer une relance (POST /factures/{id}/relance calcule et retourne un texte a la volee, sans persistance) — signale comme dependance Backend a discuter, pas construit sans autorisation." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "app/schemas/facture_ia.py + app/api/v1/endpoints/facture_ia.py"
        Explication = "Routes M7 : GET /ia/facturation/health, POST /ia/facturation/calculer-montants (Python pur, referencee mais jamais implementee jusqu'ici dans facture_calculator_service.py), POST /ia/facturation/relances/generer (HITL). Les routes HITL generiques (pending-reviews/approve/reject/stats) ne sont PAS dupliquees ici : une relance M7 apparait dans GET /ia/formations/pending-reviews?agent_id=agent_m7_relance et s'approuve via /ia/formations/reviews/{id}/approve, comme M3 et Preparation avant elle." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "app/api/v1/router.py + app/services/ia_health.py"
        Explication = "Montage de facture_ia.router dans api_router (meme emplacement que offre_ia/preparation_ia). Ajout de 'M7': facturation dans ia_health._packages() : GET /health/ia couvre desormais M3, M5, PREPARATION et M7." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "tests/unit/test_m7_facturation.py"
        Explication = "35 tests, sans reseau : seuils d'escalade (0/1/15/16/30/31/100 jours), jours de retard jamais negatif, reste du deduit des paiements et jamais negatif, gabarit Python sur les 3 niveaux, le LLM redige sans jamais changer les faits (numero/montant/niveau), echec LLM (erreur/JSON invalide/reponse tronquee) = repli gabarit, facture deja soldee ou echeance non depassee = aucune relance/aucun review cree, facture introuvable = ValueError (404 cote route), review HITL cree en criticite 'critical', routes (health, calculer-montants, calculer-montants invalide=422, generer=404 si introuvable, generer=200 avec review), garde-fou de montage dans l'application reelle." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "tests/unit/test_ia_health.py"
        Explication = "Ajout du 4e module (M7) : test_les_quatre_modules_sont_couverts (remplace test_les_trois_modules_sont_couverts) et test_agent_m7_manquant_est_signale." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "app/services/facturation/relance_generator_service.py + app/prompts/m7/relance.yaml + tests/unit/test_m7_facturation.py"
        Explication = "Demande de l'utilisateur : recommandation sur les seuils d'escalade M7, appliquee immediatement. Ancien : niveau 2 a 16j, niveau 3 (mise en demeure) a 31j. Nouveau : niveau 2 a 15j, niveau 3 a 45j. Raison : la mise en demeure a un poids quasi juridique (art. 1344 du Code civil) et ne doit pas etre envoyee trop tot, surtout avec des clients institutionnels (ministeres, cycles de paiement lents) — l'envoyer des 31 jours etait agressif et risquait la relation commerciale. Toujours une HYPOTHESE (le CDC ne fixe aucun bareme), mais alignee sur une pratique professionnelle plus standard. Exemple 'niveau 3' du prompt et seuils testes mis a jour en consequence (35j -> 50j)." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "DONNEES"; Fichier = "(aucun fichier — decision documentee)"
        Explication = "L'utilisateur confirme que la latitude du LLM sur des details procedureaux mineurs (ex. le delai de reglement propose, '8' ou '10 jours', non fixe dans le prompt) est acceptable et souhaitee. Aucun changement de code : le prompt relance.yaml n'impose pas de delai fixe fourni par Python, uniquement l'interdiction d'inventer montant/date/numero/coordonnees bancaires/procedure judiciaire precise — deja en place, laisse tel quel." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "app/services/veille/classification_service.py"
        Explication = "Nettoyage anomalie MUST (M1). Faux positif signale plusieurs fois : le mot-cle 'ia' etait cherche par simple sous-chaine ('in text'), donc 'materiaux' (contient 'r-i-a') declenchait le domaine IA, 'stabilite' (contient 's-t-a-b-i-l-i-t-e') le domaine DATA via 'bi'. Correction : chaque mot-cle est precompile en regex avec frontiere de mot (\b), verifie sur des cas accentues francais (developpement / redeveloppement). classify() est le seul point d'entree touche ; detect_country() et le scoring (_score_domain, dictionnaire exact) ne sont pas concernes." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "tests/unit/test_classification_service.py"
        Explication = "11 tests : faux positifs corriges (materiaux, stabilite, redeveloppement), vrais positifs toujours detectes (IA seule, intelligence artificielle, BI, developpement), insensibilite a la casse, aucun mot-cle -> domaine 'autre', garde-fou detect_country() inchangee." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "app/services/formation_service.py"
        Explication = "Nettoyage anomalie MUST (M5/Backend, meme categorie que le fix duree deja fait). Session.date_fin et Seance.theme sont NOT NULL en base alors que les schemas Pydantic les declarent optionnels : les omettre provoquait un HTTP 500 (NotNullViolation) au lieu d'un 201. Defauts appliques uniquement au niveau service (aucun modele/schema Backend touche) : date_fin = date_debut si absente (aucune duree n'est supposee), theme = 'Non precise' (meme formulation que duree)." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "tests/test_formation.py"
        Explication = "2 tests ajoutes (les existants inchanges) : creer une session sans date_fin et ajouter une seance sans theme ne renvoient plus 500, avec les valeurs par defaut attendues." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "app/services/llm/groq_provider.py + llm_provider.py + claude_provider.py"
        Explication = "Demande explicite de l'utilisateur : Provider Abstraction contournee par 8 services (pas 7 comme documente avant), pour pouvoir changer Groq -> Claude en ne touchant qu'une ligne (.env). Deux ecarts REELS trouves et combles avant migration (sinon regression silencieuse) : (1) le parametre json_mode existait dans l'interface mais n'etait JAMAIS applique (aucun response_format envoye) — 7 des 8 services en dependaient directement. Corrige, avec filet de securite integre : l'API Groq exige le mot 'json' dans les messages en mode JSON (erreur 400 sinon), ajoute automatiquement si absent. (2) reasoning_effort='low' (M1, evite un echec documente sur les modeles de raisonnement Groq) et un timeout par appel (M1=20s, M2=90s, provider = singleton partage entre appelants aux besoins differents) n'avaient aucun moyen de passer par l'interface — ajoutes comme parametres optionnels de generate(), ignores par ClaudeProvider qui ne les connait pas. Verifie par 4 appels Groq reels (M1, M2, Agent 1, Agent 2) : fonctionnent tous, et un essai avec LLM_PROVIDER=claude confirme qu'aucun service ne plante (degradation gracieuse vers le gabarit Python, aucun code touche)." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "CREE"; Fichier = "tests/unit/test_llm_provider.py"
        Explication = "18 tests de la Provider Abstraction elle-meme (json_mode applique + filet de securite du mot 'json', reasoning_effort et timeout transmis uniquement si fournis, forme de la reponse, erreurs Groq traduites en LLMTimeoutError/LLMRateLimitError, generate_with_retry reussit apres un echec transitoire et ne retente jamais une erreur non transitoire, factory : provider par defaut, provider inconnu, mise en cache)." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "8 services IA (M1, M2, M3-relance devenu M7, Agents 1/2/3/5/6 du M5) + app/services/facturation/relance_generator_service.py"
        Explication = "Chaque service remplace AsyncOpenAI direct par get_llm_provider() (app.services.llm) : self.client -> self.llm, self.client.chat.completions.create(...) -> self.llm.generate(...), response.choices[0].message.content -> response['content']. Logique metier NON touchee (construction des prompts, reparation JSON, gabarits de repli, validation) : seul le mecanisme d'appel change. M1 (llm_analysis_service.py) et M2 (tdr_service.py) : le retry manuel (retry_with_backoff + _do_call) est remplace par generate_with_retry(), deja integre a l'abstraction, ce qui simplifie ces 2 fichiers. Comportement volontairement change pour form_generator_service.py (Agent 1) : n'envoyait jamais response_format avant (aucune regression pour les 7 autres qui l'envoyaient deja) -> beneficie maintenant du mode JSON strict par defaut, seul effet attendu : moins de 'JSON repare' en pratique." }

    [pscustomobject]@{ Date = "2026-09-22"; Action = "MODIFIE"; Fichier = "tests/unit/test_m7_facturation.py + tests/unit/test_m5_agents_2_3.py"
        Explication = "FauxLLM reecrit pour l'interface LLMProvider.generate(system_prompt, user_prompt, ...) -> dict au lieu de simuler AsyncOpenAI (chat.completions.create -> objet a choices[0].message.content). Tous les .client renommes en .llm. Le test 'espion' qui verifiait le prompt exact envoye au LLM (Agent 3) adapte en consequence (envoye['user_prompt'] au lieu de envoye['messages'][1]['content']). Aucune assertion metier changee : memes valeurs de reference, memes garde-fous." }

    # === FIN DU JOURNAL — ajouter les nouvelles entrees AVANT cette ligne ===
)

# ----------------------------------------------------------------------
# AFFICHAGE
# ----------------------------------------------------------------------
$vue = @($Journal | Where-Object {
    ($Fichier -eq "" -or $_.Fichier -like "*$Fichier*") -and
    ($Action -eq "" -or $_.Action -eq $Action)
})

Write-Host ""
Write-Host "JOURNAL DES MODIFICATIONS DE CLAUDE CODE - FORMA-IA" -ForegroundColor Cyan
Write-Host ("{0} entree(s) affichee(s) sur {1}" -f $vue.Count, $Journal.Count)
Write-Host ""

if ($Detail) {
    foreach ($e in $vue) {
        Write-Host ("[{0}] {1}  {2}" -f $e.Date, $e.Action, $e.Fichier) -ForegroundColor Yellow
        Write-Host ("    " + $e.Explication)
        Write-Host ""
    }
}
else {
    $vue | Format-Table Date, Action, Fichier -AutoSize
    Write-Host "Astuce : .\trace-claude.ps1 -Detail   pour lire les explications completes."
}
