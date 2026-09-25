import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.services.hitl import create_review
from app.services.llm import LLMNotAvailableError, get_llm_provider
from app.services.formations.presence_analyzer_service import SEUIL_ELIGIBILITE_ATTESTATION

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# ============================================================
# CONFIG
# ============================================================
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "attestation_generation.yaml"


# ============================================================
# SERVICE
# ============================================================
class AttestationGeneratorService:
    """
    Agent 5 — Génère le contenu des attestations (1 ou batch).

    Chaque attestation est identifiée par un numéro unique :
        ALT-{ANNEE}-{CODE_DOMAINE}-{INDEX:04d}
        Exemple : ALT-2026-IA-0001
    """

    DOMAIN_CODES = {
        "IA": "IA", "Intelligence Artificielle": "IA",
        "Data": "DATA", "Data Science": "DATA",
        "Management": "MGT", "Marketing": "MKT",
        "Finance": "FIN", "RH": "RH",
    }

    # Chemins de template et output
    TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "templates" / "attestations" / "template_attestation.docx"
    OUTPUT_DIR = Path(__file__).resolve().parents[3] / "exports" / "attestations"

    def __init__(self):
        try:
            self.llm = get_llm_provider()
        except LLMNotAvailableError:
            logger.warning("⚠️  Aucun provider LLM disponible → mode fallback uniquement.")
            self.llm = None

        self.prompt_config = self._load_prompt()
        vlog(
            f"✅ AttestationGeneratorService initialisé "
            f"(provider={self.llm.get_provider_name() if self.llm else 'aucun'}, "
            f"llm={'✅' if self.llm else '❌ fallback only'})"
        )

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------
    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")
        vlog(f"✅ Prompt chargé : {PROMPT_PATH.name}")
        return config

    def _build_system_prompt(self) -> str:
        cfg = self.prompt_config
        return "\n".join([
            "=== RÔLE ===", cfg.get("role", "").strip(), "",
            "=== TÂCHE ===", cfg.get("tache", "").strip(), "",
            "=== FORMAT ===", cfg.get("format", "").strip(), "",
            "=== CONTEXTE ===", cfg.get("contexte", "").strip(), "",
            "=== RÈGLES STRICTES ===",
            cfg.get("regles", "") if isinstance(cfg.get("regles"), str)
            else "\n".join(f"- {r}" for r in cfg.get("regles", [])),
        ])

    def _build_user_prompt(
        self,
        session_info: Dict[str, Any],
        participant: Dict[str, Any],
    ) -> str:
        lines = [
            "Génère le contenu de l'attestation pour le participant suivant.",
            "",
            "=== SESSION ===",
            f"- Titre : {session_info.get('titre', 'N/A')}",
            f"- Domaine : {session_info.get('domaine', 'N/A')}",
            f"- Niveau : {session_info.get('niveau_cible', 'N/A')}",
            f"- Date début : {session_info.get('date_debut', 'N/A')}",
            f"- Date fin : {session_info.get('date_fin', 'N/A')}",
            f"- Lieu : {session_info.get('lieu', 'N/A')}",
            f"- Formateur : {session_info.get('formateur', 'N/A')}",
            f"- Durée (jours) : {session_info.get('duree_jours', 2)}",
            "",
            "=== PARTICIPANT ===",
            f"- Nom : {participant.get('nom', 'N/A')}",
            f"- Genre : {participant.get('genre', 'N/A')}",
            f"- Entreprise : {participant.get('entreprise', 'N/A')}",
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION — 1 participant (LLM + fallback)
    # --------------------------------------------------------
    async def generate_one(
        self,
        session_info: Dict[str, Any],
        participant: Dict[str, Any],
        index: int = 1,
        temperature: float = 0.4,
        max_tokens: int = 8000,
    ) -> Dict[str, Any]:
        start = datetime.now()
        numero = self._build_unique_number(session_info, index)

        vlog(f"🚀 [AttestationAgent] Génération pour {participant.get('nom')} (n° {numero})")

        content = None
        source = "fallback_template"

        # ── ÉTAPE 1 : ESSAI LLM ──
        if self.llm:
            try:
                content = await self._generate_with_llm(
                    session_info, participant, temperature, max_tokens
                )
                source = "llm"
                vlog("   ✅ Contenu généré par LLM (Groq)")
            except Exception as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule sur template Python."
                )

        # ── ÉTAPE 2 : FALLBACK ──
        if content is None:
            content = self._generate_with_template(session_info, participant)
            vlog("   ✅ Contenu généré par template Python (fallback)")

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        return {
            "success": True,
            "participant": participant,
            "content": content,
            "numero_unique": numero,
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "participant_id": participant.get("id"),
                "session_id": session_info.get("id"),
            },
        }

    # --------------------------------------------------------
    # RE-VÉRIFICATION DU SEUIL (correction 1a) — Agent 5 ne fait PAS
    # confiance à la liste fournie par l'appelant : un participant sous
    # le seuil (ou dont l'éligibilité n'est pas vérifiable) est refusé et
    # signalé, jamais généré silencieusement (conformité CDC : attestation
    # à partir de 80% de présence).
    # --------------------------------------------------------
    def _verifier_eligibilite(self, participant: Dict[str, Any]) -> "tuple[bool, Optional[str]]":
        """
        Retourne (eligible, raison_du_refus). `eligible_attestation`
        (booléen déjà calculé par l'Agent 4) fait foi s'il est présent —
        sinon on retombe sur `taux_presence` (chaîne "85.0%" ou nombre).
        Aucune donnée manquante n'est supposée éligible par défaut.
        """
        if "eligible_attestation" in participant:
            valeur = participant["eligible_attestation"]
            if isinstance(valeur, bool):
                if valeur:
                    return True, None
                return False, f"Sous le seuil de {SEUIL_ELIGIBILITE_ATTESTATION}% de présence (calcul Agent 4)."

        taux_brut = participant.get("taux_presence")
        if taux_brut is None:
            return False, (
                "Taux de présence non fourni — éligibilité non vérifiable, "
                "refus par précaution."
            )
        try:
            taux = float(str(taux_brut).rstrip("%").strip())
        except (TypeError, ValueError):
            return False, f"Taux de présence illisible ('{taux_brut}') — éligibilité non vérifiable."

        if taux >= SEUIL_ELIGIBILITE_ATTESTATION:
            return True, None
        return False, f"Taux de présence {taux}% < seuil de {SEUIL_ELIGIBILITE_ATTESTATION}%."

    def _filtrer_eligibles(
        self, eligible_participants: List[Dict[str, Any]],
    ) -> "tuple[List[Dict[str, Any]], List[Dict[str, Any]]]":
        verifies, rejetes = [], []
        for p in eligible_participants:
            ok, raison = self._verifier_eligibilite(p)
            if ok:
                verifies.append(p)
            else:
                logger.warning(f"   🚫 [AttestationAgent] Refusé (seuil) : {p.get('nom')} — {raison}")
                rejetes.append({"participant": p, "raison": raison})
        return verifies, rejetes

    # --------------------------------------------------------
    # GÉNÉRATION — BATCH
    # --------------------------------------------------------
    async def generate_batch(
        self,
        session_info: Dict[str, Any],
        eligible_participants: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [AttestationAgent] BATCH — {len(eligible_participants)} participants")
        vlog("=" * 70)

        verifies, rejetes = self._filtrer_eligibles(eligible_participants)

        attestations = []
        failed = []

        for i, p in enumerate(verifies, start=1):
            try:
                att = await self.generate_one(session_info, p, index=i)
                attestations.append(att)
            except Exception as e:
                logger.error(f"   ❌ Échec pour {p.get('nom')} : {e}")
                failed.append({"participant": p, "error": str(e)})

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        vlog("=" * 70)
        vlog(
            f"✅ [AttestationAgent] BATCH terminé — "
            f"{len(attestations)}/{len(eligible_participants)} en {elapsed}s "
            f"({len(rejetes)} refusé(s) seuil)"
        )
        vlog("=" * 70)

        return {
            "success": True,
            "session_id": session_info.get("id"),
            "total_eligible": len(eligible_participants),
            "total_generated": len(attestations),
            "total_failed": len(failed),
            "total_rejetes_seuil": len(rejetes),
            "attestations": attestations,
            "failed_participants": failed,
            "rejected_ineligible": rejetes,
            "duration_seconds": elapsed,
        }

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(
        self,
        session_info: Dict[str, Any],
        participant: Dict[str, Any],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        response = await self.llm.generate(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(session_info, participant),
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        raw = response["content"]
        finish = response["finish_reason"]

        if finish == "length":
            raise ValueError("Réponse LLM tronquée (finish_reason=length)")

        data = json.loads(raw)
        self._validate_llm_output(data)
        return data

    def _validate_llm_output(self, data: Dict[str, Any]) -> None:
        required = ["titre_attestation", "introduction", "corps", "details",
                    "competences", "cloture", "lieu_emission", "date_emission"]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")
        if not isinstance(data["competences"], list) or len(data["competences"]) < 3:
            raise ValueError("'competences' doit être une liste de 3 éléments minimum")

    # --------------------------------------------------------
    # FALLBACK TEMPLATE
    # --------------------------------------------------------
    def _generate_with_template(
        self,
        session_info: Dict[str, Any],
        participant: Dict[str, Any],
    ) -> Dict[str, Any]:
        nom = participant.get("nom", "Participant")
        genre = (participant.get("genre") or "").lower()
        civilite = "Madame" if genre in ("f", "feminin", "féminin", "femme") else "Monsieur"

        date_debut = session_info.get("date_debut", "")
        date_fin = session_info.get("date_fin", "")
        dates_str = self._format_date_range(date_debut, date_fin)

        duree_jours = session_info.get("duree_jours", 2)
        heures = duree_jours * 7
        duree_str = f"{duree_jours} jour{'s' if duree_jours > 1 else ''} ({heures} heures)"

        domaine = session_info.get("domaine", "Formation")
        formateur = session_info.get("formateur", "Formateur")

        competences = [
            f"Maîtriser les concepts fondamentaux en {domaine}",
            f"Appliquer les méthodes et outils essentiels du domaine {domaine}",
            f"Analyser des cas pratiques liés à {domaine}",
        ]

        return {
            "titre_attestation": "ATTESTATION DE FORMATION",
            "introduction": f"Le Directeur d'ALTIORA Solutions atteste que {civilite} {nom}",
            "corps": "a suivi avec assiduité et succès la formation professionnelle intitulée :",
            "details": {
                "formation": session_info.get("titre", "Formation professionnelle"),
                "dates": dates_str,
                "lieu": f"{session_info.get('lieu', 'Antananarivo')}, Madagascar",
                "duree": duree_str,
                "formateur": f"Monsieur {formateur}",
                "domaine": domaine,
                "niveau": session_info.get("niveau_cible", "Intermédiaire"),
            },
            "competences": competences,
            "cloture": (
                "En foi de quoi, la présente attestation lui est délivrée "
                "pour servir et valoir ce que de droit."
            ),
            "lieu_emission": "Antananarivo",
            "date_emission": date_fin or datetime.now().strftime("%Y-%m-%d"),
        }

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------
    def _build_unique_number(self, session_info: Dict[str, Any], index: int) -> str:
        year = datetime.now().year
        domaine = session_info.get("domaine", "GEN")
        code = self.DOMAIN_CODES.get(domaine, domaine[:3].upper() if domaine else "GEN")
        return f"ALT-{year}-{code}-{index:04d}"

    def _format_date_range(self, date_debut: str, date_fin: str) -> str:
        MOIS_FR = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ]
        try:
            d1 = datetime.strptime(date_debut, "%Y-%m-%d")
            d2 = datetime.strptime(date_fin, "%Y-%m-%d")
            if d1.month == d2.month and d1.year == d2.year:
                return f"{d1.day} au {d2.day} {MOIS_FR[d2.month - 1]} {d2.year}"
            return (
                f"{d1.day} {MOIS_FR[d1.month - 1]} au "
                f"{d2.day} {MOIS_FR[d2.month - 1]} {d2.year}"
            )
        except Exception:
            return f"{date_debut} au {date_fin}"

    # --------------------------------------------------------
    # PDF — HYBRIDE
    # --------------------------------------------------------
    def _build_attestation_pdf(
        self,
        attestation_result: Dict[str, Any],
        participant: Dict[str, Any],
    ) -> Optional[str]:
        try:
            self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            numero = attestation_result["numero_unique"]
            pdf_path = self.OUTPUT_DIR / f"attestation_{numero}.pdf"

            if self.TEMPLATE_PATH.exists():
                try:
                    return self._build_pdf_from_template(attestation_result, pdf_path)
                except Exception as e:
                    logger.warning(
                        f"   ⚠️  Template Word échoué ({type(e).__name__}: {e}). "
                        f"Bascule reportlab."
                    )
            else:
                vlog(f"   ℹ️  Template absent. Utilisation reportlab direct.")

            return self._build_pdf_with_reportlab(attestation_result, pdf_path)

        except Exception as e:
            logger.error(f"   ❌ PDF échoué : {type(e).__name__} — {e}")
            return None

    def _build_pdf_from_template(self, result: Dict[str, Any], pdf_path: Path) -> str:
        from docxtpl import DocxTemplate
        import subprocess, shutil, tempfile

        content = result["content"]
        context = {**content, "numero_unique": result["numero_unique"]}

        doc = DocxTemplate(str(self.TEMPLATE_PATH))
        doc.render(context)

        with tempfile.TemporaryDirectory() as tmp:
            docx_out = Path(tmp) / "attestation.docx"
            doc.save(str(docx_out))

            soffice = shutil.which("soffice") or shutil.which("libreoffice")
            if not soffice:
                raise RuntimeError("LibreOffice introuvable")

            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf",
                 "--outdir", str(pdf_path.parent), str(docx_out)],
                check=True, capture_output=True, timeout=60,
            )
            generated = pdf_path.parent / "attestation.pdf"
            if generated.exists():
                generated.replace(pdf_path)

        vlog(f"   ✅ PDF (template) : {pdf_path.name}")
        return str(pdf_path)

    def _build_pdf_with_reportlab(self, result: Dict[str, Any], pdf_path: Path) -> str:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT

        content = result["content"]
        d = content["details"]

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=landscape(A4),
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
        )

        styles = getSampleStyleSheet()
        title_st = ParagraphStyle("T", parent=styles["Title"], fontSize=26,
                                   textColor=colors.HexColor("#1F3A5F"),
                                   alignment=TA_CENTER, spaceAfter=18)
        header_st = ParagraphStyle("H", parent=styles["Heading1"], fontSize=20,
                                    textColor=colors.HexColor("#1F3A5F"),
                                    alignment=TA_CENTER, spaceAfter=6)
        sub_st = ParagraphStyle("S", parent=styles["Normal"], fontSize=11,
                                 alignment=TA_CENTER, textColor=colors.grey, spaceAfter=18)
        body_st = ParagraphStyle("B", parent=styles["Normal"], fontSize=14,
                                  alignment=TA_CENTER, spaceAfter=14)
        small_st = ParagraphStyle("Sm", parent=styles["Normal"], fontSize=11,
                                   alignment=TA_CENTER, spaceAfter=6)

        story = [
            Paragraph("ALTIORA SOLUTIONS", header_st),
            Paragraph("Antananarivo, Madagascar", sub_st),
            Spacer(1, 0.5*cm),
            Paragraph(content["titre_attestation"], title_st),
            Spacer(1, 0.5*cm),
            Paragraph(content["introduction"], body_st),
            Paragraph(content["corps"], body_st),
            Spacer(1, 0.5*cm),
        ]

        details_data = [
            ["Formation", d["formation"]], ["Dates", d["dates"]],
            ["Lieu", d["lieu"]], ["Durée", d["duree"]],
            ["Formateur", d["formateur"]], ["Domaine", d["domaine"]],
            ["Niveau", d["niveau"]],
        ]
        t = Table(details_data, colWidths=[4*cm, 12*cm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0,0), (-1,-1), 11),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("ALIGN", (0,0), (0,-1), "RIGHT"),
            ("ALIGN", (1,0), (1,-1), "LEFT"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#1F3A5F")),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.7*cm))

        story.append(Paragraph("<b>Compétences acquises :</b>", small_st))
        for c in content["competences"]:
            story.append(Paragraph(f"• {c}", small_st))
        story.append(Spacer(1, 0.7*cm))
        story.append(Paragraph(f"<i>{content['cloture']}</i>", small_st))
        story.append(Spacer(1, 1*cm))

        sig_st = ParagraphStyle("Sig", parent=styles["Normal"], fontSize=11, alignment=TA_RIGHT)
        story.append(Paragraph(
            f"Fait à {content['lieu_emission']}, le {content['date_emission']}", sig_st
        ))
        story.append(Paragraph("<b>Le Directeur<br/>ALTIORA Solutions</b>", sig_st))
        story.append(Spacer(1, 0.5*cm))

        num_st = ParagraphStyle("N", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
        story.append(Paragraph(f"N° {result['numero_unique']}", num_st))

        doc.build(story)
        vlog(f"   ✅ PDF (reportlab) : {pdf_path.name}")
        return str(pdf_path)

    # --------------------------------------------------------
    # PUBLIQUE — AVEC PDF
    # --------------------------------------------------------
    async def generate_one_with_pdf(
        self,
        session_info: Dict[str, Any],
        participant: Dict[str, Any],
        index: int = 1,
    ) -> Dict[str, Any]:
        result = await self.generate_one(session_info, participant, index)
        pdf_path = self._build_attestation_pdf(result, participant)

        result["pdf_path"] = pdf_path
        result["pdf_generated"] = pdf_path is not None
        result["metadata"]["pdf_generated"] = pdf_path is not None
        if pdf_path:
            result["metadata"]["pdf_path"] = pdf_path

        return result

    async def generate_batch_with_pdf(
        self,
        session_info: Dict[str, Any],
        eligible_participants: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [AttestationAgent] BATCH+PDF — {len(eligible_participants)} participants")
        vlog("=" * 70)

        verifies, rejetes = self._filtrer_eligibles(eligible_participants)

        attestations, failed = [], []
        for i, p in enumerate(verifies, start=1):
            try:
                att = await self.generate_one_with_pdf(session_info, p, index=i)
                attestations.append(att)
            except Exception as e:
                logger.error(f"   ❌ Échec {p.get('nom')} : {e}")
                failed.append({"participant": p, "error": str(e)})

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        pdf_ok = sum(1 for a in attestations if a.get("pdf_generated"))
        vlog("=" * 70)
        vlog(
            f"✅ BATCH+PDF terminé — {len(attestations)}/{len(eligible_participants)} "
            f"contenus, {pdf_ok} PDF en {elapsed}s ({len(rejetes)} refusé(s) seuil)"
        )
        vlog("=" * 70)

        result = {
            "success": True,
            "session_id": session_info.get("id"),
            "total_eligible": len(eligible_participants),
            "total_generated": len(attestations),
            "total_pdf_generated": pdf_ok,
            "total_failed": len(failed),
            "total_rejetes_seuil": len(rejetes),
            "attestations": attestations,
            "failed_participants": failed,
            "rejected_ineligible": rejetes,
            "duration_seconds": elapsed,
        }

        # ⏳ HITL — Créer un review (CRITIQUE)
        review_id = create_review(
            agent_id="agent_5_attestations",
            data=result,
            summary=(
                f"{pdf_ok} PDF générés — "
                f"à valider avant envoi email aux participants"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog(f"⏳ [HITL] Review créé : {review_id}")
        return result