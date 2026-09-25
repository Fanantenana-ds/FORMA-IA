# Base de connaissances (RAG — C3)

## À quoi ça sert

Un assistant documentaire interne : vous posez une question en langage naturel sur les formations ALTIORA (contenu, où un sujet précis est expliqué, résumé thématique) ou sur l'utilisation de FORMA-IA elle-même, et l'assistant répond **uniquement à partir des documents réellement indexés** — jamais à partir de connaissances générales.

## État actuel — à lire avant utilisation

⚠️ **Ce module est en cours de construction (Étape E sur 9 terminée à ce jour).** Ce qui suit décrit ce qui existe RÉELLEMENT dans le code au moment de la rédaction de ce guide :

- ✅ **Le chat fonctionne** : `POST /ia/rag/chat`.
- ✅ **Le téléchargement de document indexé fonctionne** : `GET /ia/rag/documents/{hash}/fichier`.
- ✅ **La liste des formations fonctionne** : `GET /ia/rag/formations`.
- ❌ **Il n'existe PAS encore de route pour indexer un document via l'API.** L'ingestion (extraction, découpage, envoi à Voyage AI, insertion en base) existe dans le code mais n'est pour l'instant accessible que par des scripts internes ou en code, pas par une route HTTP. Une route `POST /ia/rag/indexer-document` est prévue mais pas encore livrée.
- ❌ **Le guide utilisateur que vous lisez n'est pas encore indexé dans la collection `aide_plateforme`.** Tant que ce n'est pas fait, les questions sur l'utilisation de la plateforme recevront la réponse « Aucun support ALTIORA ne traite ce sujet » — ce n'est pas un bug, c'est le mode strict qui fonctionne correctement en l'absence de contenu indexé.

**Conséquence pratique aujourd'hui : le chat peut répondre correctement une fois des documents indexés (par un développeur, via script), mais un utilisateur final ne peut pas encore ajouter lui-même de nouveaux documents depuis l'interface.**

## Étapes d'utilisation (une fois des documents indexés)

1. **Poser une question** : `POST /ia/rag/chat` avec `message` et, en option, `conversation_id` (pour poursuivre une conversation, ex. relances comme « et le module 2 ? ») et `formation_code` (pour préciser explicitement de quelle formation on parle).
2. L'assistant détecte automatiquement le TYPE de votre question (catalogue des formations, contenu d'une formation, où un sujet est expliqué, question précise, aide sur la plateforme, ou simple salutation) et répond en conséquence, toujours avec ses sources quand la réponse s'appuie sur des documents.
3. **Télécharger la source d'une réponse** : utiliser le `hash` du document indiqué dans les `sources` de la réponse avec `GET /ia/rag/documents/{hash}/fichier`.
4. **Voir les formations disponibles et leur nombre de supports indexés** : `GET /ia/rag/formations`.

## Ce qui nécessite une validation

**Aucune validation humaine (HITL) sur le chat** — c'est un usage interne de consultation, pas un contenu diffusé à un client (décision explicite de la mission de ce module).

## Erreurs fréquentes

- **« Aucun support ALTIORA ne traite ce sujet »** : soit la question est réellement hors sujet, soit (plus probable actuellement) aucun document pertinent n'a encore été indexé — ce n'est pas une erreur du système.
- **« Limite de débit Voyage atteinte, réessayez dans X s »** : le service d'embeddings (Voyage AI) a atteint sa limite du palier gratuit (3 requêtes/minute) ; réessayer après le délai indiqué. Les questions de type catalogue/inventaire/conversationnel continuent de fonctionner normalement pendant ce temps (elles n'utilisent pas Voyage).
- **Réponse identique à une question déjà posée, très rapide** : normal, la réponse peut provenir du cache de requêtes (pas un signe de dysfonctionnement).
