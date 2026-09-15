import logging
from pathlib import Path
from datetime import datetime, time as dtime
from typing import Dict, Any, List, Optional
from collections import defaultdict
from app.services.hitl import create_review

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================
SEUIL_ELIGIBILITE_ATTESTATION = 80  # % présence minimum
PLAGE_HORAIRE_VALIDE = (dtime(6, 0), dtime(20, 0))  # 06:00 - 20:00


# ============================================================
# SERVICE
# ============================================================
class PresenceAnalyzerService:
    """
    Agent 4 — Analyse les présences et détecte les anomalies.

    Input  : participants + présences (par séance).
    Output : statistiques + anomalies + éligibles attestation.
    """

    def __init__(self):
        logger.info(
            f"✅ PresenceAnalyzerService initialisé "
            f"(Python pur — seuil éligibilité={SEUIL_ELIGIBILITE_ATTESTATION}%)"
        )

    # --------------------------------------------------------
    # ANALYSE PRINCIPALE
    # --------------------------------------------------------
    def analyze(
        self,
        session_info: Dict[str, Any],
        participants: List[Dict[str, Any]],
        presences: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyse complète des présences.

        Args:
            session_info: Infos session (id, titre, dates, etc.)
            participants: Liste des participants :
                [{"id": 1, "nom": "Jean Dupont", "email": "..."}, ...]
            presences: Liste des présences :
                [{
                    "participant_id": 1,
                    "date": "2026-10-15",
                    "heure": "08:30:00",
                    "present": True,
                    "methode": "qr_code"
                }, ...]

        Returns:
            Dict conforme à PresenceAnalysisResponse.
        """
        start = datetime.now()
        logger.info("=" * 70)
        logger.info("🚀 [PresenceAgent] Analyse des présences (Python pur)...")
        logger.info(f"   📋 Session : {session_info.get('titre', 'N/A')}")
        logger.info(f"   👥 Participants : {len(participants)}")
        logger.info(f"   📅 Présences : {len(presences)}")
        logger.info("=" * 70)

        # ── ÉTAPE 1 : Statistiques par participant ──
        stats_par_participant = self._compute_participant_stats(
            participants, presences
        )

        # ── ÉTAPE 2 : Statistiques globales ──
        stats_global = self._compute_global_stats(
            participants, presences, stats_par_participant
        )

        # ── ÉTAPE 3 : Détection anomalies ──
        anomalies = self._detect_anomalies(participants, presences)

        # ── ÉTAPE 4 : Éligibles attestation ──
        eligibles = [
            p["nom"] for p in stats_par_participant
            if p["eligible_attestation"]
        ]
        non_eligibles = [
            p["nom"] for p in stats_par_participant
            if not p["eligible_attestation"]
        ]

        # ── ÉTAPE 5 : Recommandations ──
        recos = self._generate_recommandations(
            stats_global, anomalies, len(non_eligibles)
        )

        # ── Résumé ──
        resume = self._build_resume(stats_global, len(anomalies), len(eligibles))

        elapsed = round((datetime.now() - start).total_seconds(), 3)
        result = {
            "success": True,
            "resume": resume,
            "statistiques": stats_global,
            "participants": stats_par_participant,
            "anomalies": anomalies,
            "eligibles_attestation": eligibles,
            "non_eligibles_attestation": non_eligibles,
            "recommandations": recos,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "session_id": session_info.get("id"),
                "methode": "python_deterministic",
            },
        }
        
        review_id = create_review(
            agent_id="agent_4_presences",
            data=result,
            summary=(
                f"{len(anomalies)} anomalies + {len(eligibles)} éligibles "
                f"— ⚠️ CONFIRMER"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        logger.info("=" * 70)
        logger.info(f"✅ [PresenceAgent] Analyse terminée en {elapsed}s (review={review_id})")
        logger.info(
            f"   📊 Taux global={stats_global['taux_presence_global']}, "
            f"Anomalies={len(anomalies)}, "
            f"Éligibles={len(eligibles)}/{len(participants)}"
        )
        logger.info("=" * 70)
        return result
        
    # --------------------------------------------------------
    # STATS PAR PARTICIPANT
    # --------------------------------------------------------
    def _compute_participant_stats(
        self,
        participants: List[Dict[str, Any]],
        presences: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Calcule le taux de présence par participant."""
        # Dates uniques de séances (toutes les dates où au moins 1 présence)
        dates_seances = sorted({
            p.get("date") for p in presences if p.get("date")
        })
        nb_seances = len(dates_seances)

        # Regrouper les présences par participant
        pres_by_participant: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for p in presences:
            pid = p.get("participant_id")
            if pid is not None:
                pres_by_participant[pid].append(p)

        result = []
        for participant in participants:
            pid = participant.get("id")
            nom = participant.get("nom", "N/A")

            # Présences effectives (present=True) et uniques par date
            dates_presentes = set()
            for pr in pres_by_participant.get(pid, []):
                if pr.get("present", False):
                    dates_presentes.add(pr.get("date"))

            nb_pres = len(dates_presentes)
            taux = round((nb_pres / nb_seances * 100), 1) if nb_seances > 0 else 0.0

            result.append({
                "participant_id": pid,
                "nom": nom,
                "nb_presences": nb_pres,
                "nb_seances": nb_seances,
                "taux_presence": f"{taux}%",
                "eligible_attestation": taux >= SEUIL_ELIGIBILITE_ATTESTATION,
            })

        return result

    # --------------------------------------------------------
    # STATS GLOBALES
    # --------------------------------------------------------
    def _compute_global_stats(
        self,
        participants: List[Dict[str, Any]],
        presences: List[Dict[str, Any]],
        stats_par_participant: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calcule les statistiques globales."""
        nb_participants = len(participants)
        dates_seances = sorted({
            p.get("date") for p in presences if p.get("date")
        })
        nb_seances = len(dates_seances)

        # Taux global = moyenne des taux individuels
        taux_list = [
            float(s["taux_presence"].rstrip("%"))
            for s in stats_par_participant
        ]
        taux_moyen = round(sum(taux_list) / len(taux_list), 1) if taux_list else 0.0

        # Nombre total de présences (uniques par participant/date)
        total_presents = sum(
            s["nb_presences"] for s in stats_par_participant
        )
        total_absents = (nb_participants * nb_seances) - total_presents

        # Nombre moyen de présents par séance
        nb_presents_moyen = (
            round(total_presents / nb_seances, 1) if nb_seances > 0 else 0.0
        )

        return {
            "total_participants": nb_participants,
            "total_seances": nb_seances,
            "taux_presence_global": f"{taux_moyen}%",
            "nb_presents_moyen": nb_presents_moyen,
            "nb_absents_total": max(total_absents, 0),
        }

    # --------------------------------------------------------
    # DÉTECTION ANOMALIES
    # --------------------------------------------------------
    def _detect_anomalies(
        self,
        participants: List[Dict[str, Any]],
        presences: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Détecte les anomalies dans les présences."""
        anomalies = []
        participant_ids = {p.get("id") for p in participants}
        participant_map = {p.get("id"): p.get("nom") for p in participants}

        # ── 1. Doublons (même participant, même date, même heure) ──
        seen = set()
        for pr in presences:
            pid = pr.get("participant_id")
            date = pr.get("date")
            heure = pr.get("heure")
            key = (pid, date, heure)
            if key in seen:
                anomalies.append({
                    "type": "doublon",
                    "severity": "warning",
                    "message": (
                        f"Doublon détecté : {participant_map.get(pid, 'Inconnu')} "
                        f"le {date} à {heure}"
                    ),
                    "participant_nom": participant_map.get(pid),
                    "participant_id": pid,
                    "details": {"date": date, "heure": heure},
                })
            seen.add(key)

        # ── 2. Participants inconnus ──
        for pr in presences:
            pid = pr.get("participant_id")
            if pid is not None and pid not in participant_ids:
                anomalies.append({
                    "type": "participant_inconnu",
                    "severity": "error",
                    "message": f"Participant ID={pid} inconnu dans la liste",
                    "participant_id": pid,
                    "details": pr,
                })

        # ── 3. Présences hors plage horaire ──
        heure_min, heure_max = PLAGE_HORAIRE_VALIDE
        for pr in presences:
            h_str = pr.get("heure")
            if not h_str:
                continue
            try:
                h = datetime.strptime(str(h_str), "%H:%M:%S").time()
                if not (heure_min <= h <= heure_max):
                    anomalies.append({
                        "type": "hors_plage",
                        "severity": "info",
                        "message": (
                            f"Présence hors plage valide : "
                            f"{participant_map.get(pr.get('participant_id'), '?')} "
                            f"à {h_str}"
                        ),
                        "participant_nom": participant_map.get(pr.get("participant_id")),
                        "participant_id": pr.get("participant_id"),
                        "details": {"date": pr.get("date"), "heure": h_str},
                    })
            except ValueError:
                anomalies.append({
                    "type": "hors_plage",
                    "severity": "warning",
                    "message": f"Format d'heure invalide : {h_str}",
                    "details": {"heure_brute": h_str},
                })

        # ── 4. Absences incohérentes (marqué présent=False pour TOUTES les séances) ──
        pres_by_participant: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for p in presences:
            pid = p.get("participant_id")
            if pid is not None:
                pres_by_participant[pid].append(p)

        for pid, prs in pres_by_participant.items():
            presents = [p for p in prs if p.get("present", False)]
            if not presents and len(prs) > 0:
                anomalies.append({
                    "type": "absence_incoherente",
                    "severity": "warning",
                    "message": (
                        f"{participant_map.get(pid, '?')} est marqué absent "
                        f"sur toutes les séances ({len(prs)})"
                    ),
                    "participant_nom": participant_map.get(pid),
                    "participant_id": pid,
                    "details": {"nb_seances": len(prs)},
                })

        logger.info(f"   🔍 {len(anomalies)} anomalie(s) détectée(s)")
        return anomalies

    # --------------------------------------------------------
    # RECOMMANDATIONS
    # --------------------------------------------------------
    def _generate_recommandations(
        self,
        stats: Dict[str, Any],
        anomalies: List[Dict[str, Any]],
        nb_non_eligibles: int,
    ) -> List[str]:
        """Génère des recommandations (Python pur, basées sur des règles)."""
        recos = []
        taux = float(stats["taux_presence_global"].rstrip("%"))

        if taux < 70:
            recos.append(
                "Taux de présence faible (<70%) — revoir le planning des séances "
                "et renforcer les rappels de convocation."
            )
        elif taux < 85:
            recos.append(
                "Taux de présence moyen — mettre en place des rappels automatiques "
                "24h avant chaque séance."
            )
        else:
            recos.append(
                "Excellent taux de présence — capitaliser sur cette dynamique "
                "pour les prochaines sessions."
            )

        if nb_non_eligibles > 0:
            recos.append(
                f"{nb_non_eligibles} participant(s) sous le seuil de 80% — "
                f"prévoir des sessions de rattrapage."
            )

        # Types d'anomalies
        types_anomalies = {a["type"] for a in anomalies}
        if "doublon" in types_anomalies:
            recos.append(
                "Doublons de présence détectés — vérifier le système de scan "
                "QR code ou la saisie manuelle."
            )
        if "participant_inconnu" in types_anomalies:
            recos.append(
                "Participants inconnus détectés — synchroniser la liste des "
                "inscriptions avec les données de présence."
            )
        if "absence_incoherente" in types_anomalies:
            recos.append(
                "Absences incohérentes détectées — vérifier les enregistrements "
                "des présences manuellement."
            )

        # Limiter à 5
        return recos[:5]

    # --------------------------------------------------------
    # RÉSUMÉ
    # --------------------------------------------------------
    def _build_resume(
        self,
        stats: Dict[str, Any],
        nb_anomalies: int,
        nb_eligibles: int,
    ) -> str:
        """Construit le résumé texte."""
        return (
            f"Sur {stats['total_participants']} participants et "
            f"{stats['total_seances']} séances, le taux de présence global "
            f"est de {stats['taux_presence_global']}. "
            f"{nb_eligibles} participant(s) sont éligibles aux attestations "
            f"(≥ {SEUIL_ELIGIBILITE_ATTESTATION}%). "
            f"{nb_anomalies} anomalie(s) détectée(s) dans les enregistrements."
        )