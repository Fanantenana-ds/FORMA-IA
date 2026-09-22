
```markdown
# FORMA-IA — CLAUDE.md

> **Document de référence pour Claude Code**
>
> **Version de référence : 21 septembre 2026**
>
> Ces règles sont obligatoires.
>
> Principe général :
>
> **Analyser avant de modifier. Ne pas casser ce qui fonctionne. Modifier uniquement ce qui est nécessaire.**
>
> Le projet est réalisé dans le cadre d'un stage de Master. Le développeur concerné intervient comme **Responsable IA & Data**. Le respect du périmètre et la coordination avec le Backend sont obligatoires.

---

# 1. Contexte du projet

Projet : **FORMA-IA**

Client : **ALTIORA PREST** — Antananarivo, Madagascar

FORMA-IA est une plateforme intelligente de gestion de la formation comprenant notamment :

* une veille marché (détection d'opportunités) ;
* une génération assistée de Termes de Référence (TDR) ;
* une génération d'offres techniques et financières ;
* un module de préparation de formation (budget + emploi du temps)  ;
* une gestion complète des sessions de formation (M5);
* un système d'attestations PDF (M6) ;
* une facturation avec relances (M7) ;
* un système RAG documentaire (C3) ;
* un module RH (M4 — bonus).

Le présent fichier définit les règles de travail de **Claude Code** dans ce projet.

Le pipeline métier officiel est :

```text
Étape 1 — Détection marché + TDR        (M1 + M2)
   ↓
Étape 2 — Offre technique + financière  (M3)
   ↓
Étape 3 — Préparation                    (Budget + EDT)
   ↓
Étape 4 — Upload supports + RAG          (C3)
   ↓
Étape 5 — Pendant la formation           (M5 + M6)
   ↓
Finale  — Facturation + Dashboard        (M7 + M8a)
```

Le projet doit progresser de manière incrémentale.

Il ne faut pas ajouter de complexité uniquement parce qu'une architecture plus complexe serait possible.

---

# 2. Rôle du développeur

Le développeur concerné travaille comme :

> **Responsable IA & Data**

Le périmètre principal est le **module IA** (agents, prompts, orchestrateurs, routes IA, sync Backend, HITL, RAG).

## Responsabilités IA

Le périmètre comprend principalement :

* orchestrateurs par module (Veille, TDR, Offre, Préparation, Formation, Facturation, RAG) ;
* agents unitaires (Provider Abstraction Groq/Claude) ;
* prompts RTFCE externalisés en YAML ;
* schémas Pydantic des sorties IA ;
* routes FastAPI `/ia/*` ;
* services de synchronisation IA → Backend (`backend_sync/`) ;
* HITL généralisé ;
* Agent RAG (C3) ;
* benchmarks et tests IA ;
* documentation technique du module IA.

## Hors périmètre

Ne pas prendre spontanément en charge :

* frontend (React — autre stagiaire) ;
* développement Backend général (CRUD, models SQLAlchemy, migrations Alembic) ;
* authentification JWT ;
* DevOps / CI/CD / Docker de production ;
* infrastructure générale ;
* fonctionnalités métier sans rapport direct avec le module IA.

Une modification hors périmètre nécessite une autorisation explicite du binôme Backend.

---

# 3. Principe fondamental : analyser avant de modifier

Avant toute modification :

1. lire `CLAUDE.md` ;
2. vérifier l'état Git (`git status`) ;
3. lire le code existant ;
4. lire les tests concernés ;
5. comprendre les dépendances (Backend, DB, autres modules) ;
6. identifier précisément le problème ;
7. proposer une correction minimale ;
8. modifier uniquement les fichiers autorisés ;
9. exécuter les tests nécessaires ;
10. vérifier le `git diff` ;
11. vérifier le `git status`.

Ne jamais :

* réécrire un agent fonctionnel sans raison ;
* faire une refonte générale pour corriger un petit problème ;
* supprimer du code simplement parce qu'il semble inutilisé ;
* supposer qu'une fonctionnalité existe parce qu'un fichier existe ;
* considérer un fichier vide comme une fonctionnalité implémentée ;
* modifier plusieurs couches lorsqu'une correction locale suffit ;
* modifier le Backend pour faciliter rapidement le développement IA.

Principe :

> **Modification minimale, compréhension maximale.**

---

# 4. Architecture IA de référence

```text
                      FORMA-IA
                         │
                         ▼
              ┌──────────┴──────────┐
              │                     │
         PIPELINE MÉTIER       PROVIDER ABSTRACTION
              │                     │
    ┌─────────┼─────────┐      ┌────┴────┐
    │         │         │      │         │
  M1/M2     M3      Prépa   Groq      Claude
  (Veille)  (Off.)  (EDT)   (dev)    (prod)
    │         │         │      │         │
  M5/M6     M7       C3/RAG   │         │
  (Form.)  (Fact.)   (RAG)     │         │
    │         │         │      │         │
    └─────────┴─────────┴──────┴─────────┘
                    │
                    ▼
            backend_sync/  (IA → Backend)
                    │
                    ▼
             Backend FastAPI
                    │
                    ▼
              PostgreSQL
```

Point de connexion avec le Backend :

```text
app/api/v1/endpoints/         ← Routes IA (FastAPI)
        │
        ▼
app/orchestrator/             ← Orchestrateurs M1..M7
        │
        ▼
app/services/                 ← Agents IA + services
        │
        ├── llm/              ← Provider Abstraction
        ├── backend_sync/     ← Sync IA → Backend
        └── hitl/             ← Human-in-the-Loop
```

Le branchement réel entre l'IA et le Backend doit toujours être vérifié dans le code réel.

Ne pas considérer l'architecture cible comme la preuve que le branchement est effectivement terminé.

---

# 5. Stack technique — décision définitive

```text
Langage       : Python 3.11+
Framework     : FastAPI
LLM (dev)     : Groq API — openai/gpt-oss-20b
LLM (prod)    : Claude API (préparé, non actif)
DB            : PostgreSQL
Documents     : docxtpl + reportlab
Recherche web : Tavily
Frontend      : React (autre stagiaire — hors périmètre IA)
```

Ne pas remplacer Groq par un autre provider LLM sans autorisation explicite.

---

# 6. Provider Abstraction

Principe : séparer strictement l'orchestration métier (agents + prompts RTFCE) du fournisseur LLM effectivement appelé.

```text
app/services/llm/
├── llm_provider.py       ← interface abstraite
├── groq_provider.py      ← implémentation active
├── claude_provider.py    ← implémentation future
└── llm_factory.py        ← sélection via .env
```

Configuration `.env` :

```text
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-20b
ANTHROPIC_API_KEY=...          (préparé)
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

Migration Groq → Claude : ne doit pas nécessiter de modification de la logique métier des agents.

---

# 7. Structure du module IA

```text
app/
├── api/v1/endpoints/
│   ├── formation_ia.py         ← Routes M5
│   ├── offre_ia.py             ← Routes M3
│   ├── preparation_ia.py       ← Routes Préparation
│   └── facture_ia.py           ← Routes M7 (à créer)
│
├── orchestrator/
│   ├── veille_orchestrator.py
│   ├── tdr_orchestrator.py
│   ├── offre_orchestrator.py
│   ├── preparation_orchestrator.py
│   ├── formation_orchestrator.py
│   └── facturation_orchestrator.py  ← à créer
│
├── services/
│   ├── veille/                 ← M1
│   ├── tdr/                    ← M2
│   ├── offres/                 ← M3
│   ├── preparation/            ← Préparation
│   ├── formations/             ← M5 + M6 (6 agents)
│   ├── backend_sync/           ← Sync IA → Backend
│   ├── hitl/                   ← HITL générique
│   └── llm/                    ← Provider Abstraction
│

├── prompts/
│   ├── m1/                     ← veille, classification, scoring
│   ├── m2/                     ← tdr
│   ├── m3/                     ← offre_technique, offre_financiere
│   ├── m5/                     ← form, level, satisfaction, attestation, report
│   ├── m_prep/                 ← edt_generation
│   └── m7/                     ← relance (à créer)
│
├── schemas/
│   ├── formation_ia.py
│   ├── offre_ia.py
│   ├── preparation_ia.py
│   └── facture_ia.py           ← à créer
│
└── templates/
    ├── attestations/template_attestation.docx
    └── tdr/template_tdr_formation.docx
```

L'existence d'un dossier ou d'un fichier ne signifie pas automatiquement que la fonctionnalité correspondante est terminée.

---

# 8. Modules CDC (MoSCoW V2.0)

| Réf | Module                           | Étape     | Priorité | Statut |
| ---- | -------------------------------- | ---------- | --------- | ------ |
| M1   | Veille marché                   | 1          | MUST      | ✅     |
| M2   | Génération TDR                 | 1          | MUST      | ✅     |
| M3   | Offres (technique + financière) | 2          | MUST      | 🟢     |
| —   | Préparation (EDT, budget)       | 3          | MUST      | 🟢     |
| C3   | RAG / catalogue documentaire     | 4          | SHOULD    | ⏳     |
| M5   | Gestion formations (6 agents)    | 5          | MUST      | ✅     |
| M6   | Attestations                     | 5          | MUST      | ✅     |
| M7   | Facturation + relances           | Finale     | MUST      | 🟡     |
| M8a  | Dashboard                        | Finale     | MUST      | ⏳     |
| M4   | Assistance RH (bonus)            | Transverse | COULD     | ⏳     |

Ne pas considérer un module « terminé » sans test réel et sans validation.

---

# 9. Agents IA — 6 agents du M5

Le M5 est le cœur du projet selon l'encadreur.

| Agent | Nom                       | Rôle                      | Techno             |
| ----- | ------------------------- | -------------------------- | ------------------ |
| 1     | FormGeneratorAgent        | 4 formulaires Google Forms | Groq direct        |
| 2     | LevelAnalyzerAgent        | Niveaux avant/après       | Groq + pandas      |
| 3     | SatisfactionAnalyzerAgent | Analyse satisfaction       | Groq + pandas      |
| 4     | PresenceAnalyzerAgent     | Anomalies présences       | Python pur         |
| 5     | AttestationGeneratorAgent | Attestations PDF           | Python + reportlab |
| 6     | ReportGeneratorAgent      | Rapport final              | Groq + reportlab   |

Chaque agent suit le pattern :

```text
app/prompts/m5/{agent}.yaml    (prompt RTFCE)
        +
app/services/formations/{agent}_service.py   (1 classe)
        ↓
app/orchestrator/formation_orchestrator.py    (coordination)
        ↓
app/api/v1/endpoints/formation_ia.py           (routes)
```

Ne pas modifier un agent fonctionnel sans problème démontré par un test.

---

# 10. Prompts RTFCE

Le projet utilise une approche de prompt engineering :

> **RTFCE** — Rôle, Tâche, Format, Contexte, Exemples

Les prompts sont externalisés en YAML dans `app/prompts/`.

Toute évolution doit préserver les éléments :

* rôle ;
* tâche ;
* format ;
* contexte ;
* contraintes (règles) ;
* exemples.

Ne pas modifier un prompt uniquement pour obtenir ponctuellement une réponse différente.

---

# 11. Sync IA → Backend

Le module IA produit du JSON. Le Backend persiste en DB.

Flux :

```text
IA (orchestrateur)
     ↓
backend_sync/*.py
     ↓
POST /api/v1/{ressource}
     ↓
Backend FastAPI
     ↓
PostgreSQL
```

Services existants :

```text
app/services/backend_sync/
├── base_sync.py                  ← Auth + HTTP + verify
├── formation_sync.py             ← M5
├── offre_sync.py                 ← M3
├── preparation_sync.py           ← Préparation
├── facture_sync.py               ← M7
├── facture_calculator_service.py ← Calculs Python purs
├── opportunity_sync.py           ← M1
├── opportunity_fetcher.py
└── tdr_sync.py                   ← M2
```

Règles :

* authentification gérée dans `base_sync.py` (login + re-login sur 401) ;
* UUID (str) pour les IDs Backend, pas int ;
* vérification GET après POST (couche 2) ;
* skip gracieux si endpoint absent (404) ;
* ne pas modifier le contrat Backend sans autorisation.

---

# 12. HITL (Human-in-the-Loop)

Le HITL est généralisé à tous les modules produisant un contenu à diffusion externe.

```text
app/services/hitl/hitl_helper.py
```

Fonctions :

* `create_review(agent_id, data, summary, criticity)` ;
* `list_pending(agent_id, criticity)` ;
* `get_review(review_id)` ;
* `approve_review(review_id, reviewer_note)` ;
* `reject_review(review_id, reason)` ;
* `get_stats()`.

Routes :

```text
GET    /ia/formations/pending-reviews
GET    /ia/formations/reviews/stats
GET    /ia/formations/reviews/{id}
POST   /ia/formations/reviews/{id}/approve
POST   /ia/formations/reviews/{id}/reject
```

Criticité :

```text
critical → validation obligatoire
medium   → validation recommandée
low      → validation optionnelle
```

Ne pas supprimer ni modifier `hitl_helper.py` sans problème démontré.

---

# 13. Frontière Backend ↔ IA

```text
app/
├── api/v1/         ← Routes IA (périmètre partagé)
├── orchestrator/   ← Orchestrateurs IA (périmètre IA)
├── services/
│   ├── backend_sync/  ← Sync (périmètre IA)
│   └── hitl/          ← HITL (périmètre IA)
├── models/         ← Backend (NE PAS MODIFIER)
├── db/             ← Backend (NE PAS MODIFIER)
├── core/           ← Backend (NE PAS MODIFIER)
└── main.py
```

Le périmètre principal du Dev IA est :

```text
app/orchestrator/           ← périmètre IA
app/services/{m1,m2,m3,formations,offres,preparation,backend_sync,hitl,llm}/
app/prompts/
app/schemas/*_ia.py
app/api/v1/endpoints/*_ia.py
```

---

# 14. Protection du Backend

Claude Code peut :

* lire les modèles Backend ;
* lire les migrations Alembic ;
* lire les tests Backend ;
* analyser les champs, relations, dépendances ;
* identifier une incompatibilité ;
* proposer une modification.

Mais Claude Code ne doit pas modifier spontanément :

* les modèles SQLAlchemy (`app/models/`) ;
* les migrations Alembic ;
* les colonnes DB ;
* les contraintes DB ;
* les relations DB ;
* les enums Backend ;
* les schémas Pydantic Backend (`app/schemas/*.py` sauf `*_ia.py`) ;
* les routes Backend (`app/api/v1/endpoints/*.py` sauf `*_ia.py`).

Si une correction IA nécessite une modification Backend :

> **STOP → identifier la dépendance → expliquer le besoin → demander l'autorisation.**

---

# 15. Contrat API Backend

Les endpoints Backend sont hors du périmètre IA sauf autorisation explicite.

Ne pas modifier sans autorisation :

* méthode HTTP ;
* URL ;
* paramètres ;
* payload ;
* réponse ;
* statuts HTTP ;
* authentification ;
* contrat multipart ;
* validation Backend.

Le module IA doit s'intégrer au contrat Backend existant.

Il ne faut pas modifier le contrat Backend simplement pour faciliter le développement IA.

---

# 16. Tests — règle générale

Toute modification fonctionnelle doit :

1. identifier les tests existants ;
2. conserver les tests existants ;
3. ajouter les tests nécessaires ;
4. exécuter les tests pertinents ;
5. exécuter la suite complète lorsque nécessaire ;
6. vérifier la couverture ;
7. vérifier les régressions.

Ne pas supprimer un test simplement parce qu'il bloque une modification.

Si un test doit être modifié, expliquer pourquoi.

---

# 17. Environnement local — pytest / coverage / ruff

Les outils suivants sont installés dans le `venv` local Windows :

```text
pytest
coverage
ruff
```

Ils se trouvent dans :

```text
venv/
```

Le développeur les utilise déjà localement.

**Ne pas les réinstaller.**

Ne jamais exécuter spontanément :

```powershell
pip install pytest
pip install coverage
pip install ruff
pip install -r ...
```

Commandes locales de référence :

```powershell
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report
ruff check .
```

Utiliser le `venv` existant.


---

# 22. Secrets

Ne jamais mettre dans le code :

* `GROQ_API_KEY` ;
* `TAVILY_API_KEY` ;
* `ANTHROPIC_API_KEY` ;
* `BACKEND_SYNC_TOKEN` ;
* `ADMIN_PASSWORD` ;
* mot de passe DB ;
* JWT secret ;
* token ;
* credential.

Utiliser les variables d'environnement (`.env`).

Ne jamais afficher une clé secrète dans un rapport.

Ne jamais recopier une valeur secrète dans logs, commits, tests, documentation, ou `CLAUDE.md`.

---

# 23. Git

Avant toute modification :

```powershell
git status
```

Ne jamais :

```powershell
git reset --hard
git clean -fd
git push --force
```

sans autorisation explicite.

Ne jamais supprimer les modifications d'un autre développeur.

---

# 24. Commits

Claude Code ne doit pas créer automatiquement de commit.

Un commit nécessite une demande explicite de l'utilisateur.

Pendant une mission d'audit :

```text
aucun commit
```

Pendant une mission de correction :

```text
aucun commit
```

sauf demande explicite.

---

# 25. Mission d'audit

Lorsqu'une mission est explicitement appelée **AUDIT**, elle est strictement en lecture seule.

Interdictions :

* aucune modification ;
* aucun fichier créé ;
* aucun fichier supprimé ;
* aucune migration ;
* aucune modification DB ;
* aucun commit ;
* aucun push ;
* aucune installation ;
* aucun build ;
* aucun pull ;
* aucun démarrage automatique de Docker Desktop.

L'audit doit décrire l'état réel du projet.

Il doit distinguer :

```text
Terminé
Fonctionnel
Partiel
Squelette
Bloqué
Non testé
```

---

# 26. État de référence connu

État connu à vérifier contre le code réel :

```text
Provider Abstraction         ✅
HITL générique               ✅
M1 — Veille                  ✅
M2 — TDR                     ✅
M3 — Offres                  🟢
Préparation (Budget + EDT)   🟢
M5 — Formations (6 agents)   ✅
M6 — Attestations            ✅
M7 — Relances                🟡
C3 — RAG                     ⏳
M4 — RH                      ⏳
backend_sync/                ✅
```

Cette liste ne remplace pas l'analyse du code réel.

---

# 27. Anti-régression — Composants stabilisés

Les composants suivants sont stabilisés et ne doivent pas être modifiés sans problème concret :

* `app/services/formations/*` (6 agents du M5) ;
* `app/services/hitl/hitl_helper.py` ;
* `app/services/backend_sync/base_sync.py` ;
* `app/orchestrator/formation_orchestrator.py` ;
* `app/prompts/m5/*.yaml` ;
* `app/schemas/formation_ia.py`.

Toute modification doit d'abord expliquer :

```text
Quel nouveau problème justifie la modification ?
```

---

# 28. Procédure pour une nouvelle tâche

## Étape 1 — Comprendre

Lire :

* `CLAUDE.md` ;
* code concerné ;
* tests concernés ;
* dépendances.

## Étape 2 — Vérifier

Identifier :

* état réel ;
* comportement actuel ;
* problème exact.

## Étape 3 — Planifier

Avant modification importante, indiquer :

* fichiers à modifier ;
* classes/fonctions ;
* tests ;
* risques ;
* dépendances Backend.

## Étape 4 — Modifier

Modifier uniquement les fichiers autorisés.

## Étape 5 — Tester

Utiliser le `venv` local pour pytest / coverage / ruff.

Utiliser Docker uniquement lorsque l'intégration conteneurisée est réellement nécessaire.

## Étape 6 — Vérifier

Contrôler :

```text
tests
coverage
régressions
git diff
git status
```

## Étape 7 — Rapport

Indiquer :

* modifications ;
* tests exécutés ;
* résultats ;
* couverture ;
* problèmes restants ;
* dépendances Backend ;
* prochaines étapes.

---

# 29. Lorsqu'une modification Backend est nécessaire

Si une tâche IA semble nécessiter une modification de :

```text
app/models/
app/db/
app/core/
app/api/v1/endpoints/ (hors *_ia.py)
```

ne pas modifier automatiquement.

Présenter :

```text
Fichier concerné :
Fonction / classe :
Problème :
Comportement actuel :
Pourquoi la modification est nécessaire :
Impact :
Correction proposée :
Tests nécessaires :
```

Puis demander l'autorisation au binôme Backend.

---

# 30. Format de rapport d'audit

Pour chaque problème important :

```text
Fichier :
Fonction / classe :
Comportement actuel :
Problème constaté :
Impact :
Preuve / test :
Correction minimale proposée :
Dépendance backend :
Priorité :
```

Distinguer clairement :

```text
Fait constaté
Hypothèse
Risque
Dépendance externe
```

Ne pas transformer une hypothèse en fait.

---

# 31. Rapport attendu après une modification

Après toute correction, Claude Code doit fournir :

```text
1. Ce qui a été modifié
2. Pourquoi
3. Fichiers modifiés
4. Tests ajoutés/modifiés
5. Tests exécutés
6. Résultat des tests
7. Résultat Ruff
8. Couverture si exécutée
9. Git diff résumé
10. Git status
11. Dépendances Backend
12. Risques restants
13. Prochaine étape recommandée
```

Ne pas présenter comme terminé un élément qui n'a pas été vérifié.

---

# 32. Pas de suppositions sur l'état du projet

Claude Code doit toujours distinguer :

```text
Le fichier existe
```

de :

```text
La fonctionnalité fonctionne
```

et :

```text
La fonctionnalité est utilisée en production
```

Exemple :

```text
formation_ia.py existe
```

ne signifie pas automatiquement :

```text
Les routes /ia/formations sont branchées et testées
```

Exemple :

```text
backend_sync/formation_sync.py existe
```

ne signifie pas :

```text
Le Backend reçoit réellement les données du M5
```

Toujours vérifier.

---

# 33. Principes de documentation

Les rapports doivent être :

```text
factuels
courts lorsque possible
précis
vérifiables
```

Éviter :

* formulations vagues ;
* affirmations sans preuve ;
* « probablement » présenté comme un fait ;
* chiffres inventés ;
* tests non exécutés présentés comme passés.

Utiliser explicitement :

```text
Fait constaté :
Hypothèse :
Risque :
Dépendance :
```

lorsque nécessaire.

---

# 34. Priorités actuelles

À la date de cette version :

### Priorité 1

Finaliser les modules **MUST HAVE** restants :

```text
M7 — Relances (prompt + service + orchestrateur + routes)
```

### Priorité 2

Vérifier le **sync Backend** pour M3 et Préparation.

### Priorité 3

Audit **routes IA ↔ Backend** (si applicable).

### Priorité 4

Implémenter **C3 — RAG** (LangChain + ChromaDB ou pgvector).

### Priorité 5

**M4 — RH** (bonus).

Ces priorités peuvent changer si une régression ou un blocage critique est découvert.

---

# 35. Principe de séparation des responsabilités

Le système doit conserver cette séparation :

```text
Frontend (React)
   ↓
Backend API (FastAPI)
   ↓
Routes IA (/ia/*)
   ↓
Orchestrateur
   ↓
Agents IA
   ↓
backend_sync
   ↓
Backend (persistance)
   ↓
PostgreSQL
```

Le Dev IA ne doit pas contourner les couches.

Exemple interdit :

```text
IA écrit directement dans la DB
```

La bonne méthode est :

```text
identifier → documenter → coordonner → modifier avec autorisation → tester
```

---

# 36. Principe de prudence avec les données

Les données de la base peuvent être des données métier.

Toujours privilégier :

```text
lecture seule
```

pour les diagnostics.

Avant toute écriture :

```text
Quel est l'objectif ?
Quelles données sont touchées ?
Est-ce réversible ?
Est-ce nécessaire ?
Est-ce autorisé ?
```

En cas de doute :

> ne pas écrire.

---

# 37. Principe de prudence avec les dépendances externes

Les services externes comprennent notamment :

```text
Groq API
Tavily
Google Forms/Sheets/Drive
SMTP
Claude API (future)
```

Toute opération pouvant générer coût, quota, latence ou consommation réseau doit être volontaire.

Pour les tests : `mock` lorsque le test porte sur l'orchestration.

Utiliser le service réel lorsque la validation réelle du fournisseur est nécessaire.

---

# 38. Principe de traçabilité

Toute correction importante doit pouvoir être expliquée simplement :

```text
Problème
   ↓
Preuve
   ↓
Cause
   ↓
Correction
   ↓
Test
   ↓
Résultat
```

Éviter les corrections dont la raison ne peut pas être expliquée.

---

# 39. Règle sur les performances

Ne pas optimiser prématurément.

Avant d'optimiser :

1. identifier le coût réel ;
2. mesurer lorsque possible ;
3. déterminer si le coût est significatif ;
4. proposer une optimisation ciblée.

Les appels LLM sont la principale source de latence.

---

# 40. Principe directeur

Le développement du module IA doit rester :

```text
Propre
Progressif
Testé
Maintenable
Compatible avec le Backend
Économe en ressources
Traçable
```

La priorité n'est pas de produire rapidement beaucoup de code.

La priorité est de :

> **stabiliser progressivement un pipeline métier fiable, testable et maintenable, sans casser les composants existants ni dépasser le périmètre IA.**

Le développement doit suivre cette logique :

```text
ANALYSER
   ↓
PROUVER
   ↓
PLANIFIER
   ↓
MODIFIER LE MINIMUM avec une demande d'accord
   ↓
TESTER
   ↓
VÉRIFIER
   ↓
DOCUMENTER
```

Et lorsqu'une dépendance Backend est nécessaire :

```text
IDENTIFIER
   ↓
DOCUMENTER
   ↓
COORDONNER AVEC BACKEND
   ↓
ATTENDRE L'AUTORISATION
   ↓
INTÉGRER
   ↓
TESTER
```

**Ne jamais confondre vitesse de développement et progression réelle du projet.**
