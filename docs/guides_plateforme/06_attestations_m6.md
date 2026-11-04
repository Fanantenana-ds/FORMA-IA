# M6 — Attestations de formation

## Rôle dans le parcours FORMA-IA

M6 intervient après la réalisation des séances M5. Il confirme la participation à une session, prépare un PDF par personne admissible et conserve la décision humaine avant remise. Le calcul ne dépend pas d'un taux saisi dans le navigateur.

## Éligibilité calculée sur les données Backend

L'API `GET /api/v1/ia/formations/sessions/{session_id}/attestations/eligibilite` relit, dans le tenant authentifié, la session, ses inscriptions, ses séances et les pointages associés.

- Seuil : **75 %** des séances.
- `PRESENT` et `RETARD` sont comptés comme présence ; `ABSENT` et `EXCUSE` ne le sont pas.
- Un pointage manquant n'est pas traité comme une absence : l'interface indique « À compléter » et bloque la génération.
- Les taux, le nombre de pointages manquants et le statut d'éligibilité sont recalculés côté serveur.

## Préparer et valider un lot

1. Dans la session M5, créer les séances et compléter le statut de chaque participant à chaque séance.
2. Dans la carte **Attestations de formation · M6**, actualiser l'éligibilité puis préparer les attestations si les pointages sont complets.
3. L'Agent 5 fabrique un PDF paysage A4 d'une page par participant éligible. Le logo ALTIORA PREST, les informations de session, les compétences de référence et un numéro unique sont ajoutés.
4. Le lot apparaît dans **Espace IA → Validation IA**. La direction peut prévisualiser chaque PDF, approuver les attestations une par une ou approuver tout le lot.
5. Un PDF individuel est téléchargeable après son approbation. Le ZIP n'est disponible qu'une fois tout le lot approuvé.

La génération est bloquée si des pointages manquent. Un deuxième lot ne peut pas être créé tant qu'un lot est en attente ou qu'un lot a déjà été approuvé pour cette session. Un lot rejeté peut être repris.

## Contenu des compétences et lien C3/RAG

Les compétences et contenus abordés viennent en priorité des extraits des supports RAG indexés pour le `formation_code` de la session. En l'absence de ces extraits, le service consulte le syllabus C3 déjà **approuvé** pour le même code ; à défaut, il utilise les thèmes des séances réellement enregistrés. Si les sources ne permettent pas d'étayer les compétences, la génération est refusée. L'attestation confirme la participation, mais ne certifie pas la maîtrise individuelle d'une compétence : le parcours ne relie pas encore un score de test à chaque compétence et aucun seuil de réussite officiel n'est défini.

Le **portfolio** C3 reste un document de références pour l'offre M3 ; il ne sert pas de source aux compétences d'un participant. Le **syllabus** est la source pédagogique pertinente ici.

## Historique, numéros et signature

Chaque lot reste dans l'historique HITL avec son état et sa note de validation. Les numéros sont réservés atomiquement dans le registre de génération afin d'éviter les doublons lors de lots répétés ou concurrents.

Le dépôt contient le logo ALTIORA PREST, mais aucun fichier de signature manuscrite autorisée du directeur n'a été trouvé. Le PDF comporte donc une zone « Signature et cachet » à signer ; aucune image de signature n'est inventée. Une signature visuelle officielle pourra être intégrée quand ALTIORA fournira son fichier autorisé.

## Routes M6

- `GET /api/v1/ia/formations/sessions/{session_id}/attestations/eligibilite`
- `POST /api/v1/ia/formations/sessions/{session_id}/attestations/generer`
- `GET /api/v1/ia/formations/reviews/{review_id}/attestations/{numero}/preview`
- `POST /api/v1/ia/formations/reviews/{review_id}/attestations/{numero}/approve`
- `GET /api/v1/ia/formations/reviews/{review_id}/attestations/{numero}/download`
- `GET /api/v1/ia/formations/reviews/{review_id}/attestations.zip`

Les opérations sont limitées aux rôles DIRECTION, ADMIN et ASSISTANT et aux données du tenant authentifié.
