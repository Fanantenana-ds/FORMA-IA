# FORMA-IA

**Plateforme intelligente de gestion de la formation professionnelle pour ALTIORA PREST (Antananarivo, Madagascar)**

Stage de Master Informatique — ENI Madagascar — 2025-2026

> État décrit : **13 octobre 2026**, branche `main`.
> Chaque statut ci-dessous distingue ce qui est **vérifié** (code lu, test exécuté ou essai réel) de ce qui reste **à mesurer**.

---

## Sommaire

1. [Objectif](#objectif)
2. [Équipe](#équipe)
3. [Pipeline métier](#pipeline-métier)
4. [Architecture](#architecture)
5. [Agents IA par module](#agents-ia-par-module)
6. [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl)
7. [RAG — Voyage AI + pgvector](#rag--voyage-ai--pgvector)
8. [Qualité logicielle](#qualité-logicielle)
9. [Installation et lancement](#installation-et-lancement)
10. [Structure du dépôt](#structure-du-dépôt)
11. [Limites connues](#limites-connues)

---

## Objectif

ALTIORA PREST gère manuellement tout le cycle d'une formation : repérer les appels d'offres, rédiger TDR et offres, préparer, animer et évaluer la formation, produire les attestations, facturer et relancer.

FORMA-IA automatise cette chaîne avec des **agents LLM orchestrés par module** et un **moteur RAG documentaire**, tout en gardant **un humain qui valide** chaque contenu destiné à l'extérieur.

## Équipe

| Rôle | Membre |
|---|---|
| Responsable IA & Data — chef de projet | RANDRIANIRINIMARO Manaosoa Fanantenana Jean Claude |
| Développeur Backend | ANDRIANOTAHINA Todisoa Olivier |
| Développeur Frontend | RAKOTOZAFIMALALA Fandeferana Michel Princy |
| Développeur Frontend | RAKOTONDRAZAKA Notahinjanahary Mirajo |
| DevOps | RAZAFIMANJATO Tombomara Marcelo |

Encadreur professionnel : M. RANAIVOSOA Sandamampianina

---

## Pipeline métier

```text
Étape 1  Détection marché + TDR          M1 + M2
   ↓
Étape 2  Offre technique + financière    M3
   ↓
Étape 3  Préparation (EDT + budget)      Préparation
   ↓
Étape 4  Supports + RAG                  C3
   ↓
Étape 5  Pendant la formation            M5 + M6
   ↓
Finale   Facturation + tableau de bord   M7 + M8a
Transverse  Assistance RH (bonus)        M4
```

| Module | Fonction | Statut |
|---|---|---|
| **M1** Veille | Recherche Tavily, analyse LLM, classification et scoring en Python, détection automatique planifiée (quota Tavily : 1000/mois, plafond 980), HITL `medium` sur la recherche manuelle | ✅ Précision 1,00 au benchmark (voir [Qualité](#qualité-logicielle)) |
| **M2** TDR | Génération du TDR, HITL obligatoire avant synchronisation | ✅ |
| **M3** Offres | Offre technique + financière, montants calculés en Python, HITL `critical`, export Word/PDF | ✅ |
| **Préparation** | EDT (gabarit Python, LLM optionnel), budget en Python pur, HITL ; projet, EDT et budget envoyés au Backend (`/projets`, `/projets/{id}/budget`) | 🟢 |
| **C3** RAG | Ingestion, embeddings Voyage AI, recherche pgvector, chat MODE STRICT, portfolio, syllabus, questions | ✅ Validé de bout en bout le 10/10/2026 |
| **M5** Formations | 6 agents (formulaires, niveaux, satisfaction, présences, attestations, rapport), publication Google Forms (OAuth2) après HITL | ✅ |
| **M6** Attestations | Attestations PDF, seuil de présence 80 % revérifié | ✅ |
| **M7** Facturation | Montants en Python, relances LLM à 3 niveaux, HITL `critical`, relances approuvées enregistrées (`POST /factures/{id}/relances`) | 🟢 |
| **M8a** Dashboard | `GET /api/v1/dashboard/statistiques` | 🟡 Non raccordé au frontend |
| **M4** RH (bonus) | Extraction et présélection de CV, entretiens, contrats et évaluation des formateurs, e-mails RH | 🟢 |

Légende : ✅ vérifié · 🟢 fonctionnel et testé, écarts documentés · 🟡 partiel.

---

## Architecture

```text
Frontend React
     ↓
Backend FastAPI  (/api/v1, JWT + rôles)
     ↓
Routes IA  (/api/v1/ia/*, jeton interne partagé)
     ↓
Orchestrateurs  (veille, tdr, offre, preparation, formation, facturation, rag, chat, rh)
     ↓
Agents IA  ── Provider Abstraction LLM (Groq actif, Claude préparé)
     ↓
backend_sync/  (IA → Backend, uniquement après approbation HITL)
     ↓
PostgreSQL + pgvector
```

**Stack** : Python 3.11+ · FastAPI · SQLAlchemy + Alembic · PostgreSQL + pgvector · Groq (`openai/gpt-oss-20b`) · Voyage AI (`voyage-4-large`) · Tavily · docxtpl + reportlab · Google Forms/Drive API · React (frontend).

### Principes d'architecture

1. **Python calcule, le LLM rédige** : montants, scores, dates et seuils ne sont jamais produits par le LLM.
2. **HITL généralisé** : tout contenu diffusé à l'extérieur est validé par un humain.
3. **Provider Abstraction** : la logique métier ne dépend pas du fournisseur LLM.
4. **Fallback systématique** : si le LLM échoue, un gabarit Python prend le relais.
5. **MODE STRICT du RAG** : aucune réponse sans source indexée.
6. **Idempotence** des synchronisations : un seul envoi par review approuvée.
7. **Prompts RTFCE** (Rôle, Tâche, Format, Contexte, Exemples) externalisés en YAML.
8. **L'IA n'écrit jamais directement en base** : elle passe par l'API Backend.
9. **Sécurité ZIP** : refus des bombes ZIP, du Zip Slip et des ZIP imbriqués.
10. **Tests isolés** : ni base réelle ni réseau dans les tests unitaires.

### Provider Abstraction LLM

```text
app/services/llm/
├── llm_provider.py      interface abstraite
├── groq_provider.py     implémentation active (openai/gpt-oss-20b)
├── claude_provider.py   préparé — is_available() renvoie encore False
└── llm_factory.py       sélection via LLM_PROVIDER
```

Notes Groq : `reasoning_effort="low"` est obligatoire pour les modèles de raisonnement (sinon le budget de tokens s'épuise avant le JSON) ; `json_mode` est appliqué avec un filet de sécurité.

---

## Agents IA par module

### M5 — Gestion des formations (cœur du projet)

| # | Agent | Technologie | HITL |
|---|---|---|---|
| 1 | FormGenerator — 4 formulaires (+ publication Google Forms) | Groq | critical |
| 2 | LevelAnalyzer — niveaux avant/après | Groq + pandas | medium |
| 3 | SatisfactionAnalyzer | Groq + pandas | medium |
| 4 | PresenceAnalyzer — anomalies de présence | Python pur | critical |
| 5 | AttestationGenerator — seuil 80 % revérifié | Python + reportlab | critical |
| 6 | ReportGenerator — rapport final | Groq + reportlab | critical |

### Autres modules

| Module | Service principal | Type |
|---|---|---|
| M2 | TdrOrchestrator | LLM + HITL |
| M3 | OffreOrchestrator (technique + financière) | LLM + HITL |
| Préparation | EDTGenerator + BudgetCalculator | LLM optionnel + Python |
| M7 | RelanceGenerator (3 niveaux) | LLM + HITL |
| M4 | CV, présélection, entretien, contrat, évaluation, e-mails | LLM + Python |
| M1 | VeilleOrchestrator — HITL `medium` (recherche manuelle) | LLM + Python |
| C3 | RagOrchestrator + ChatOrchestrator | Voyage AI + pgvector + LLM |

---

## Human-in-the-Loop (HITL)

```text
Agent IA → contenu généré → create_review() → pending_review
                                                  │
                     ┌────────────────────────────┴───────────────────────┐
                 approve                                                reject
                     ↓                                                     ↓
       synchronisation Backend autorisée                  feedback → régénération
       (route /synchroniser du module)
```

| Criticité | Règle |
|---|---|
| critical | validation obligatoire |
| medium | validation recommandée |
| low | validation optionnelle |

Routes : `GET /ia/formations/pending-reviews`, `GET /ia/formations/reviews/{id}`, `POST /ia/formations/reviews/{id}/approve`, `POST /ia/formations/reviews/{id}/reject`, `GET /ia/formations/reviews/stats`.

Garde-fou commun : `backend_sync/review_sync.py` refuse toute synchronisation d'une review non approuvée.
M1 : la recherche manuelle et l'analyse de texte créent une review `agent_m1_veille` (`medium`), synchronisée par `POST /ia/veille/synchroniser-backend` après approbation. **Écart assumé** : la détection automatique planifiée envoie directement au Backend les opportunités au-dessus du score minimal, sans review (veille interne, aucun contenu diffusé à l'extérieur).
Stockage actuel des reviews : fichier JSON local (`data/hitl_reviews.json`).

---

## RAG — Voyage AI + pgvector

### Pourquoi Voyage AI ?

`sentence-transformers` + `torch` étaient prévus, mais **bloqués par Smart App Control** de Windows (DLL non signée). Le projet est passé à **Voyage AI**, appelé directement en HTTP (httpx) : aucune installation lourde, modèle `voyage-4-large`, dimension 1024. Le découpage de texte est réimplémenté en Python pur (`texte_splitter.py`), LangChain ayant été retiré.

### Pipeline d'ingestion

```text
Fichier (PDF/DOCX/PPTX/XLSX)
 → hash SHA-256 (idempotence) → confidentialité → classification (OCR si scanné)
 → extraction (page / diapo / feuille) → nettoyage → découpage (700 tokens, chevauchement 100)
 → embeddings par lot (limiteur de débit) → PostgreSQL knowledge_base (pgvector, HNSW, cosinus)
 → résumé Groq
```

### Chat documentaire — MODE STRICT

9 types de questions routés automatiquement (`conversationnel`, `catalogue`, `inventaire`, `contenu_formation`, `localisation`, `question_fond`, `synthese_thematique`, `aide_plateforme`, `hors_sujet`). Si la recherche ne renvoie rien, la réponse fixe « Aucun support ALTIORA ne traite ce sujet » est renvoyée **sans appeler le LLM**.

### Validation réelle du 10/10/2026 (Swagger, services réels)

| Étape | Résultat |
|---|---|
| Upload `POST /api/v1/documents/upload` | PDF de 34 pages enregistré (nom = hash SHA-256) |
| Indexation `POST /api/v1/ia/rag/indexer-document` | 30 chunks, `voyage-4-large`, 4 lots (50-58 s d'attente entre lots, palier gratuit) |
| Statut `GET /api/v1/ia/rag/statut/{hash}` | `indexe`, résumé et mots-clés générés |
| Recherche `POST /api/v1/ia/rag/rechercher` | scores cosinus ≥ 0,70 sur les passages pertinents |
| Questions de révision | générées depuis le support indexé |
| Syllabus + HITL | review créée → approuvée → export DOCX |
| Chat | réponse sourcée |

Incident observé et documenté : une première indexation en tâche de fond a échoué sans remonter d'erreur (statut `erreur`) ; la relance a réussi.

Doublons corrigés le 12/10/2026 : une reprise d'indexation avait réinséré 16 chunks. Désormais un lot repris **remplace** ses chunks (`knowledge_repository.inserer_chunks`) et l'index unique `uq_kb_hash_collection_chunk` (doc_hash, collection, chunk_index) rejette tout doublon.

### Évaluation du 12/10/2026 (`scripts/evaluer_rag.py`)

Base : 1 support (30 chunks) + 9 guides `aide_plateforme` (10 chunks). Jeu `data/rag/eval_questions.yaml` : 15 questions support (page attendue vérifiée), 10 questions plateforme (guide attendu vérifié), 5 hors sujet.

| Recall@5 | Score moyen bonnes réponses | Score max hors sujet | Seuil proposé |
|---|---|---|---|
| **1,00** (25/25) | 0,540 | 0,288 | **0,414** → confirme `RAG_MIN_SCORE=0.41` du `.env` |

---

## Qualité logicielle

| Indicateur | Valeur | Source |
|---|---|---|
| Exécution complète | **996 passés / 4 en échec**, couverture **75 %** (14 328 instructions) | 12/10/2026, clés API factices |
| Échecs restants | 4 tests `TestIntegrationGoogleForms` : exigent `GOOGLE_REFRESH_TOKEN` (dépendance d'environnement) | `tests/unit/test_google_forms_publisher.py` |
| CI GitHub Actions | ✅ vert (ruff + pytest, image Postgres avec pgvector) | `.github/workflows/ci.yml` |
| Routes API | 176 | comptage du dépôt |
| Migrations Alembic | 13 | `alembic/versions/` |
| Prompts YAML | 28 | `app/prompts/` |

### Benchmark M1 (`scripts/benchmark_m1.py`)

Corpus `data/corpus_veille/corpus_v1.jsonl` : 105 textes annotés (84 `dev`, 21 `test`), dont **8 opportunités seulement**.

| Mesure | Précision | Rappel | Extraction | Latence moy. |
|---|---|---|---|---|
| 12/10, version initiale, 15 premiers textes | 1,00 | 0,50 | 0,571 | 10,4 s |
| 13/10, après les 5 commits M1, 20 textes `test` | 1,00 | 1,00 (2/2) | 0,80 | 10,7 s |

Objectifs CDC : précision > 85 % ✅ · extraction > 90 % ❌ (organisme jamais extrait) · latence < 3 s ❌. Mesure sur les 105 textes à faire : `python scripts/benchmark_m1.py --limit 105 --pause 15` (lots de 10 sauvegardés, arrêt propre si quota Groq épuisé, reprise avec `--reprendre`).

Corrections critiques notables : seuil de 80 % non revérifié (M6), TDR envoyé sans HITL (M2), benchmark M1 qui polluait la base, route `/documents` non montée (404 partout), `parse_budget('5M Ar')` → 5 au lieu de 5 000 000, champ `date` qui masquait son propre type dans deux schémas (PATCH de date toujours refusé), doublon des modèles `projets/salles/edt_sessions/budgets_formation`, chunks RAG indexés en double (12/10).

---

## Installation et lancement

```powershell
git clone https://github.com/Fanantenana-ds/FORMA-IA.git
cd FORMA-IA
git checkout main
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # puis remplacer chaque CHANGE_ME
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

- Swagger : `http://localhost:8000/api/docs`
- Deux authentifications dans Swagger : **JWT** (routes Backend, ex. `/documents/upload`) et **jeton interne `SHARED_INTERNAL_TOKEN`** (routes `/ia/*`).
- Windows : préférer `python -m uvicorn` si `uvicorn.exe` est bloqué par Smart App Control.

Tests :

```powershell
python -m pytest tests/unit -q --noconftest   # sans base de données
python -m coverage run -m pytest -q
python -m coverage report
ruff check .
```

Docker : `docker-compose up -d` (fichiers `Dockerfile`, `docker-compose.yml`, `docker-compose.recette.yml`, `docker-compose.monitoring.yml`).

---

## Structure du dépôt

```text
app/
├── api/v1/endpoints/      routes Backend + routes IA (*_ia.py)
├── orchestrator/          un orchestrateur par module
├── services/
│   ├── llm/               Provider Abstraction
│   ├── hitl/              Human-in-the-Loop
│   ├── backend_sync/      synchronisation IA → Backend
│   ├── veille/ tdr/ offres/ preparation/ formations/ facturation/ rh/
│   ├── rag/               C3 : embeddings, ingestion, recherche, chat, portfolio, syllabus
│   ├── benchmark/         benchmark M1
│   └── storage/           stockage local → GCS
├── models/  schemas/  repositories/  core/  utils/
├── prompts/               prompts RTFCE (YAML)
└── templates/             modèles Word
alembic/                   migrations
scripts/                   diagnostic RAG, import de corpus, vérifications
tests/                     unitaires (tests/unit) + Backend
docs/                      guide utilisateur, bilan d'écart CDC, contrat d'intégration IA, infra
```

Données d'exécution (non versionnées) : `data/` — registre RAG, fichiers indexés, reviews HITL, quota Tavily, état de la veille automatique.

---

## Limites connues

Présentées telles quelles, sans les masquer :

| Limite | Module |
|---|---|
| Frontend React encore largement en données simulées, non raccordé à `/api/v1` ni au JWT | Frontend |
| Vues HITL, RAG, Préparation et M3 absentes du frontend | Frontend |
| M1 mesuré sur 20 à 35 textes ; corpus pauvre en opportunités (8/105) ; extraction de l'organisme et latence hors objectif | M1 |
| Corpus réel ALTIORA non encore importé dans le RAG | C3 |
| Latence du chat parfois > 3 s ; quotas gratuits Voyage et Groq | C3 |
| Indexation en tâche de fond : un échec peut rester silencieux jusqu'à la consultation du statut | C3 |
| Fournisseur Claude préparé mais non actif | LLM |
| Reviews HITL stockées dans un fichier JSON local (pas multi-instance) | HITL |
| Route `endpoints/preparation.py` (ingestion d'EDT) non montée et à reprendre | Préparation |
| Charge (10 utilisateurs), disponibilité (99 %) et déploiement de production non mesurés | Infra |
