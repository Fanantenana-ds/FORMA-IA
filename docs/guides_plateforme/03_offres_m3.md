# Module M3 — Offres commerciales

## À quoi ça sert

Le module Offres commerciales génère automatiquement une offre technique et financière complète à partir du TDR et des informations de session. Il produit deux parties :
- L'offre **technique** : programme, objectifs, méthodologie, profil du formateur.
- L'offre **financière** : budget détaillé, tarifs, conditions.

C'est l'outil utilisé par les chargés d'offres et les directeurs pour préparer rapidement des propositions professionnelles destinées aux clients.

## Comment l'utiliser

1. **Préparez le TDR** : l'offre se construit à partir d'un TDR validé (module M2). Assurez-vous qu'il est disponible.
2. **Lancez la génération complète** : depuis le module Offres, sélectionnez le TDR et les informations de session, puis demandez la génération de l'offre complète (technique + financière en une seule fois).
3. **Ou générez séparément** : vous pouvez générer l'offre technique ou l'offre financière indépendamment si vous avez déjà l'une des deux.
4. **Validation obligatoire** : chaque offre générée crée une demande de validation (review HITL). Un responsable doit approuver l'offre avant qu'elle puisse être utilisée.
5. **Après approbation** : l'offre approuvée est synchronisée avec le Backend et devient disponible pour la suite du processus.
6. **Si rejetée** : l'offre peut être régénérée en prenant en compte le motif de rejet.

## Ce qui nécessite une validation humaine

Toute offre générée par l'IA doit être relue et approuvée par un responsable avant envoi au client. Cette étape est obligatoire — voir le guide sur la Validation HITL.

## Si quelque chose ne fonctionne pas

- **Génération échoue** : le service IA est peut-être indisponible — réessayez.
- **L'offre ne s'affiche pas après validation** : vérifiez que la synchronisation avec le Backend a bien été effectuée.
- **Erreur sur l'offre financière** : les données de budget sont peut-être incomplètes — vérifiez les informations de session.
