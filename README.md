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
