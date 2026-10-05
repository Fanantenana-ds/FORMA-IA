"""
Setup OAuth2 Google — VERSION SIMPLIFIÉE (copier-coller)
=========================================================
1. Le script affiche une URL
2. Tu l'ouvres dans ton navigateur
3. Tu te connectes + acceptes
4. Google te donne un code → tu le colles ici
5. Terminé — refresh_token sauvegardé dans .env

Usage :
    python scripts/setup_google_oauth.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CLIENT_SECRETS = BASE_DIR / "secrets" / "google_oauth_client.json"
ENV_FILE = BASE_DIR / ".env"

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive",
]


def main():
    # ── Vérifications préliminaires ──────────────────────────
    if not CLIENT_SECRETS.exists():
        print(f"❌ Fichier introuvable : {CLIENT_SECRETS}")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("❌ Package manquant. Lance : pip install google-auth-oauthlib")
        sys.exit(1)

    print()
    print("=" * 60)
    print("  SETUP OAUTH2 GOOGLE — FORMA-IA")
    print("=" * 60)

    # ── Générer l'URL d'autorisation ─────────────────────────
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS),
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",  # mode "copier-coller"
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    print()
    print("ÉTAPE 1 — Ouvre cette URL dans ton navigateur :")
    print()
    print(f"  {auth_url}")
    print()
    print("ÉTAPE 2 — Connecte-toi avec ton compte Google")
    print("          et accepte les permissions.")
    print()
    print("ÉTAPE 3 — Google affiche un code (ex: 4/0AX4...).")
    print("          Copie-le et colle-le ici.")
    print()

    code = input("Code d'autorisation → ").strip()
    if not code:
        print("❌ Code vide. Relance le script.")
        sys.exit(1)

    # ── Échanger le code contre les tokens ───────────────────
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        print(f"❌ Erreur lors de l'échange du code : {e}")
        print("   → Vérifie que tu as copié le code complet")
        sys.exit(1)

    credentials = flow.credentials
    refresh_token = credentials.refresh_token

    if not refresh_token:
        print("❌ Pas de refresh_token. Relance avec un autre compte.")
        sys.exit(1)

    print()
    print(f"✅ Autorisation accordée ! Token obtenu.")

    # ── Sauvegarder dans .env ────────────────────────────────
    _update_env(refresh_token)

    # ── Test réel : créer un formulaire puis le supprimer ────
    print()
    print("🧪 Test Google Forms API...")
    _test_forms(credentials)

    print()
    print("=" * 60)
    print("✅ Setup terminé ! GOOGLE_REFRESH_TOKEN dans .env")
    print("   GoogleFormsPublisherService est prêt.")
    print("=" * 60)


def _update_env(refresh_token: str):
    content = ENV_FILE.read_text(encoding="utf-8")
    marker = "GOOGLE_REFRESH_TOKEN="

    if marker in content:
        lines = []
        for line in content.splitlines():
            if line.startswith(marker):
                lines.append(f"{marker}{refresh_token}")
            else:
                lines.append(line)
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        # Insérer après GOOGLE_DRIVE_FOLDER_ID
        lines = []
        inserted = False
        for line in content.splitlines():
            lines.append(line)
            if "GOOGLE_DRIVE_FOLDER_ID" in line and not inserted:
                lines.append(f"{marker}{refresh_token}")
                inserted = True
        if not inserted:
            lines.append(f"{marker}{refresh_token}")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✅ GOOGLE_REFRESH_TOKEN sauvegardé dans .env")


def _test_forms(credentials):
    from googleapiclient.discovery import build

    forms_svc = build("forms", "v1", credentials=credentials)
    drive_svc  = build("drive", "v3", credentials=credentials)

    try:
        form = forms_svc.forms().create(
            body={"info": {"title": "TEST FORMA-IA — suppression automatique"}}
        ).execute()
        form_id = form["formId"]
        print(f"   ✅ Formulaire créé : https://docs.google.com/forms/d/{form_id}/edit")
        drive_svc.files().delete(fileId=form_id).execute()
        print(f"   ✅ Formulaire test supprimé — Forms API opérationnelle !")
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        print()
        print("   → Va sur : https://console.cloud.google.com/apis/library")
        print("     Projet : forma-ia-510012")
        print("     Cherche 'Google Forms API' → Enable")
        print("     Puis relance ce script.")


if __name__ == "__main__":
    main()
