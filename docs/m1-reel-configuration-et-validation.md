# M1 réel — configuration et validation (30 octobre 2026)

## Configuration active

`app/config/veille_sources.yaml` définit quatre familles : institutionnel
(FID/ARMP), international (UNGM/PNUD), missions privées
(LinkedIn/Asako/PortalJob) et découverte (dgMarket/AFD).
La détection automatique collecte d'abord institutionnel puis missions privées,
international et découverte, avant de fusionner les sources pour l'analyse Groq.
Les familles prévues, exécutées et interrompues sont
exposées dans `source_groups` ; le budget global ne garantit pas leur exécution complète.
Chaque source possède un identifiant, ses domaines, un interrupteur `enabled`,
des chemins privilégiés et des chemins exclus. Les chemins privilégiés améliorent
le classement ; ils ne prouvent pas qu'une annonce est recevable.

Le registre est validé au chargement. Une famille dépassant `TAVILY_SITES_MAX`
est refusée explicitement au lieu d'ignorer silencieusement ses derniers domaines.
Tavily reçoit `include_domains` et `exclude_domains` ; les exclusions sont aussi
vérifiées dans les résultats et dans le repli. Le repli sans opérateurs `site:`
garde les domaines de la famille et est identifié par `search_strategy=family_fallback`.
La famille privée désactive le téléchargement brut des pages et utilise les extraits
indexés pour réduire la latence ; toute preuve manquante nécessite une vérification.
Toutes les familles ont un budget de recherche de 25 secondes. Les tentatives
institutionnelles/internationales/découverte sont bornées à 12 secondes, toutes
phases HTTP incluses. Après un timeout, un seul repli sans opérateurs est tenté,
sans contenu brut. Le chemin institutionnel utilise également les extraits à la
première recherche. Les erreurs 5xx ont au plus deux tentatives dans le budget.
Pour les missions privées, les sites absents font l'objet d'une requête ciblée
chacun, sans nouvelle analyse Groq : concurrence maximale deux, 10 secondes par
repli et respect du budget total. Un 429 arrête les nouvelles tentatives.
La limite globale de la détection reste applicable.
Une URL inconnue ne peut pas être confirmée
automatiquement : elle nécessite une vérification humaine.
Les avis de listes plus anciens que la fenêtre de publication restent conservés
après les avis récents. Une ancienne publication ou une ancienne référence ne
prouve pas l'expiration. Une date de tableau sans en-tête explicite est conservée
comme `observed_table_date`, sans être présentée comme date de publication.

Les anciennes variables restent prises en compte :

| Variable | Effet réel |
|---|---|
| `TAVILY_INCLUDE_DOMAINS` | Ajouts au registre, sans masquer FID ni les autres familles |
| `TAVILY_EXCLUDE_DOMAINS` | Exclusion de domaines et sous-domaines |
| `TAVILY_REJECTED_KEYWORDS` | Mots supplémentaires de bruit ; les noms d'acheteurs protégés, dont UNICEF, sont ignorés |
| `TAVILY_JOB_KEYWORDS` | Signal `employment_signal`, jamais une preuve de prestation |
| `M1_ANALYSIS_BUDGET_S` | Budget total d'un appel d'analyse (20 s par défaut) |
| `M1_DETECTION_BUDGET_S` | Budget de la détection automatique entière (90 s par défaut) |

Le vrai `.env` et le paramètre `DEMO_MODE` n'ont pas été modifiés.

## Preuves et décisions

Groq doit donner des extraits exacts du besoin, de l'organisme, de la localisation
et de l'échéance. Python vérifie ces extraits dans une source effectivement
collectée et rattache l'URL à cette source. Le titre ou résumé généré ne sert pas
de preuve de localisation. Une page de catégorie, une ligne datée sans objet,
une URL inventée, une échéance non étayée ou un recrutement salarié ambigu ne
peuvent pas devenir automatiquement une opportunité confirmée.

`opportunities` contient les candidats documentés ayant passé les règles et le
score métier Python (au moins 40). Une confiance d'extraction d'au moins 0,75 est
requise ; ce nombre reste une estimation du modèle, pas une probabilité calibrée.
La confiance de classification du domaine ne remplace plus celle d'extraction.
Les candidats incomplets vont dans `to_review_candidates` : ils ne sont pas
synchronisés comme opportunités. Le score n'est pas artificiellement augmenté.

Les suggestions sont contrôlées après la vérification :

- informations insuffisantes : consulter la source et vérifier les points listés ;
- avis documenté : examiner le dossier et l'éligibilité, obtenir la validation
  humaine, puis préparer le TDR ou l'offre correspondant au besoin ;
- avis expiré : rejet déterministe, conservé dans les diagnostics des sources.

La validation porte sur les extraits renvoyés par Tavily ou sur le contenu
principal d'une page publique effectivement lue. Elle ne prouve ni
l'éligibilité d'ALTIORA, ni la disponibilité directe actuelle du site, ni l'absence
d'un avenant ou d'une annulation. `verification_status=documented` et
`verification_method=tavily_excerpt` rendent cette limite explicite.
`last_verified_at` reste nul sans vérification directe ; `last_checked_at` indique
le contrôle des extraits. La capture et la publication proviennent des sources
collectées, et ne sont pas remplacées par les dates inventées du modèle.

## API et frontend

Le JSON et le SSE réel conservent les champs historiques. Le SSE transmet en plus
les preuves, dates, recommandations et l'événement `candidat_a_verifier`. L'événement
final contient `analyzed_sources`, `pending_sources`, `to_review_candidates` et
les statistiques. La vue Veille affiche ces listes uniquement si les champs réels
sont présents. Aucun budget fictif n'est affiché pour les détections réelles.

Statuts : `success`, `no_results`, `partial`, `technical_error`, `quota_atteint`.
Un lot non traité ou des candidats à vérifier empêchent un faux bilan complet.
En REST, une panne totale donne HTTP 503 ; un quota HTTP 429 ; un résultat partiel garde
HTTP 200 avec son statut explicite. En SSE, une erreur après ouverture du flux est
signalée par les événements `erreur` et `fin`, avec le statut concerné.
Un 429 Groq/Tavily arrête les relances du
passage. Les requêtes planifiées et celles effectivement exécutées sont séparées.

La branche SSE `DEMO_MODE`, son archive JSON, son service et `demo_vocal.html`
sont préservés. Les panneaux frontend supplémentaires sont conditionnés à la
présence des diagnostics réels. L'authentification SSE existante n'a pas changé.

## Tester sans écrire dans le Backend

Depuis `C:\Projets\FORMA-IA` (consomme les quotas réels) :

```powershell
.\venv\Scripts\python.exe -m scripts.diagnostic_m1_reel --query "appel d'offres formation intelligence artificielle Madagascar" --source-group institutionnel --max-batches 1 --batch-size 3 --budget-seconds 60
```

Pour examiner spécifiquement les missions privées :

```powershell
.\venv\Scripts\python.exe -m scripts.diagnostic_m1_reel --query "recherche formateur externe informatique Madagascar" --source-group missions_privees --max-batches 1 --batch-size 3 --budget-seconds 60
```

Le diagnostic ne démarre pas le scheduler, ne modifie pas `.env`, ne crée pas de
review HITL et n'effectue aucune synchronisation Backend. Les compteurs de quota
Tavily restent enregistrés. Le budget de 60 secondes concerne cet essai limité,
pas une promesse de résultat positif ni une mesure de toutes les familles.

Essai réel observé pendant l'intervention : 18,866 s, 15 résultats collectés,
3 analysés, un avis FID individuel retenu à 52/100 avec échéance extraite au
30 octobre 2026, un candidat à vérifier, statut global partiel. Aucun appel
Backend ni diffusion d'offre. Cette annonce évolue : refaire le contrôle avant
toute candidature, notamment après son échéance.

Essai privé observé : la collecte LinkedIn/PortalJob a abouti en 5,853 s après
adaptation du budget de la famille, puis Groq a dépassé son budget de 20 s.
Résultat `technical_error` en 25,831 s, trois sources conservées en attente et
aucune promue. La collecte privée a donc été observée ; une analyse privée
complète et positive n'est pas revendiquée. Les résultats dépendent de
l'indexation des plateformes, de l'accessibilité des publications et des quotas.

Vérifications de cette intervention : 883 tests unitaires réussis, quatre tests
Google Forms ignorés sans identifiants ; tests M1 ciblés repassés après les derniers
ajustements. TypeScript et compilation Python réussis. Ruff absent du venv et
couverture globale non remesurée. Les assertions historiques attendant `degraded`
pour une panne LLM totale ont été adaptées au contrat explicite `technical_error`.
Le test d'orchestration double le contrôle des preuves pour isoler ses étapes ;
`test_m1_final.py` teste aussi le parcours réel avec ce contrôle actif.

## Correctifs des journaux du 30 octobre

La résolution des avis est locale au M1 réel (`notice_resolution_service.py`).
Les annonces individuelles pertinentes sont lues avant les pages paginées.
Sinon le résolveur suit les liens des pages de listes, en privilégiant la page
courante. Il lit au plus deux listes et deux détails dans un budget total de
14 secondes, sans navigateur, sans contournement de connexion et sans LLM.
Les pages sont limitées à 1,2 Mo ; redirections et domaines sont contrôlés.
Les liens PDF/DOCX sont laissés à la vérification documentaire, sans prétendre
que leur contenu a été lu. Une panne conserve la source indexée à vérifier.

Les menus et encarts associés sont retirés du contenu principal. Une lecture
réussie porte `verification_method=direct_public_page` et `last_verified_at`.
Cela prouve la lecture du contenu, pas l'admissibilité commerciale d'ALTIORA.
Les doublons d'URL ou de référence chez un même éditeur sont regroupés ; deux
listes partageant seulement les 200 premiers caractères ne sont plus fusionnées.

La clôture utilise le fuseau de Madagascar. Une heure ne devient `deadline_at`
que si elle accompagne la date dans le texte du même avis avec un fuseau
interprétable. Une date seule aujourd'hui reste à confirmer. Le scoring réel
ne pénalise plus un avis clôturant à 16 h comme expiré à minuit ; la fonction de
scoring partagée et les chemins démonstration/benchmark gardent leur comportement.

Champs pour le binôme frontend :

- `collection_diagnostics.attempts` : tentatives, durée totale, statut HTTP,
  temps renvoyé par Tavily et identifiant de requête, sans clé API ;
- `collection_diagnostics.domain_coverage` : résultat indexé, absence de résultat
  indexé, échec ou site non recherché ; ce n'est pas une mesure de disponibilité du site ;
- `collection_diagnostics.notice_resolution` : lectures publiques et échecs ;
- `statistics.llm_candidates_proposed`, `documented_candidates` et
  `confirmed_opportunities` : étapes séparées ; `groq_results` compte les propositions ;
- `score_evaluated=false`, `score_label="Non évalué"` : score non attribué faute de
  preuves ; le zéro numérique est gardé pour compatibilité, pas affiché comme une note ;
- `deadline_at`, `deadline_precision`, `deadline_timezone` : heure étayée ou date seule.

Pour parcourir les quatre familles dans un diagnostic sans synchronisation :

```powershell
.\venv\Scripts\python.exe -m scripts.diagnostic_m1_reel --query "formation informatique intelligence artificielle Madagascar" --source-group all --max-batches 1 --batch-size 3 --budget-seconds 120
```

Cette commande consomme le quota manuel réel : avec `--max-batches 1`, un seul
lot Groq global après la collecte des familles. Une limite Groq ne bloque plus
la collecte de la dernière famille. Une famille non exécutée est explicitement signalée.
Les suggestions restent fondées sur les preuves ; aucun avis n'est confirmé
pour augmenter artificiellement le compteur.

Validation du 30 octobre, avant le correctif du diagnostic global :

- Suite unitaire : **896 réussis, 4 ignorés**, avertissements existants.
- FID réel : **24,553 s**, 15 résultats API, 10 documents conservés,
  trois analysés, une opportunité retenue **55/100**, sept sources non analysées
  (`partial`). Annonce individuelle lue, clôture extraite
  `2026-10-30T16:00:00+03:00`, aucune synchronisation Backend.
- Privé réel : **15,795 s**, les trois domaines LinkedIn/Asako/PortalJob présents
  après les replis ciblés, six documents, trois analysés, un candidat à vérifier,
  trois sources non analysées, zéro opportunité confirmée (`partial`). Trois
  appels Tavily et un lot Groq ; aucune annonce générique promue artificiellement.
- Les parcours simulés couvrent aussi toutes les familles et les interruptions.
  Le mode `all` complet n'a pas été relancé contre les quatre familles réelles
  afin de limiter les quotas ; aucune validation visuelle frontend revendiquée.
- Service et archive de démonstration, page HTML de démo et branche `DEMO_MODE`
  SSE : empreintes identiques au début de l'intervention. Aucun fichier frontend
  modifié dans cette intervention. Aucun commit/push ni installation.

Les essais intermédiaires ont exposé un timeout Tavily à 25 s et la sélection
d'anciens avis avant l'annonce IA. Les correctifs finaux bornent chaque tentative,
désactivent le contenu brut institutionnel et privilégient la lecture des avis
individuels pertinents. Les mesures positives ci-dessus ne garantissent ni une
latence constante ni la présence future d'un marché admissible.

## Diagnostic global : preuves documentaires et débit Groq

Le diagnostic utilisateur atteignait 8 018 tokens demandés/utilisés pour un
plafond de 8 000 TPM, puis abandonnait la famille découverte. Le service automatique
et le diagnostic `all` utilisent maintenant `collect_first=True` : collecte sous
budget, regroupement, retrait des pages de navigation et analyse globale. Le
parcours historique par requête reste disponible pour compatibilité interne.

`app/prompts/m1/analyse_compacte.yaml` conserve rôle, contexte, tâche, contraintes,
format et exemples. Il demande les faits et les citations ; le scoring et les
recommandations restent contrôlés en Python. Le plafond de sortie est 1 800 tokens
sur ce chemin. Une requête IA ne rend pas une prestation web/PAO hors périmètre.
Les demandes directement lues passent avant les posts chargés de hashtags.

Un 429 sans indication exploitable remonte sans retry aveugle. Une indication
fournisseur de réessai d'au plus deux secondes autorise un seul réessai, attente
et marge incluses dans le budget total d'analyse. Une deuxième erreur arrête
l'analyse. Ce mécanisme n'est pas une garantie de quota disponible : les autres
modules partagent la limite de l'organisation Groq.

Le cas FID présentait aussi des citations omises ou placées dans le mauvais
champ : une citation du besoin était utilisée pour l'organisme. Le chemin réel
retrouve désormais un titre demandeur réellement présent dans le corps lu,
le nom proposé de l'organisme s'il y est littéralement présent, et une date
précédée d'un marqueur explicite de clôture. Les variantes typographiques
d'apostrophes/espaces sont tolérées, sans rapprochement sémantique ni invention.
Une publication seule n'est jamais une clôture ; plusieurs dates de clôture
distinctes ne permettent pas de compléter automatiquement une date manquante.

`evidence_origin` distingue `validated_model_quote`, `direct_source_heading`,
`direct_source_match` et `direct_closing_clause`. Les origines sont ajoutées aux
opportunités réelles, sans remplacer une validation humaine d'éligibilité.
`navigation_sources` conserve les pages non envoyées à Groq. `analysis_batches`
expose taille du prompt et consommation retournée par le fournisseur.
`collection_complete` indique l'achèvement des requêtes de collecte prévues,
pas l'analyse de toutes les pages ni la disponibilité de chaque site.

Rejeu du cas FID problématique après nouvelle lecture HTTP, sans Tavily/Groq :
preuves complètes, échéance extraite au 30/10/2026 16 h +03:00 et une opportunité
retenue à 52/100 par le scoring existant. Il s'agit d'un rejeu d'une proposition
réelle enregistrée pendant le test, pas d'une nouvelle réponse LLM ni d'une
modification de l'archive de démonstration.

Validation finale du parcours global après ces corrections : **910 tests
unitaires réussis, 4 ignorés** ; avertissements existants. Essai réel `all` :
**43,921 secondes**, quatre familles collectées, 30 documents collectés,
18 sources après filtrage, trois analysées et quinze en attente (`partial`).
Une opportunité FID retenue **52/100**, lue sur sa page originale, clôture
extraite `2026-10-30T16:00:00+03:00`. Six pages de navigation écartées de Groq.
Un seul lot Groq : **1 686 tokens d'entrée + 457 de sortie = 2 143**, aucun 429
dans cet essai. Aucune synchronisation Backend. Les zéros intermédiaires ont
permis d'identifier la priorité d'un ancien avis, les citations dans le mauvais
champ et les dates omises ; aucun seuil métier n'a été baissé pour les contourner.
Ces mesures ne garantissent pas une disponibilité constante des sites ou de Groq.

Les sources non analysées restent distinctes de celles rejetées ; leur présence
explique le statut partiel, même avec une opportunité retenue. Après sa clôture,
l'avis FID ne doit plus être présenté comme une candidature ouverte. Le mode de
démonstration, son archive et ses dates n'ont pas été modifiés.

## Qualité, temps de collecte et affichage du bouton

La collecte globale exécute au plus deux familles simultanément, avec un contexte
de source isolé par tâche et les mêmes recherches prévues. Les appels Groq restent
par lots successifs. Un quota arrête les nouvelles collectes en attente ; les
requêtes déjà en cours peuvent se terminer. Les articles de blog, pages LinkedIn
d'agrégation, certains rapports explicites, ventes de véhicules et localisations
étrangères explicites sont mieux séparés. Les annonces individuelles techniques
sont analysées avant les publications génériques ; aucune note métier n'est augmentée.

Un rejet du modèle fondé seulement sur « hors IA » ou l'absence d'appel d'offres
officiel ne confirme plus un rejet métier d'une source informatique : le candidat
est marqué `review_reason=unsupported_rejection`, non actionnable et non évalué.
Cela ne le transforme pas en opportunité. Les demandes privées externes restent
recevables ; les publicités et emplois salariés ne le deviennent pas automatiquement.

Le filtrage final met à jour les décisions `filtered_score` / `filtered_limit`,
les compteurs, `below_requested_score` et `omitted_by_limit`. Une demande de score
100 n'affiche plus l'avis à 52 comme retenu dans ses diagnostics. Les erreurs
Tavily gardent leurs tentatives même sur un échec réseau hors timeout global.

Le bouton React existant utilise `GET /api/v1/ia/veille/detecter/stream`.
Le POST reste une réponse JSON finale ; le suivi immédiat passe par le SSE.
Aucun fichier React n'a été modifié : le composant sait déjà afficher le journal
et les champs `ai_recommendation`, dates et sources des opportunités.

Le backend transmet réellement la progression pendant son travail via
`progress_service.py` (callback par ContextVar) et une file SSE bornée :

| Événement existant | Champ `stage` | Contenu |
|---|---|---|
| `requete` | `collection_started` | Requête/famille réellement démarrée |
| `analyse` | `web_search`, `source_reading` | Interrogation web et lecture publique |
| `analyse` | `collection_completed`, `source_collected` | Documents collectés, encore non qualifiés |
| `analyse` | `prefilter`, `llm_analysis`, `verification` | Classement, analyse et contrôles |
| `analyse` | `source_decision`, `ranking_completed` | Décisions et fin du classement |
| `analyse` | `partial_completion` | Résultat incomplet, distinct d'une panne totale |
| `opportunite` | — | Opportunité documentée avec recommandation, preuves, dates et rang |
| `fin` | — | Résultats classés, candidats à vérifier et sources restantes |

Les étapes ne sont plus préannoncées comme déjà lancées avant la collecte. Les
messages `source_collected` ne sont jamais présentés comme des marchés confirmés.
Les commentaires keep-alive maintiennent le flux sans inventer de pourcentage.
La fermeture du flux annule la tâche associée. Le paquet `fin.opportunites` est
trié par score décroissant ; les cartes individuelles sont émises dans l'ordre
inverse car le composant actuel insère chaque nouvelle carte en tête. Ce
comportement ne supprime pas les anciennes cartes déjà conservées par React.

Vérifications : suite unitaire **919 réussis, 4 ignorés** ; tests spécifiques de
progression avant fin, annulation client, vidage de la file et ordre des résultats.
La visualisation complète dans le navigateur n'a pas été rejouée. Un essai réel
avant ajout du flux continu, avec budget CLI de 45 s, a retenu FID à 52/100 en
**33,688 s**, un lot de **1 699 tokens** ; institutionnel/privé ont abouti,
international/découverte n'ont pas abouti dans ce passage, donc `partial` et
`collection_complete=false`. Cette mesure ne démontre pas quatre familles
complètes en 34 secondes et ne constitue pas une promesse de durée constante.

### Login Backend et accès M1 — correction du 30 octobre 2026

Le formulaire de connexion appelle maintenant POST /api/v1/auth/login puis
GET /api/v1/auth/me. Le profil et le rôle proviennent du Backend. L'inscription
utilise le contrat /auth/register existant. Le JWT est gardé dans sessionStorage
pour l'onglet et utilisé automatiquement dans Authorization: Bearer pour M1.
Aucun champ de clé interne à renseigner dans M1 ; aucun JWT dans l'URL SSE.
Le profil restauré est revérifié par /auth/me et logout appelle /auth/logout.
Les accès rapides de démonstration restent des profils locaux, sans accès JWT
aux services réels. Se connecter avec un compte Backend pour tester ce parcours.

L'adaptateur IA app/services/veille/access_service.py accepte le JWT en appelant
le validateur Backend existant, incluant expiration, révocation et compte actif.
Il préserve aussi la clé interne historique pour Swagger et la page de démo.
Aucun changement de core, models, db, routes auth ou des traitements DEMO_MODE.
Les fixtures métier M1 sont adaptées à la nouvelle dépendance, avec tests
d'accès séparés. Les autres contrats CRUD ne sont pas tous raccordés par cette
correction du login ; l'acceptation des cartes M1 reste locale.

Démarrer depuis C:\Projets\FORMA-IA :

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Dans un second terminal :

```powershell
cd C:\Projets\FORMA-IA\frontend
npm run dev
```

Ouvrir http://localhost:3000, utiliser un vrai compte Backend sur le formulaire
email/mot de passe, puis cliquer Lancer la détection IA dans Veille marché IA.
Redémarrer Vite et recharger la page si un ancien EventSource ?token= apparaît.
ECONNREFUSED 127.0.0.1:8000 indique un backend injoignable : attendre le message
Application startup complete et contrôler http://127.0.0.1:8000/health.
La connexion n'est pas remplacée par un profil inventé en cas de panne.

Les essais unitaires isolent le HTTP/DB : ils ne remplacent pas une connexion
avec un vrai compte sur la base locale. Aucune création de compte ni modification
du mode DEMO_MODE n'a été effectuée pour ces tests.

Validation de cette correction : 30 tests Python et 9 tests Node réussis ;
TypeScript et build Vite réussis, avertissement existant sur la taille du bundle.
Empreintes de la branche SSE démo, du service, de l’archive et de la page démo
identiques à celles relevées avant cette correction. Trace Codex mise à jour.

### Reprise de collecte et sélections au tableau de bord

Après une nouvelle détection réelle, le bouton « Analyser les sources restantes »
appelle POST /api/v1/ia/veille/sources/reprendre. Trois documents déjà collectés
sont traités par clic avec la vérification/scoring existante et le seuil initial ;
aucune nouvelle recherche Tavily ni boucle automatique. Les documents restants
et diagnostics sont actualisés sans effacer les opportunités déjà affichées.
Le handle est lié au compte, verrouillé pendant une analyse, valable 30 minutes,
en mémoire du processus (20 collectes, 200 documents/4 Mo par collecte maximum).
Un redémarrage ou un autre worker rend la reprise indisponible : relancer une
collecte dans ce cas. Le délai d'analyse est borné à 90 s. Les erreurs et quotas
conservent les sources pour une reprise manuelle, sans garantie de nouveau marché.

Pour les résultats réels, « Retenir » appelle le CRUD Backend avec le JWT courant,
puis contrôle la création par GET. Un échec ne devient pas une acceptation locale.
Le contrat ne comporte pas de statut « acceptée » : la sélection est explicitement
identifiée par un marqueur forma_ia_selection_v1 et les métadonnées de la carte
dans le champ contenu. Le statut Backend EN_ATTENTE n'est pas présenté comme un
marché gagné. Aucune migration ou modification de contrat Backend. Les sélections
sont rechargées depuis la base au dashboard et permettent de préparer les TDR ;
l'UUID Backend est transmis au brief M2 pour l'association du document. Une
sélection déjà trouvée par URL est réutilisée ; ce contrôle ne garantit pas
l'unicité entre deux navigateurs créant simultanément la même sélection.
Le score métier est conservé dans les métadonnées, pas copié dans le champ score
Backend que le contrat de création ne permet pas de renseigner.
Le parcours de démo reste local ; les empreintes de sa branche SSE, de son
service, de son archive et de sa page sont inchangées.

Tester : redémarrer le Backend, lancer une nouvelle détection réelle, reprendre
un lot en attente, puis retenir un résultat avec un compte Direction/Assistant.
Vérifier la carte au dashboard, recharger la page, et ouvrir M2 depuis cette carte.
Les tests automatisés isolent les fournisseurs/DB ; aucun enregistrement réel
ni analyse payante n'a été effectué pour ces vérifications.
