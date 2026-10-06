# INTERFACES MANQUANTES — FORMA-IA

> **Pour qui ?** Le développeur frontend chargé de compléter le projet.  
> **Objectif :** Liste exhaustive de tout ce qui n'existe pas encore côté frontend, avec le code exact à écrire.  
> **Backend :** 100% prêt sur tous les points listés ici.  
> **Dernière mise à jour :** 2026-10-06

---

## RÉSUMÉ RAPIDE

| Priorité | Quoi | Fichier | Bloque quoi |
|---|---|---|---|
| 🔴 **CRITIQUE** | Auth réelle (token JWT) | `api.ts` + `AuthPage.tsx` | TOUT — sans ça, 0 donnée réelle |
| 🔴 **CRITIQUE** | `HitlReviewView.tsx` | À créer | Aucun contenu IA ne peut être validé |
| 🟠 **Haute** | Brancher 5 vues existantes sur le Backend | Voir ci-dessous | Données toujours mockées |
| 🟠 **Haute** | `SupportsFormationView.tsx` | À créer | Upload RAG inaccessible |
| 🟡 **Moyenne** | `PreparationView.tsx` | À créer | Projets/salles/EDT inaccessibles |
| 🟡 **Moyenne** | `BilanFormationsView.tsx` | À créer | Bilan Direction inaccessible |
| 🟢 **Faible** | Boutons agents IA dans les vues | Toutes les vues | Génération IA inaccessible |

---

## PARTIE 1 — CE QUI EST CASSÉ DANS LES FICHIERS EXISTANTS

### 1.1 — `AuthPage.tsx` — L'authentification est un mock

**État actuel :** La fonction `quickDemoLogin()` simule une connexion sans jamais appeler le Backend. Aucun token JWT n'est généré. Toutes les routes protégées retournent HTTP 401.

**Ce qu'il faut faire :**

```ts
// Dans api.ts — ajouter la méthode login()
async login(email: string, password: string): Promise<string> {
  const res = await fetch('http://127.0.0.1:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw new Error('Identifiants invalides')
  const data = await res.json()
  // data = { access_token: "eyJ...", token_type: "bearer" }
  localStorage.setItem('token', data.access_token)
  return data.access_token
}
```

```ts
// Dans api.ts — ajouter le token sur TOUS les appels
private async request(url: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...options.headers,
  }
  const res = await fetch(`http://127.0.0.1:8000/api/v1${url}`, { ...options, headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    return
  }
  return res.json()
}
```

```tsx
// Dans AuthPage.tsx — remplacer quickDemoLogin() par :
const handleLogin = async (email: string, password: string) => {
  try {
    await apiService.login(email, password)
    // naviguer vers le dashboard
  } catch {
    setError('Email ou mot de passe incorrect')
  }
}
```

**Tester :**
```
POST http://127.0.0.1:8000/api/v1/auth/login
Body: { "email": "votre_email", "password": "votre_mdp" }
Réponse attendue: { "access_token": "eyJ...", "token_type": "bearer" }
```

---

### 1.2 — `VeilleMarcheView.tsx` — Données mockées, 0 appel API

**État actuel :** State local uniquement. Aucun appel à `/opportunites`.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async getOpportunites() {
  return this.request('/opportunites')
}
async updateOpportunite(id: string, data: Partial<Opportunite>) {
  return this.request(`/opportunites/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}
// Pour la recherche IA (déclenche un agent → retourne un review_id à valider dans HitlReviewView)
async rechercherVeille(query: string) {
  return this.request('/ia/veille/rechercher', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}
```

```tsx
// Dans VeilleMarcheView.tsx — remplacer le state local par :
useEffect(() => {
  apiService.getOpportunites().then(setOpportunites)
}, [])
```

---

### 1.3 — `OpportunitesCrmView.tsx` — `DEFAULT_ACCEPTED_MARKETS` codé en dur

**État actuel :** La liste des marchés est une constante hardcodée. Aucun appel à `/opportunites`.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async getOpportunites() {
  return this.request('/opportunites')
}
async createOpportunite(data: {
  entreprise: string
  contact: string
  domaine: string
  statut: 'PROSPECT' | 'QUALIFICATION' | 'PROPOSITION' | 'NEGOCIE' | 'GAGNE' | 'PERDU'
  email?: string
  telephone?: string
  budget_estime?: number
}) {
  return this.request('/opportunites', { method: 'POST', body: JSON.stringify(data) })
}
async deleteOpportunite(id: string) {
  return this.request(`/opportunites/${id}`, { method: 'DELETE' })
}
```

```tsx
// Dans OpportunitesCrmView.tsx
useEffect(() => {
  apiService.getOpportunites().then(data => setOpportunites(data.data ?? []))
}, [])
```

---

### 1.4 — `SessionsGroupesView.tsx` — Participants sauvegardés en local uniquement

**État actuel :** `setPresencesList` met à jour un tableau React local. Rien n'est envoyé au Backend.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async getParticipants(sessionId: string) {
  return this.request(`/sessions/${sessionId}/participants`)
}
async inscrireParticipant(sessionId: string, participantId: string) {
  return this.request(`/sessions/${sessionId}/inscrire`, {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId }),
  })
}
async retirerParticipant(sessionId: string, participantId: string) {
  return this.request(`/sessions/${sessionId}/inscrire/${participantId}`, { method: 'DELETE' })
}
async updateSession(id: string, data: Partial<Session>) {
  return this.request(`/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async deleteSession(id: string) {
  return this.request(`/sessions/${id}`, { method: 'DELETE' })
}
```

```tsx
// Dans SessionsGroupesView.tsx
const handleAjouterParticipant = async (participantId: string) => {
  await apiService.inscrireParticipant(session.id, participantId)
  const updated = await apiService.getParticipants(session.id)
  setParticipants(updated)
}
```

---

### 1.5 — `SuiviPresencesView.tsx` — Présences non persistées

**État actuel :** Marquer présent/absent modifie un état React local. Rien n'est sauvegardé en base.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async getPresences(seanceId: string) {
  return this.request(`/seances/${seanceId}/presences`)
}
async enregistrerPresence(seanceId: string, data: {
  participant_id: string
  present: boolean
  motif_absence?: string
}) {
  return this.request(`/seances/${seanceId}/presences`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
async corrigerPresence(presenceId: string, data: { present?: boolean; motif_absence?: string }) {
  return this.request(`/seances/presences/${presenceId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}
```

```tsx
// Dans SuiviPresencesView.tsx
const handleMarquerPresence = async (participantId: string, present: boolean) => {
  await apiService.enregistrerPresence(seanceId, { participant_id: participantId, present })
  const updated = await apiService.getPresences(seanceId)
  setPresences(updated)
}
```

---

### 1.6 — `FormateursStaffView.tsx` — Création/modification non persistée

**État actuel :** Le bouton "Ajouter un formateur" appelle `onAddFormateur(created)` (callback parent). Aucun appel POST au Backend.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async createFormateur(data: {
  nom: string
  email: string
  specialites: string[]
  tarif_journalier: number
}) {
  return this.request('/rh/formateurs', { method: 'POST', body: JSON.stringify(data) })
}
async updateFormateur(id: string, data: Partial<Formateur>) {
  return this.request(`/rh/formateurs/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async deleteFormateur(id: string) {
  return this.request(`/rh/formateurs/${id}`, { method: 'DELETE' })
}
```

```tsx
// Dans FormateursStaffView.tsx — remplacer le callback
const handleCreateFormateur = async (data: CreateFormateurDto) => {
  const created = await apiService.createFormateur(data)
  setFormateurs(prev => [...prev, created])
}
```

---

### 1.7 — `FacturationDevisView.tsx` — Paiements, relance et export absents

**État actuel :** La lecture et la création fonctionnent. Il manque : modifier le statut, enregistrer un paiement, générer une relance IA, exporter.

**Ce qu'il faut ajouter dans `api.ts` :**

```ts
async updateFacture(id: string, data: Partial<Facture>) {
  return this.request(`/factures/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async enregistrerPaiement(factureId: string, data: {
  montant: number
  date_paiement: string
  mode: string
}) {
  return this.request(`/factures/${factureId}/paiements`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
async exportComptable(format: 'csv' | 'xlsx' | 'pdf' = 'csv') {
  const token = localStorage.getItem('token')
  window.open(`http://127.0.0.1:8000/api/v1/exports?format=${format}&token=${token}`, '_blank')
}
// Relance IA → retourne un review_id à valider dans HitlReviewView
async genererRelance(factureId: string) {
  return this.request('/ia/facturation/relances/generer', {
    method: 'POST',
    body: JSON.stringify({ facture_id: factureId }),
  })
  // → { review_id: "...", necessaire: true, niveau: "FERME" }
}
```

---

## PARTIE 2 — VUES COMPLÈTES À CRÉER

### 2.1 — `SupportsFormationView.tsx` (priorité haute — formateurs)

> Upload des supports de cours, suivi d'indexation RAG, téléchargement résumé en 1 clic.

**Ajouter dans `api.ts` :**

```ts
async uploaderSupport(
  file: File,
  formationCode: string,
  module?: string,
  collection = 'support'
) {
  const token = localStorage.getItem('token')
  const formData = new FormData()
  formData.append('fichier', file)
  formData.append('formation_code', formationCode)
  formData.append('collection', collection)
  if (module) formData.append('module', module)

  const res = await fetch('http://127.0.0.1:8000/api/v1/documents/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData,
    // Ne pas mettre Content-Type ici — le navigateur le met automatiquement avec le boundary
  })
  return res.json()
  // → { success, hash, fichier, chemin_fichier, formation_code, module,
  //     statut: "en_attente", deja_present, taille_octets }
}

async listerSupports(formationCode?: string) {
  const query = formationCode ? `?formation_code=${formationCode}` : ''
  return this.request(`/documents/rag/supports${query}`)
  // → { success, total, data: [{ hash, fichier, formation_code, module, statut,
  //     nb_chunks, date_debut, date_fin, fichier_disponible }] }
}

async supprimerSupport(hash: string) {
  return this.request(`/documents/rag/supports/${hash}`, { method: 'DELETE' })
  // → { success, nb_chunks_supprimes, fichier_supprime }
}

async telechargerResumeFormation(formationCode: string) {
  const token = localStorage.getItem('token')
  const res = await fetch(
    `http://127.0.0.1:8000/api/v1/documents/rag/supports/resume-formation?formation_code=${formationCode}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  )
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `resume_${formationCode}.docx`
  a.click()
  URL.revokeObjectURL(url)
}

async lancerIndexation(cheminFichier: string, formationCode: string) {
  return this.request('/ia/rag/indexer-document', {
    method: 'POST',
    body: JSON.stringify({ chemin_fichier: cheminFichier, formation_code: formationCode }),
  })
}
```

**Structure de la vue :**

```tsx
// SupportsFormationView.tsx
import React, { useState, useEffect } from 'react'
import { apiService } from '../services/api'

interface Support {
  hash: string
  fichier: string
  formation_code: string
  module?: string
  statut: 'en_attente' | 'en_cours' | 'indexe' | 'erreur'
  nb_chunks?: number
  date_fin?: string
  fichier_disponible: boolean
}

export function SupportsFormationView() {
  const [supports, setSupports] = useState<Support[]>([])
  const [formationCode, setFormationCode] = useState('')
  const [module, setModule] = useState('')
  const [fichier, setFichier] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')

  // Charger les supports d'une formation
  const chargerSupports = async () => {
    if (!formationCode) return
    const res = await apiService.listerSupports(formationCode)
    setSupports(res.data ?? [])
  }

  useEffect(() => { chargerSupports() }, [formationCode])

  // Upload + indexation automatique
  const handleUpload = async () => {
    if (!fichier || !formationCode) return
    setUploading(true)
    try {
      const res = await apiService.uploaderSupport(fichier, formationCode, module || undefined)
      if (res.success) {
        // Lancer l'indexation automatiquement après l'upload
        await apiService.lancerIndexation(res.chemin_fichier, formationCode)
        setMessage(`✅ "${fichier.name}" uploadé et indexation lancée`)
        chargerSupports()
      }
    } catch (e) {
      setMessage('❌ Erreur lors de l\'upload')
    } finally {
      setUploading(false)
    }
  }

  // Grouper les supports par module
  const parModule = supports.reduce<Record<string, Support[]>>((acc, s) => {
    const key = s.module || 'Supports généraux'
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})

  const iconeStatut: Record<string, string> = {
    indexe: '✅',
    en_cours: '⏳',
    en_attente: '🕐',
    erreur: '❌',
  }

  return (
    <div>
      <h2>Supports de formation</h2>

      {/* Formulaire d'upload */}
      <section>
        <h3>Uploader un support</h3>
        <input
          type="text"
          placeholder="Code formation (ex: PYTHON-2026)"
          value={formationCode}
          onChange={e => setFormationCode(e.target.value)}
        />
        <input
          type="text"
          placeholder="Module (ex: Module 1 — Introduction) — optionnel"
          value={module}
          onChange={e => setModule(e.target.value)}
        />
        <input
          type="file"
          accept=".pdf,.docx,.pptx,.xlsx,.txt,.md"
          onChange={e => setFichier(e.target.files?.[0] ?? null)}
        />
        <button onClick={handleUpload} disabled={uploading || !fichier || !formationCode}>
          {uploading ? 'Upload en cours...' : 'Uploader et indexer'}
        </button>
        {message && <p>{message}</p>}
      </section>

      {/* Résumé DOCX en 1 clic */}
      {formationCode && (
        <button onClick={() => apiService.telechargerResumeFormation(formationCode)}>
          ⬇️ Télécharger le résumé DOCX de {formationCode}
        </button>
      )}

      {/* Liste des supports groupés par module */}
      {Object.entries(parModule).map(([mod, items]) => (
        <section key={mod}>
          <h4>{mod} ({items.length} support{items.length > 1 ? 's' : ''})</h4>
          {items.map(s => (
            <div key={s.hash}>
              <span>{iconeStatut[s.statut] ?? '?'}</span>
              <span>{s.fichier}</span>
              {s.nb_chunks && <span>— {s.nb_chunks} fragments indexés</span>}
              <button onClick={async () => {
                if (confirm(`Supprimer "${s.fichier}" ? Cette action est irréversible.`)) {
                  await apiService.supprimerSupport(s.hash)
                  chargerSupports()
                }
              }}>
                Supprimer
              </button>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
```

**Ajouter dans `ViewRouter.tsx` :**

```tsx
import { SupportsFormationView } from './SupportsFormationView'

// Dans le switch/router :
case 'supports_formation':
  return <SupportsFormationView />
```

**Ajouter dans le menu (Sidebar) :**

```tsx
// Section Formateur — visible pour les rôles Form. et Dir.
{ id: 'supports_formation', label: 'Supports de cours', roles: ['Form.', 'Dir.', 'Assist.'] }
```

---

### 2.2 — `BilanFormationsView.tsx` (Direction uniquement)

> Télécharge un bilan DOCX de toutes les formations sur une période choisie.

**Ajouter dans `api.ts` :**

```ts
async telechargerBilanFormations(dateDebut?: string, dateFin?: string) {
  const token = localStorage.getItem('token')
  const params = new URLSearchParams()
  if (dateDebut) params.append('date_debut', dateDebut)
  if (dateFin) params.append('date_fin', dateFin)

  const res = await fetch(
    `http://127.0.0.1:8000/api/v1/documents/rag/supports/bilan-formations?${params}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  )
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bilan_formations_${dateDebut ?? 'complet'}.docx`
  a.click()
  URL.revokeObjectURL(url)
}
```

**Structure de la vue :**

```tsx
// BilanFormationsView.tsx
export function BilanFormationsView() {
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')

  return (
    <div>
      <h2>Bilan des formations</h2>
      <p>Téléchargez un bilan complet de toutes les formations sur une période donnée.</p>

      <label>Période du :</label>
      <input type="date" value={dateDebut} onChange={e => setDateDebut(e.target.value)} />
      <label>au :</label>
      <input type="date" value={dateFin} onChange={e => setDateFin(e.target.value)} />

      <button onClick={() => apiService.telechargerBilanFormations(dateDebut || undefined, dateFin || undefined)}>
        ⬇️ Télécharger le bilan DOCX
      </button>

      <p style={{ color: '#888', fontSize: '0.9em' }}>
        Le bilan contient : toutes les formations de la période, leurs supports indexés,
        les modules couverts et les thèmes principaux (mots-clés extraits par l'IA).
      </p>
    </div>
  )
}
```

**Rôles autorisés :** `Dir.` et `Assist.` uniquement — masquer dans le menu pour `Form.`.

---

### 2.3 — `HitlReviewView.tsx` — Validation humaine des contenus IA (CRITIQUE)

> **Sans cette vue, aucun contenu généré par l'IA ne peut être sauvegardé.** C'est le verrou central de toute la logique IA.

**Ajouter dans `api.ts` :**

```ts
async getPendingReviews(agentId?: string) {
  const query = agentId ? `?agent_id=${agentId}` : ''
  return this.request(`/ia/formations/pending-reviews${query}`)
}

async getReview(reviewId: string) {
  return this.request(`/ia/formations/reviews/${reviewId}`)
  // → { review_id, agent_id, contenu_genere: {...}, statut, created_at }
}

async approuverReview(reviewId: string, commentaire = '') {
  return this.request(`/ia/formations/reviews/${reviewId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ commentaire }),
  })
}

async rejeterReview(reviewId: string, feedback: string) {
  // feedback doit faire au moins 10 caractères
  return this.request(`/ia/formations/reviews/${reviewId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ feedback }),
  })
}
```

**Structure de la vue :**

```tsx
// HitlReviewView.tsx
import React, { useState, useEffect } from 'react'
import { apiService } from '../services/api'

interface Review {
  review_id: string
  agent_id: string
  statut: string
  created_at: string
  contenu_genere?: Record<string, unknown>
}

const LABELS_AGENT: Record<string, string> = {
  agent_m1_veille:       'Veille marché',
  agent_m2_tdr:          'Génération TDR',
  agent_m3_complete:     'Génération offre',
  agent_preparation:     'Préparation (EDT + budget)',
  agent_1_forms:         'Formulaires d\'évaluation',
  agent_m7_relance:      'Relance facture',
  agent_m4_preselection: 'Présélection CV',
}

export function HitlReviewView() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [selected, setSelected] = useState<Review | null>(null)
  const [feedback, setFeedback] = useState('')
  const [loading, setLoading] = useState(false)

  const chargerReviews = async () => {
    const res = await apiService.getPendingReviews()
    setReviews(Array.isArray(res) ? res : (res.data ?? []))
  }

  useEffect(() => { chargerReviews() }, [])

  const handleApprouver = async (reviewId: string) => {
    setLoading(true)
    await apiService.approuverReview(reviewId)
    setSelected(null)
    await chargerReviews()
    setLoading(false)
    // Note : après approbation, certains modules nécessitent une 2e route /synchroniser
    // Voir GUIDE_INTEGRATION_FRONTEND.md Section 4 pour savoir laquelle appeler
  }

  const handleRejeter = async (reviewId: string) => {
    if (feedback.length < 10) {
      alert('Le feedback doit faire au moins 10 caractères.')
      return
    }
    setLoading(true)
    await apiService.rejeterReview(reviewId, feedback)
    setFeedback('')
    setSelected(null)
    await chargerReviews()
    setLoading(false)
  }

  const handleVoirDetail = async (review: Review) => {
    const detail = await apiService.getReview(review.review_id)
    setSelected(detail)
  }

  return (
    <div>
      <h2>Contenus IA en attente de validation ({reviews.length})</h2>

      {reviews.length === 0 && <p>Aucun contenu en attente. ✅</p>}

      <ul>
        {reviews.map(r => (
          <li key={r.review_id}>
            <strong>{LABELS_AGENT[r.agent_id] ?? r.agent_id}</strong>
            <span> — {new Date(r.created_at).toLocaleString('fr-FR')}</span>
            <button onClick={() => handleVoirDetail(r)}>Voir le contenu</button>
          </li>
        ))}
      </ul>

      {/* Panneau de détail */}
      {selected && (
        <div>
          <h3>Contenu généré — {LABELS_AGENT[selected.agent_id] ?? selected.agent_id}</h3>
          <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12 }}>
            {JSON.stringify(selected.contenu_genere, null, 2)}
          </pre>

          <div>
            <button
              onClick={() => handleApprouver(selected.review_id)}
              disabled={loading}
              style={{ background: '#22c55e', color: '#fff', marginRight: 8 }}
            >
              ✓ Approuver
            </button>

            <textarea
              placeholder="Feedback pour rejet (min 10 caractères)..."
              value={feedback}
              onChange={e => setFeedback(e.target.value)}
              rows={3}
            />
            <button
              onClick={() => handleRejeter(selected.review_id)}
              disabled={loading || feedback.length < 10}
              style={{ background: '#ef4444', color: '#fff' }}
            >
              ✗ Rejeter
            </button>

            <button onClick={() => setSelected(null)}>Fermer</button>
          </div>
        </div>
      )}
    </div>
  )
}
```

**Ajouter dans `ViewRouter.tsx` :**

```tsx
import { HitlReviewView } from './HitlReviewView'

case 'hitl_review':
  return <HitlReviewView />
```

**Ajouter dans le menu (Sidebar) — avec badge de compteur :**

```tsx
// Charger le compteur de reviews en attente
const [pendingCount, setPendingCount] = useState(0)
useEffect(() => {
  apiService.getPendingReviews().then(res => {
    const arr = Array.isArray(res) ? res : (res.data ?? [])
    setPendingCount(arr.length)
  })
}, [])

// Dans la Sidebar
{ id: 'hitl_review', label: `Validation IA${pendingCount > 0 ? ` (${pendingCount})` : ''}` }
```

---

### 2.4 — `PreparationView.tsx` — Projets, salles, EDT, budget

**Ajouter dans `api.ts` :**

```ts
// Projets
async getProjets() { return this.request('/projets') }
async createProjet(data: {
  titre: string; client: string; date_debut: string; date_fin: string
  statut?: 'BROUILLON' | 'EN_COURS' | 'VALIDE' | 'TERMINE' | 'ANNULE'
}) {
  return this.request('/projets', { method: 'POST', body: JSON.stringify(data) })
}
async updateProjet(id: string, data: Partial<Projet>) {
  return this.request(`/projets/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
async deleteProjet(id: string) {
  return this.request(`/projets/${id}`, { method: 'DELETE' })
}

// EDT d'un projet
async getEdt(projetId: string) { return this.request(`/projets/${projetId}/edt`) }
async ajouterSeanceEdt(projetId: string, data: {
  date: string; heure_debut: string; heure_fin: string; titre_module: string
}) {
  return this.request(`/projets/${projetId}/edt`, { method: 'POST', body: JSON.stringify(data) })
}
async supprimerSeanceEdt(projetId: string, edtId: string) {
  return this.request(`/projets/${projetId}/edt/${edtId}`, { method: 'DELETE' })
}

// Budget d'un projet
async getBudget(projetId: string) { return this.request(`/projets/${projetId}/budget`) }
async saveBudget(projetId: string, data: object) {
  return this.request(`/projets/${projetId}/budget`, { method: 'POST', body: JSON.stringify(data) })
}

// Salles
async getSalles(disponible?: boolean) {
  const query = disponible !== undefined ? `?disponible=${disponible}` : ''
  return this.request(`/salles${query}`)
}
async createSalle(data: { nom: string; capacite: number; tarif_journalier?: number }) {
  return this.request('/salles', { method: 'POST', body: JSON.stringify(data) })
}

// Génération IA de préparation (HITL → review_id)
async genererPreparation(data: {
  offre_data: { titre: string; modules: string[]; duree_jours: number }
  projet_info: { client: string; date_debut: string; date_fin: string }
  ressources: { formateur: { nom: string; tarif_journalier: number }; salle?: { nom: string; tarif_journalier: number } }
  options?: { nb_participants?: number }
}) {
  return this.request('/ia/preparation/generer-complet', {
    method: 'POST',
    body: JSON.stringify(data),
  })
  // → { review_id: "...", requires_human_action: true }
  // Ensuite : approuver dans HitlReviewView → POST /ia/preparation/synchroniser
}
```

**Structure minimale de la vue :**

```tsx
// PreparationView.tsx — onglets Projets | Salles | Génération IA
export function PreparationView() {
  const [onglet, setOnglet] = useState<'projets' | 'salles' | 'ia'>('projets')
  const [projets, setProjets] = useState([])
  const [salles, setSalles] = useState([])

  useEffect(() => {
    apiService.getProjets().then(r => setProjets(r.data ?? []))
    apiService.getSalles().then(r => setSalles(r.data ?? []))
  }, [])

  return (
    <div>
      <nav>
        <button onClick={() => setOnglet('projets')}>Projets</button>
        <button onClick={() => setOnglet('salles')}>Salles</button>
        <button onClick={() => setOnglet('ia')}>Générer avec l'IA</button>
      </nav>
      {onglet === 'projets' && <ProjetsTab projets={projets} onRefresh={() => apiService.getProjets().then(r => setProjets(r.data ?? []))} />}
      {onglet === 'salles' && <SallesTab salles={salles} />}
      {onglet === 'ia' && <PreparationIaTab />}
    </div>
  )
}
```

---

## PARTIE 3 — BOUTONS AGENTS IA MANQUANTS DANS LES VUES EXISTANTES

Ces boutons déclenchent des agents IA. Ils retournent tous un `review_id` → l'utilisateur approuve dans `HitlReviewView`.

| Vue | Bouton à ajouter | Route backend | Après approbation |
|---|---|---|---|
| `VeilleMarcheView` | "Rechercher avec l'IA" | `POST /ia/veille/rechercher` | `POST /ia/veille/synchroniser-backend` |
| `OpportunitesCrmView` | "Générer un TDR" | `POST /ia/tdr/generer` | `POST /ia/tdr/synchroniser` |
| `FacturationDevisView` | "Générer une relance" | `POST /ia/facturation/relances/generer` | `POST /ia/facturation/relances/synchroniser` |
| `FormateursStaffView` | "Analyser un CV" | `POST /ia/rh/preselection` | `POST /ia/rh/synchroniser/candidat` |
| `SessionsGroupesView` | "Générer les formulaires" | `POST /ia/formations/generate-forms` | `POST /ia/formations/creer-formulaires` → cycle M5 |

**Pattern commun pour chaque bouton :**

```tsx
const handleGenererIA = async (inputData: object) => {
  try {
    const res = await apiService.request('/ia/[module]/generer', {
      method: 'POST',
      body: JSON.stringify(inputData),
    })
    // res.review_id → rediriger vers HitlReviewView pour validation
    setCurrentSection('hitl_review')
    // ou afficher un toast : "Contenu généré ! Allez valider dans 'Validation IA'."
  } catch (e) {
    setError('Erreur lors de la génération IA')
  }
}
```

---

## PARTIE 4 — ORDRE D'IMPLÉMENTATION RECOMMANDÉ

```
Semaine 1 :
  J1  → Auth réelle (api.ts + AuthPage.tsx)              ← débloque TOUT
  J2  → HitlReviewView.tsx                               ← débloque la validation IA
  J3  → Brancher VeilleMarcheView + OpportunitesCrmView
  J4  → Brancher SessionsGroupesView + SuiviPresencesView
  J5  → Brancher FormateursStaffView + FacturationDevisView

Semaine 2 :
  J6  → Créer SupportsFormationView.tsx                  ← supports RAG
  J7  → Créer PreparationView.tsx
  J8  → Créer BilanFormationsView.tsx (Direction)
  J9  → Ajouter les boutons agents IA dans toutes les vues
  J10 → Cycle M5 complet (Google Forms + sync-responses + analyze-*)
```

---

## RÉFÉRENCE DES ROUTES BACKEND MANQUANTES (résumé)

> Toutes ces routes sont **prêtes et testées** côté backend. Elles attendent juste d'être appelées.

| Route | Méthode | Utilisée dans |
|---|---|---|
| `/auth/login` | POST | `AuthPage.tsx` |
| `/auth/me` | GET | Header/profil utilisateur |
| `/opportunites` | GET/POST/PUT/DELETE | `VeilleMarcheView`, `OpportunitesCrmView` |
| `/sessions/{id}/inscrire` | POST/DELETE | `SessionsGroupesView` |
| `/sessions/{id}/participants` | GET | `SessionsGroupesView` |
| `/seances/{id}/presences` | GET/POST | `SuiviPresencesView` |
| `/seances/presences/{id}` | PATCH | `SuiviPresencesView` |
| `/rh/formateurs` | POST/PATCH/DELETE | `FormateursStaffView` |
| `/factures/{id}/paiements` | POST | `FacturationDevisView` |
| `/exports` | GET | `FacturationDevisView` |
| `/documents/upload` | POST (multipart) | `SupportsFormationView` |
| `/documents/rag/supports` | GET | `SupportsFormationView` |
| `/documents/rag/supports/resume-formation` | GET | `SupportsFormationView` |
| `/documents/rag/supports/bilan-formations` | GET | `BilanFormationsView` |
| `/documents/rag/supports/{hash}` | DELETE | `SupportsFormationView` |
| `/projets` | GET/POST/PATCH/DELETE | `PreparationView` |
| `/projets/{id}/edt` | GET/POST/DELETE | `PreparationView` |
| `/projets/{id}/budget` | GET/POST | `PreparationView` |
| `/salles` | GET/POST | `PreparationView` |
| `/ia/formations/pending-reviews` | GET | `HitlReviewView` |
| `/ia/formations/reviews/{id}` | GET | `HitlReviewView` |
| `/ia/formations/reviews/{id}/approve` | POST | `HitlReviewView` |
| `/ia/formations/reviews/{id}/reject` | POST | `HitlReviewView` |
| `/ia/veille/rechercher` | POST | `VeilleMarcheView` |
| `/ia/tdr/generer` | POST | `OpportunitesCrmView` |
| `/ia/offres/generer-complet` | POST | `PreparationView` |
| `/ia/preparation/generer-complet` | POST | `PreparationView` |
| `/ia/formations/generate-forms` | POST | `SessionsGroupesView` |
| `/ia/formations/creer-formulaires` | POST | `SessionsGroupesView` |
| `/ia/formations/sync-responses` | POST | `SessionsGroupesView` |
| `/ia/facturation/relances/generer` | POST | `FacturationDevisView` |
| `/ia/rh/preselection` | POST | `FormateursStaffView` |
| `/ia/rag/chat` | POST | À créer (chat contextuel) |

---

*Voir `GUIDE_INTEGRATION_FRONTEND.md` pour le détail complet de chaque route (format des corps de requête, réponses, exemples).*
