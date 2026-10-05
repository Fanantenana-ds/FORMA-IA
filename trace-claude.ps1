# =============================================================================
# TRACE DES INTERVENTIONS CLAUDE — FORMA-IA Backend
# =============================================================================
# Ce fichier retrace toutes les actions majeures effectuées par Claude Code
# sur le backend. À lire pour comprendre l'historique des décisions.
# =============================================================================

Write-Host @"
============================================================
  TRACE DES INTERVENTIONS CLAUDE — FORMA-IA Backend
============================================================

SESSION 1 — Architecture initiale
----------------------------------
- Création du backend FastAPI (169 routes, modules M1 à M8)
- Structure : app/api/v1/endpoints/, app/services/, app/models/
- Configuration : requirements.txt, pytest.ini, .env.example
- Branche : develop → GitHub RTcello/altiora-forma-ia

SESSION 2 — Tests et couverture CI
-----------------------------------
- Objectif : couverture ≥ 75% pour CI
- Résultat : 78% de couverture globale (951 tests verts)

Nouveaux fichiers de tests créés :
  tests/unit/test_security.py
    → 5 tests : token absent/vide/mauvais/bon, credentials None
  tests/unit/test_tdr_service.py
    → TestBuildPrompt : placeholders, valeurs par défaut, accolades résiduelles
    → TestExtractJson : JSON direct/dans texte/invalide/vide/imbriqué
    → TestGenerate : brief vide/None/réponse invalide/valide/exception LLM
  tests/unit/test_validation_service.py
    → quality_filter, normalize_opportunity, _extract_employer_from_url
    → deduplicate, validate_against_schema, fallback_response
    → _flag_ambiguous_organizer

Configuration CI créée :
  .coveragerc
    → [run] source = app, omit migrations + venv
    → [report] fail_under = 75, show_missing = true
  pytest.ini (modifié)
    → addopts = -p no:langsmith_plugin
    → (--cov retiré pour ne pas bloquer les runs partiels)

Fix notable :
  test_ajoute_flag_si_source_egal_organizer_et_plateforme
    → Cause : source "recrute" déclenchait retour anticipé dans _flag_ambiguous_organizer
    → Fix : source = "asako.mg" sans mot-clé recrute/hiring

SESSION 3 — Google Forms + Drive (OAuth2)
------------------------------------------
Problème de départ : service account → HTTP 500 sur Forms API
  → Forms API nécessite OAuth2 utilisateur, pas service account seul

Solution choisie : flux OAuth2 "copier-coller" (InstalledAppFlow OOB)
  → scripts/setup_google_oauth.py créé
  → Génère URL d'autorisation → user colle code → GOOGLE_REFRESH_TOKEN dans .env
  → Teste en créant + supprimant un vrai formulaire

Fichiers créés :
  app/services/formations/google_forms_publisher_service.py
    → GoogleFormsPublisherService : Agent 1b (publication après HITL)
    → publish_all(forms_data, session_titre) → dict {section: url}
    → publish_one(section_data, titre, section_type) → str URL
    → _build_batch_requests(questions, section_type) → List[Dict]
    → _build_question_item(label, q_type, options, required, is_test, raw_q)
    → _move_to_folder(file_id, folder_id)
    → delete_form(form_id) → bool (pour les tests)
    → is_available() → bool (vérifie GOOGLE_REFRESH_TOKEN)

  app/services/formations/__init__.py (modifié)
    → Import GoogleFormsPublisherService avec try/except (graceful degradation)
    → Exposé dans __all__ si disponible

  app/api/v1/endpoints/formation_ia.py (modifié)
    → Nouvelle route : POST /ia/formations/reviews/{id}/publish-forms
    → Vérifie : review existe + status == "approved" + agent_id == "agent_1_forms"
    → Vérifie GOOGLE_REFRESH_TOKEN présent (503 sinon)
    → Retourne : {success, message, forms_urls, forms_count}

  scripts/setup_google_oauth.py
    → Script one-time pour obtenir le refresh_token OAuth2
    → Lit secrets/google_oauth_client.json
    → Sauvegarde GOOGLE_REFRESH_TOKEN dans .env automatiquement

  tests/unit/test_google_forms_publisher.py
    → TestIsAvailable : token absent/présent
    → TestBuildBatchRequests : texte, QCM, scale, textarea, vide, ordre index
    → TestRoutePublishForms : 404, 422 non approuvée, 422 mauvais agent, 503 token absent
    → TestIntegrationGoogleForms : 3 tests réels (skipped si GOOGLE_REFRESH_TOKEN absent)
      * test_publisher_initialise_correctement
      * test_publish_one_inscription → crée + supprime formulaire réel
      * test_publish_all_4_formulaires → crée + supprime 4 formulaires réels
      * test_publish_one_qcm → vérifie questions QCM

Résultats tests d'intégration réels :
  ✅ 4/4 tests d'intégration verts (46s)
  ✅ 4 formulaires Google Forms créés et supprimés automatiquement

Fix notable — TestRoutePublishForms :
  Cause : monkeypatch ciblait hitl.get_review mais route importe get_review as _get
  Fix :   monkeypatch.setattr(app.api.v1.endpoints.formation_ia, "_get", lambda...)

Variables d'environnement requises (dans .env, jamais dans le code) :
  GOOGLE_REFRESH_TOKEN       — obtenu via scripts/setup_google_oauth.py
  GOOGLE_OAUTH_CLIENT_PATH   — chemin vers secrets/google_oauth_client.json
  GOOGLE_DRIVE_FOLDER_ID     — dossier Drive cible (optionnel)

SESSION 4 — Documentation frontend
-------------------------------------
Fichier mis à jour :
  docs_frontend/GUIDE_INTEGRATION_FRONTEND.md
    → Guide réécrit en tutoriel 4 étapes progressives
    → Étape 1 : Auth + supprimer mock
    → Étape 2 : corriger vues existantes
    → Étape 3 : créer vues manquantes (Documents, Préparation, HitlReview)
    → Étape 4 : brancher agents IA
    → Section M5 Google Forms ajoutée : route POST /reviews/{id}/publish-forms
    → Tableau récapitulatif et planning 10 jours

============================================================
  ÉTAT ACTUEL
============================================================
  Backend       : 169 routes, 951 tests verts, 78% couverture
  Google Forms  : OAuth2 configuré, 4 formulaires publiables
  CI            : .coveragerc fail_under=75, prêt pour GitHub Actions
  Branche       : develop → RTcello/altiora-forma-ia
============================================================
"@
