# app/services/rh/candidature_service.py
# ============================================================
# SERVICE CANDIDATURE — Logique commune aux deux canaux
#   Canal 1 : Formulaire web  → POST /ia/rh/cv/postuler
#   Canal 2 : Email IMAP      → tâche planifiée
# ============================================================

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"

POSTES_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "postes_rh.yaml"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CHARGEMENT CONFIG POSTES
# =============================================================================

def charger_postes() -> dict[str, Any]:
    """Charge la configuration des postes depuis postes_rh.yaml."""
    try:
        with open(POSTES_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"❌ postes_rh.yaml introuvable : {POSTES_CONFIG_PATH}")
        return {}
    except Exception as exc:
        logger.error(f"❌ Erreur lecture postes_rh.yaml : {exc}")
        return {}


def get_poste(code: str) -> dict[str, Any] | None:
    """Retourne la config d'un poste ou None si inexistant/inactif."""
    postes = charger_postes()
    poste = postes.get(code)
    if not poste:
        return None
    if not poste.get("actif", True):
        return None
    return poste


def lister_postes_actifs() -> dict[str, Any]:
    """Retourne tous les postes actifs (code → titre + description)."""
    postes = charger_postes()
    return {
        code: {"titre": p["titre"], "description": p.get("description", "")}
        for code, p in postes.items()
        if p.get("actif", True)
    }


# =============================================================================
# ENVOI EMAIL ACCUSÉ DE RÉCEPTION (SMTP)
# =============================================================================

async def envoyer_accuse_reception(
    nom_candidat: str,
    email_candidat: str,
    titre_poste: str,
    score: int | None = None,
) -> bool:
    """
    Envoie un email d'accusé de réception au candidat après soumission.
    Retourne True si envoyé, False si échec (non bloquant).
    """
    smtp_host  = os.getenv("SMTP_HOST", "")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_user  = os.getenv("SMTP_USER", "")
    smtp_pass  = os.getenv("SMTP_PASSWORD", "")
    email_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        vlog("⚠️ SMTP non configuré — accusé de réception non envoyé", "warning")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Candidature reçue — {titre_poste} | ALTIORA PREST"
        msg["From"]    = f"ALTIORA PREST <{email_from}>"
        msg["To"]      = email_candidat

        corps = f"""Bonjour {nom_candidat},

Nous avons bien reçu votre candidature pour le poste de {titre_poste} chez ALTIORA PREST.

Votre dossier est en cours d'analyse. Vous recevrez une réponse de notre équipe RH dans les 48 heures ouvrées.

Cordialement,
L'équipe RH — ALTIORA PREST
"""
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, email_candidat, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_pass)
                server.sendmail(email_from, email_candidat, msg.as_string())

        vlog(f"✅ Accusé de réception envoyé à {email_candidat}")
        return True

    except Exception as exc:
        vlog(f"⚠️ Envoi email échoué ({email_candidat}) : {exc}", "warning")
        return False


# =============================================================================
# LECTURE EMAILS IMAP (canal 2)
# =============================================================================

def lire_candidatures_email() -> list:
    """
    Lit les emails non lus de la boîte RH et extrait les CV en pièce jointe.
    Retourne une liste de dict : {nom, email, fichier_nom, fichier_contenu, poste_code}.

    Variables d'environnement requises :
        IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASSWORD
        RH_EMAIL_POSTE_DEFAUT (code poste si non détectable depuis l'objet)
    """
    import email as email_lib
    import imaplib
    from email.header import decode_header

    imap_host  = os.getenv("IMAP_HOST", "")
    imap_port  = int(os.getenv("IMAP_PORT", "993"))
    imap_user  = os.getenv("IMAP_USER", "")
    imap_pass  = os.getenv("IMAP_PASSWORD", "")
    poste_defaut = os.getenv("RH_EMAIL_POSTE_DEFAUT", "formateur-ia")

    if not imap_host or not imap_user or not imap_pass:
        vlog("⚠️ IMAP non configuré — lecture emails ignorée", "warning")
        return []

    candidatures = []
    postes = charger_postes()

    try:
        with imaplib.IMAP4_SSL(imap_host, imap_port) as imap:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")

            # Chercher emails non lus avec "CV" ou "Candidature" dans l'objet
            _, ids = imap.search(None, '(UNSEEN SUBJECT "CV")')
            _, ids2 = imap.search(None, '(UNSEEN SUBJECT "candidature")')
            tous_ids = set(ids[0].split()) | set(ids2[0].split())

            for uid in tous_ids:
                _, data = imap.fetch(uid, "(RFC822)")
                msg = email_lib.message_from_bytes(data[0][1])

                # Décoder l'objet
                sujet_raw, enc = decode_header(msg["Subject"])[0]
                sujet = sujet_raw.decode(enc or "utf-8") if isinstance(sujet_raw, bytes) else sujet_raw

                # Déduire le poste depuis l'objet (ex: "CV formateur-ia")
                poste_code = poste_defaut
                for code in postes:
                    if code.lower() in sujet.lower():
                        poste_code = code
                        break

                # Extraire nom et email expéditeur
                expediteur = msg.get("From", "")
                email_candidat = ""
                nom_candidat = "Candidat"
                if "<" in expediteur:
                    nom_candidat = expediteur.split("<")[0].strip().strip('"')
                    email_candidat = expediteur.split("<")[1].rstrip(">")
                else:
                    email_candidat = expediteur.strip()

                # Chercher pièce jointe CV
                for part in msg.walk():
                    ct = part.get_content_type()
                    cd = part.get("Content-Disposition", "")
                    if "attachment" in cd:
                        fichier_nom = part.get_filename() or "cv.pdf"
                        fichier_contenu = part.get_payload(decode=True)
                        ext = Path(fichier_nom).suffix.lower()
                        if ext in {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".txt"}:
                            candidatures.append({
                                "nom": nom_candidat,
                                "email": email_candidat,
                                "poste_code": poste_code,
                                "fichier_nom": fichier_nom,
                                "fichier_contenu": fichier_contenu,
                            })
                            # Marquer comme lu
                            imap.store(uid, "+FLAGS", "\\Seen")
                            break

        vlog(f"📧 {len(candidatures)} candidature(s) trouvée(s) par email")
        return candidatures

    except Exception as exc:
        logger.error(f"❌ Lecture IMAP échouée : {exc}")
        return []
