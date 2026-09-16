# 🎓 FORMA-IA

**Plateforme intelligente de gestion de la formation pour ALTIORA Prest**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-API-orange)](https://groq.com)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## 📖 Description

**FORMA-IA** est une plateforme intelligente destinée à automatiser et
centraliser le cycle complet de l'activité de formation professionnelle
d'**ALTIORA Prest**.

Le pipeline couvre la chaîne métier depuis la **détection des opportunités
de formation** jusqu'à la **facturation et au suivi des paiements**, avec
une génération assistée de documents tels que les TDR, offres,
attestations et rapports.

Le projet intègre :

* **7 agents IA** orchestrés pour le module de gestion des formations ;
* une couche de **validation humaine obligatoire (HITL — Human-In-The-Loop)** ;
* une architecture **Provider Abstraction** permettant de changer de
  fournisseur LLM sans modifier la logique métier ;
* une architecture modulaire basée sur **FastAPI** ;
* des mécanismes de **fallback** pour limiter la dépendance aux services IA
  externes.

**Client :** ALTIORA Prest — Antananarivo, Madagascar

**Contexte :** Stage de Master Informatique — ENI Madagascar

---

## 🏗️ Pipeline Métier

Le projet suit un pipeline métier en **5 étapes + finalisation**, validé par
l'encadreur professionnel.

### 🔹 ÉTAPE 1 — DÉTECTION MARCHÉ + TDR

**Veille → Classification → Scoring → Génération TDR**

* **Modules :** M1, M2
* **Statut :** ✅ Développé

⬇️

### 🔹 ÉTAPE 2 — OFFRE TECHNIQUE + FINANCIÈRE

**Trame technique → Grille tarifaire → Export Word/PDF**

* **Module :** M3
* **Statut :** 🚧 En cours

⬇️

### 🔹 ÉTAPE 3 — PRÉPARATION DE LA FORMATION

**EDT → Formateur → Salle → Budget prévisionnel**

* **Module :** Préparation
* **Statut :** ❌ À développer

⬇️

### 🔹 ÉTAPE 4 — UPLOAD SUPPORTS + RAG

**Upload documents → Embeddings → Recherche sémantique**

* **Module :** C3 (RAG)
* **Statut :** ❌ À développer

⬇️

### 🔹 ÉTAPE 5 — PENDANT LA FORMATION

**Présences → Tests → Satisfaction → Attestations → Rapport**

* **Modules :** M5, M6
* **Statut :** ✅ Développé — **7 agents**

⬇️

### 🔹 ÉTAPE FINALE — FACTURATION + SUIVI DES PAIEMENTS

**Factures → Relances → Export comptable → Dashboard**

* **Modules :** M7, M8a
* **Statut :** 🟡 Partiel

---

### 📊 Vue synthétique

| Étape      | Fonction principale          | Module(s)   | Statut                 |
| ---------- | ---------------------------- | ----------- | ---------------------- |
| **1**      | Détection marché + TDR       | M1, M2      | ✅ Développé            |
| **2**      | Offre technique + financière | M3          | 🚧 En cours            |
| **3**      | Préparation de la formation  | Préparation | ❌ À développer         |
| **4**      | Supports + RAG               | C3          | ❌ À développer         |
| **5**      | Exécution de la formation    | M5, M6      | ✅ Développé — 7 agents |
| **Finale** | Facturation + paiements      | M7, M8a     | 🟡 Partiel             |

---

## 🤖 Les 7 Agents IA

Le module **M5 — Gestion des Formations** constitue l'un des principaux
modules intelligents du projet. Il coordonne plusieurs agents spécialisés
via un orchestrateur central.

| #     | Agent                    | Type                 | Fonction                                    | Criticité HITL |
| ----- | ------------------------ | -------------------- | ------------------------------------------- | -------------- |
| **1** | **FormGenerator**        | LLM                  | Génération de 4 formulaires Google Forms    | 🔴 Critical    |
| **2** | **LevelAnalyzer**        | Pandas + LLM         | Analyse des niveaux avant/après formation   | 🟡 Medium      |
| **3** | **SatisfactionAnalyzer** | Pandas + LLM         | Analyse de la satisfaction des participants | 🟡 Medium      |
| **4** | **PresenceAnalyzer**     | Python pur           | Détection des anomalies de présence         | 🔴 Critical    |
| **5** | **AttestationGenerator** | LLM + PDF            | Génération des attestations PDF             | 🔴 Critical    |
| **6** | **ReportGenerator**      | LLM + fallback       | Génération du rapport final de formation    | 🔴 Critical    |
| **7** | **KnowledgeBase (RAG)**  | LangChain + ChromaDB | Base vectorielle et recherche sémantique    | ⏳ À venir      |

> **Remarque :** le statut de chaque agent doit être interprété selon
> l'avancement réel du module correspondant. Le composant **KnowledgeBase
> (RAG)** est prévu pour une évolution ultérieure.

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
review_id
(ex. HITL-A1F-0001)
   ↓
Frontend
   ↓
/pending-reviews
   ↓
Révision humaine
   ├── APPROUVE → /reviews/{id}/approve
   │                 ↓
   │              Workflow continue
   │
   └── REJETTE → /reviews/{id}/reject
                     ↓
                  Feedback
                     ↓
                  Correction /
                  Régénération
```

### Modules soumis au HITL

| Module               | Agents / Fonction                                                      | Criticité   |
| -------------------- | ---------------------------------------------------------------------- | ----------- |
| **M3 — Offres**      | Offre technique, offre financière                                      | 🔴 Critical |
| **M4 — RH**          | Email candidat                                                         | 🔴 Critical |
| **M5 — Formations**  | FormGenerator, PresenceAnalyzer, AttestationGenerator, ReportGenerator | 🔴 Critical |
| **M5 — Formations**  | LevelAnalyzer, SatisfactionAnalyzer                                    | 🟡 Medium   |
| **M7 — Facturation** | Facture, relance                                                       | 🔴 Critical |

---

## 🔌 Provider Abstraction — LLM

L'architecture sépare strictement **la logique métier et l'orchestration**
du **fournisseur LLM**.

Cette abstraction permet de remplacer un fournisseur LLM sans modifier les
services métier qui utilisent l'intelligence artificielle.

```text
app/services/llm/
├── llm_provider.py          # Interface abstraite
├── groq_provider.py         # Implémentation Groq — actif
├── claude_provider.py       # Implémentation Claude — V3
└── llm_factory.py           # Sélection du provider via .env
```

Le fournisseur actif est sélectionné à partir de la configuration du projet.

---

## 🚀 Lancement

### Développement

Activer l'environnement virtuel :

```powershell
.\venv\Scripts\Activate.ps1
```

Puis démarrer le serveur FastAPI :

```powershell
python -m uvicorn app.main:app --reload
```

> **Note Windows :** l'utilisation de `python -m uvicorn` est recommandée
> si l'exécution directe de `uvicorn.exe` est bloquée par une stratégie de
> contrôle d'application.

Le serveur sera accessible à :

```text
http://localhost:8000
```

### 📚 Documentation interactive

**Swagger UI**

```text
http://localhost:8000/api/docs
```

**ReDoc**

```text
http://localhost:8000/api/redoc
```

**OpenAPI JSON**

```text
http://localhost:8000/api/openapi.json
```

---

## 🐳 Production — Docker

### Build

```bash
docker-compose build
```

### Démarrer les services

```bash
docker-compose up -d
```

### Consulter les logs

```bash
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
│   │   │   │   ├── document.py             # Génération documents
│   │   │   │   ├── facture.py              # Facturation — M7
│   │   │   │   ├── formation.py            # Sessions, participants
│   │   │   │   ├── formation_ia.py         # M5 — Routes IA
│   │   │   │   └── dashboard.py            # Statistiques
│   │   │   ├── routes_tdr.py               # M2 — Routes TDR
│   │   │   ├── routes_veille.py            # M1 — Routes veille
│   │   │   └── router.py                   # Agrégateur
│   │   │
│   │   ├── orchestrator/
│   │   │   ├── formation_orchestrator.py   # M5 — Orchestrateur IA
│   │   │   ├── tdr_orchestrator.py         # M2
│   │   │   └── veille_orchestrator.py      # M1
│   │   │
│   │   ├── services/
│   │   │   ├── llm/                        # Provider Abstraction
│   │   │   ├── hitl/                       # HITL générique
│   │   │   ├── formations/                 # M5 — Agents
│   │   │   ├── veille/                     # M1
│   │   │   ├── tdr/                        # M2
│   │   │   ├── offres/                     # M3 — à venir
│   │   │   ├── rh/                         # M4 — à venir
│   │   │   └── facturation/                # M7 — partiel
│   │   │
│   │   ├── schemas/                        # Pydantic schemas
│   │   ├── models/                         # SQLAlchemy models
│   │   ├── prompts/                        # Prompts RTFCE — YAML
│   │   │   ├── m1/                         # Veille
│   │   │   ├── m2/                         # TDR
│   │   │   ├── m3/                         # Offres — à venir
│   │   │   └── m5/                         # Formations
│   │   ├── templates/                      # Templates Word
│   │   │   ├── tdr/
│   │   │   ├── attestations/
│   │   │   └── rapports/
│   │   ├── core/                           # Configuration, sécurité
│   │   └── utils/                          # Helpers
│   │
│   ├── scripts/                            # Scripts utilitaires
│   ├── tests/                              # Tests pytest
│   ├── docs/                               # Documentation
│   ├── .env.example                        # Template de configuration
│   ├── .gitignore                          # Fichiers ignorés
│   ├── requirements.txt                    # Dépendances Python
│   └── README.md                           # Documentation du projet
│
├── venv/                                   # Environnement virtuel
├── docker-compose.yml                      # Orchestration Docker
└── ...
```

---

## 📊 Avancement Global

```text
████████████████████░░░░░░░░░░░░░░░░  ~55 %
```

### État actuel

| Domaine                      | Avancement     |
| ---------------------------- | -------------- |
| Détection marché + TDR       | ✅ Développé    |
| Offre technique + financière | 🚧 En cours    |
| Préparation formation        | ❌ À développer |
| Supports + RAG               | ❌ À développer |
| Gestion de la formation      | ✅ Développé    |
| Facturation + paiements      | 🟡 Partiel     |
| **Avancement global estimé** | **~55 %**      |

---

## 🔐 Principes d'architecture

FORMA-IA repose sur plusieurs principes structurants :

1. **Modularité** — séparation claire des domaines métier.
2. **Human-In-The-Loop** — validation humaine des productions IA critiques.
3. **Provider Abstraction** — indépendance vis-à-vis du fournisseur LLM.
4. **Fallback** — continuité de fonctionnement lorsque cela est possible
   sans dépendre exclusivement du LLM.
5. **Traçabilité** — suivi des générations, validations et workflows.
6. **API-first** — exposition des fonctionnalités métier via FastAPI.
7. **Évolutivité** — possibilité d'ajouter progressivement les modules
   M3, M4, C3/RAG, préparation et facturation.

---

## 📌 Statut du projet

**FORMA-IA est actuellement en phase de développement.**

Les modules **M1, M2 et M5** constituent le socle fonctionnel actuellement
développé. Les autres composants sont progressivement intégrés selon le
pipeline métier défini avec l'encadrement professionnel.

**Avancement global estimé : ~55 %.**
