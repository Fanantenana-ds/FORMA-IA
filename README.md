
# 🎓 FORMA-IA

**Plateforme intelligente de gestion de la formation pour ALTIORA Prest**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-API-orange)](https://groq.com)
[![Voyage AI](https://img.shields.io/badge/Voyage%20AI-Embeddings-purple)](https://voyageai.com)
[![pgvector](https://img.shields.io/badge/pgvector-PostgreSQL-blueviolet)](https://github.com/pgvector/pgvector)
[![Tests](https://img.shields.io/badge/tests-624%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-70%25-yellowgreen)]()
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## 📖 Description

**FORMA-IA** est une plateforme intelligente destinée à automatiser et
centraliser le cycle complet de l'activité de formation professionnelle
d'**ALTIORA Prest**.

Le pipeline couvre la chaîne métier depuis la **détection des opportunités
de formation** jusqu'à la **facturation et au suivi des paiements**, avec
une génération assistée de documents tels que les TDR, offres, attestations
et rapports.

Le projet intègre :

* **13 agents IA / services intelligents** orchestrés par module ;
* une couche de **validation humaine obligatoire (HITL — Human-In-The-Loop)**
  généralisée à tous les modules produisant un contenu à diffusion externe ;
* une architecture **Provider Abstraction** permettant de changer de
  fournisseur LLM sans modifier la logique métier ;
* un **moteur RAG complet** (ingestion, recherche sémantique, chat, portfolio,
  syllabus) basé sur **Voyage AI + pgvector** ;
* une architecture modulaire basée sur **FastAPI** ;
* des mécanismes de **fallback Python pur** pour limiter la dépendance aux
  services IA externes.

**Client :** ALTIORA Prest — Antananarivo, Madagascar

**Contexte :** Stage de Master Informatique — ENI Madagascar (2025-2026)

---

## 🏗️ Pipeline Métier

Le projet suit un pipeline métier en **5 étapes + finalisation**, validé par
l'encadreur professionnel.

### 🔹 ÉTAPE 1 — DÉTECTION MARCHÉ + TDR

**Veille → Classification → Scoring → Génération TDR**

* **Modules :** M1, M2
* **Statut :** ✅ Développé
* **Points clés :**
  - M1 : analyse LLM + classification et scoring en **Python déterministe**
  - M1 : détection automatique planifiée (mode 2) avec **quota Tavily**
    (1000 appels/mois, plafond dur 980)
  - M2 : TDR avec **HITL obligatoire** avant synchronisation Backend
    (correction critique du 25/09/2026)

⬇️

### 🔹 ÉTAPE 2 — OFFRE TECHNIQUE + FINANCIÈRE

**Trame technique → Grille tarifaire → Export Word/PDF**

* **Module :** M3
* **Statut :** ✅ Développé
* **Points clés :**
  - Montants calculés en **Python pur** (le LLM ne doit jamais inventer de chiffres)
  - HITL `critical` avant synchronisation Backend
  - Route `POST /ia/offres/synchroniser` avec idempotence

⬇️

### 🔹 ÉTAPE 3 — PRÉPARATION DE LA FORMATION

**EDT → Formateur → Salle → Budget prévisionnel**

* **Module :** Préparation
* **Statut :** 🟡 Partiel
* **Points clés :**
  - EDT généré (gabarit Python, LLM optionnel)
  - Budget calculé en Python pur
  - HITL obligatoire
  - ⚠️ **Limite connue :** budget **non persisté** côté Backend

⬇️

### 🔹 ÉTAPE 4 — UPLOAD SUPPORTS + RAG

**Upload documents → Embeddings → Recherche sémantique → Chat**

* **Module :** C3 (RAG)
* **Statut :** ✅ Développé
* **Points clés :**
  - Pipeline complet : hash → idempotence → confidentialité →
    classification → extraction → nettoyage → découpage → embeddings par lot
  - **Voyage AI** `voyage-4-large` (dimension 1024) appelé par httpx
  - Base vectorielle **PostgreSQL + pgvector** (index HNSW, cosinus)
  - **Chat avec MODE STRICT** : aucune réponse sans source indexée
  - Portfolio, syllabus, questions, aide plateforme
  - Guide utilisateur indexé (collection `aide_plateforme`, 10 chunks)

⬇️

### 🔹 ÉTAPE 5 — PENDANT LA FORMATION

**Présences → Tests → Satisfaction → Attestations → Rapport**

* **Modules :** M5, M6
* **Statut :** ✅ Développé — **6 agents opérationnels sur 7**
* **Points clés :**
  - Attestations avec **revérification du seuil 80%** côté Agent 5
    (correction critique du 25/09/2026)
  - HITL sur les agents critiques
  - ⚠️ Agent 7 (KnowledgeBase V2) : vestige d'un ancien projet, non implémenté

⬇️

### 🔹 ÉTAPE FINALE — FACTURATION + SUIVI DES PAIEMENTS

**Factures → Relances → Export comptable → Dashboard**

* **Modules :** M7, M8a
* **Statut :** 🟡 Partiel
* **Points clés :**
  - Relances générées par LLM avec 3 niveaux (15j / 45j)
  - HITL `critical` obligatoire
  - ⚠️ **Limite connue :** relance **non persistée** côté Backend
  - Backend ne dispose pas encore de route de stockage de relance

---

### 📊 Vue synthétique

| Étape      | Fonction principale          | Module(s)   | Statut                 |
| ---------- | ---------------------------- | ----------- | ---------------------- |
| **1**      | Détection marché + TDR       | M1, M2      | ✅ Développé            |
| **2**      | Offre technique + financière | M3          | ✅ Développé            |
| **3**      | Préparation de la formation  | Préparation | 🟡 Partiel (budget non persisté) |
| **4**      | Supports + RAG               | C3          | ✅ Développé            |
| **5**      | Exécution de la formation    | M5, M6      | ✅ Développé — 6/7 agents |
| **Finale** | Facturation + paiements      | M7, M8a     | 🟡 Partiel             |

---

## 🤖 Les Agents IA / Services Intelligents

### Module M5 — Gestion des Formations

| #     | Agent                    | Type                 | Fonction                                    | Criticité HITL |
| ----- | ------------------------ | -------------------- | ------------------------------------------- | -------------- |
| **1** | **FormGenerator**        | LLM (Groq)           | Génération de 4 formulaires                 | 🔴 Critical    |
| **2** | **LevelAnalyzer**        | Pandas + LLM         | Analyse des niveaux avant/après formation   | 🟡 Medium      |
| **3** | **SatisfactionAnalyzer** | Pandas + LLM         | Analyse de la satisfaction des participants | 🟡 Medium      |
| **4** | **PresenceAnalyzer**     | Python pur           | Détection des anomalies de présence         | 🔴 Critical    |
| **5** | **AttestationGenerator** | LLM + PDF            | Attestations PDF (seuil 80% revérifié)      | 🔴 Critical    |
| **6** | **ReportGenerator**      | LLM + fallback       | Rapport final de formation                  | 🔴 Critical    |

### Module C3 — RAG (Assistant documentaire)

| Service                     | Type                  | Fonction                                          |
| --------------------------- | --------------------- | ------------------------------------------------- |
| **RagOrchestrator**         | Pipeline Python       | Ingestion, résumés, portfolio, syllabus, questions |
| **ChatOrchestrator**        | 9 types de questions  | Chat documentaire en MODE STRICT                  |
| **EmbeddingProvider**       | Voyage AI + httpx     | Embeddings `voyage-4-large` (1024 dim)            |
| **RechercheService**        | pgvector              | Similarité cosinus, seuil configurable            |
| **KnowledgeRepository**     | SQL direct            | Accès BDD isolé, testable sans PostgreSQL         |

### Autres modules

| Module        | Service principal              | Type            | Fonction                              |
| ------------- | ------------------------------ | --------------- | ------------------------------------- |
| **M1**        | OpportuniteAnalyseIAService    | LLM + Python    | Analyse, classification, scoring      |
| **M1**        | AutoDetectionService           | Python          | Détection auto planifiée (quota)      |
| **M2**        | TdrOrchestrator                | LLM + HITL      | Génération TDR                        |
| **M3**        | OffreOrchestrator              | LLM + HITL      | Offres technique + financière         |
| **Préparation** | BudgetCalculatorService      | Python pur      | Calcul budget prévisionnel            |
| **Préparation** | EDTGeneratorService          | LLM optionnel   | Emploi du temps                       |
| **M7**        | RelanceGeneratorService        | LLM + HITL      | Relances facture (3 niveaux)          |

> **Note :** L'Agent 7 « KnowledgeBase (RAG V2) » apparaît dans
> `app/services/formations/__init__.py` comme vestige d'un ancien projet V2
> distinct du module C3 actuel. Il est protégé par `OPTIONNELS=('Agent 7',)`
> et n'entre pas dans le décompte réel des 6 agents M5.

---

## 🔄 Human-In-The-Loop (HITL)

Toute génération IA destinée à une **utilisation ou diffusion externe**
doit faire l'objet d'une **validation humaine obligatoire** avant son
utilisation.

### Statuts de validation

| Statut           | Signification            | Action                                   |
| ---------------- | ------------------------ | ---------------------------------------- |
| `pending_review` | En attente de validation | Affichage au frontend                    |
| `approved`       | Validé par l'utilisateur | Le workflow continue                     |
| `rejected`       | Rejeté                   | Régénération ou correction avec feedback |

### Fonctionnement

```text
Agent IA
   ↓
Génération du contenu
   ↓
create_review()
   ↓
review_id (ex. HITL-A1F-0001)
   ↓
Frontend
   ↓
/ia/formations/pending-reviews
   ↓
Révision humaine
   ├── APPROUVE → /reviews/{id}/approve
   │                 ↓
   │              Synchronisation Backend autorisée
   │              (route /synchroniser du module)
   │
   └── REJETTE → /reviews/{id}/reject
                     ↓
                  Feedback transmis à l'agent
                     ↓
                  Régénération


### Modules soumis au HITL

| Module               | Agents / Fonction                                                      | Criticité   |
| -------------------- | ---------------------------------------------------------------------- | ----------- |
| **M2 — TDR**         | Génération TDR                                                         | 🔴 Critical |
| **M3 — Offres**      | Offre technique, offre financière                                      | 🔴 Critical |
| **M5 — Formations**  | FormGenerator, PresenceAnalyzer, AttestationGenerator, ReportGenerator | 🔴 Critical |
| **M5 — Formations**  | LevelAnalyzer, SatisfactionAnalyzer                                    | 🟡 Medium   |
| **Préparation**      | EDT, budget                                                            | 🔴 Critical |
| **M7 — Facturation** | Relance facture                                                        | 🔴 Critical |
| **C3 — RAG**         | Portfolio, syllabus (export DOCX uniquement après approbation)         | 🔴 Critical |

> **Écart documenté :** M1 (Veille) ne dispose **pas** de HITL — c'est un
> usage interne, aucun contenu n'est diffusé à l'extérieur.

---

## 🔌 Provider Abstraction — LLM

L'architecture sépare strictement **la logique métier et l'orchestration**
du **fournisseur LLM**.

```text
app/services/llm/
├── llm_provider.py          # Interface abstraite LLMProvider
├── groq_provider.py         # Implémentation Groq — actif (openai/gpt-oss-20b)
├── claude_provider.py       # Implémentation Claude — préparée
└── llm_factory.py           # Sélection du provider via LLM_PROVIDER (.env)
```

### Configuration `.env`

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=xxx
GROQ_MODEL=openai/gpt-oss-20b

# Migration Claude (préparée)
ANTHROPIC_API_KEY=xxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**Migration Groq → Claude :** estimée à **1 jour-homme maximum** (écriture
de `claude_provider.py` + tests, sans modification de la logique métier).

### Notes importantes

- **`reasoning_effort='low'`** est requis pour les modèles de raisonnement
  Groq (évite l'épuisement du budget de tokens avant émission du JSON).
- **`json_mode`** appliqué automatiquement avec filet de sécurité (le mot
  « json » est ajouté si absent, exigence de l'API Groq).
- **Fallback Python** : si le LLM échoue, un gabarit Python prend le relais
  (jamais d'échec côté route).

---

## 🔍 RAG — Voyage AI + pgvector

### Pourquoi Voyage AI ?

**sentence-transformers + torch** initialement prévus, mais **bloqués par
Smart App Control** sur le poste de développement (DLL `_regex.cp312-win_amd64.pyd`
non signée). Migration vers **Voyage AI** (API HTTP via httpx) :

- Aucune installation lourde requise
- Modèle `voyage-4-large`, dimension 1024
- Appel direct par `httpx` (pas de SDK officiel)

### Base vectorielle

- **PostgreSQL + extension pgvector** (0.8.6)
- Migration `Vector(384)` → `Vector(1024)` exécutée sur la base `formaia`
- Index **HNSW** pour la recherche approximative
- Similarité **cosinus** (`1 - cosine_distance`)

### Pipeline d'ingestion

```text
Fichier (PDF/DOCX/PPTX/XLSX)
   ↓
Hash (idempotence)
   ↓
Vérification confidentialité
   ↓
Classification (image / vidéo-audio / PDF scanné → OCR requis)
   ↓
Extraction (Segment avec numéro de page/diapo/feuille)
   ↓
Nettoyage (text_cleaner_service)
   ↓
Découpage (chunk_segments / chunk_pptx_slides)
   ↓
Embeddings par lot (rate_limiter + Voyage AI)
   ↓
Insertion PostgreSQL (knowledge_base)
   ↓
Résumé Groq (résumé support → résumé formation)
```

### Sécurité ZIP

- Refus > 200 Mo compressé, > 500 Mo décompressé
- Refus Zip Slip (`..`, chemin absolu)
- Refus ZIP imbriqué (`.zip` dans `.zip`)
- Refus > 200 fichiers

### Chat documentaire — MODE STRICT

9 types de questions routées automatiquement :

| Type                       | Voyage | LLM | HITL |
| -------------------------- | ------ | --- | ---- |
| `conversationnel`          | Non    | Non | Non  |
| `catalogue`                | Non    | Non | Non  |
| `inventaire`               | Non    | Non | Non  |
| `contenu_formation`        | Non    | Oui | Non  |
| `localisation`             | Oui    | Oui | Non  |
| `question_fond`            | Oui    | Oui | Non  |
| `synthese_thematique`      | Oui    | Oui | Non  |
| `aide_plateforme`          | Oui    | Oui | Non  |
| `hors_sujet`               | Non    | Non | Non  |

**Règle MODE STRICT :** si la recherche ne retourne rien, le message fixe
« Aucun support ALTIORA ne traite ce sujet » est renvoyé **SANS appeler le LLM**.

---

## 📊 Qualité logicielle

### Tests et couverture

| Métrique                  | Valeur                    |
| ------------------------- | ------------------------- |
| **Tests passés**          | **624** (au 26/09/2026)   |
| **Couverture**            | **70 %** (objectif CDC atteint) |
| **Amélioration**          | 59 % → 70 % (133 nouveaux tests) |

### Corrections critiques pipeline (25/09/2026)

| #   | Module            | Bug                                                            |
| --- | ----------------- | -------------------------------------------------------------- |
| 1a  | M5 / Attestations | Pas de revérification du seuil 80% côté Agent 5                 |
| 1b  | M2 / TDR          | Envoi au Backend **sans validation HITL**                       |
| 1c  | M1 / Benchmark    | Benchmark polluait la base `formaia`                            |
| 1d  | M1 / Benchmark    | `extraction_accuracy` comptait sans comparer au gold            |
| 1e  | M1 / Classification | Pluriels non détectés (`bureautiques`, `applications`)        |

### Bugs réels documentés (extraits)

- Import `langchain.text_splitter` cassé avec langchain 1.4.2
- `reasoning_effort` manquant sur RAG → Groq épuisait son budget
- Route `/documents` non montée dans `router.py` → 404 sur toutes les routes
- `parse_budget('5M Ar')` → 5.0 au lieu de 5 000 000
- `+{progression_absolue}` → `+-10.0` pour une progression négative

### Health check global

Route `GET /health/ia` retourne l'état de **5 modules** :

```json
{
  "status": "healthy",
  "modules": {
    "M5": "6/7 agents",
    "M3": "OK",
    "PREPARATION": "OK",
    "M7": "OK",
    "C3": "OK"
  }
}
```

Retourne `degraded` si un agent requis est indisponible (ex. `pandas` manquant).

---

## 🚀 Lancement

### Développement

Activer l'environnement virtuel :

```powershell
.\venv\Scripts\Activate.ps1
```

Démarrer le serveur FastAPI :

```powershell
python -m uvicorn app.main:app --reload
```

> **Note Windows :** l'utilisation de `python -m uvicorn` est recommandée
> si `uvicorn.exe` est bloqué par une stratégie de contrôle d'application
> (Smart App Control).

Le serveur sera accessible à :

```text
http://localhost:8000
```

### 📚 Documentation interactive

- **Swagger UI** : `http://localhost:8000/api/docs`
- **ReDoc** : `http://localhost:8000/api/redoc`
- **OpenAPI JSON** : `http://localhost:8000/api/openapi.json`

### 🐳 Production — Docker

```bash
docker-compose build
docker-compose up -d
docker-compose logs -f
```

---

## 📁 Structure du Projet

```text
FORMA-IA/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py                 # Authentification JWT
│   │   │   │   ├── opportunite.py          # CRUD opportunités
│   │   │   │   ├── analyse.py              # Analyse M1 + scoring
│   │   │   │   ├── document.py             # Génération documents
│   │   │   │   ├── facture.py              # M7 — CRUD factures
│   │   │   │   ├── facture_ia.py           # M7 — Routes IA
│   │   │   │   ├── formation.py            # Sessions, participants
│   │   │   │   ├── formation_ia.py         # M5 — Routes IA + HITL
│   │   │   │   ├── offre_ia.py             # M3 — Routes IA + HITL
│   │   │   │   ├── preparation_ia.py       # Préparation — Routes IA
│   │   │   │   ├── rag_ia.py               # C3 — Routes RAG + chat
│   │   │   │   └── dashboard.py            # Statistiques
│   │   │   ├── routes_tdr.py               # M2 — Routes TDR
│   │   │   ├── routes_veille.py            # M1 — Routes veille + quota
│   │   │   └── router.py                   # Agrégateur
│   │   │
│   │   ├── orchestrator/
│   │   │   ├── formation_orchestrator.py   # M5
│   │   │   ├── tdr_orchestrator.py         # M2 + HITL
│   │   │   ├── veille_orchestrator.py      # M1
│   │   │   ├── offre_orchestrator.py       # M3 + HITL
│   │   │   ├── preparation_orchestrator.py # Préparation + HITL
│   │   │   ├── facturation_orchestrator.py # M7 + HITL
│   │   │   ├── rag_orchestrator.py         # C3
│   │   │   └── chat_orchestrator.py        # C3 — chat
│   │   │
│   │   ├── services/
│   │   │   ├── llm/                        # Provider Abstraction
│   │   │   │   ├── llm_provider.py
│   │   │   │   ├── groq_provider.py
│   │   │   │   ├── claude_provider.py
│   │   │   │   └── llm_factory.py
│   │   │   ├── hitl/                       # HITL générique
│   │   │   ├── backend_sync/               # Sync IA → Backend
│   │   │   │   ├── base_sync.py
│   │   │   │   ├── review_sync.py
│   │   │   │   ├── tdr_sync.py
│   │   │   │   ├── offre_sync.py
│   │   │   │   ├── preparation_sync.py
│   │   │   │   ├── facture_sync.py
│   │   │   │   ├── facture_calculator_service.py
│   │   │   │   └── opportunity_sync.py
│   │   │   ├── formations/                 # M5 — 6 agents
│   │   │   │   ├── form_generator_service.py
│   │   │   │   ├── level_analyzer_service.py
│   │   │   │   ├── satisfaction_analyzer_service.py
│   │   │   │   ├── presence_analyzer_service.py
│   │   │   │   ├── attestation_generator_service.py
│   │   │   │   └── report_generator_service.py
│   │   │   ├── veille/                     # M1
│   │   │   │   ├── llm_analysis_service.py
│   │   │   │   ├── classification_service.py
│   │   │   │   ├── scoring_service.py
│   │   │   │   ├── auto_detection_service.py
│   │   │   │   ├── tavily_service.py
│   │   │   │   └── tavily_quota_service.py
│   │   │   ├── tdr/                        # M2
│   │   │   │   ├── tdr_service.py
│   │   │   │   └── tdr_document_generator.py
│   │   │   ├── offres/                     # M3
│   │   │   │   ├── offre_technique_service.py
│   │   │   │   ├── offre_financiere_service.py
│   │   │   │   └── grille_tarifaire_service.py
│   │   │   ├── preparation/                # Préparation
│   │   │   │   ├── budget_calculator_service.py
│   │   │   │   └── edt_generator_service.py
│   │   │   ├── facturation/                # M7
│   │   │   │   └── relance_generator_service.py
│   │   │   ├── rag/                        # C3 — RAG complet
│   │   │   │   ├── embedding_provider.py
│   │   │   │   ├── embedding_service.py
│   │   │   │   ├── rate_limiter.py
│   │   │   │   ├── document_loader_service.py
│   │   │   │   ├── text_cleaner_service.py
│   │   │   │   ├── texte_splitter.py       # Python pur
│   │   │   │   ├── chunking_service.py
│   │   │   │   ├── zip_securite.py
│   │   │   │   ├── catalogue_service.py
│   │   │   │   ├── registry_service.py
│   │   │   │   ├── resume_service.py
│   │   │   │   ├── knowledge_repository.py
│   │   │   │   ├── recherche_service.py
│   │   │   │   ├── query_cache_service.py
│   │   │   │   ├── formation_resolver_service.py
│   │   │   │   ├── type_detection_service.py
│   │   │   │   ├── conversation_service.py
│   │   │   │   ├── chat_log_service.py
│   │   │   │   ├── portfolio_service.py
│   │   │   │   ├── syllabus_service.py
│   │   │   │   ├── questions_service.py
│   │   │   │   ├── rag_document_generator.py
│   │   │   │   └── llm_json_helper.py
│   │   │   ├── benchmark/                  # Benchmark M1
│   │   │   ├── generator/                  # PDF/Word
│   │   │   └── ia_health.py                # Health check IA
│   │   │
│   │   ├── schemas/                        # Pydantic schemas
│   │   ├── models/                         # SQLAlchemy models
│   │   │   └── knowledge_base.py           # C3 — pgvector
│   │   ├── prompts/                        # Prompts RTFCE — YAML
│   │   │   ├── m1/                         # Veille
│   │   │   ├── m2/                         # TDR
│   │   │   ├── m3/                         # Offres
│   │   │   ├── m5/                         # Formations
│   │   │   ├── m7/                         # Facturation
│   │   │   ├── m_prep/                     # Préparation
│   │   │   └── rag/                        # RAG (10 prompts)
│   │   ├── templates/                      # Templates Word
│   │   ├── core/                           # Configuration, sécurité
│   │   └── utils/                          # Helpers
│   │
│   ├── scripts/                            # Scripts utilitaires
│   │   ├── setup_pgvector.py
│   │   ├── migrer_knowledge_base_v1024.py
│   │   ├── verifier_voyage.py
│   │   ├── diagnostic_rag.py
│   │   ├── importer_corpus.py
│   │   ├── valider_corpus.py
│   │   ├── prechauffer_cache.py
│   │   ├── evaluer_rag.py
│   │   ├── stats_chat.py
│   │   ├── verifier_sync.py
│   │   └── verifier_provider.py
│   │
│   ├── tests/
│   │   ├── unit/                           # ~500 tests
│   │   └── integration/                    # ~120 tests
│   │
│   ├── docs/
│   │   ├── guide_utilisateur/              # 9 fichiers Markdown indexés
│   │   └── protocole_annotation_corpus_m1.md
│   │
│   ├── data/                               # Données persistées (gitignore)
│   │   ├── rag/
│   │   │   ├── index_registry.json
│   │   │   ├── query_cache.json
│   │   │   ├── conversations/
│   │   │   ├── chat_logs.jsonl
│   │   │   └── fichiers/{hash}.{ext}
│   │   ├── backend_sync_registry.json
│   │   ├── hitl_reviews.json
│   │   ├── veille_auto_state.json
│   │   └── tavily_quota.json
│   │
│   ├── requirements.txt
│   └── README.md
│
├── docker-compose.yml
└── ...
```

---

## 📊 Avancement Global

```text
██████████████████████████████░░░░░░░░░  ~75 %
```

### État actuel (au 26/09/2026)

| Domaine                      | Avancement                                        |
| ---------------------------- | ------------------------------------------------- |
| Détection marché + TDR (M1, M2) | ✅ Développé (HITL sur M2)                     |
| Offre technique + financière (M3) | ✅ Développé (HITL)                          |
| Préparation formation        | 🟡 Partiel (budget non persisté)                 |
| RAG / Base de connaissances (C3) | ✅ Développé (chat, portfolio, syllabus)     |
| Gestion de la formation (M5, M6) | ✅ Développé — 6/7 agents                    |
| Facturation + paiements (M7) | 🟡 Partiel (relance non persistée)               |
| Tableau de bord (M8a)        | 🟡 Partiel                                       |
| **Qualité**                  | ✅ 624 tests, 70% couverture                    |
| **Avancement global estimé** | **~75 %**                                         |

---

## 🔐 Principes d'architecture

FORMA-IA repose sur plusieurs principes structurants :

1. **Python calcule, le LLM rédige** — les montants, scores, dates, seuils
   sont toujours calculés en Python pur. Le LLM ne fait que rédiger du texte.
2. **Human-In-The-Loop généralisé** — tout contenu à diffusion externe passe
   par une validation humaine.
3. **Provider Abstraction** — indépendance vis-à-vis du fournisseur LLM
   (Groq actif, Claude préparé).
4. **Fallback systématique** — si le LLM échoue, un gabarit Python prend le
   relais. Aucune route ne plante à cause de l'IA.
5. **MODE STRICT du RAG** — aucune réponse sans source indexée.
6. **Idempotence des synchronisations** — un seul envoi par review approuvé.
7. **Traçabilité complète** — journal `trace-claude.ps1` documente chaque
   modification.
8. **API-first** — exposition des fonctionnalités métier via FastAPI.
9. **Sécurité ZIP** — protections contre bombes ZIP, Zip Slip, ZIP imbriqués.
10. **Tests isolés** — aucun test ne touche la base réelle ni le réseau.

---

## ⚠️ Limites connues

À assumer honnêtement devant le jury :

| Limite                                | Module       | Statut        |
| ------------------------------------- | ------------ | ------------- |
| Budget non persisté côté Backend      | Préparation  | Documenté     |
| Relance non persistée côté Backend    | M7           | Documenté     |
| Enchaînement inter-modules via Frontend | Pipeline   | Documenté     |
| Latence chat RAG > 3s sur certaines questions | C3   | À surveiller  |
| Mesure précision M1 (>85%) non réalisée | M1         | À faire       |
| Import corpus réel RAG non effectué   | C3           | À faire       |
| Intégration Google Forms réelle       | M5           | À faire       |
| Déploiement Docker production         | Infrastructure | À faire     |

Ces limites sont **documentées** dans le code et les prompts, et ne sont
**jamais masquées**.

---

## 📌 Statut du projet

**FORMA-IA est en phase finale de développement.**

Le socle fonctionnel actuel couvre :

**Avancement global estimé : ~55 %.**
=======
# FORMA-IA

Plateforme intelligente de gestion de la formation pour ALTIORA SOLUTIONS.

## Objectif

Automatiser la veille commerciale, la production documentaire (TDR, attestations)
et la gestion opérationnelle des formations grâce à un agent IA basé sur l'API
Claude d'Anthropic.

## Stack technique

- Backend : FastAPI, PostgreSQL, SQLAlchemy
- IA : API Claude (Anthropic), LangChain
- Frontend : Streamlit
- Infrastructure : Docker, docker-compose
- Tests : pytest, coverage.py, ruff

## Équipe

| Rôle | Étudiant |
| --- | --- |
| Intégrateur IA & Data — chef de projet | RANDRIANIRINIMARO Manaosoa Fanantenana Jean Claude |
| Développeur Backend | ANDRIANOTAHINA Todisoa Olivier |
| Développeur Frontend | RAKOTOZAFIMALALA Fandeferana Michel Princy |
| Développeur Frontend | RAKOTONDRAZAKA Notahinjanahary Mirajo |
| DevOps | RAZAFIMANJATO Tombomara Marcelo |

Encadreur professionnel : M. RANAIVOSOA Sandamampianina (ALTIORA SOLUTIONS)

## Démarrage

_À compléter au fur et à mesure (instructions Docker à venir)._
>>>>>>> altiora/develop
