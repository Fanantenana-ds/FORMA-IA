# GUIDE D'INTÉGRATION FRONTEND — FORMA-IA

> **Pour qui ?** Le binôme frontend qui branche le React sur le Backend FastAPI.  
> **Backend :** 100% terminé, 169 routes, 717 tests verts.  
> **URL locale :** `http://127.0.0.1:8000`  
> **Dernière mise à jour :** 2026-10-06

---

## AVANT TOUT — Les 3 types de routes

Chaque route du backend appartient à l'une de ces 3 catégories. Tu vas voir ces icônes partout dans ce guide.

| Icône | Qui appelle | Quand |
|---|---|---|
| 🟢 **VERT** | Le frontend appelle directement | À tout moment |
| 🔵 **BLEU** | **Jamais le frontend** — réservé aux orchestrateurs IA internes | — |
| 🟡 **JAUNE** | Le frontend appelle, mais dans un ordre précis | Cycle HITL uniquement (voir Section 4) |

**Règle simple :** si c'est sous `/ia/*/generer-*` ou `/ia/*/analyser-*` → c'est 🔵 BLEU, ne jamais l'appeler depuis le frontend sans passer par le cycle HITL.

---

## ÉTAPE 0 — Comprendre la liaison Backend ↔ IA

> **C'est la partie la plus importante à lire avant de coder quoi que ce soit.**

Le projet FORMA-IA a **deux couches** : le **Backend** (données métier) et le module **IA** (génération de contenu). Elles ne sont pas indépendantes — les agents IA lisent et écrivent dans le Backend.

### Schéma général

```
FRONTEND
   │
   ├── 🟢 CRUD direct → Backend (routes /api/v1/sessions, /opportunites, etc.)
   │         ↓
   │    Données stockées en base (PostgreSQL)
   │
   └── 🟡 Déclenchement IA → Module IA (routes /api/v1/ia/...)
             ↓
        Agent IA génère un contenu
             ↓
        Review HITL créée (en attente de validation humaine)
             ↓
        Utilisateur approuve via HitlReviewView
             ↓
        🟡 Synchronisation → contenu IA écrit dans le Backend
```

### La règle d'or : un `id` Backend → un agent IA

Quand tu déclenches un agent IA, tu **passes toujours un `id` Backend** pour que l'agent sache sur quoi travailler.

| Tu veux générer… | Tu passes à l'agent… | Qui vient de… |
|---|---|---|
| Un TDR | `opportunite_id` | `GET /opportunites` → `data[n].id` |
| Une offre complète | `tdr_data` + `session_info` | `GET /documents` + `GET /sessions` |
| Une préparation (EDT+budget) | `offre_data` + `projet_info` + `ressources` | `GET /offres` + `GET /projets` |
| Des formulaires M5 | `session_id` ou les infos session | `GET /sessions` → `data[n]` |
| Une relance facture | `facture_id` | `GET /factures` → `data[n].id` |
| Une présélection CV | `cv_texte` + `criteres_poste` | Saisi par l'utilisateur |

**Exemple concret — M2 TDR :**

```
1. Frontend charge la liste des opportunités : GET /api/v1/opportunites
2. Utilisateur sélectionne l'opportunité id="opp-42"
3. Frontend appelle : POST /api/v1/ia/tdr/generer  Body: { opportunite_id: "opp-42", ... }
4. IA génère le TDR → retourne { review_id: "HITL-A2T-0003" }
5. Utilisateur approuve dans HitlReviewView
6. Frontend appelle : POST /api/v1/ia/tdr/synchroniser  Body: { review_id: "HITL-A2T-0003", opportunite_id: "opp-42" }
7. Le TDR est maintenant dans GET /api/v1/documents
```

---

## ÉTAPE 1 — Débloquer tout le reste (à faire en premier)

> ⚠️ **Tant que cette étape n'est pas faite, AUCUNE donnée réelle ne sera visible.** Les données affichées maintenant sont des mocks codés en dur.

### Problème actuel dans `api.ts`

```ts
// ❌ Ce flag bloque tout appel réel — à supprimer
isMockFallback = true
```

```ts
// ❌ Aucun header Authorization envoyé → 401 sur toutes les routes
fetch(url, { method, body })
```

### Ce qu'il faut faire (dans l'ordre)

**1.1 — Supprimer le mock dans `api.ts`**

```ts
// Avant
isMockFallback = true  // ← supprimer cette ligne ou la passer à false
```

**1.2 — Ajouter la méthode `login()` dans `api.ts`**

```ts
async login(email: string, password: string): Promise<string> {
  const res = await fetch('http://127.0.0.1:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await res.json()
  // data = { access_token: "eyJ...", token_type: "bearer" }
  localStorage.setItem('token', data.access_token)
  return data.access_token
}
```

**1.3 — Envoyer le token sur tous les appels dans `request()`**

```ts
private async request(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...options.headers,
  }
  const res = await fetch(`http://127.0.0.1:8000/api/v1${url}`, {
    ...options,
    headers,
  })
  // Rediriger vers login si le token est expiré
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    return
  }
  return res.json()
}
```

**1.4 — Brancher `AuthPage.tsx` sur le Backend**

```ts
// Dans AuthPage.tsx, au clic "Se connecter"
const handleLogin = async () => {
  try {
    await apiService.login(email, password)
    navigate('/dashboard')
  } catch {
    setError('Email ou mot de passe incorrect')
  }
}
```

**1.5 — Tester que ça marche**

```
POST http://127.0.0.1:8000/api/v1/auth/login
Body: { "email": "test@forma-ia.fr", "password": "votre_mdp" }
→ Réponse attendue: { "access_token": "eyJ...", "token_type": "bearer" }
```

Si tu reçois le token → l'étape 1 est terminée. Les appels suivants doivent fonctionner.

---

## ÉTAPE 2 — Corriger les vues existantes

### 2.1 — `VeilleMarcheView.tsx` — Supprimer le mock

**Problème :** `getVeilles()` dans `api.ts` retourne toujours un mock, jamais des données réelles.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — remplacer la fonction getVeilles()
async getOpportunites() {
  return this.request('/opportunites')
  // → retourne la liste réelle depuis le backend
}
```

```ts
// Dans VeilleMarcheView.tsx
useEffect(() => {
  apiService.getOpportunites().then(setOpportunites)
}, [])
```

**Bouton "Accepter un marché" :**

```ts
// Mettre à jour le statut d'une opportunité
async updateOpportunite(id: string, data: Partial<Opportunite>) {
  return this.request(`/opportunites/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}
```

**Bouton "Rechercher avec l'IA" → déclenche la veille :**

> ⚠️ Cette route est 🔵 BLEU — elle génère un contenu IA qui doit passer par validation humaine (HITL).  
> Voir Section 4 pour comprendre le cycle HITL complet.

```ts
// Appeler la recherche IA → retourne un review_id
async rechercherVeille(query: string) {
  return this.request('/ia/veille/rechercher', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
  // → { success: true, data: { opportunities: [...] } }
  // Ensuite : afficher les résultats → l'utilisateur approuve → synchroniser
}
```

---

### 2.2 — `OpportunitesCrmView.tsx` — Brancher le CRUD Backend

**Problème :** La vue affiche des données codées en dur (`DEFAULT_ACCEPTED_MARKETS`). Elle ne lit pas le Backend du tout.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter ces fonctions
async getOpportunites() {
  return this.request('/opportunites')
}
async createOpportunite(data: CreateOpportuniteDto) {
  return this.request('/opportunites', { method: 'POST', body: JSON.stringify(data) })
}
async updateOpportunite(id: string, data: Partial<Opportunite>) {
  return this.request(`/opportunites/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}
async deleteOpportunite(id: string) {
  return this.request(`/opportunites/${id}`, { method: 'DELETE' })
}
```

```ts
// Dans OpportunitesCrmView.tsx
useEffect(() => {
  apiService.getOpportunites().then(setOpportunites)
}, [])
```

**Format d'une opportunité :**

```ts
// POST /api/v1/opportunites
{
  entreprise: "Nom de l'entreprise",
  contact: "Nom du contact",
  domaine: "Informatique",
  statut: "PROSPECT",        // PROSPECT | QUALIFICATION | PROPOSITION | NEGOCIE | GAGNE | PERDU
  // champs optionnels :
  email?: string,
  telephone?: string,
  budget_estime?: number,
}
```

---

### 2.3 — `SessionsGroupesView.tsx` — Sauvegarder les participants

**Problème :** Le bouton "+ Ajouter un participant" crée un objet local avec `setPresencesList`. Rien n'est envoyé au Backend.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter
async inscrireParticipant(sessionId: string, participantId: string) {
  return this.request(`/sessions/${sessionId}/inscrire`, {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId }),
  })
}
async retirerParticipant(sessionId: string, participantId: string) {
  return this.request(`/sessions/${sessionId}/inscrire/${participantId}`, {
    method: 'DELETE',
  })
}
async getParticipants(sessionId: string) {
  return this.request(`/sessions/${sessionId}/participants`)
}
```

```ts
// Dans SessionsGroupesView.tsx — remplacer setPresencesList par :
const handleAjouterParticipant = async (participantId: string) => {
  await apiService.inscrireParticipant(session.id, participantId)
  const updated = await apiService.getParticipants(session.id)
  setParticipants(updated)
}
```

**Modifier / supprimer une session :**

```ts
async updateSession(id: string, data: Partial<Session>) {
  return this.request(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async deleteSession(id: string) {
  return this.request(`/sessions/${id}`, { method: 'DELETE' })
}
```

---

### 2.4 — `SuiviPresencesView.tsx` — Remplacer la gestion locale

**Problème :** Marquer présent/absent met à jour un état React local. Rien n'est sauvegardé.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter
async getPresences(seanceId: string) {
  return this.request(`/seances/${seanceId}/presences`)
}
async enregistrerPresence(seanceId: string, data: { participant_id: string, present: boolean, motif_absence?: string }) {
  return this.request(`/seances/${seanceId}/presences`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
async corrigerPresence(presenceId: string, data: { present?: boolean, motif_absence?: string }) {
  return this.request(`/seances/presences/${presenceId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}
```

```ts
// Dans SuiviPresencesView.tsx — remplacer le state local
const handleMarquerPresence = async (participantId: string, present: boolean) => {
  await apiService.enregistrerPresence(seanceId, { participant_id: participantId, present })
  const updated = await apiService.getPresences(seanceId)
  setPresences(updated)
}
```

---

### 2.5 — `FormateursStaffView.tsx` — Persister la création

**Problème :** Le bouton "Ajouter un formateur" appelle `onAddFormateur(created)` (callback local). Aucun appel API n'est fait.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter
async createFormateur(data: CreateFormateurDto) {
  return this.request('/rh/formateurs', { method: 'POST', body: JSON.stringify(data) })
}
async updateFormateur(id: string, data: Partial<Formateur>) {
  return this.request(`/rh/formateurs/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async deleteFormateur(id: string) {
  return this.request(`/rh/formateurs/${id}`, { method: 'DELETE' })
}
```

```ts
// Format de création d'un formateur
{
  nom: "Jean Dupont",
  email: "jean@example.com",
  specialites: ["Python", "Data Science"],
  tarif_journalier: 800,
}
```

```ts
// Dans FormateursStaffView.tsx — remplacer le callback par un vrai appel API
const handleCreateFormateur = async (data: CreateFormateurDto) => {
  const created = await apiService.createFormateur(data)
  setFormateurs(prev => [...prev, created])
}
```

---

### 2.6 — `FacturationDevisView.tsx` — Compléter les fonctionnalités

**Problème :** La lecture et la création fonctionnent. Il manque : modifier le statut, enregistrer un paiement, générer une relance, exporter.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter
async updateFacture(id: string, data: Partial<Facture>) {
  return this.request(`/factures/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async enregistrerPaiement(factureId: string, data: { montant: number, date_paiement: string, mode: string }) {
  return this.request(`/factures/${factureId}/paiements`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
async exportComptable(format: 'csv' | 'xlsx' | 'pdf' = 'csv') {
  window.open(`http://127.0.0.1:8000/api/v1/exports?format=${format}`, '_blank')
}
```

**Générer une relance IA :**

> ⚠️ Route 🔵 BLEU — déclenche un agent IA, retourne un `review_id`.  
> L'utilisateur doit approuver avant que la relance soit envoyée. Voir Section 4.

```ts
async genererRelance(factureId: string) {
  return this.request('/ia/facturation/relances/generer', {
    method: 'POST',
    body: JSON.stringify({ facture_id: factureId }),
  })
  // → { review_id: "...", necessaire: true, niveau: "FERME" }
  // Ensuite : rediriger vers HitlReviewView pour approbation
}
```

---

## ÉTAPE 3 — Créer les vues manquantes

### 3.1 — `DocumentsView.tsx` — Gestion des documents

Cette vue n'existe pas encore. Elle doit permettre d'uploader et de consulter les documents.

**Endpoints à utiliser :**

```ts
// Lister les documents validés
GET /api/v1/documents
→ [{ id, titre, type, statut, created_at }]

// Uploader un support de formation (PDF, DOCX, PPTX)
POST /api/v1/documents/supports   (multipart/form-data)
→ { id, titre, statut_indexation }

// Lister les supports + leur statut d'indexation RAG
GET /api/v1/documents/supports
→ [{ id, fichier, statut_indexation: "indexé" | "en_cours" | "erreur" }]

// Télécharger un document
GET /api/v1/documents/{id}/export
→ Fichier DOCX ou PDF

// Supprimer
DELETE /api/v1/documents/{id}
```

**Structure minimale de la vue :**

```tsx
function DocumentsView() {
  const [documents, setDocuments] = useState([])

  useEffect(() => {
    apiService.request('/documents').then(setDocuments)
  }, [])

  const handleUpload = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('token')
    await fetch('http://127.0.0.1:8000/api/v1/documents/supports', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })
    // Recharger la liste
  }

  return (
    <div>
      <input type="file" onChange={e => handleUpload(e.target.files[0])} />
      {documents.map(doc => <div key={doc.id}>{doc.titre}</div>)}
    </div>
  )
}
```

---

### 3.2 — `PreparationView.tsx` — Projets, salles, EDT, budget

**Endpoints à utiliser :**

```ts
// Projets
GET    /api/v1/projets                   → liste des projets
POST   /api/v1/projets                   → créer un projet
PATCH  /api/v1/projets/{id}              → modifier
DELETE /api/v1/projets/{id}              → supprimer (cascade EDT + budget)

// Salles
GET    /api/v1/salles?disponible=true    → lister les salles disponibles
POST   /api/v1/salles                    → créer une salle

// EDT d'un projet
GET    /api/v1/projets/{id}/edt         → voir l'EDT
POST   /api/v1/projets/{id}/edt         → ajouter une séance
DELETE /api/v1/projets/{id}/edt/{edt_id} → supprimer une séance

// Budget d'un projet
GET    /api/v1/projets/{id}/budget      → voir le budget
POST   /api/v1/projets/{id}/budget      → créer / remplacer le budget
```

**Format pour créer un projet :**

```ts
{
  titre: "Formation Python Avancé",
  client: "Entreprise XYZ",
  date_debut: "2026-11-01",
  date_fin: "2026-11-05",
  statut: "BROUILLON",  // BROUILLON | EN_COURS | VALIDE | TERMINE | ANNULE
}
```

**Format pour ajouter une séance à l'EDT :**

```ts
{
  date: "2026-11-01",
  heure_debut: "09:00",
  heure_fin: "12:00",
  titre_module: "Introduction à Python",
}
```

---

### 3.3 — `HitlReviewView.tsx` — Validation humaine des contenus IA

> **Cette vue est critique.** Sans elle, aucun contenu généré par l'IA ne peut être sauvegardé dans le Backend.

**Ce que cette vue doit faire :**
1. Afficher la liste des contenus IA en attente d'approbation
2. Permettre de voir le détail de chaque contenu
3. Permettre d'approuver ou rejeter

**Endpoints à utiliser :**

```ts
// 1. Lister les reviews en attente
GET /api/v1/ia/formations/pending-reviews?skip=0&limit=20
→ [{ review_id, agent_id, statut: "pending_review", created_at }]

// Filtrer par module :
?agent_id=agent_m1_veille        → veille marché
?agent_id=agent_m2_tdr           → TDR
?agent_id=agent_m3_complete      → offres
?agent_id=agent_preparation      → préparation
?agent_id=agent_1_forms          → formulaires M5
?agent_id=agent_m7_relance       → relances factures
?agent_id=agent_m4_preselection  → présélection CV

// 2. Voir le contenu d'un review
GET /api/v1/ia/formations/reviews/{review_id}
→ { review_id, agent_id, contenu_genere: {...}, statut }

// 3. Approuver
POST /api/v1/ia/formations/reviews/{review_id}/approve
Body: { commentaire: "OK pour envoi" }  // optionnel
→ { review_id, status: "approved" }

// 4. Rejeter avec feedback
POST /api/v1/ia/formations/reviews/{review_id}/reject
Body: { feedback: "Le ton est trop formel, reformuler" }  // minimum 10 caractères
→ { review_id, status: "rejected" }
```

**Structure minimale de la vue :**

```tsx
function HitlReviewView() {
  const [reviews, setReviews] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    apiService.request('/ia/formations/pending-reviews').then(setReviews)
  }, [])

  const handleApprove = async (reviewId: string) => {
    await apiService.request(`/ia/formations/reviews/${reviewId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ commentaire: '' }),
    })
    // Après approbation → appeler la route /synchroniser du module concerné
    // Voir Section 4 pour savoir quelle route appeler selon le module
    setReviews(prev => prev.filter(r => r.review_id !== reviewId))
  }

  const handleReject = async (reviewId: string, feedback: string) => {
    await apiService.request(`/ia/formations/reviews/${reviewId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ feedback }),
    })
    setReviews(prev => prev.filter(r => r.review_id !== reviewId))
  }

  return (
    <div>
      <h2>Contenus IA en attente ({reviews.length})</h2>
      {reviews.map(r => (
        <div key={r.review_id}>
          <span>{r.agent_id} — {r.created_at}</span>
          <button onClick={() => setSelected(r)}>Voir</button>
          <button onClick={() => handleApprove(r.review_id)}>Approuver ✓</button>
          <button onClick={() => handleReject(r.review_id, 'feedback...')}>Rejeter ✗</button>
        </div>
      ))}
    </div>
  )
}
```

---

## ÉTAPE 4 — Brancher les agents IA (cycle HITL)

> **Important :** chaque agent IA suit le même cycle. Apprends-le une fois, il s'applique partout.

### Le cycle HITL en 5 étapes

```
Étape 1 : L'utilisateur clique "Générer"
           ↓
Étape 2 : Frontend appelle POST /ia/.../generer-*
           ↓
Étape 3 : Backend retourne { review_id: "abc123", requires_human_action: true }
           ↓
Étape 4 : Frontend redirige vers HitlReviewView
          L'utilisateur lit le contenu généré et décide : Approuver ou Rejeter
           ↓
Étape 5 : Si Approuvé → Frontend appelle POST /ia/.../synchroniser avec { review_id: "abc123" }
          → Le contenu est sauvegardé dans le Backend
```

**⚠️ Règle absolue :** Ne jamais appeler `/synchroniser` sans un `review_id` avec statut `"approved"`. Le Backend retourne HTTP 422 si la review n'est pas approuvée.

---

### Cycle par module

#### M1 — Veille marché

```ts
// Étape 2
POST /api/v1/ia/veille/rechercher
Body: { query: "formation Python entreprises", min_score: 0.5, limit: 10 }
→ { success: true, data: { opportunities: [...] } }

// Étape 5 (après approbation)
POST /api/v1/ia/veille/synchroniser-backend
Body: { review_id: "abc123" }
→ { success: true }
// → L'opportunité est créée dans /api/v1/opportunites
```

---

#### M2 — Génération de TDR

```ts
// Pré-remplir depuis une opportunité existante
GET /api/v1/ia/tdr/from-opportunite/{opportunite_id}
→ { brief: { client, domaine, objectifs, ... }, opportunite }

// Étape 2 — générer le TDR
POST /api/v1/ia/tdr/generer
Body: {
  client: "Entreprise XYZ",
  domaine: "Développement logiciel",
  objectifs: "...",
  public_cible: "Développeurs juniors",
  duree_jours: 3,
  lieu: "Paris",
}
→ { review_id: "abc123", data: {...}, files: ["tdr_xyz.docx"] }

// Étape 5 (après approbation)
POST /api/v1/ia/tdr/synchroniser
Body: { review_id: "abc123", opportunite_id: "opp_id" }
→ { success: true }
// → Le TDR est créé dans /api/v1/documents
```

---

#### M3 — Génération d'offre

```ts
// Étape 2
POST /api/v1/ia/offres/generer-complet
Body: {
  tdr_data: { client, domaine, objectifs, public_cible, duree_jours },
  session_info: { titre, lieu, formateur },
  options: {
    nb_participants: 10,
    type_formateur: "interne",
    type_salle: "propre",
    tva_applicable: true,
  }
}
→ { review_id: "abc123", requires_human_action: true }

// Étape 5 (après approbation)
POST /api/v1/ia/offres/synchroniser
Body: { review_id: "abc123", opportunite_id: "opp_id" }
→ { success: true }
// → L'offre est créée dans /api/v1/offres
```

---

#### PREP — Génération de préparation (EDT + budget)

```ts
// Étape 2
POST /api/v1/ia/preparation/generer-complet
Body: {
  offre_data: { titre, modules: ["Module 1", "Module 2"], duree_jours: 3 },
  projet_info: { client, date_debut, date_fin },
  ressources: {
    formateur: { nom, tarif_journalier: 800 },
    salle: { nom, tarif_journalier: 200 },
  },
  options: { nb_participants: 12 }
}
→ { review_id: "abc123", requires_human_action: true }

// Étape 5 (après approbation)
POST /api/v1/ia/preparation/synchroniser
Body: { review_id: "abc123", formateur_id: "form_id" }
→ { success: true }
// → La session est créée dans /api/v1/sessions
```

---

#### M5 — Formulaires d'évaluation Google Forms

> **Ce module a un cycle plus long que les autres** car il implique Google Forms et les réponses des participants.

```
Étape 1 : Générer le contenu des 4 formulaires (IA) → HITL
Étape 2 : Créer les formulaires réels sur Google Forms
Étape 3 : Les participants remplissent les formulaires (sur Google)
Étape 4 : Récupérer les réponses depuis Google
Étape 5 : Analyser les réponses (agents 2, 3, 4)
```

**Étape A — Générer le contenu IA (HITL)**

```ts
// 1. Appeler l'agent 1 → génère le contenu des 4 formulaires
POST /api/v1/ia/formations/generate-forms
Body: {
  titre: "Python Avancé",
  domaine: "Informatique",
  niveau_cible: "Intermédiaire",
  date_debut: "2026-11-01",
  date_fin: "2026-11-05",
  lieu: "Paris",
  formateur: "Jean Dupont",
  max_participants: 12,
}
→ { review_id: "HITL-A1F-0001", requires_human_action: true }

// 2. L'utilisateur approuve dans HitlReviewView
POST /api/v1/ia/formations/reviews/HITL-A1F-0001/approve
```

**Étape B — Créer les formulaires sur Google Forms**

```ts
// 3. Après approbation → créer les 4 formulaires Google réels
//    ⚠️ Nécessite GOOGLE_CREDENTIALS_PATH configuré côté serveur
POST /api/v1/ia/formations/creer-formulaires
Body: {
  review_id: "HITL-A1F-0001",
  session_title: "Python Avancé — Nov 2026",  // préfixe dans les noms de formulaires
}
→ {
    success: true,
    data: {
      forms: {
        inscription:  { form_id: "1abc...", responder_uri: "https://docs.google.com/forms/..." },
        test_avant:   { form_id: "1def...", responder_uri: "https://docs.google.com/forms/..." },
        test_apres:   { form_id: "1ghi...", responder_uri: "https://docs.google.com/forms/..." },
        satisfaction: { form_id: "1jkl...", responder_uri: "https://docs.google.com/forms/..." },
      },
      total_created: 4,
    }
  }

// ✅ Les form_id sont automatiquement stockés dans la review côté backend
//    Tu n'as PAS besoin de les sauvegarder toi-même
```

> **Ce que le frontend doit afficher :** les 4 liens `responder_uri` à distribuer aux participants (par email, QR code, etc.).

**Étape C — Récupérer les réponses des participants**

```ts
// 4. Une fois que les participants ont rempli les formulaires
//    → récupérer toutes les réponses en une seule route
POST /api/v1/ia/formations/sync-responses
Body: {
  review_id: "HITL-A1F-0001",
  // sections optionnel — si absent, récupère toutes les sections
  // sections: ["satisfaction", "test_avant"]
}
→ {
    success: true,
    data: {
      review_id: "HITL-A1F-0001",
      total_responses: 15,
      sections: {
        inscription: {
          form_id: "1abc...",
          count: 12,
          responses: [
            { response_id: "...", submitted_at: "2026-11-01T09:15:00Z", answers: { "q_id_1": "Jean Dupont", ... } },
            ...
          ]
        },
        test_avant:   { form_id: "1def...", count: 12, responses: [...] },
        test_apres:   { form_id: "1ghi...", count: 10, responses: [...] },
        satisfaction: { form_id: "1jkl...", count: 11, responses: [...] },
      }
    }
  }
```

**Étape D — Analyser les réponses (passer aux agents IA)**

```ts
// 5. Passer les réponses test_avant à l'agent 2 (niveaux)
POST /api/v1/ia/formations/analyze-levels
Body: {
  session_info: { titre: "Python Avancé", niveau_cible: "Intermédiaire" },
  responses: data.sections.test_avant.responses,  // ← extrait de sync-responses
}
→ { review_id: "HITL-A2L-0001", requires_human_action: true }

// 6. Passer les réponses satisfaction à l'agent 3
POST /api/v1/ia/formations/analyze-satisfaction
Body: {
  session_info: { titre: "Python Avancé" },
  responses: data.sections.satisfaction.responses,  // ← extrait de sync-responses
}
→ { review_id: "HITL-A3S-0001", requires_human_action: true }

// 7. Passer les réponses inscription à l'agent 4 (présences)
POST /api/v1/ia/formations/analyze-presences
Body: {
  session_info: { titre: "Python Avancé" },
  participants: data.sections.inscription.responses,  // ← extrait de sync-responses
}
→ { review_id: "HITL-A4P-0001", requires_human_action: true }
```

**Résumé du flux M5 complet :**

```
generate-forms → [HITL approve] → creer-formulaires
                                        ↓
                               Partager les liens Google aux participants
                                        ↓
                               [Participants remplissent]
                                        ↓
                               sync-responses (récupère tout)
                                        ↓
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
             analyze-levels   analyze-satisfaction  analyze-presences
             [HITL approve]    [HITL approve]        [HITL approve]
```

---

#### M7 — Relance de facture

```ts
// Étape 2
POST /api/v1/ia/facturation/relances/generer
Body: { facture_id: "fact_id" }
→ { review_id: "abc123", necessaire: true, niveau: "FERME" }

// Étape 5 (après approbation)
POST /api/v1/ia/facturation/relances/synchroniser
Body: { review_id: "abc123" }
→ { success: true }
// → La relance est enregistrée dans /api/v1/factures/{id}/relances
```

---

#### M4 — Présélection CV

```ts
// Étape 2
POST /api/v1/ia/rh/preselection
Body: {
  cv_texte: "Nom: ... Expériences: ...",
  criteres_poste: "3 ans Python, expérience formation",
}
→ { review_id: "abc123" }

// Étape 5 (après approbation)
POST /api/v1/ia/rh/synchroniser/candidat
Body: { review_id: "abc123" }
→ { success: true }
// → Le candidat est créé dans /api/v1/rh/candidats
```

---

#### C3 — Chat avec les documents (RAG)

```ts
// Poser une question sur les formations indexées
POST /api/v1/ia/rag/chat
Body: {
  question: "Quels sont les prérequis de la formation Python ?",
  session_id: "optionnel"
}
→ { answer: "Les prérequis sont...", sources: [{ fichier, page }] }

// Vérifier quel health check passer pour le chat RAG
GET /api/v1/ia/rag/health
→ { success: true, nb_docs_indexes: 3 }
```

---

## RÉFÉRENCE RAPIDE — Tous les endpoints par catégorie

### Authentification

| Endpoint | Méthode | Rôle | Body | Réponse |
|---|---|---|---|---|
| `/auth/login` | POST | Connexion | `{email, password}` | `{access_token}` |
| `/auth/logout` | POST | Déconnexion | header `Authorization` | `{message}` |
| `/auth/me` | GET | Mon profil | — | `UserResponse` |
| `/auth/register` | POST | Créer compte | `{email, password, nom, role}` | `UserResponse` |

---

### Opportunités (M1)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/opportunites` | GET | Lister |
| 🟢 `/opportunites` | POST | Créer |
| 🟢 `/opportunites/{id}` | GET | Lire |
| 🟢 `/opportunites/{id}` | PUT | Remplacer |
| 🟢 `/opportunites/{id}` | DELETE | Supprimer |
| 🔵 `/ia/veille/rechercher` | POST | Recherche IA → review_id |
| 🔵 `/ia/veille/detecter` | POST | Détection auto → review_id |
| 🟡 `/ia/veille/synchroniser-backend` | POST | Sync après approbation |

---

### Documents (M2)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/documents` | GET | Lister les documents |
| 🟢 `/documents/{id}/export` | GET | Télécharger |
| 🟢 `/documents/{id}` | DELETE | Supprimer |
| 🟢 `/documents/supports` | POST | Upload support RAG |
| 🟢 `/documents/supports` | GET | Lister supports + statut indexation |
| 🔵 `/ia/tdr/generer` | POST | Générer TDR → review_id |
| 🟡 `/ia/tdr/from-opportunite/{id}` | GET | Pré-remplir brief TDR |
| 🟡 `/ia/tdr/synchroniser` | POST | Sync après approbation |
| 🟡 `/ia/tdr/download/{filename}` | GET | Télécharger le TDR généré |

---

### Offres (M3)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/offres` | GET | Lister |
| 🟢 `/offres` | POST | Créer |
| 🟢 `/offres/{id}` | GET/PUT/PATCH/DELETE | CRUD |
| 🔵 `/ia/offres/generer-complet` | POST | Générer → review_id |
| 🟡 `/ia/offres/synchroniser` | POST | Sync après approbation |

---

### Préparation — Projets / Salles / EDT / Budget

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/projets` | GET/POST | Lister / Créer |
| 🟢 `/projets/{id}` | GET/PUT/PATCH/DELETE | CRUD |
| 🟢 `/projets/{id}/edt` | GET/POST | Voir / Ajouter séance EDT |
| 🟢 `/projets/{id}/edt/{edt_id}` | DELETE | Supprimer séance |
| 🟢 `/projets/{id}/budget` | GET/POST | Voir / Créer budget |
| 🟢 `/salles` | GET/POST | Lister / Créer |
| 🟢 `/salles/{id}` | GET/PUT/PATCH/DELETE | CRUD |
| 🔵 `/ia/preparation/generer-complet` | POST | Générer → review_id |
| 🟡 `/ia/preparation/synchroniser` | POST | Sync après approbation |

---

### Sessions / Présences (M5/M6)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/sessions` | GET/POST | Lister / Créer |
| 🟢 `/sessions/{id}` | GET/PATCH/DELETE | CRUD |
| 🟢 `/sessions/{id}/seances` | GET/POST | Séances d'une session |
| 🟢 `/seances/{id}` | PATCH/DELETE | Modifier / Supprimer séance |
| 🟢 `/seances/{id}/presences` | GET/POST | Présences d'une séance |
| 🟢 `/seances/presences/{id}` | PATCH | Corriger une présence |
| 🟢 `/sessions/{id}/inscrire` | POST | Inscrire un participant |
| 🟢 `/sessions/{id}/inscrire/{pid}` | DELETE | Désinscrire |
| 🟢 `/sessions/{id}/participants` | GET | Lister les participants |
| 🔵 `/ia/formations/generate-forms` | POST | Générer contenu 4 formulaires → review_id |
| 🟡 `/ia/formations/creer-formulaires` | POST | Créer les formulaires Google réels (après approbation) |
| 🟡 `/ia/formations/sync-responses` | POST | Récupérer les réponses des participants depuis Google |
| 🔵 `/ia/formations/analyze-levels` | POST | Analyser niveaux → review_id |
| 🔵 `/ia/formations/analyze-satisfaction` | POST | Analyser satisfaction → review_id |
| 🔵 `/ia/formations/analyze-presences` | POST | Analyser présences → review_id |
| 🔵 `/ia/formations/generate-attestations` | POST | Générer attestations → review_id |

---

### Facturation (M7)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/factures` | GET/POST | Lister / Créer |
| 🟢 `/factures/{id}` | GET/PATCH/DELETE | CRUD |
| 🟢 `/factures/{id}/paiements` | POST | Enregistrer paiement |
| 🟢 `/exports` | GET | Export comptable (`?format=csv\|xlsx\|pdf`) |
| 🔵 `/ia/facturation/relances/generer` | POST | Générer relance → review_id |
| 🟡 `/ia/facturation/relances/synchroniser` | POST | Sync après approbation |

---

### RH — Formateurs, Candidats, Entretiens (M4)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/rh/formateurs` | GET/POST | Lister / Créer |
| 🟢 `/rh/formateurs/{id}` | GET/PATCH/DELETE | CRUD |
| 🟢 `/rh/candidats` | GET/POST | Lister / Créer |
| 🟢 `/rh/candidats/{id}` | GET/PATCH/DELETE | CRUD |
| 🟢 `/rh/candidats/{id}/entretiens` | GET/POST | Entretiens d'un candidat |
| 🟢 `/rh/entretiens/{id}` | GET/PATCH/DELETE | CRUD |
| 🔵 `/ia/rh/preselection` | POST | Analyser CV → review_id |
| 🔵 `/ia/rh/entretien/compte-rendu` | POST | CR entretien → review_id |
| 🟡 `/ia/rh/synchroniser/candidat` | POST | Sync après approbation |
| 🟡 `/ia/rh/synchroniser/entretien-cr` | POST | Sync CR entretien |

---

### HITL — Validation humaine (global)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟡 `/ia/formations/pending-reviews` | GET | Lister les reviews en attente |
| 🟡 `/ia/formations/reviews/{id}` | GET | Voir le contenu d'un review |
| 🟡 `/ia/formations/reviews/{id}/approve` | POST | Approuver |
| 🟡 `/ia/formations/reviews/{id}/reject` | POST | Rejeter avec feedback |
| 🟡 `/ia/formations/reviews/stats` | GET | Statistiques |

---

### RAG — Chat avec documents (C3)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🔵 `/ia/rag/chat` | POST | Chat avec les supports indexés |
| 🔵 `/ia/rag/indexer` | POST | Indexer un document |
| 🟡 `/ia/rag/statut/{doc_hash}` | GET | Statut d'indexation |
| 🟡 `/ia/rag/formations` | GET | Lister les formations indexées |
| 🔵 `/ia/rag/portfolio` | POST | Générer portfolio → review_id |
| 🟡 `/ia/rag/portfolio/{review_id}/exporter` | POST | Export DOCX portfolio approuvé |

---

### Dashboard (M8a)

| Endpoint | Méthode | Rôle |
|---|---|---|
| 🟢 `/dashboard/statistiques` | GET | KPIs globaux, domaines, facturation |

---

## RÉCAPITULATIF — Ce qui est fait vs. ce qui reste

| Module | Fichier | État actuel | Ce qui manque |
|---|---|---|---|
| Auth | `api.ts` + `AuthPage.tsx` | ❌ Non branché | Étape 1 complète |
| Veille | `VeilleMarcheView.tsx` | ❌ Mock uniquement | Brancher `/opportunites` |
| Opportunités | `OpportunitesCrmView.tsx` | ❌ Données codées en dur | CRUD complet Backend |
| Sessions (liste) | `SessionsGroupesView.tsx` | ✅ Lecture OK via props | — |
| Sessions (inscriptions) | `SessionsGroupesView.tsx` | ❌ Local uniquement | Appels API inscription |
| Présences | `SuiviPresencesView.tsx` | ❌ Local uniquement | Appels `/seances/{id}/presences` |
| Formateurs (lecture) | `FormateursStaffView.tsx` | ✅ GET branché | — |
| Formateurs (écriture) | `FormateursStaffView.tsx` | ❌ Callback local | Appels POST/PATCH/DELETE |
| Factures (lecture + création) | `FacturationDevisView.tsx` | ✅ GET + POST branchés | Paiements, relance, export |
| Documents | — | ❌ Vue inexistante | Créer `DocumentsView.tsx` |
| Préparation | — | ❌ Vue inexistante | Créer `PreparationView.tsx` |
| Validation HITL | — | ❌ Vue inexistante | Créer `HitlReviewView.tsx` (priorité max) |
| Formulaires M5 | — | ❌ Non branché | Cycle complet Section 4 M5 |
| Agents IA (boutons) | Toutes les vues | ❌ Absent partout | Étape 4 |

---

## ORDRE RECOMMANDÉ (planning sur 2 semaines)

| Jour | Tâche | Impact |
|---|---|---|
| J1 | **Étape 1** — Auth + supprimer mock | Débloque toutes les données réelles |
| J2 | Corriger `VeilleMarcheView.tsx` + `OpportunitesCrmView.tsx` | M1 fonctionnel |
| J3 | Corriger `SessionsGroupesView.tsx` + `SuiviPresencesView.tsx` | M5/M6 fonctionnel |
| J4 | Corriger `FormateursStaffView.tsx` + `FacturationDevisView.tsx` | M4/M7 fonctionnel |
| J5-J6 | Créer `HitlReviewView.tsx` | Validation IA possible |
| J7-J8 | Créer `DocumentsView.tsx` + `PreparationView.tsx` | M2/PREP fonctionnels |
| J9-J10 | Brancher les boutons agents IA (M1, M2, M3, M7, M4) | Étape 4 complète |
| J11-J12 | Brancher le cycle M5 complet (Google Forms + sync-responses) | M5 entier fonctionnel |
