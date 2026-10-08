# M7 — Facturation et relances

## À quoi ça sert

Calcule les montants d'une facture (HT, TVA, TTC, remise) et génère des courriers de relance pour les factures en retard, avec 3 niveaux d'escalade selon le nombre de jours de retard :
- **Niveau 1** — rappel courtois (dès l'échéance dépassée)
- **Niveau 2** — relance ferme (au-delà de 15 jours de retard)
- **Niveau 3** — mise en demeure formelle (au-delà de 45 jours de retard)

## Étapes d'utilisation

1. **Calculer les montants** (sans IA, Python pur) : `POST /ia/facturation/calculer-montants` avec `type_client`, `nb_participants`, `tarif_unitaire`, `tva_taux`, `remise_pct`.
2. **Générer une relance** : `POST /ia/facturation/relances/generer` avec `facture_id`. Le système :
   1. lit la facture dans le Backend,
   2. calcule le reste dû, les jours de retard et le niveau d'escalade,
   3. rédige le texte de la relance (IA, avec un modèle de secours en Python si le LLM échoue),
   4. crée un review HITL — **aucune relance n'est jamais envoyée sans validation humaine**.
   - **Si la facture est déjà soldée ou que l'échéance n'est pas dépassée**, la route répond `necessaire: false` avec la raison, sans appeler l'IA ni créer de review.
3. **Validation** : voir le [guide HITL](08_validation_hitl.md) — les relances apparaissent avec `agent_id = agent_m7_relance`.

## Ce qui nécessite une validation

**Validation HITL obligatoire** avant tout envoi d'une relance à un client (contenu à diffusion externe, criticité élevée).

**Limite actuelle importante : il n'existe pas de route `/synchroniser`.** Contrairement à M3/Préparation, le Backend n'a pas de route pour stocker ou envoyer une relance après son approbation — une fois validée, le texte doit être transmis au client par un autre moyen pour l'instant.

## Erreurs fréquentes

- **`necessaire: false` alors qu'une relance était attendue** : vérifier la date d'échéance et le statut de paiement de la facture dans le Backend.
- **404 sur `/relances/generer`** : la facture indiquée est introuvable côté Backend.
- **Relance générée mais aucun moyen de l'envoyer automatiquement** : normal, voir la limite ci-dessus.
