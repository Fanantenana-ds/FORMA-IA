# Préparation (Budget + Emploi du temps)

## À quoi ça sert

Prépare le lancement opérationnel d'une formation déjà vendue (offre approuvée en M3) : calcule le budget prévisionnel (coût formateur, salle, supports — calcul Python pur, sans IA) et génère l'emploi du temps (avec l'IA).

## Étapes d'utilisation

1. **Route principale — `POST /ia/preparation/generer-complet`** : calcule le budget ET génère l'EDT en une fois, à partir de `offre_data` (issue de M3), `projet_info` (client, participants) et `ressources` (formateur, salle). Options : `date_debut`/`date_fin` (si absentes, des dates par défaut sont utilisées). Crée un review HITL.
2. **Calculs séparés** (si besoin) :
   - `POST /ia/preparation/calculer-budget` — budget seul (aucun appel IA, résultat immédiat).
   - `POST /ia/preparation/generer-edt` — EDT seul.
3. **Validation** : voir le [guide HITL](08_validation_hitl.md).
4. **Si rejetée** : `POST /ia/preparation/regenerer` avec `review_id` + `feedback` (10 caractères minimum).
5. **Une fois approuvée** : `POST /ia/preparation/synchroniser` — crée une session et une séance par jour d'EDT dans le Backend.

## Ce qui nécessite une validation

**Validation HITL obligatoire** avant `/synchroniser`, même principe que M3 : refusé (422) tant que le review n'est pas approuvé, un seul envoi par review sauf `force: true`.

**Important — le budget n'est PAS enregistré dans le Backend.** Seul l'EDT (session + séances) est synchronisé ; le budget calculé n'a pas de route de stockage côté Backend actuellement. La réponse de synchronisation le signale explicitement (`data.backend_sync.budget.skipped`).

## Erreurs fréquentes

- **`/synchroniser` renvoie 422** : review non approuvé.
- **Budget absent après synchronisation** : normal, voir ci-dessus — ce n'est pas une erreur, mais une limite actuelle du Backend.
- **Dates d'EDT incohérentes** : si `date_debut`/`date_fin` ne sont pas fournies, des dates par défaut à partir du 15/10/2026 sont utilisées — à vérifier avant validation.
