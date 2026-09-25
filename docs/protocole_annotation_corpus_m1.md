# Protocole d'annotation — Corpus de benchmark M1 (veille marché)

> **Objectif** : constituer un corpus annoté d'**au moins 100 documents**
> (exigence CDC §4) pour mesurer réellement la précision de classification
> de M1 (objectif > 85 %) et l'exactitude d'extraction des champs
> (objectif > 90 %).
>
> **Ce document ne contient aucune donnée annotée.** C'est un guide pour
> l'annotateur humain (vous). Claude Code ne doit jamais générer ni
> deviner une annotation à votre place — une donnée annotée inventée
> fausserait la mesure de précision qu'elle est censée garantir.

---

## 1. Où et comment écrire les annotations

Fichier : `data/corpus_veille/corpus_v1.jsonl`

Format : **JSON Lines** — une ligne = un objet JSON valide, encodage UTF-8,
pas de virgule finale, pas de saut de ligne à l'intérieur d'un objet.

État actuel (vérifié le 2026-09-26) : **14 documents** annotés (7 positifs
« is_opportunity: true », 7 négatifs). Il en manque au moins **86** pour
atteindre le seuil CDC de 100.

Pour ajouter une annotation : ouvrez le fichier dans un éditeur de texte,
ajoutez une nouvelle ligne à la fin (ne touchez pas aux lignes existantes),
puis validez avec `scripts/valider_corpus.py` (voir §4) avant de continuer.

---

## 2. Schéma d'un document annoté

```json
{
  "id": "corpus-00XX",
  "source_type": "texte | linkedin | site_web | pdf",
  "date_collected": "AAAA-MM-JJ",
  "annotator": "Votre nom",
  "raw_text": "Le texte brut exact tel qu'il serait collé dans le système (annonce, offre, article...).",
  "gold": {
    "is_opportunity": true,
    "domain": "ia | data | devops | developpement | bureautique | autre",
    "budget_expected": "Valeur EXACTE telle qu'elle apparaît dans le texte, ex. '5M Ar'",
    "deadline_expected": "AAAA-MM-JJ",
    "organizer_expected": "Nom de l'organisation telle qu'elle apparaît dans le texte"
  },
  "notes": "Pourquoi ce cas est intéressant, ce qui le rend facile ou difficile à classer."
}
```

### Règles précises par champ

- **`id`** : unique dans tout le fichier (le script de validation le
  vérifie). Convention actuelle : `corpus-0001`, `corpus-0002`, etc.
- **`raw_text`** : le texte **réel** tel qu'il apparaîtrait dans la
  source (annonce LinkedIn, page web, extrait de PDF...). Ne reformulez
  pas — le pipeline M1 sera testé sur ce texte exact.
- **`gold.is_opportunity`** : `true` uniquement si le texte décrit une
  **opportunité concrète et actionnable** pour ALTIORA (mission,
  formation à dispenser, appel d'offres, recrutement lié à l'IA/data/
  bureautique...). `false` pour tout le reste : article générique,
  actualité, offre hors sujet, page de listing.
- **`gold.domain`** — **OBLIGATOIRE si `is_opportunity: true`**, sinon
  omettre la clé entièrement (ne pas mettre `null`). La valeur doit être
  **exactement** l'une de : `ia`, `data`, `devops`, `developpement`,
  `bureautique`, `autre` — ce sont les seules valeurs que le classifieur
  peut produire (`app/services/veille/classification_service.py`,
  `DOMAIN_KEYWORDS`). Une autre valeur (ex. `"IA"` en majuscules, ou un
  domaine non listé) fausse silencieusement `domain_classification_accuracy`.
- **`gold.budget_expected` / `deadline_expected` / `organizer_expected`** :
  - Mettez la **valeur réelle** (recopiée du texte) si l'information est
    extractible, ou **`null`** si elle ne l'est pas — les deux sont
    strictement équivalents pour `benchmark_runner.py` (`dict.get()`
    renvoie `None` que la clé soit absente ou valant `null`), vérifié
    sur le corpus existant (ex. `corpus-0002`, `budget_expected: null`,
    annoté intentionnellement pour tester l'extraction partielle — voir
    ses `notes`). Omettre la clé fonctionne aussi, à votre convenance.
  - N'utilisez **jamais** une chaîne vide `""` ni un texte-placeholder
    comme `"Non précisé"` — ambigu, pourrait être confondu avec une
    vraie valeur extraite par un futur outil automatisé. Utilisez `null`.
  - `deadline_expected` : format `AAAA-MM-JJ` de préférence (permet une
    comparaison de date exacte plutôt qu'une comparaison de texte, voir
    `_dates_concordent` dans `benchmark_runner.py`).
  - `budget_expected` / `organizer_expected` : recopiez la formulation
    **exacte** du texte source (ex. `"5M Ar"`, pas `"5 000 000 Ariary"`
    si le texte dit `"5M Ar"`) — la comparaison est stricte, pas
    approximative (voir §1d de la mission précédente : une comparaison
    floue masquerait de vraies erreurs d'extraction).
- **`notes`** : libre, sert à expliquer pourquoi ce cas est dans le
  corpus (utile pour vous, pas lu par le code).

---

## 3. Composition recommandée du corpus (≥ 100 documents)

Pour que les métriques soient représentatives (pas seulement le total) :

| Catégorie | Recommandation |
| --- | --- |
| Équilibre positif/négatif | Viser 40-60 % de `is_opportunity: true` — un corpus à 95 % de négatifs rendrait la précision trompeuse (facile d'avoir 0 faux positif en ne détectant presque rien). |
| Couverture des domaines | Au moins quelques exemples de **chaque** domaine (`ia`, `data`, `devops`, `developpement`, `bureautique`) **et** de `autre` — le corpus actuel n'a **aucun** exemple `autre` positif. |
| Cas pièges déjà connus | Inclure des textes contenant des mots comme *matériaux*, *stabilité*, *redéveloppement* dans un contexte **hors sujet**, pour vérifier qu'ils ne déclenchent pas de faux positif (protection déjà en place, testée dans `tests/unit/test_classification_service.py`). |
| Pluriels | Inclure des formulations au pluriel (« outils bureautiques », « applications », etc. — corrigé en 1e) pour confirmer la détection. |
| Champs partiellement absents | Inclure des opportunités réelles où le budget ou l'échéance ne sont **pas** mentionnés (pour vérifier que rien n'est inventé à leur place). |
| Difficulté | Mélanger des cas évidents et des cas ambigus (ex. formation généraliste qui pourrait sembler une opportunité sans en être une). |

---

## 4. Validation après chaque lot d'annotations

```powershell
python scripts/valider_corpus.py
```

Le script (lecture seule, décrit en détail dans son en-tête) vérifie la
structure de **chaque** ligne (JSON valide, champs requis, domaines
reconnus, dates au bon format, identifiants uniques) et affiche un
résumé de couverture (total, équilibre positif/négatif, répartition par
domaine). Il ne modifie et n'invente jamais rien — c'est un contrôle,
pas une génération.

Une fois le corpus validé et étoffé, relancer le benchmark réel :

```powershell
python -c "import asyncio; from app.services.benchmark.benchmark_runner import BenchmarkRunner; print(asyncio.run(BenchmarkRunner().run(limit=120)))"
```

Ou via la route existante `POST /api/v1/benchmark` (`app/api/v1/routes_veille.py:178-179`,
paramètre `limit`, **plafonné à 100 par la route** — utiliser l'appel
Python direct ci-dessus si le corpus dépasse 100 documents). Avec
≥ 100 documents, le rapport n'est plus « indicatif » (voir
l'avertissement déjà présent dans `benchmark_runner.py`) mais devient la
mesure de recette exigée par le CDC.

---

## 5. Ce que Claude Code ne fera jamais dans ce processus

- Écrire une ligne dans `corpus_v1.jsonl` à votre place.
- Deviner un `budget_expected` / `deadline_expected` / `organizer_expected`
  qui ne serait pas visible dans le `raw_text` fourni.
- Modifier une annotation existante sans vous le signaler explicitement.
- Considérer le corpus « suffisant » avant d'avoir vérifié réellement
  le nombre de lignes et leur validité structurelle.
