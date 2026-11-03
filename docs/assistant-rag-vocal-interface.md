# Assistant FORMA-IA — interface RAG et voix

Le moteur RAG C3 existant est conservé. Le client appelle /ia/vocal/commande
avec le JWT du login et le conversation_id du tour précédent. Les routes vocal
et RAG acceptent cette session via le validateur Backend existant ; aucun secret
interne supplémentaire à saisir, compatibilité de la clé interne conservée.

## Utilisation

- Cliquer sur le compagnon pour ouvrir la conversation ; le glisser pour le déplacer.
- Déplacer le panneau par son en-tête ou l'agrandir ; Échap le ferme.
- Réglages vocaux et position : lecture automatique, voix et réinitialisation.
- Cliquer le micro, autoriser le navigateur, parler en français ; la transcription
  apparaît pendant la dictée. Arrêter, corriger si nécessaire, puis envoyer.
- Entrée envoie, Maj+Entrée ajoute une ligne. Limite du contrat : 500 caractères.
- Arrêter coupe le micro, la lecture et la requête en cours. La dictée s'arrête
  aussi après 60 secondes ou si l'onglet est masqué. Aucun redémarrage automatique.
- Lire les références/pages de la réponse ; les liens HTTP(S) sont consultables
  lorsqu'ils sont fournis par le moteur, aucun lien documentaire n'est inventé.

La voix dépend des voix françaises masculines détectées (ex. Microsoft Paul).
En leur absence, les réponses restent écrites et les réglages signalent le manque.
La reconnaissance dépend du navigateur, du microphone, de la connexion et de
l'accent : aucune qualité parfaite n'est garantie. Utiliser un micro proche,
une salle calme et vérifier la transcription avant envoi.

L'historique affiché reste local en mémoire (20 messages), pas sauvegardé après
rechargement. Nouvelle conversation réinitialise le contexte du panneau sans
supprimer les conversations du serveur. Les boutons d'action ouvrent les écrans
prévus ; ils ne constituent pas une preuve d'exécution d'une action métier.

## Vérification manuelle après redémarrage Backend et rechargement frontend

1. Login réel, ouverture sans champ de clé, question documentaire et références.
2. Dicter une phrase, contrôler la transcription, arrêter, corriger et envoyer.
3. Contrôler la voix masculine, arrêter et relire une réponse.
4. Glisser le compagnon aux quatre bords : pas d'ouverture accidentelle ; cliquer.
5. Glisser l'en-tête, agrandir/réduire, redimensionner la fenêtre et réinitialiser.
6. Nouvelle conversation, session expirée et microphone refusé : erreurs explicites.

Tests automatisés avec doublures ; pas de validation micro ou navigateur réel
revendiquée. La présentation ne change pas les preuves exigées par le RAG et
ne modifie pas le mode démonstration M1.


## Évolution du 30 octobre — dictée, exécution et corpus

Le bouton visible « Réponse vocale activée / désactivée » coupe immédiatement
la lecture et mémorise le choix localement. Couper la lecture pendant une
requête empêche aussi sa réponse de démarrer à voix haute après coup.
La dictée renforcée utilise MediaRecorder avec réduction de bruit, contrôle
automatique du gain et suppression d'écho demandés au navigateur. Le niveau
micro affiche une mesure réelle, jamais une animation faisant croire à du son.
Le mode utilise Groq Whisper large v3 turbo, français, via /ia/vocal/transcrire ;
8 Mo maximum, sans stockage audio applicatif, timeout fournisseur 35 s et
aucun retry automatique sur quota. L'enregistrement est limité à 60 s dans le
client. L'indicateur de niveau ne bloque pas l'enregistrement si AudioContext
est suspendu. Le moteur navigateur reste une option alternative.

L'option « Envoyer la dictée après transcription » est activée par défaut pour
le guidage vocal demandé. La désactiver pour corriger avant envoi. L'arrêt global,
la fermeture et le masquage d'onglet annulent la capture ; l'arrêt via l'icône
micro termine une dictée destinée à être transcrite. La lecture coupe le micro
pour éviter de reprendre la propre voix de l'assistant.

Les demandes explicites raccordées exécutent automatiquement : lancement M1
avec navigation, création d'une session, création d'une séance dans une session
existante et génération du brouillon TDR. Les champs sont contrôlés côté client
puis par les routes Backend existantes ; les droits restent ceux du compte.
Session/séance créée est relue avant confirmation. Une ambiguïté ou un champ
manquant pose une question ; le contexte est renvoyé au tour suivant. Les
créations identiques déjà trouvées sont réutilisées sans garantir une contrainte
d'unicité entre navigateurs. Un arrêt après envoi ne garantit pas l'annulation.
Les autres mutations restent signalées comme non raccordées et les documents
externes gardent leur approbation humaine.

Les résultats réels de détection M1 sont conservés une heure par compte dans
le processus serveur pour les demandes d'explication. Un redémarrage efface ce
contexte : lancer une nouvelle détection après mise à jour. Les sources, scores,
dates et limites d'analyse sont fournis au LLM pour une explication distincte
à l'écrit et à l'oral. Les reprises d'analyse enrichissent ce dernier bilan.
Ce contexte temporaire ne remplace ni la persistance des sélections en base,
ni l'indexation des supports de formation.

Identité et rôle sont précisés dans les prompts vocal/C3. Une présentation
simple est traitée localement sans quota et sans support de formation ; une
procédure précise ou une connaissance de cours nécessite toujours ses sources.
Les réponses d'introduction ne sont plus supprimées au motif qu'elles n'ont
pas de source documentaire. Les graphies françaises de « plateforme » et les
questions de rôle courantes sont reconnues.
