import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.services.formations.presence_analyzer_service import SEUIL_ELIGIBILITE_ATTESTATION
from app.services.hitl import create_review
from app.services.llm import LLMNotAvailableError, get_llm_provider

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
    def _load_prompt(self) -> dict[str, Any]:
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
        session_info: dict[str, Any],
        participant: dict[str, Any],
        contexte_rag: str = "",
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
            f"- Durée : {session_info.get('duree_jours', 0)} jour(s)",
            f"- Durée totale observée : {session_info.get('duree_heures') or 'Non renseignée'} heure(s)",
            "",
            "=== PARTICIPANT ===",
            f"- Nom : {participant.get('nom', 'N/A')}",
            f"- Genre : {participant.get('genre', 'N/A')}",
            f"- Entreprise : {participant.get('entreprise', 'N/A')}",
        ]

        if contexte_rag:
            lines += [
                "",
                "=== CONTENU DE RÉFÉRENCE DE LA FORMATION ===",
                contexte_rag,
                "",
                "→ Utilise ces extraits pour rédiger des compétences précises et "
                "spécifiques aux thèmes, outils et techniques abordés.",
            ]
        elif session_info.get("require_grounded_competencies") and session_info.get("themes"):
            lines += [
                "",
                "=== THÈMES CONSIGNÉS AUX SÉANCES ===",
                *[f"- {theme}" for theme in session_info["themes"]],
                "",
                "Base les compétences uniquement sur ces thèmes enregistrés.",
            ]

        lines += ["", "Retourne UNIQUEMENT le JSON valide, sans texte autour."]
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION — 1 participant (LLM + fallback)
    # --------------------------------------------------------
    async def generate_one(
        self,
        session_info: dict[str, Any],
        participant: dict[str, Any],
        index: int = 1,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        start = datetime.now()
        numero = self._build_unique_number(session_info, index)

        vlog(f"🚀 [AttestationAgent] Génération pour {participant.get('nom')} (n° {numero})")

        # ── ÉTAPE 0 : CONTEXTE RAG ──
        contexte_rag = ""
        try:
            from app.services.formations.knowledge_base_service import KnowledgeBaseService

            # Résoudre formation_code si absent : chercher dans le registre par titre
            formation_code = session_info.get("formation_code") or session_info.get("code")
            if not formation_code:
                from app.services.rag.registry_service import charger_registre
                titre = (session_info.get("titre") or "").lower()
                for entree in charger_registre().values():
                    if entree.formation_code and titre and titre in (entree.formation_titre or "").lower():
                        formation_code = entree.formation_code
                        break

            kb = KnowledgeBaseService()
            contexte_rag = await kb.get_formation_context(
                formation_titre=session_info.get("titre", ""),
                domaine=session_info.get("domaine", ""),
                formation_code=formation_code,
            )
            if contexte_rag:
                vlog(f"   📚 [AttestationAgent] Contexte RAG injecté (formation_code={formation_code})")
        except Exception as exc:
            logger.warning(f"   ⚠️  [AttestationAgent] RAG non disponible : {exc}")

        session_themes = [
            str(theme).strip()
            for theme in session_info.get("themes", [])
            if str(theme).strip()
        ]
        syllabus_competencies: list[str] = []
        formation_code = session_info.get("formation_code") or session_info.get("code")
        if not contexte_rag and formation_code:
            try:
                from app.services.hitl import get_review, list_reviews

                for review_info in list_reviews(status="approved", agent_id="agent_rag_syllabus"):
                    review = get_review(review_info.get("review_id", "")) or {}
                    syllabus = review.get("data") or {}
                    if str(syllabus.get("code", "")) != str(formation_code):
                        continue
                    syllabus_competencies = [
                        str(value).strip()
                        for value in syllabus.get("competences", [])
                        if str(value).strip()
                    ]
                    if not syllabus_competencies:
                        syllabus_competencies = [
                            str(module.get("titre", "")).strip()
                            for module in syllabus.get("modules", [])
                            if isinstance(module, dict) and str(module.get("titre", "")).strip()
                        ]
                    if syllabus_competencies:
                        contexte_rag = "Syllabus approuvé par validation humaine :\n" + "\n".join(
                            f"- {value}" for value in syllabus_competencies
                        )
                        break
            except Exception as exc:
                logger.warning("   ⚠️ Syllabus approuvé indisponible : %s", type(exc).__name__)
        grounded_competencies = list(dict.fromkeys(syllabus_competencies + [
            f"Contenu travaillé : {theme}" for theme in session_themes
        ]))
        require_grounded_competencies = bool(session_info.get("require_grounded_competencies"))
        has_training_sources = bool(
            (contexte_rag and not contexte_rag.startswith("Syllabus approuvé"))
            or len(grounded_competencies) >= 3
        )

        content = None
        source = "fallback_template"

        # Sans source pédagogique, le LLM ne doit pas inventer de compétences.
        # Une attestation de participation reste possible si l'éligibilité est
        # vérifiée par les pointages en amont.
        if self.llm and (not require_grounded_competencies or has_training_sources):
            try:
                content = await self._generate_with_llm(
                    session_info, participant, temperature, max_tokens,
                    contexte_rag=contexte_rag,
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
            content = self._generate_with_template(
                {**session_info, "syllabus_competencies": grounded_competencies},
                participant,
                session_themes=session_themes,
            )
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
                "competencies_source": (
                    "participation_only" if not content.get("competences") else
                    "approved_syllabus" if contexte_rag.startswith("Syllabus approuvé") else
                    "rag_supports" if contexte_rag else
                    "session_themes" if session_themes else "generic_fallback"
                ),
            },
        }

    # --------------------------------------------------------
    # RE-VÉRIFICATION DU SEUIL (correction 1a) — Agent 5 ne fait PAS
    # confiance à la liste fournie par l'appelant : un participant sous
    # le seuil (ou dont l'éligibilité n'est pas vérifiable) est refusé et
    # signalé, jamais généré silencieusement (conformité CDC : attestation
    # à partir de 80% de présence).
    # --------------------------------------------------------
    def _verifier_eligibilite(self, participant: dict[str, Any]) -> "tuple[bool, str | None]":
        """
        Retourne (eligible, raison_du_refus). `eligible_attestation`
        un booléen négatif de l'Agent 4 fait foi. Un booléen positif est
        revérifié contre `taux_presence` lorsqu'il est fourni.
        Aucune donnée manquante n'est supposée éligible par défaut.
        """
        if "eligible_attestation" in participant:
            valeur = participant["eligible_attestation"]
            if isinstance(valeur, bool):
                if not valeur:
                    return False, f"Sous le seuil de {SEUIL_ELIGIBILITE_ATTESTATION}% de présence (calcul Agent 4)."
                if participant.get("taux_presence") is None:
                    return True, None

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
        self, eligible_participants: list[dict[str, Any]],
    ) -> "tuple[list[dict[str, Any]], list[dict[str, Any]]]":
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
        session_info: dict[str, Any],
        eligible_participants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [AttestationAgent] BATCH — {len(eligible_participants)} participants")
        vlog("=" * 70)

        verifies, rejetes = self._filtrer_eligibles(eligible_participants)

        semaphore = asyncio.Semaphore(5)

        async def _generer(index: int, p: dict[str, Any]):
            async with semaphore:
                return await self.generate_one(session_info, p, index=index)

        resultats = await asyncio.gather(
            *[_generer(i, p) for i, p in enumerate(verifies, start=1)],
            return_exceptions=True,
        )

        attestations = []
        failed = []
        for p, res in zip(verifies, resultats):
            if isinstance(res, Exception):
                logger.error(f"   ❌ Échec pour {p.get('nom')} : {res}")
                failed.append({"participant": p, "error": str(res)})
            else:
                attestations.append(res)

        elapsed = round((datetime.now() - start).total_seconds(), 2)
        vlog("=" * 70)
        vlog(
            f"✅ [AttestationAgent] BATCH terminé — "
            f"{len(attestations)}/{len(eligible_participants)} en {elapsed}s "
            f"({len(rejetes)} refusé(s) seuil)"
        )
        vlog("=" * 70)

        result = {
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

        review_id = create_review(
            agent_id="agent_5_attestations",
            data=result,
            summary=(
                f"{len(attestations)} attestation(s) générée(s) — "
                f"à valider avant envoi aux participants"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"
        vlog(f"⏳ [HITL] Review créé : {review_id}")
        return result

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------
    async def _generate_with_llm(
        self,
        session_info: dict[str, Any],
        participant: dict[str, Any],
        temperature: float,
        max_tokens: int,
        contexte_rag: str = "",
    ) -> dict[str, Any]:
        response = await self.llm.generate(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(session_info, participant, contexte_rag),
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

    def _validate_llm_output(self, data: dict[str, Any]) -> None:
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
        session_info: dict[str, Any],
        participant: dict[str, Any],
        session_themes: list[str] | None = None,
    ) -> dict[str, Any]:
        nom = participant.get("nom", "Participant")
        genre = (participant.get("genre") or "").lower()
        civilite = (
            "Madame" if genre in ("f", "feminin", "féminin", "femme") else
            "Monsieur" if genre in ("m", "masculin", "homme") else
            ""
        )

        date_debut = session_info.get("date_debut", "")
        date_fin = session_info.get("date_fin", "")
        dates_str = self._format_date_range(date_debut, date_fin)

        duree_jours = session_info.get("duree_jours", 2)
        heures = session_info.get("duree_heures")
        duree_str = f"{duree_jours} jour{'s' if duree_jours > 1 else ''}"
        if heures:
            duree_str += f" ({heures:g} heures)"

        domaine = session_info.get("domaine", "Formation")
        formateur = session_info.get("formateur", "Formateur")

        if session_info.get("require_grounded_competencies"):
            competences = (session_info.get("syllabus_competencies") or [])[:5]
            if not competences:
                competences = [
                    f"Contenu travaillé : {theme}"
                    for theme in (session_themes or [])[:5]
                ]
        else:
            competences = [
                f"Maîtriser les concepts fondamentaux en {domaine}",
                f"Appliquer les méthodes et outils essentiels du domaine {domaine}",
                f"Analyser des cas pratiques liés à {domaine}",
            ]
        designation = f"{civilite} {nom}".strip()

        return {
            "titre_attestation": (
                "ATTESTATION DE PARTICIPATION"
                if session_info.get("require_grounded_competencies")
                else "ATTESTATION DE FORMATION"
            ),
            "introduction": f"La Direction d’ALTIORA PREST a le plaisir de reconnaître la participation de {designation}",
            "corps": (
                f"a participé à la formation professionnelle « {session_info.get('titre', 'Formation professionnelle')} ». "
                "Sa présence, confirmée par les pointages de la session, témoigne de son engagement dans ce parcours d’apprentissage."
            ),
            "details": {
                "formation": session_info.get("titre", "Formation professionnelle"),
                "dates": dates_str,
                "lieu": f"{session_info.get('lieu', 'Antananarivo')}, Madagascar",
                "duree": duree_str,
                "formateur": formateur,
                "domaine": domaine,
                "niveau": session_info.get("niveau_cible", "Intermédiaire"),
            },
            "competences": competences,
            "cloture": (
                f"ALTIORA PREST adresse ses félicitations à {designation} et lui souhaite pleine réussite "
                "dans la suite de son parcours professionnel."
            ),
            "lieu_emission": "Antananarivo",
            "date_emission": date_fin or datetime.now().strftime("%Y-%m-%d"),
        }

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------
    def _build_unique_number(self, session_info: dict[str, Any], index: int) -> str:
        year = datetime.now().year
        domaine = session_info.get("domaine", "GEN")
        code = self.DOMAIN_CODES.get(domaine, domaine[:3].upper() if domaine else "GEN")
        code = re.sub(r"[^A-Z0-9]", "", str(code).upper())[:8] or "GEN"
        registry = self.OUTPUT_DIR / ".numero_registry"
        registry.mkdir(parents=True, exist_ok=True)
        for serial in range(1, 1_000_000):
            numero = f"ALT-{year}-{code}-{serial:04d}"
            reservation = registry / f"{numero}.reserve"
            try:
                reservation.touch(exist_ok=False)
                return numero
            except FileExistsError:
                continue
        raise RuntimeError("Espace de numérotation des attestations épuisé.")

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
        attestation_result: dict[str, Any],
        participant: dict[str, Any],
        output_path: Path | None = None,
    ) -> str | None:
        try:
            self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            numero = attestation_result["numero_unique"]
            pdf_path = output_path or self.OUTPUT_DIR / f"attestation_{numero}.pdf"
            pdf_path = Path(pdf_path).resolve()
            if self.OUTPUT_DIR.resolve() not in pdf_path.parents:
                raise ValueError("Le PDF doit être enregistré dans le dossier des attestations.")
            # ReportLab est utilisé pour garantir la page paysage unique même
            # lorsque le contenu pédagogique généré est long.
            return self._build_pdf_with_reportlab(attestation_result, pdf_path)

        except Exception as e:
            logger.error(f"   ❌ PDF échoué : {type(e).__name__} — {e}")
            return None

    def _build_pdf_from_template(self, result: dict[str, Any], pdf_path: Path) -> str:
        import shutil
        import subprocess
        import tempfile

        from docxtpl import DocxTemplate

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

    def _build_pdf_with_reportlab(self, result: dict[str, Any], pdf_path: Path) -> str:
        from xml.sax.saxutils import escape

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import KeepInFrame, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        content = result["content"]
        details = content.get("details") or {}
        participant = result.get("participant") or {}
        metadata = result.get("metadata") or {}
        palette = {
            "navy": colors.HexColor("#0B1F4D"),
            "dark_navy": colors.HexColor("#06132F"),
            "gold": colors.HexColor("#D4AF37"),
            "gold_dark": colors.HexColor("#B88A1A"),
            "gold_light": colors.HexColor("#F3E5AB"),
            "ink": colors.HexColor("#06132F"),
            "muted": colors.HexColor("#5D5D5D"),
            "line": colors.HexColor("#E3E5E8"),
            "wash": colors.HexColor("#F7F7F6"),
            "white": colors.white,
        }

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=landscape(A4),
            leftMargin=1.65*cm, rightMargin=1.65*cm,
            topMargin=1.35*cm, bottomMargin=1.35*cm,
        )

        styles = getSampleStyleSheet()
        brand_st = ParagraphStyle("Brand", parent=styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=14, leading=16, textColor=palette["navy"])
        address_st = ParagraphStyle("Address", parent=styles["Normal"], fontSize=8.5,
                                    leading=11, textColor=palette["muted"])
        ref_st = ParagraphStyle("Reference", parent=styles["Normal"], fontName="Helvetica-Bold",
                                fontSize=8, leading=11, alignment=TA_RIGHT, textColor=palette["gold_dark"])
        title_st = ParagraphStyle("CertificateTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                                  fontSize=21, leading=24, textColor=palette["navy"],
                                  alignment=TA_CENTER, spaceAfter=2)
        lead_st = ParagraphStyle("Lead", parent=styles["Normal"], fontSize=11,
                                 leading=14, alignment=TA_CENTER, textColor=palette["muted"])
        person_st = ParagraphStyle("Person", parent=styles["Normal"], fontName="Helvetica-Bold",
                                   fontSize=19, leading=23, alignment=TA_CENTER, textColor=palette["navy"])
        body_st = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5,
                                 leading=14, alignment=TA_CENTER, textColor=palette["ink"])
        label_st = ParagraphStyle("FactLabel", parent=styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=7, leading=9, textColor=palette["muted"])
        value_st = ParagraphStyle("FactValue", parent=styles["Normal"], fontName="Helvetica-Bold",
                                  fontSize=9, leading=12, textColor=palette["ink"])
        section_st = ParagraphStyle("Section", parent=styles["Normal"], fontName="Helvetica-Bold",
                                    fontSize=8.5, leading=11, textColor=palette["navy"])
        confirmation_st = ParagraphStyle("Confirmation", parent=styles["Normal"], fontSize=9,
                                         leading=12, textColor=palette["ink"])
        competency_st = ParagraphStyle("Competency", parent=styles["Normal"], fontSize=8.5,
                                       leading=11, leftIndent=8, textColor=palette["ink"])
        closing_st = ParagraphStyle("Closing", parent=styles["Normal"], fontSize=8,
                                    leading=11, textColor=palette["muted"])
        signature_st = ParagraphStyle("Signature", parent=styles["Normal"], fontSize=8.5,
                                      leading=12, alignment=TA_CENTER, textColor=palette["ink"])

        _logo_path = Path(__file__).resolve().parents[2] / "templates" / "logo_altiora_prest.png"
        story = []

        def para(value: Any, style: ParagraphStyle) -> Paragraph:
            return Paragraph(escape(str(value or "")), style)

        if _logo_path.exists():
            logo = RLImage(str(_logo_path), width=3.45*cm, height=1.25*cm, kind="proportional")
            logo.hAlign = "LEFT"
            brand = [para("ALTIORA PREST", brand_st), para("Antananarivo, Madagascar", address_st)]
            header_left = Table([[logo, brand]], colWidths=[4.0*cm, 7.5*cm])
            header_left.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
        else:
            header_left = [para("ALTIORA PREST", brand_st), para("Antananarivo, Madagascar", address_st)]

        reference = Paragraph(f"RÉFÉRENCE<br/>{escape(str(result.get('numero_unique', '')))}", ref_st)
        header = Table([[header_left, reference]], colWidths=[doc.width * 0.72, doc.width * 0.28])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 1, palette["line"]),
            ("LINEBELOW", (0, 0), (0, 0), 2, palette["gold"]),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([header, Spacer(1, 0.42*cm), para(content.get("titre_attestation", "ATTESTATION DE FORMATION"), title_st)])

        # Garder le texte légal éditable tout en mettant le nom en valeur quand
        # il apparaît à la fin de la phrase générée.
        introduction = str(content.get("introduction") or "")
        person_name = " ".join(str(value).strip() for value in (participant.get("prenom"), participant.get("nom")) if value)
        if person_name and person_name in introduction:
            lead, _, _ = introduction.rpartition(person_name)
            story.extend([para(lead.strip(), lead_st), para(person_name, person_st)])
        else:
            story.append(para(introduction, person_st))
        story.extend([para(content.get("corps", ""), body_st), Spacer(1, 0.25*cm)])

        def fact(label: str, key: str, fallback: str = "—") -> list[Paragraph]:
            value = details.get(key) or fallback
            return [para(label.upper(), label_st), para(value, value_st)]

        fact_rows = [
            [fact("Formation", "formation", "Formation professionnelle"), fact("Dates", "dates"), fact("Lieu", "lieu")],
            [fact("Durée", "duree"), fact("Formateur", "formateur"), [
                para("DOMAINE ET NIVEAU", label_st),
                para(" · ".join(str(value) for value in (details.get("domaine"), details.get("niveau")) if value) or "—", value_st),
            ]],
        ]
        try:
            attendance_rate = float(str(participant.get("taux_presence", "")).rstrip("% ").replace(",", "."))
        except (TypeError, ValueError):
            attendance_rate = None
        facts = Table(fact_rows, colWidths=[doc.width / 3] * 3, rowHeights=[1.25*cm, 1.25*cm])
        facts.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), palette["wash"]),
            ("BOX", (0, 0), (-1, -1), 0.7, palette["line"]),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, palette["line"]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([facts, Spacer(1, 0.3*cm)])

        if attendance_rate is not None or metadata.get("competencies_source") == "participation_only":
            threshold = SEUIL_ELIGIBILITE_ATTESTATION
            rate_text = (
                f"Taux de présence vérifié : {attendance_rate:g} % ; seuil requis : {threshold} %."
                if attendance_rate is not None
                else f"Le seuil de présence de {threshold} % est atteint, selon les pointages enregistrés."
            )
            confirmation_title = (
                "PRÉSENCE ET PARTICIPATION CONFIRMÉES"
                if metadata.get("competencies_source") == "participation_only"
                else "ASSIDUITÉ VÉRIFIÉE"
            )
            confirmation = Table([[ [para(confirmation_title, section_st), para(rate_text, confirmation_st)] ]], colWidths=[doc.width])
            confirmation.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), palette["gold_light"]),
                ("BOX", (0, 0), (-1, -1), 0.8, palette["gold_dark"]),
                ("LINEBEFORE", (0, 0), (0, 0), 4, palette["gold"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(confirmation)

        competences = content.get("competences") or []
        if competences:
            story.extend([Spacer(1, 0.24*cm), para("CONTENUS DE FORMATION DOCUMENTÉS", section_st)])
            competency_data = [[[
                para(f"• {value}", competency_st) for value in competences[:6]
            ]]]
            competency_table = Table(competency_data, colWidths=[doc.width], hAlign="LEFT")
            competency_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), palette["white"]),
                ("BOX", (0, 0), (-1, -1), 0.55, palette["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(competency_table)

        story.extend([Spacer(1, 0.25*cm), para(content.get("cloture", ""), closing_st)])
        issuance = para(
            f"Fait à {content.get('lieu_emission', 'Antananarivo')}, le {content.get('date_emission', '')}",
            signature_st,
        )
        signature = Paragraph(
            "<b>La Direction</b><br/>ALTIORA PREST<br/><br/><font color='#657487'>Signature et cachet</font>",
            signature_st,
        )
        sign_block = Table([[issuance, signature]], colWidths=[doc.width * 0.62, doc.width * 0.38])
        sign_block.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"), ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("LINEABOVE", (1, 0), (1, 0), 0.7, palette["gold"]),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.extend([Spacer(1, 0.22*cm), sign_block])

        def draw_page(canvas: Any, _document: Any) -> None:
            canvas.saveState()
            page_width, page_height = landscape(A4)
            canvas.setStrokeColor(palette["navy"])
            canvas.setLineWidth(0.8)
            canvas.roundRect(0.55*cm, 0.55*cm, page_width - 1.1*cm, page_height - 1.1*cm, 8, stroke=1, fill=0)
            canvas.setStrokeColor(palette["gold"])
            canvas.setLineWidth(1.8)
            canvas.line(0.8*cm, page_height - 0.72*cm, 3.2*cm, page_height - 0.72*cm)
            canvas.setFillColor(palette["muted"])
            canvas.setFont("Helvetica", 7)
            canvas.drawCentredString(page_width / 2, 0.83*cm, "ALTIORA PREST  ·  ATTESTATION À CONSERVER PAR LE BÉNÉFICIAIRE")
            canvas.restoreState()

        # Une attestation tient toujours sur une seule page paysage. KeepInFrame
        # réduit proportionnellement le contenu si les textes générés sont longs.
        doc.build(
            [KeepInFrame(doc.width, doc.height, story, mode="shrink", vAlign="TOP")],
            onFirstPage=draw_page,
            onLaterPages=draw_page,
        )
        vlog(f"   ✅ PDF (reportlab) : {pdf_path.name}")
        return str(pdf_path)

    # --------------------------------------------------------
    # PUBLIQUE — AVEC PDF
    # --------------------------------------------------------
    async def generate_one_with_pdf(
        self,
        session_info: dict[str, Any],
        participant: dict[str, Any],
        index: int = 1,
        create_individual_review: bool = True,
    ) -> dict[str, Any]:
        result = await self.generate_one(session_info, participant, index)
        pdf_path = self._build_attestation_pdf(result, participant)

        result["pdf_path"] = pdf_path
        result["pdf_generated"] = pdf_path is not None
        result["approval_status"] = "pending_review"
        result["metadata"]["pdf_generated"] = pdf_path is not None
        if pdf_path:
            result["metadata"]["pdf_path"] = pdf_path

        if create_individual_review:
            review_id = create_review(
                agent_id="agent_5_attestations",
                data=result,
                summary=(
                    f"Attestation {result['numero_unique']} — "
                    f"{participant.get('nom', 'N/A')} — à valider avant envoi"
                ),
                criticity="critical",
            )
            result["_review_id"] = review_id
            result["_review_status"] = "pending_review"
            vlog(f"⏳ [HITL] Review créé : {review_id}")

        return result

    async def generate_batch_with_pdf(
        self,
        session_info: dict[str, Any],
        eligible_participants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [AttestationAgent] BATCH+PDF — {len(eligible_participants)} participants")
        vlog("=" * 70)

        verifies, rejetes = self._filtrer_eligibles(eligible_participants)

        semaphore = asyncio.Semaphore(5)

        async def _generer_pdf(index: int, p: dict[str, Any]):
            async with semaphore:
                return await self.generate_one_with_pdf(
                    session_info, p, index=index, create_individual_review=False
                )

        resultats = await asyncio.gather(
            *[_generer_pdf(i, p) for i, p in enumerate(verifies, start=1)],
            return_exceptions=True,
        )

        attestations, failed = [], []
        for p, res in zip(verifies, resultats):
            if isinstance(res, Exception):
                logger.error(f"   ❌ Échec {p.get('nom')} : {res}")
                failed.append({"participant": p, "error": str(res)})
            elif not res.get("pdf_generated"):
                failed.append({
                    "participant": p,
                    "error": "Le PDF n'a pas pu être généré ; aucune validation n'a été créée.",
                })
            else:
                attestations.append(res)

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

        # Aucun dossier HITL vide : il n'y a rien à valider ni à télécharger.
        if pdf_ok:
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
        else:
            result["_review_status"] = "generation_failed"
            result["message"] = "Aucun PDF n'a pu être généré. Consultez les erreurs par participant."
        return result
