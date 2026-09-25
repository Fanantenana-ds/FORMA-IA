# M2 — Génération de Termes de Référence (TDR)

## À quoi ça sert

Génère un Termes de Référence (TDR) complet à partir d'un brief client (objectifs, public, durée...), avec export Word et PDF automatique.

Peut être pré-rempli à partir d'une opportunité détectée par le module M1, pour éviter de ressaisir les informations déjà connues.

## Étapes d'utilisation

1. **Optionnel — pré-remplir depuis une opportunité M1** : `GET /ia/tdr/from-opportunite/{opportunite_id}` renvoie un brief pré-rempli à compléter (champs manquants : public, durée, lieu).
2. **Générer le TDR** : `POST /ia/tdr/generer` avec le brief complet (`client`, `objectifs`, `public`, `duree` sont obligatoires ; `format`, `budget`, `lieu`, `deadline` sont optionnels). Le système produit le contenu du TDR puis les fichiers Word et PDF.
3. **Télécharger un fichier généré** : `GET /ia/tdr/download/{filename}`.
4. **Lister les TDR déjà générés** : `GET /ia/tdr/list`.
5. **Lister les opportunités disponibles** (pour choisir laquelle utiliser à l'étape 1) : `GET /ia/tdr/opportunites-disponibles`.

## Ce qui nécessite une validation

**Aucune validation humaine (HITL) n'est actuellement appliquée à ce module.** Le TDR généré est immédiatement disponible en téléchargement, sans étape d'approbation avant diffusion — même écart que pour M1, signalé tel quel.

## Erreurs fréquentes

- **Échec de génération (`success: false`)** : peut venir d'un problème côté service IA (Groq indisponible) — le message d'erreur exact est renvoyé dans la réponse.
- **Fichier introuvable au téléchargement (404)** : le nom de fichier doit correspondre exactement à celui renvoyé par la génération ; les noms contenant `..`, `/` ou `\` sont refusés par sécurité.
- **`opportunites-disponibles` renvoie une liste vide avec une erreur** : le Backend est peut-être injoignable — la route ne plante pas dans ce cas, elle renvoie `success: false` avec le détail de l'erreur.
