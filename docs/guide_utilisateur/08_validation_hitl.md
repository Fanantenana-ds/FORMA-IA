# Validation humaine (HITL — Human-in-the-Loop)

## À quoi ça sert

Avant qu'un contenu généré par l'IA ne soit diffusé à l'extérieur (client, organisme) ou enregistré définitivement, un être humain doit le relire et l'approuver ou le rejeter. C'est un mécanisme **transversal**, partagé par tous les modules qui produisent ce type de contenu : M3 (offres), Préparation (EDT/budget), M5 (les 6 agents), M7 (relances).

Chaque contenu en attente est appelé un **review**, identifié par un `review_id` et rattaché à un `agent_id` qui indique quel module/agent l'a produit (ex. `agent_m3_complete`, `agent_2_levels`, `agent_m7_relance`...).

## Étapes d'utilisation

Toutes les routes HITL sont regroupées sous `/ia/formations/...`, même si le contenu provient d'un autre module (M3, Préparation, M7) — il suffit de filtrer par `agent_id`.

1. **Voir ce qui est en attente** : `GET /ia/formations/pending-reviews`, avec filtres optionnels `agent_id` et `criticity`.
2. **Voir les statistiques globales** : `GET /ia/formations/reviews/stats` (nombre en attente, approuvés, rejetés).
3. **Consulter le détail d'un contenu précis** : `GET /ia/formations/reviews/{review_id}`.
4. **Approuver** : `POST /ia/formations/reviews/{review_id}/approve`, avec une note optionnelle (`reviewer_note`).
5. **Rejeter** : `POST /ia/formations/reviews/{review_id}/reject`, avec un `reason` obligatoire (3 caractères minimum) — le module d'origine propose alors généralement une route `/regenerer` pour reprendre en tenant compte du motif de rejet.

## Criticité

Chaque review porte un niveau de criticité :
- **critical** — validation obligatoire (ex. contenu adressé directement à un client : relance de facture, offre complète).
- **medium** — validation recommandée.
- **low** — validation optionnelle.

Le niveau exact appliqué dépend de l'agent qui a créé le review — se référer au détail du review (`GET /reviews/{id}`) plutôt qu'à une règle générale, car il peut varier d'un agent à l'autre.

## Ce qui nécessite une validation

Par construction, **tout ce qui apparaît dans `/pending-reviews` nécessite une décision** (approuver ou rejeter) avant que le module d'origine n'autorise l'étape suivante (téléchargement définitif, envoi au Backend, envoi au client selon le module).

## Erreurs fréquentes

- **404 sur `/reviews/{id}`, `/approve` ou `/reject`** : le `review_id` n'existe pas (vérifier qu'il a bien été copié depuis la réponse de génération).
- **Un module refuse de continuer (422) après approbation** : vérifier que c'est bien le **bon** review qui a été approuvé — certains modules (M3) ont un review global ET des reviews individuels par agent ; seul le review global compte pour la synchronisation.
- **Rejet sans motif suffisant** : le champ `reason` doit faire au moins 3 caractères.
