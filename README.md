# 🎓 FORMA-IA

**Plateforme intelligente de gestion de la formation pour ALTIORA Prest**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-API-orange)](https://groq.com)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## 📖 Description

**FORMA-IA** est une plateforme intelligente qui automatise le cycle complet
de l'activité de formation professionnelle d'**ALTIORA Prest** : de la
détection d'opportunités (veille marché) jusqu'à la facturation, en passant
par la génération assistée de documents (TDR, offres, attestations,
rapports).

Le projet intègre **7 agents IA** orchestrés, une couche de **validation
humaine obligatoire (HITL)** et une architecture **Provider Abstraction**
permettant de migrer entre fournisseurs LLM sans modifier le code métier.

**Client** : ALTIORA Prest — Antananarivo, Madagascar
**Contexte** : Stage Master Informatique ENI Madagascar 

---

## 🏗️ Pipeline Métier

Le projet suit un pipeline en **5 étapes + finalisation** validé par
l'encadreur professionnel :
─────────────────────────────────────────────────────────────────┐
│ ÉTAPE 1 — DÉTECTION MARCHÉ + TDR │
│ Veille → Classification → Scoring → Génération TDR │
│ Modules : M1, M2 | Statut : ✅ DÉVELOPPÉ │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ ÉTAPE 2 — OFFRE TECHNIQUE + FINANCIÈRE │
│ Trame technique + Grille tarifaire + Export Word/PDF │
│ Module : M3 | Statut : 🚧 EN COURS │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ ÉTAPE 3 — PRÉPARATION DE LA FORMATION │
│ EDT + Formateur + Salle + Budget prévisionnel │
│ Module : Préparation | Statut : ❌ À DÉVELOPPER │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ ÉTAPE 4 — UPLOAD SUPPORTS + RAG │
│ Upload documents + Embeddings + Recherche sémantique │
│ Module : C3 (RAG) | Statut : ❌ À DÉVELOPPER │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ ÉTAPE 5 — PENDANT LA FORMATION │
│ Présences + Tests + Satisfaction + Attestations + Rapport │
│ Modules : M5, M6 | Statut : ✅ DÉVELOPPÉ (7 agents) │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│ ÉTAPE FINALE — FACTURATION + SUIVI PAIEMENTS │
│ Factures + Relances + Export comptable + Dashboard │
│ Modules : M7, M8a | Statut : 🟡 PARTIEL │
└─────────────────────────────────────────────────────────────────┘


---

## 🤖 Les 7 Agents IA (M5)

Le module **M5 (Gestion des Formations)** est le cœur du projet. Il
coordonne 7 agents IA via un orchestrateur central.

| # | Agent | Type | Fonction | Criticité HITL |
|---|-------|------|----------|----------------|
| **1** | FormGenerator | LLM | Génère 4 formulaires Google Forms | 🔴 Critical |
| **2** | LevelAnalyzer | Pandas + LLM | Analyse niveaux avant/après | 🟡 Medium |
| **3** | SatisfactionAnalyzer | Pandas + LLM | Analyse satisfaction participants | 🟡 Medium |
| **4** | PresenceAnalyzer | Python pur | Détection anomalies présences | 🔴 Critical |
| **5** | AttestationGenerator | LLM + PDF | Génère attestations PDF | 🔴 Critical |
| **6** | ReportGenerator | LLM + fallback | Rapport final de formation | 🔴 Critical |
| **7** | KnowledgeBase (RAG) | LangChain + ChromaDB | Base vectorielle (V2) | ⏳ À venir |

---

## 🔄 Human-In-The-Loop (HITL)

**Toute génération IA destinée à une diffusion externe** doit faire l'objet
d'une **validation humaine obligatoire** avant utilisation.

### Statuts

| Statut | Signification | Action |
|--------|---------------|--------|
| `pending_review` | En attente | Affichage au frontend |
| `approved` | Validé | Workflow continue |
| `rejected` | Rejeté | Régénération avec feedback |

### Fonctionnement
Agent IA génère contenu
→ create_review() → review_id (ex: HITL-A1F-0001)

Frontend interroge /pending-reviews
→ Affichage au réviseur humain

Réviseur approuve ou rejette
→ /reviews/{id}/approve ou /reviews/{id}/reject

Workflow continue (si approuvé)



### Modules avec HITL

| Module | Agents | Criticité |
|--------|--------|-----------|
| M3 — Offres | Technique, Financière | 🔴 Critical |
| M4 — RH | Email candidat | 🔴 Critical |
| M5 — Formations | Agents 1, 4, 5, 6 | 🔴 Critical |
| M5 — Formations | Agents 2, 3 | 🟡 Medium |
| M7 — Facturation | Facture, Relance | 🔴 Critical |

---

## 🔌 Provider Abstraction (LLM)

L'architecture sépare strictement **l'orchestration métier** du
**fournisseur LLM** :
app/services/llm/
├── llm_provider.py # Interface abstraite
├── groq_provider.py # Implémentation Groq (actif)
├── claude_provider.py # Implémentation Claude (V3)
└── llm_factory.py # Sélection via .env

🏃 Lancement
Développement
bash
# Démarrer le serveur avec reload automatique
uvicorn app.main:app --reload
Le serveur sera accessible sur : http://localhost:8000

Documentation interactive
Swagger UI : http://localhost:8000/api/docs

ReDoc : http://localhost:8000/api/redoc

OpenAPI JSON : http://localhost:8000/api/openapi.json

Production (Docker)
bash
# Build
docker-compose build

# Démarrer tous les services
docker-compose up -d

# Logs
docker-compose logs -f

📁 Structure du Projet

FORMA-IA/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py                 # Authentification JWT
│   │   │   │   ├── opportunite.py          # CRUD opportunités
│   │   │   │   ├── document.py             # Génération documents
│   │   │   │   ├── facture.py              # Facturation (M7)
│   │   │   │   ├── formation.py            # Sessions, participants
│   │   │   │   ├── formation_ia.py         # M5 — Routes IA
│   │   │   │   └── dashboard.py            # Statistiques
│   │   │   ├── routes_tdr.py               # M2 — Routes TDR
│   │   │   ├── routes_veille.py            # M1 — Routes veille
│   │   │   └── router.py                   # Agrégateur
│   │   ├── orchestrator/
│   │   │   ├── formation_orchestrator.py   # M5 — 7 agents
│   │   │   ├── tdr_orchestrator.py         # M2
│   │   │   └── veille_orchestrator.py      # M1
│   │   ├── services/
│   │   │   ├── llm/                        # 🆕 Provider Abstraction
│   │   │   ├── hitl/                       # 🆕 HITL Générique
│   │   │   ├── formations/                 # M5 — Agents 1-6
│   │   │   ├── veille/                     # M1
│   │   │   ├── tdr/                        # M2
│   │   │   ├── offres/                     # M3 (à venir)
│   │   │   ├── rh/                         # M4 (à venir)
│   │   │   └── facturation/                # M7 (partiel)
│   │   ├── schemas/                        # Pydantic schemas
│   │   ├── models/                         # SQLAlchemy models
│   │   ├── prompts/                        # Prompts RTFCE (YAML)
│   │   │   ├── m1/                         # Veille
│   │   │   ├── m2/                         # TDR
│   │   │   ├── m3/                         # Offres (à venir)
│   │   │   └── m5/                         # Formations (7 prompts)
│   │   ├── templates/                      # Templates Word
│   │   │   ├── tdr/
│   │   │   ├── attestations/
│   │   │   └── rapports/
│   │   ├── core/                           # Config, security
│   │   └── utils/                          # Helpers
│   ├── scripts/                            # Scripts utilitaires
│   ├── tests/                              # Tests pytest
│   ├── docs/                               # Documentation
│   ├── .env.example                        # Template config
│   ├── .gitignore                          # Fichiers ignorés
│   ├── requirements.txt                    # Dépendances
│   └── README.md                           # Ce fichier



Avancement global

████████████████████░░░░░░░░░░░░░░░░  ~55%
