# Module M6 — Attestations de formation

## À quoi ça sert

Le module Attestations génère automatiquement les attestations de participation pour les participants éligibles d'une session de formation. Chaque attestation est créée en format PDF, prête à être remise ou envoyée.

L'éligibilité d'un participant est déterminée par l'analyse des présences (Agent 4 du module M5) : seuls les participants ayant atteint le seuil de présence requis reçoivent une attestation.

## Comment l'utiliser

1. **Assurez-vous que l'analyse des présences est validée** (Agent 4, module M5). C'est elle qui détermine qui est éligible.
2. **Lancez la génération des attestations** depuis le module Attestations ou depuis le module M5 (Agent 5).
3. **Validation obligatoire** : un responsable doit approuver les attestations générées avant que les PDF soient produits.
4. **Après approbation** : les PDF sont créés par le Backend et disponibles pour chaque participant éligible.

## Points importants

- Si aucun participant n'est éligible, la génération retourne une liste vide — c'est un résultat normal, pas une erreur.
- Les attestations ne sont pas générées pour les participants absents ou ayant un taux de présence insuffisant.

## Si quelque chose ne fonctionne pas

- **Aucune attestation générée** : vérifiez que l'analyse des présences est bien validée et que des participants ont été déclarés éligibles.
- **L'Agent 5 est indisponible** : consultez l'état des agents dans le module M5 et attendez que le service soit disponible.
- **Numéros d'attestation en doublon** : une attestation a peut-être déjà été générée pour cette session — vérifiez dans la liste des attestations existantes.
