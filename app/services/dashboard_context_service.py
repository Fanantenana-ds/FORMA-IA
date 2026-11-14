"""
Service utilitaire — Génère un résumé textuel du tableau de bord FORMA-IA
pour injection dans le contexte des agents IA (chat RAG et assistant vocal).

Utilisé par :
  - chat_orchestrator  → `consigne_additionnelle` quand la question porte sur le TDB
  - assistant_vocal_service → `contexte_action` injecté avant traitement
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _ar(v: int | float | None) -> str:
    """Format Ariary lisible."""
    if v is None:
        return "non disponible"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f} million(s) d'Ariary"
    if v >= 1_000:
        return f"{v / 1_000:.0f}k Ariary"
    return f"{int(v):,} Ariary"


def construire_contexte_dashboard(stats: dict[str, Any]) -> str:
    """
    Construit un bloc de contexte Markdown à injecter dans le prompt IA.

    ``stats`` est le dictionnaire retourné par DashboardService
    (ou tout dict compatible KPIStats du frontend).
    """
    now = datetime.now()
    date_str = now.strftime("%A %d %B %Y à %H:%M")

    # ── Formations ───────────────────────────────────────────────
    sessions       = stats.get("sessions_realisees") or stats.get("session_realisees") or 0
    participants   = stats.get("participants_formes") or stats.get("participant") or 0
    taux_presence  = stats.get("taux_presence_moyen") or stats.get("taux_presence") or 0
    statut_presence = "✅ objectif atteint (≥ 85%)" if taux_presence >= 85 else f"⚠️ sous l'objectif de 85%"

    # ── Opportunités ─────────────────────────────────────────────
    opp_total      = stats.get("opportunites_detectees") or stats.get("opportunite_total") or 0
    opp_domaines   = stats.get("opportunite_par_domaine") or {}

    # ── Documents ────────────────────────────────────────────────
    tdr            = stats.get("tdr_generes") or 0
    offres         = stats.get("offres_generees") or 0
    attestations   = stats.get("attestations_generees") or 0
    relances       = stats.get("relances_envoyees") or 0

    # ── Facturation ──────────────────────────────────────────────
    ca_facture     = stats.get("chiffre_affaires_facture") or 0
    ca_encaisse    = stats.get("chiffre_affaires_encaisse") or 0
    montant_impaye = stats.get("montant_impaye") or 0
    factures_retard = stats.get("factures_en_retard") or 0
    sante_fin = "✅ bonne" if factures_retard == 0 else f"⚠️ {factures_retard} facture(s) en retard"

    # ── Domaines lisibles ─────────────────────────────────────────
    domaines_str = ""
    if isinstance(opp_domaines, dict) and opp_domaines:
        domaines_str = ", ".join(f"{d}: {n}" for d, n in opp_domaines.items())
    elif isinstance(opp_domaines, list):
        domaines_str = ", ".join(
            f"{item.get('domaine','?')}: {item.get('nombre',0)}"
            for item in opp_domaines[:5]
            if isinstance(item, dict)
        )

    contexte = f"""---
📊 CONTEXTE TEMPS RÉEL — Tableau de bord FORMA-IA
Date : {date_str}

## Formations
- Sessions réalisées : {sessions}
- Participants formés : {participants}
- Taux de présence moyen : {taux_presence}% — {statut_presence}

## Pipeline commercial (CRM)
- Marchés / appels d'offres détectés : {opp_total}
{f"- Répartition par domaine : {domaines_str}" if domaines_str else ""}

## Documents générés
- TDR produits : {tdr}
- Offres générées : {offres}
- Attestations émises : {attestations}
- Relances envoyées : {relances}

## Situation financière
- Chiffre d'affaires facturé HT : {_ar(ca_facture)}
- Montant encaissé : {_ar(ca_encaisse)}
- Montant impayé restant : {_ar(montant_impaye)}
- Santé de la facturation : {sante_fin}
---"""

    return contexte.strip()


def est_question_dashboard(texte: str) -> bool:
    """
    Détecte si un message utilisateur porte sur les indicateurs / tableau de bord.
    Utilisé par le chat_orchestrator pour décider d'injecter le contexte KPI.
    """
    mots_cles = (
        "tableau de bord", "dashboard", "indicateur", "kpi", "statistique",
        "chiffre", "bilan", "résultat", "performance", "taux de présence",
        "sessions", "participants", "factur", "encaiss", "impayé", "retard",
        "opportunité", "domaine", "ca ", "chiffre d'affaire", "attesta",
        "comment va", "état de la plateforme", "santé", "activité", "rapport général",
        "ce qui se passe", "plateforme fait", "avancement",
    )
    t = texte.lower()
    return any(m in t for m in mots_cles)
