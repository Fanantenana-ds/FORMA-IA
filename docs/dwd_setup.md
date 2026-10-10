# Délégation d'autorité Google Workspace (Domain-Wide Delegation)

## Contexte

Le module M5 (FormGeneratorService) crée 4 Google Forms par session.
Par défaut, le Service Account crée ces formulaires en son propre nom (compte de service).
Avec la DWD activée, les formulaires apparaissent dans le Google Drive d'un utilisateur réel du domaine (ex. admin@altiora.mg).

## Variables .env concernées

```
GOOGLE_CREDENTIALS_PATH=secrets/google_credentials.json   # Service Account JSON
GOOGLE_SUBJECT_EMAIL=admin@altiora.mg                      # Activer la DWD
```

Laisser `GOOGLE_SUBJECT_EMAIL` vide (ou commenté) = pas de DWD, formulaires créés au nom du SA.

## Étapes de configuration

### 1. Google Cloud Console — Activer les APIs

URL : https://console.cloud.google.com/apis/library?project=forma-ia-510012

Activer :
- Google Forms API
- Google Drive API

### 2. Google Cloud Console — Récupérer le Client ID du Service Account

URL : https://console.cloud.google.com/iam-admin/serviceaccounts?project=forma-ia-510012

1. Cliquer sur le Service Account utilisé (celui dans `secrets/google_credentials.json`)
2. Onglet "Clés" → vérifier qu'une clé JSON active existe
3. Onglet "Détails" → noter le **Unique ID** (numérique, ex. `112345678901234567890`)

### 3. Google Workspace Admin — Configurer la DWD

URL : https://admin.google.com/ac/owl/domainwidedelegation

Conditions : accès administrateur Google Workspace requis.

1. Cliquer **"Ajouter un nouveau"**
2. **Client ID** : coller le Unique ID du Service Account (étape 2)
3. **Scopes OAuth** : copier exactement ces deux lignes :
   ```
   https://www.googleapis.com/auth/forms.body,https://www.googleapis.com/auth/drive.file
   ```
4. Cliquer **"Autoriser"**

### 4. Configurer .env

```
GOOGLE_SUBJECT_EMAIL=admin@altiora.mg
```

Remplacer `admin@altiora.mg` par l'adresse d'un utilisateur réel du domaine Google Workspace.
Cet utilisateur deviendra propriétaire des formulaires créés.

## Vérification

Après configuration, appeler la route :
```
POST /ia/formations/creer-formulaires
{
  "review_id": "<review HITL approuvée>",
  "session_title": "Test DWD"
}
```

Les formulaires doivent apparaître dans le Google Drive de `GOOGLE_SUBJECT_EMAIL`.

## Sans DWD (mode dégradé)

Si `GOOGLE_SUBJECT_EMAIL` est absent :
- Les formulaires sont créés au nom du Service Account
- Ils ne sont pas visibles dans le Drive d'un utilisateur humain sans partage manuel
- Fonctionnel pour les tests, pas pour la production

## Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `unauthorized_client` | DWD non configurée ou Client ID incorrect | Vérifier l'étape 3 |
| `access_denied` | Scope manquant dans la DWD | Re-vérifier les scopes (étape 3) |
| `FileNotFoundError: GOOGLE_CREDENTIALS_PATH` | Fichier JSON absent | Vérifier `secrets/google_credentials.json` |
| `Token has been expired or revoked` | Clé SA révoquée | Regénérer la clé dans Google Cloud Console |
