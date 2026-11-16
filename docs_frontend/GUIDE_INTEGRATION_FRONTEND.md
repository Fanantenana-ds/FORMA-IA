# GUIDE D'INTÉGRATION FRONTEND — FORMA-IA

> **Pour qui ?** Le binôme frontend qui branche le React (`frontend/`) sur l'API FastAPI.
> **Mis à jour le :** 13/10/2026. Chaque route, champ et valeur de ce guide a été **vérifié dans le code du backend** (schéma OpenAPI).
> **Référence vivante :** Swagger sur `http://127.0.0.1:8000/api/docs` — en cas de doute, c'est lui qui a raison.
> **Diagnostic détaillé vue par vue :** voir `INTERFACES_MANQUANTES.md`.

---

## 0. Ce qu'il faut retenir (5 règles)

1. **Toutes les URL commencent par `/api/v1`.** Exemple : `http://127.0.0.1:8000/api/v1/sessions`.
2. **Deux sortes de routes, deux jetons différents** (voir §2) :
   - routes **Backend** (`/api/v1/sessions`, `/factures`, …) → jeton **JWT** de l'utilisateur connecté ;
   - routes **IA** (`/api/v1/ia/...`) → **jeton interne** `SHARED_INTERNAL_TOKEN`.
3. **Un contenu généré par l'IA n'est jamais enregistré directement.** Il crée une *review* (`review_id`) qu'un humain approuve, puis le frontend appelle la route `/synchroniser` du module (voir §5).
4. **Les noms de champs sont ceux du backend**, pas ceux des mocks (`mockData.ts`). Il faudra adapter les types TypeScript (voir §4).
5. **Ne plus masquer les erreurs.** Aujourd'hui `request()` renvoie les données simulées dès qu'une erreur survient, même un 401 ou un 422 : on ne voit jamais que l'appel a échoué (voir §1).

---

## 1. Ce qui bloque aujourd'hui dans `frontend/src/services/api.ts`

| Constat dans le code | Conséquence |

|---|---|
| `request<T>(endpoint, fallbackData, options)` renvoie `fallbackData` (le mock) **pour toute erreur** | Un 401, un 404 ou un 422 ressemble à un succès : l'écran affiche des données fictives |
| Aucun en-tête `Authorization` | Toutes les routes protégées répondent **401** |
| Plusieurs chemins n'existent pas côté backend | Toujours le mock (tableau ci-dessous) |
| `isMockFallback` n'est **pas** une ligne à supprimer : il est recalculé à chaque appel | Il passera à `false` tout seul quand les appels réussiront |

Chemins actuels à corriger :

| Méthode dans `api.ts` | Chemin actuel (n'existe pas) | Chemin réel |
|---|---|---|
| `getKPIs`, `getDomainOpportunities`, `getFacturationStatuts`, `getRecentActivities` | `/api/dashboard/...` | **une seule route** : `GET /api/v1/dashboard/statistiques` |
| `getVeilles` | `/api/market-watch` | `GET /api/v1/opportunites` (opportunités enregistrées) |
| `getPresences` | `/api/attendance` | `GET /api/v1/sessions/seances/{seance_id}/presences` (par séance) |
| `getFormateurs` | `/api/trainers` | `GET /api/v1/rh/formateurs` |

### 1.1 — Nouvelle version de `request()` (à adapter, pas à copier aveuglément)

```ts
// Garder le mock UNIQUEMENT si le serveur est injoignable (erreur réseau).
// Une réponse HTTP d'erreur (401, 403, 404, 422…) doit remonter à l'écran.
private async request<T>(endpoint: string, fallbackData: T, options: RequestInit = {}): Promise<T> {
  const isIA = endpoint.startsWith('/api/v1/ia/');
  const token = isIA ? import.meta.env.VITE_IA_TOKEN : localStorage.getItem('token');

  let response: Response;
  try {
    response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    this.isMockFallback = true;          // serveur éteint → mode démo
    this.notify();
    return fallbackData;
  }

  if (response.status === 401 && !isIA) {  // JWT expiré → retour à la connexion
    localStorage.removeItem('token');
    window.location.href = '/login';
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail ? JSON.stringify(detail.detail) : `HTTP ${response.status}`);
  }
  this.isMockFallback = false;
  this.notify();
  return response.status === 204 ? (undefined as T) : response.json();
}
```

> ⚠️ Le délai actuel de **3 s** (`AbortController`) est trop court pour les routes IA : une génération prend souvent **10 à 20 s**. Ne pas mettre de délai sur `/api/v1/ia/...`, et afficher un indicateur de chargement.

---

## 2. Authentification

### 2.1 — Routes Backend : JWT

```ts
// POST /api/v1/auth/login   corps : { email, password }
async login(email: string, password: string) {
  const res = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error('Email ou mot de passe incorrect');
  const data = await res.json();          // { access_token, token_type: "bearer" }
  localStorage.setItem('token', data.access_token);
}
```

| Route | Rôle |
|---|---|
| `POST /api/v1/auth/login` | Connexion → `access_token` |
| `POST /api/v1/auth/logout` | Déconnexion (le jeton est révoqué côté serveur) |
| `GET /api/v1/auth/me` | Profil connecté (id, nom, email, **rôle**) — pour afficher ou masquer les menus |
| `POST /api/v1/auth/register` | Création de compte |
| `GET/PATCH/DELETE /api/v1/auth/users/{id}`, `GET /auth/users` | Gestion des comptes (administrateur) |

Les routes Backend vérifient aussi le **rôle** : une réponse **403** veut dire « connecté, mais pas autorisé ». Afficher un message, ne pas rediriger vers la connexion.

### 2.2 — Routes IA : jeton interne ⚠️ point ouvert

Les routes `/api/v1/ia/...` **n'acceptent pas le JWT** : elles attendent `Authorization: Bearer <SHARED_INTERNAL_TOKEN>`.

- **En développement local** : mettre le jeton dans `frontend/.env.local` (fichier **non versionné**) : `VITE_IA_TOKEN=...` (le demander au responsable IA). C'est ce que fait la fonction du §1.1.
- **En production, ce n'est pas acceptable** : tout ce qui est dans le code du navigateur est lisible par l'utilisateur. La solution définitive (routes IA acceptant le JWT avec contrôle du rôle, ou passage par le backend) **est à décider avec l'équipe backend/IA**. Ne pas inventer de contournement de votre côté.
- Exception constatée : les routes **TDR** (`/api/v1/ia/tdr/...`) ne demandent actuellement **aucun** jeton.

---

## 3. Tableau des routes Backend (CRUD) — jeton JWT

Les champs marqués `*` sont obligatoires.

### Opportunités (M1)

| Route | Corps / paramètres | Réponse |
|---|---|---|
| `GET /opportunites` | `?statut=&domaine=&skip=&limit=` | **`{ opportunites: [...], total }`** (objet, pas tableau) |
| `POST /opportunites` | `source*` (`TEXTE`\|`PDF`\|`URL`), `contenu*`, `objet`, `budget`, `echeance`, `domaine` | opportunité |
| `GET /opportunites/{id}` · `DELETE /opportunites/{id}` | — | |
| `PUT /opportunites/{id}` | `source*`, `contenu*`, `objet*`, `domaine*`, `budget`, `echeance` | |
| `POST /opportunites/{id}/analyse` | — | analyse IA de l'opportunité |

Valeurs : `domaine` = `DEVOPS`\|`DEVELOPPEMENT`\|`IA`\|`DATA`\|`BUREAUTIQUE`\|`AUTRE` · `statut` = `EN_ATTENTE`\|`ANALYSEE`\|`ARCHIVEE`.
Une opportunité a aussi `score_pertinence` et `date_creation` (lecture seule). Il n'y a **pas** de champs `entreprise`, `contactName`… : ceux du mock sont à abandonner.

### Sessions, séances, présences, participants (M5/M6)

| Route | Corps / paramètres |
|---|---|
| `GET /sessions` | `?formateur_id=&client=&date_debut_min=&date_debut_max=&skip=&limit=` → tableau |
| `POST /sessions` | `titre*`, `date_debut*`, `client`, `date_fin`, `formateur_id` |
| `GET` · `PATCH` · `DELETE /sessions/{id}` | PATCH : mêmes champs, tous optionnels |
| `GET` · `POST /sessions/{id}/seances` | POST : `date*`, `duree`, `theme` |
| `PATCH` · `DELETE /sessions/seances/{seance_id}` | |
| `GET` · `POST /sessions/seances/{seance_id}/presences` | POST : `participant_id*`, `statut*` (`PRESENT`\|`ABSENT`\|`EXCUSE`), `source` (`MANUEL`\|`GOOGLE_FORMS`) |
| `PATCH /sessions/seances/presences/{presence_id}` | `statut*` |
| `POST /sessions/{id}/inscrire` | `participant_id*` |
| `DELETE /sessions/{id}/inscrire/{participant_id}` | |
| `GET /sessions/{id}/participants` | |
| `GET` · `POST /participants`, `GET` · `PATCH` · `DELETE /participants/{id}` | fiche participant |

> Attention : les séances et présences sont **sous `/sessions/seances/...`**, pas sous `/seances/...`. Une présence se marque avec `statut`, **pas** avec un booléen `present`.

### Factures (M7)

| Route | Corps / paramètres |
|---|---|
| `GET /factures` | `?statut=&client=&skip=&limit=` |
| `POST /factures` | `client*`, `montant*`, `tva_taux`, `date_echeance` |
| `GET` · `PATCH` · `DELETE /factures/{id}` | PATCH : `client`, `date_echeance`, `statut` (`EMISE`\|`PARTIELLEMENT_PAYEE`\|`PAYEE`\|`EN_RETARD`\|`ANNULEE`) |
| `POST /factures/{id}/paiements` | `montant*`, `date*`, `mode` |
| `GET /factures/{id}/relances` | historique des relances |
| `GET /exports/comptable` | `?format=csv\|excel\|pdf&statut=&client=&annee=` → **fichier** |

Pour un fichier (export, DOCX, PDF), `window.open` ne transmet pas le jeton : utiliser `fetch` avec l'en-tête, puis `res.blob()` et `URL.createObjectURL(blob)`.

### Préparation : projets, EDT, budget, salles

| Route | Corps / paramètres |
|---|---|
| `GET /projets` | `?statut=&skip=&limit=` |
| `POST /projets` | `titre*`, `client`, `date_debut`, `date_fin`, `statut` (`BROUILLON`\|`EN_COURS`\|`VALIDE`\|`TERMINE`\|`ANNULE`), `notes`, `opportunite_id`, `offre_id` |
| `GET` · `PUT` · `PATCH` · `DELETE /projets/{id}` | DELETE supprime aussi EDT et budget |
| `GET` · `POST /projets/{id}/edt` | POST : `date*`, `heure_debut`, `heure_fin`, `module`, `formateur_id`, `salle_id` |
| `DELETE /projets/{id}/edt/{edt_id}` | |
| `GET` · `POST /projets/{id}/budget` | POST : `cout_formateur`, `cout_salle`, `cout_supports`, `valide` |
| `GET /salles` | `?disponible=true&skip=&limit=` |
| `POST /salles` | `nom*`, `adresse`, `capacite`, `tarif_journalier`, `equipements`, `disponible` |
| `GET` · `PUT` · `PATCH` · `DELETE /salles/{id}` | |

### RH (M4)

| Route | Corps / paramètres |
|---|---|
| `GET /rh/formateurs` | `?specialite=&statut=` |
| `POST /rh/formateurs` | `nom*`, `prenom`, `email`, `telephone`, `adresse`, `specialite` (**texte**, pas tableau), `tarif_journalier`, `notes_internes` |
| `GET` · `PATCH` · `DELETE /rh/formateurs/{id}` | |
| `GET` · `POST /rh/candidats`, `GET` · `PATCH` · `DELETE /rh/candidats/{id}` | |
| `GET` · `POST /rh/candidats/{id}/entretiens`, `GET` · `PATCH` · `DELETE /rh/entretiens/{id}` | |

### Documents et supports RAG

| Route | Corps / paramètres |
|---|---|
| `GET /documents`, `GET` · `DELETE /documents/{id}` | documents générés (TDR, offres, attestations) |
| `GET /documents/{id}/export` | **fichier** |
| `POST /documents/{id}/valider` | validation d'un document |
| `POST /documents/upload` | **multipart** : `fichier*`, `formation_code`, `collection`, `module` → renvoie `chemin_fichier` |
| `GET /documents/rag/supports` | `?formation_code=&statut=` → supports et statut d'indexation |
| `DELETE /documents/rag/supports/{doc_hash}` | |
| `GET /documents/rag/supports/resume-formation?formation_code=` · `GET /documents/rag/supports/bilan-formations` | résumés |

Envoi d'un fichier : utiliser `FormData` **sans** fixer `Content-Type` (le navigateur l'ajoute avec la bonne frontière).

```ts
const form = new FormData();
form.append('fichier', file);                 // le champ s'appelle "fichier"
form.append('formation_code', 'PY-DATA');
const res = await fetch(`${base}/api/v1/documents/upload`, {
  method: 'POST', headers: { Authorization: `Bearer ${jwt}` }, body: form,
});
const { chemin_fichier } = await res.json();
// puis lancer l'indexation (route IA) : POST /api/v1/ia/rag/indexer-document { chemin_fichier, formation_code }
// et suivre l'avancement : GET /api/v1/ia/rag/statut/{doc_hash}
```

### Tableau de bord (M8a)

`GET /dashboard/statistiques` → KPIs, répartition par domaine, facturation. Remplace les quatre méthodes `getKPIs`, `getDomainOpportunities`, `getFacturationStatuts`, `getRecentActivities`.

---

## 4. Adapter les types TypeScript

Les types de `src/types` ont été écrits pour les mocks. Pour chaque écran branché :

1. ouvrir la route dans Swagger, section *Schemas* (ex. `OpportuniteResponse`, `SessionResponse`, `FactureResponse`) ;
2. créer le type correspondant (ex. `OpportuniteApi`) avec **les noms du backend** ;
3. si l'écran a besoin d'autres noms, écrire une petite fonction de conversion (`toOpportuniteCRM(api)`) plutôt que renommer côté backend.

Les dates arrivent en texte ISO (`"2026-11-01"` ou `"2026-11-01T09:00:00+03:00"`) ; les identifiants sont des **UUID** (texte).

---

## 5. Le cycle de validation humaine (HITL) — le même pour tous les agents

```text
1. L'utilisateur clique « Générer »         → POST /api/v1/ia/<module>/generer...
2. La réponse contient un review_id         → { success, review_id, review_status: "pending_review", data }
3. Écran « Validation » : lire le contenu   → GET  /api/v1/ia/formations/reviews/{review_id}
4a. Approuver                               → POST /api/v1/ia/formations/reviews/{review_id}/approve  { reviewer_note? }
4b. Rejeter                                 → POST /api/v1/ia/formations/reviews/{review_id}/reject   { reason* (3 caractères min.) }
5. Si approuvé : enregistrer dans le Backend → POST /api/v1/ia/<module>/synchroniser  { review_id }
```

- Les routes de validation sont **communes à tous les modules**, même si elles sont rangées sous `/ia/formations/`.
- Appeler `/synchroniser` avant l'approbation renvoie **422**. Un second appel avec le même `review_id` ne crée pas de doublon (il renvoie le premier résultat).
- Liste des contenus en attente : `GET /api/v1/ia/formations/pending-reviews?agent_id=&criticity=` → **`{ success, total, filters, reviews: [...] }`** (pas de pagination).
- Statistiques : `GET /api/v1/ia/formations/reviews/stats`.

### Correspondance module → agent → route de synchronisation

| Module | Génération | `agent_id` | Synchronisation après approbation |
|---|---|---|---|
| M1 Veille | `POST /ia/veille/rechercher` `{ query*, domains, min_score, limit }` | `agent_m1_veille` | `POST /ia/veille/synchroniser-backend` `{ review_id* }` |
| M2 TDR | `POST /ia/tdr/generer` `{ client*, objectifs*, public*, duree*, format, budget, lieu, deadline, opportunite_id }` | `agent_m2_tdr` | `POST /ia/tdr/synchroniser` `{ review_id*, opportunite_id }` |
| M3 Offres | `POST /ia/offres/generer-complet` `{ tdr_data*, session_info*, options }` | `agent_m3_complete` | `POST /ia/offres/synchroniser` `{ review_id*, opportunite_id }` |
| Préparation | `POST /ia/preparation/generer-complet` `{ offre_data*, projet_info*, ressources*, options }` | `agent_preparation` | `POST /ia/preparation/synchroniser` `{ review_id*, formateur_id }` |
| M5 Formulaires | `POST /ia/formations/generate-forms` `{ titre*, domaine*, niveau_cible*, date_debut*, date_fin*, lieu*, formateur*, max_participants*, public_cible, supports_resume }` | `agent_1_forms` | `POST /ia/formations/reviews/{review_id}/publish-forms` `{ session_titre }` (Google Forms) |
| M5 Niveaux / satisfaction / présences | `POST /ia/formations/analyze-levels` · `analyze-satisfaction` · `analyze-presences` | `agent_2_levels` · `agent_3_satisfaction` · `agent_4_presences` | `POST /ia/formations/synchroniser/presences` (présences) |
| M6 Attestations | `POST /ia/formations/generate-attestations` | `agent_5_attestations` | `POST /ia/formations/synchroniser/attestations` |
| M5 Rapport final | `POST /ia/formations/generate-report` | `agent_6_report` | — |
| M7 Relance | `POST /ia/facturation/relances/generer` `{ facture_id* }` | `agent_m7_relance` | `POST /ia/facturation/relances/synchroniser` `{ review_id* }` |
| M4 Présélection CV | `POST /ia/rh/preselection` `{ cv_texte*, criteres_poste* (objet) }` | `agent_m4_preselection` | `POST /ia/rh/synchroniser/candidat` `{ review_id* }` |
| M4 Compte rendu d'entretien | `POST /ia/rh/entretien/compte-rendu` | `agent_m4_compte_rendu` | `POST /ia/rh/synchroniser/entretien-cr` |
| C3 Syllabus | `POST /ia/rag/syllabus` | `agent_rag_syllabus` | `POST /ia/rag/syllabus/{review_id}/exporter` (DOCX) |
| C3 Portfolio | `POST /ia/rag/portfolio` | `agent_rag_portfolio` | `POST /ia/rag/portfolio/{review_id}/exporter` (DOCX) |

Pour les corps non détaillés ici, consulter Swagger : chaque route y affiche un exemple.

> M1 : la **détection automatique** (`POST /ia/veille/detecter`, suivi par `GET /ia/veille/detecter/statut`) enregistre directement les opportunités au-dessus du score minimal, **sans** review. Seule la recherche manuelle passe par la validation.

---

## 6. Chat documentaire (RAG)

```ts
// POST /api/v1/ia/rag/chat
{ message: "Quels sont les prérequis de la formation Python ?", conversation_id: null, formation_code: null }
// réponse :
{ conversation_id, type_reponse, reponse, sources: [...], formation_resolue, suggestions: [...], duree_ms }
```

- Renvoyer le `conversation_id` reçu dans les messages suivants : l'assistant garde le contexte.
- Afficher `sources` (fichier, pages) sous la réponse et `suggestions` sous forme de boutons.
- Si aucun support ne traite la question, la réponse l'indique : c'est **normal**, pas une erreur.
- Autres routes utiles : `GET /ia/rag/formations` (formations indexées), `POST /ia/rag/rechercher` (recherche seule), `POST /ia/rag/generer-questions`, `GET /ia/rag/documents/{doc_hash}/fichier` (télécharger la source).

---

## 7. Ordre de travail conseillé

| Étape | Tâche | Écrans débloqués |
|---|---|---|
| 1 | `request()` (§1.1) + connexion JWT (§2.1) + `.env.local` (§2.2) | tous |
| 2 | Tableau de bord sur `/dashboard/statistiques` | Dashboard |
| 3 | Opportunités, sessions, présences, factures, formateurs : lecture puis écriture | M1, M5, M6, M7, M4 |
| 4 | **Écran « Validation »** (liste, détail, approuver, rejeter) | indispensable à tous les agents IA |
| 5 | Boutons « Générer » + synchronisation, module par module (§5) | M1, M2, M3, Préparation, M7, M4 |
| 6 | Supports + chat RAG (§3 Documents, §6) | C3 |

**Critère de fin d'une étape** : l'écran affiche des données réelles quand le serveur tourne, et un **message d'erreur visible** quand une route refuse la requête.

---

## 8. Questions fréquentes

| Symptôme | Cause probable |
|---|---|
| 401 sur une route `/ia/...` alors que je suis connecté | Ces routes attendent le jeton interne, pas le JWT (§2.2) |
| 403 | Rôle insuffisant pour cette action |
| 422 | Corps invalide (champ manquant, mauvaise valeur d'énumération) — le détail indique le champ ; ou synchronisation d'une review non approuvée |
| 404 sur `/seances/...` | Le bon chemin est `/sessions/seances/...` |
| La génération IA « ne répond pas » | Elle prend 10 à 20 s ; vérifier qu'aucun délai de 3 s ne coupe la requête |
| CORS bloqué dans la console | L'origine du frontend (ex. `http://localhost:3000`) doit figurer dans la variable `CORS_ORIGINS` du `.env` du serveur (à demander au responsable backend) |
