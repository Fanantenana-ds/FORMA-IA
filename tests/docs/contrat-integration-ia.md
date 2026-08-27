# Contrat d'intégration — Module Analyse IA (FORMA-IA)

**Périmètre** : Backend (Olivier) livre l'auth, le CRUD, la persistance et les endpoints. L'IA (autre dev) implémente le résumé structuré, la classification du domaine et le scoring de pertinence.

ℹ️ Il existe deux routes d'analyse dans le code. Seule la route B (`/{opportunite_id}/analyse`) est le vrai point d'intégration de production. La route A (`/opportunites/analyse`) est une route de test/dev sans persistance — elle ne fait pas partie du périmètre d'intégration IA, mais reste documentée ci-dessous pour référence.

---

## Route de test — `OpportuniteAnalyseService.analyse()` (hors périmètre production)

Utilisée par la route **`POST /api/v1/opportunites/analyse`** (analyse d'un contenu brut, sans opportunité déjà en base) — usage test/dev uniquement.

**Fichier à modifier** : `app/services/opportunite_analyse_service.py`
**Interface à respecter** : `IOpportuniteAnalyseService` (`app/services/interfaces/iopportunite_analyse_service.py`)

### Signature exacte

```python
def analyse(self, contenu: str) -> OpportuniteAnalyseResult:
```

### Entrée

| Paramètre | Type | Détail |
|---|---|---|
| `contenu` | `str` | Texte brut de l'opportunité (TDR, email, etc.) ou URL convertie en string en amont par le endpoint |

### Sortie attendue — `OpportuniteAnalyseResult`

| Champ | Type | Contraintes |
|---|---|---|
| `objet` | `Optional[str]` | — |
| `budget` | `Optional[float]` | `>= 0` |
| `echeance` | `Optional[datetime]` | — |
| `domaine` | `Optional[Domaine]` | Enum : `DEVOPS`, `DEVELOPPEMENT`, `IA`, `DATA`, `BUREAUTIQUE`, `AUTRE` |
| `score_pertinente` | `float` | **Obligatoire**, `0.0 <= x <= 1.0` |

Actuellement, cette méthode retourne un résultat statique (`"Analyse temporaire"`, `score_pertinente=0.0`) — c'est le stub à remplacer.

Ce point d'intégration **n'écrit rien en base** — il retourne uniquement le résultat au endpoint, qui le renvoie tel quel au client. Aucune opportunité ni historique n'est créé ici.

---

## Point d'intégration réel — `AnalyseService.analyser()`

Utilisé par la route **`POST /api/v1/opportunites/{opportunite_id}/analyse`** (analyse d'une opportunité déjà existante en base).

**Fichier** : `app/services/analyse_service.py` (déjà implémenté côté backend — persistance)
**Ce que l'IA doit fournir en amont** : le dict `resultat_ia` passé en paramètre, actuellement codé en dur dans `app/api/v1/endpoints/analyse.py` :

```python
resultat_ia = {
    "objet": opportunite.objet or "Analyse temporaire",
    "budget": opportunite.budget,
    "echeance": opportunite.echeance,
    "domaine": opportunite.domaine,
    "score_pertinente": 0.0
}
```

### Ce que l'IA doit produire

Un `dict` (ou un objet convertible en dict) avec les clés suivantes, à substituer au bloc statique ci-dessus dans l'endpoint :

| Clé | Type | Contraintes |
|---|---|---|
| `objet` | `str` | Résumé structuré de l'opportunité |
| `budget` | `float \| None` | — |
| `echeance` | `datetime \| None` | — |
| `domaine` | `Domaine` (valeur de l'enum) | Une des 6 valeurs listées ci-dessus |
| `score_pertinente` | `float` | `0.0 <= x <= 1.0` |

### Ce que le backend garantit pour ce point B

- Persistance automatique dans `historique_analyses` (via `HistoriqueAnalyse`), avec `user_id` (utilisateur ayant déclenché l'analyse) et `date_analyse` (horodatage automatique) renseignés systématiquement
- Mise à jour du `statut` de l'opportunité à `ANALYSEE`
- Authentification déjà vérifiée en amont (`get_current_user`) — l'IA ne reçoit jamais de requête non authentifiée
- Toutes les colonnes de type date (`date_creation`, `date_analyse`, `echeance`) sont stockées en `TIMESTAMP WITH TIME ZONE`, en UTC — si l'IA fournit un `echeance`, un `datetime` conscient du fuseau (`tzinfo` renseigné) est recommandé pour éviter toute ambiguïté

---

## Enum `Domaine` (contrat de classification)

Valeurs autorisées, à respecter strictement (sinon erreur de validation SQLAlchemy/Pydantic) :

```
DEVOPS, DEVELOPPEMENT, IA, DATA, BUREAUTIQUE, AUTRE
```

---

## Points ouverts à trancher avant de démarrer l'intégration IA

1. **Faute de frappe cohérente mais à corriger un jour** : le champ s'appelle `score_pertinente` partout dans le code (modèles, schémas, service) — pas `score_pertinence`. À garder tel quel pour la cohérence tant que ce n'est pas renommé partout en même temps (migration Alembic incluse).
2. **Gestion des erreurs IA** : aucun contrat défini actuellement sur ce que l'IA doit faire en cas d'échec (contenu illisible, timeout de l'appel Claude/Tavily, etc.). À définir : lever une exception dédiée ? Retourner un `OpportuniteAnalyseResult` avec `score_pertinente=0.0` et `objet=None` ?

## Déjà couvert côté backend (mis à jour)

- ✅ `HistoriqueAnalyse` a maintenant `user_id` (nullable) et `date_analyse` (obligatoire, horodatage automatique)
- ✅ Migrations Alembic en place et appliquées : enums PostgreSQL corrigés (noms cohérents avec les modèles), valeur `BUREAUTIQUE` ajoutée à l'enum `domaine`, colonnes de date en `TIMESTAMP WITH TIME ZONE`
- ✅ Tests pytest couvrant l'authentification, les rôles (`require_role`) et le cas nominal de l'endpoint d'analyse de production
