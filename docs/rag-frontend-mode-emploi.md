# Base documentaire FORMA-IA — mode d'emploi du 30 octobre 2026

Les routes et formats de docs_frontend/GUIDE_INTEGRATION_FRONTEND.md ont été
vérifiés dans le code réel avant raccordement. Le module utilise le JWT du login.
Aucune nouvelle clé interne à saisir côté interface.

## Tester Upload et chunking

1. Redémarrer le Backend, recharger le frontend, se connecter avec un vrai compte.
2. Menu Base documentaire, onglet Supports et guides.
3. Choisir une formation du catalogue si nécessaire et la collection Supports.
4. Choisir un PDF avec texte, Word, PowerPoint, Excel, TXT ou Markdown de moins
   de 20 Mo ; préciser éventuellement le module pédagogique.
5. Cliquer Envoyer et indexer. Le client envoie FormData avec fichier,
   formation_code, collection et module à /documents/upload, puis transmet le
   chemin_fichier renvoyé à /ia/rag/indexer-document. Le chemin n'est pas affiché.
6. Attendre le statut Indexé. En cours ne signifie pas terminé. Le suivi
   automatique s'arrête après deux minutes ; Actualiser permet de poursuivre
   sans relancer automatiquement l'indexation. Erreur/OCR requis restent visibles.
7. Cliquer Inspecter les extraits enregistrés (chunks) : le nombre et le texte
   viennent d'une lecture réelle de knowledge_base, pas du seul registre JSON.
   Pagination de 20 extraits, pages et modèle disponibles ; aucun vecteur affiché.
8. Dans Recherche, saisir un concept présent dans le fichier ; consulter les
   passages, pages et scores de similarité. Le seuil est configurable.
9. Dans Assistant documentaire, sélectionner la même formation et poser une
   question sur le contenu. Vérifier les références, télécharger le document.
10. Pour vérifier la mémoire persistante, recharger la page ou redémarrer le
    Backend puis inspecter à nouveau les extraits. La base vectorielle et les
    documents persistés sont distincts de l'historique de chat en mémoire client.

L'upload n'est pas une preuve d'indexation. Un document scanné peut nécessiter
un OCR absent de ce parcours ; un quota Voyage/Groq ou un problème de base doit
être traité avant de considérer le document exploitable. Une réponse absente
n'est pas remplacée par un faux contenu.

## Fonctionnement de la plateforme

Indexer le guide FORMA-IA actuel ajoute le guide daté à aide_plateforme. L'action
est explicite, déclenche les services existants et peut consommer leurs quotas.
Les anciens guides sont historiques ; le guide 00_parcours_interface_actuel.md
distingue les parcours réellement raccordés des agents Backend seulement.
Le rôle/identité et l'introduction générale sont connus localement et ne
nécessitent pas un cours indexé ; les procédures précises exigent leurs sources.

## Créations pédagogiques

Questions : sélectionner une formation, choisir 1 à 30 questions, générer.
Syllabus : formation, modules, durées et contenus ; vérifier la durée totale.
Portfolio : domaine/référence facultatifs. Relire le brouillon et ses références.
Pour syllabus/portfolio, noter la relecture puis approuver ou refuser ; exporter
Word uniquement après approbation. Retrouver les brouillons en attente permet
de reprendre une validation C3. Les exports utilisent les générateurs existants.
Le résumé de formation et le bilan utilisent les routes Backend déjà présentes.

## Vérifications et limites

Lecture seule réelle de la base locale : 30 chunks support et 10 chunks d'aide,
avec lecture d'un texte effectif sans afficher son contenu privé dans le rapport.
Tests d'inspection en SQLite isolé et tests de contrats avec doublures ; aucun
nouveau document injecté dans le corpus de production par ces vérifications.
La prise micro et le rendu visuel navigateur restent à tester par l'utilisateur.
Le stockage Backend local contient une convention de racine à faire vérifier
par le binôme Backend ; ce module respecte le chemin retourné par son upload.
Aucun modèle, schéma DB, migration ou core Backend n'a été modifié.

## Présentation de l'upload et progression — 30 octobre 2026

L'onglet Supports et guides propose un dépôt par glisser-déposer ou sélection,
un récapitulatif du fichier, la collection, la formation et le module facultatif.
La limite frontend reste 20 Mo. L'upload et l'indexation restent deux appels
successifs avec le JWT de la session ; aucune clé supplémentaire n'est demandée.

Le panneau suit GET /ia/rag/statut/{hash} toutes les 1,2 secondes, sans requêtes
simultanées, pendant deux minutes maximum. Les requêtes de suivi sont bornées
à 15 secondes ; un suivi interrompu peut être relancé. Quitter l'écran arrête
la surveillance cliente, sans garantir l'annulation de l'indexation serveur.

Le registre IA conserve un champ progression optionnel compatible avec les
anciennes entrées : extraction, découpage, vectorisation, enregistrement et fin.
Les étapes rapides peuvent ne pas apparaître individuellement entre deux lectures.
Les chunks préparés sont distingués des chunks dont l'insertion a réussi.
Le pourcentage porte uniquement sur les lots enregistrés, jamais sur le temps
restant ni sur une animation temporisée. Le statut indexe confirme la disponibilité
documentaire ; les résumés peuvent encore être préparés ensuite.

La recherche affiche les passages, leur similarité, les pages et le temps de
réponse réseau complet. Le seuil serveur est conservé par défaut ; sa modification
reste facultative. Le téléchargement de la source est proposé si le résultat
correspond sans ambiguïté à un support disponible dans la liste chargée.

Vérification de cette intervention : 29 tests Python ciblés et 28 tests Node
réussis, compilation TypeScript et build Vite réussis. Les fournisseurs sont
doublés dans les tests : aucun nouvel embedding réel n'est revendiqué ici.
