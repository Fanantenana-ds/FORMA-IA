
# 🎓 FORMA-IA

**Plateforme intelligente de gestion de la formation pour ALTIORA Solutions**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-API-orange)](https://groq.com)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

---

## 📖 Description

FORMA-IA est une plateforme qui automatise le cycle complet de la formation
professionnelle : de la détection d'opportunités (veille marché) jusqu'à
la génération du rapport final, en passant par la création des formulaires,
l'analyse des niveaux et la génération des attestations.

**Client** : ALTIORA Solutions (Antananarivo, Madagascar)
**Équipe** : 5 stagiaires Master ENI + 1 responsable IA

---

## 🏗️ Architecture modulaire

| Module            | Nom                    | Description                                             |
| ----------------- | ---------------------- | ------------------------------------------------------- |
| **M1**      | Veille Marché         | Détection d'opportunités (Tavily + Groq)              |
| **M2**      | TDR                    | Génération de Termes de Référence (Word + PDF)      |
| **M5**      | Gestion des Formations | 7 agents IA coordonnés (cœur du projet)               |
| **M6**      | Attestations           | Génération automatique des PDF                        |
| **Backend** | API REST               | Auth JWT, CRUD complet, sessions, participants,Dashbord |

---

## 🤖 M5 — Les 7 Agents IA

| # | Agent                          | Type           | Taches                                  |
| - | ------------------------------ | -------------- | --------------------------------------- |
| 1 | **FormGenerator**        | LLM            | Génère les 4 formulaires Google Forms |
| 2 | **LevelAnalyzer**        | Pandas + LLM   | Analyse niveaux avant/après            |
| 3 | **SatisfactionAnalyzer** | Pandas + LLM   | Analyse satisfaction                    |
| 4 | **PresenceAnalyzer**     | Python pur     | Détection anomalies présences         |
| 5 | **AttestationGenerator** | LLM + PDF      | Génère attestations PDF               |
| 6 | **ReportGenerator**      | LLM + fallback | Rapport final de formation              |
| 7 | **KnowledgeBase (RAG)**  | LangChain      | Base vectorielle (V2)                   |

---

## 🚀 Démarrage rapide

### 1. Prérequis

- Python 3.11+
- PostgreSQL 14+ (ou SQLite pour dev)
- Clé API Groq ([console.groq.com](https://console.groq.com))
- Clé API Tavily ([tavily.com](https://tavily.com))

### 2. Installation

```bash
# Cloner le repo
git clone <repository-url>
cd "FORMA IA"

# Créer l'environnement virtuel
python -m venv venv

# Activer
# Windows :
venv\Scripts\activate
# Linux/Mac :
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```
