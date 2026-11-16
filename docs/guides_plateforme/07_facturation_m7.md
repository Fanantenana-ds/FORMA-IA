# Module M7 — Facturation et relances

## À quoi ça sert

Le module Facturation gère deux aspects financiers :
1. **Calcul des factures** : montant hors taxe (HT), TVA, remises, total TTC — calculé automatiquement à partir des données de la session.
2. **Relances clients** : génère automatiquement des courriers de relance pour les factures impayées, avec trois niveaux d'escalade selon le retard.

C'est l'outil utilisé par les assistants administratifs et les directeurs pour le suivi financier des formations.

## Comment utiliser la facturation

1. Ouvrez le module Facturation.
2. Sélectionnez la session concernée.
3. Les montants (HT, TVA, TTC) sont calculés automatiquement à partir des informations de la session.
4. Vérifiez et ajustez si nécessaire.

## Comment générer une relance client

1. Identifiez la facture impayée dans la liste.
2. Lancez la génération d'une lettre de relance.
3. Le système détermine automatiquement le niveau d'escalade selon le nombre de jours de retard :
   - **Niveau 1** : rappel courtois (retard de quelques jours)
   - **Niveau 2** : relance formelle (retard plus important)
   - **Niveau 3** : mise en demeure (retard prolongé)
4. L'IA rédige le texte de la lettre — un texte de secours est utilisé si le service IA est temporairement indisponible.
5. **Validation obligatoire** : toute lettre de relance doit être approuvée par un responsable avant envoi.

## Points importants

- La synchronisation des factures avec le Backend n'est pas encore disponible dans cette version — les factures sont gérées localement dans FORMA-IA pour l'instant.

## Si quelque chose ne fonctionne pas

- **Le calcul de la facture est incorrect** : vérifiez les informations de session (nombre de participants, tarif journalier, durée).
- **La génération de relance échoue** : le service IA est peut-être indisponible — un texte standard sera utilisé en remplacement.
- **La relance n'est pas envoyée** : vérifiez que la validation (review HITL) a bien été approuvée avant l'envoi.
