# M3 — Offres techniques et financières

## À quoi ça sert

Génère une offre complète à envoyer à un client : une trame technique (méthodologie, programme, planning) et une trame financière (grille tarifaire, TVA, échéancier), à partir du TDR (M2) et des informations de session.

## Étapes d'utilisation

1. **Route principale — `POST /ia/offres/generer-complet`** : génère la trame technique ET financière en une seule fois, à partir de `tdr_data`, `session_info` et `options` (nombre de participants, type de formateur senior/junior, type de salle standard/premium, TVA applicable...). Crée automatiquement un review HITL global.
2. **Générations séparées** (si vous n'avez besoin que d'une partie) :
   - `POST /ia/offres/generer-technique` — trame technique seule.
   - `POST /ia/offres/generer-financiere` — trame financière seule (a besoin de l'offre technique déjà générée).
3. **Après génération** : la réponse indique `requires_human_action: true` avec un `review_id` — voir le [guide de validation HITL](08_validation_hitl.md) pour approuver ou rejeter.
4. **Si rejetée** : `POST /ia/offres/regenerer` avec le `review_id` et un `feedback` d'au moins 10 caractères expliquant ce qui doit changer.
5. **Une fois approuvée** : `POST /ia/offres/synchroniser` avec le `review_id` (du review **global**, pas d'un review individuel) pour enregistrer l'offre dans le Backend. Refusé (422) tant que le review n'est pas approuvé. Un seul envoi par review sauf `force: true` (qui crée alors un doublon côté Backend — à utiliser avec précaution).

## Ce qui nécessite une validation

**Validation HITL obligatoire.** Chaque génération (technique, financière, et le review global de l'offre complète) crée un review qui doit être approuvé avant que `/synchroniser` n'accepte d'envoyer l'offre au Backend.

## Erreurs fréquentes

- **`/synchroniser` renvoie 422** : le review n'est pas (encore) approuvé, ou ce n'est pas le review global (`agent_m3_complete`) mais un review individuel technique/financier.
- **`/regenerer` échoue en disant que les données d'entrée sont absentes** : ce cas concerne un review créé avant que la mémorisation des entrées (`_inputs`) n'existe — relancer `/generer-complet` à la place.
- **501 Not Implemented** : une fonctionnalité prévue mais non codée a été appelée.
