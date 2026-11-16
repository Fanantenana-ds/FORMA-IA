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
            f"- Intitulé administratif de la session (ne pas recopier automatiquement) : {session_info.get('titre', 'N/A')}",
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

        lines += [
            "",
            "=== TITRE À AFFICHER SUR LE CERTIFICAT ===",
            "Dans details.formation, rédige un intitulé court et naturel (4 à 9 mots) "
            "à partir des contenus réellement étudiés dans les supports, le syllabus "
            "ou les thèmes des séances. N'utilise jamais le titre administratif s'il "
            "décrit un appel d'offres, un recrutement, un marché ou une offre. "
            "Si aucun contenu pédagogique fiable n'est disponible, écris seulement "
            "« Formation professionnelle ».",
        ]

        lines += ["", "Retourne UNIQUEMENT le JSON valide, sans texte autour."]
        return "\n".join(lines)

    async def suggest_certificate_title(self, session_info: dict[str, Any]) -> dict[str, str]:
        """Propose un titre à partir des thèmes saisis, sans reprendre le titre administratif."""
        topics = list(dict.fromkeys(
            str(theme).strip() for theme in session_info.get("themes", []) if str(theme).strip()
        ))
        if not topics:
            return {"title": "Formation professionnelle", "source": "fallback"}

        if self.llm:
            try:
                response = await self.llm.generate(
                    system_prompt=(
                        "Tu es un rédacteur pédagogique. Propose un intitulé de formation court, "
                        "fidèle uniquement aux thèmes fournis. Ignore tout titre administratif. "
                        "N'ajoute aucune compétence ou sujet absent des thèmes. Retourne un JSON "
                        "avec la clé title, 4 à 9 mots maximum."
                    ),
                    user_prompt="Thèmes réellement travaillés :\n" + "\n".join(f"- {topic}" for topic in topics),
                    temperature=0.1,
                    max_tokens=100,
                    json_mode=True,
                )
                suggested = str(json.loads(response["content"]).get("title", "")).strip()
                if suggested and len(suggested) <= 120:
                    safe_title = self._formation_certificate_title(
                        {"details": {"formation": suggested}}, session_info, topics,
                    )
                    if safe_title == suggested:
                        return {"title": suggested, "source": "ia"}
            except Exception as exc:
                logger.warning("Proposition du titre d'attestation indisponible : %s", type(exc).__name__)

        return {
            "title": self._formation_certificate_title({"details": {"formation": ""}}, session_info, topics),
            "source": "themes_seances",
        }

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
                    formation_titre = str(getattr(entree, "formation_titre", "") or "").lower()
                    if entree.formation_code and titre and titre in formation_titre:
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
        # Garantir les clés minimales attendues par le générateur PDF
        if "titre_attestation" not in content:
            content["titre_attestation"] = (
                "ATTESTATION DE PARTICIPATION"
                if session_info.get("require_grounded_competencies")
                else "ATTESTATION DE FORMATION"
            )
        if not isinstance(content.get("details"), dict):
            content["details"] = {
                "formation": session_info.get("titre", ""),
                "dates": content.get("date_emission", ""),
                "lieu": session_info.get("lieu", ""),
                "duree": f"{session_info.get('duree_jours', '')} jour(s)",
                "formateur": session_info.get("formateur", ""),
                "domaine": session_info.get("domaine", ""),
                "niveau": session_info.get("niveau_cible", ""),
            }

        title_sources = list(dict.fromkeys(syllabus_competencies + session_themes))
        if contexte_rag and not contexte_rag.startswith("Syllabus approuvé"):
            title_sources.extend(content.get("competences") or [])
        content["details"]["formation"] = self._formation_certificate_title(
            content, session_info, title_sources,
        )
        confirmed_title = str(session_info.get("attestation_title") or "").strip()
        if confirmed_title:
            content["details"]["formation"] = confirmed_title

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
        # titre_attestation est optionnel (le fallback template le génère)
        required = ["introduction", "corps", "cloture", "lieu_emission", "date_emission"]
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

    def _formation_certificate_title(
        self,
        content: dict[str, Any],
        session_info: dict[str, Any],
        source_topics: list[str],
    ) -> str:
        """Keep offer/market titles off certificates; prefer a grounded course title."""
        candidate = str((content.get("details") or {}).get("formation") or "").strip()
        administrative_title = str(session_info.get("titre") or "").strip()
        offer_title = re.search(
            r"\b(?:appel\s+(?:[àa]\s+manifestation\s+d['’]?int[eé]r[eê]t|"
            r"d['’]?offres|[àa]\s+projet)|march[eé]\s+public|recrutement\s+d['’]?)\b",
            candidate,
            flags=re.IGNORECASE,
        )
        generic_titles = {"formation", "formation professionnelle", "formation de formation"}
        if (
            candidate
            and candidate.casefold() != administrative_title.casefold()
            and not offer_title
            and candidate.casefold() not in generic_titles
            and source_topics
        ):
            return candidate

        for topic in source_topics:
            value = re.sub(r"^\s*(?:contenu travaill[eé]\s*:\s*)", "", str(topic), flags=re.IGNORECASE)
            value = re.sub(r"\s+", " ", value).strip(" \t\r\n.;:—-–")
            if not value:
                continue
            # A topic from an approved session is safe to display as the certificate title.
            if len(value) > 64:
                value = value[:61].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
            return value[:1].upper() + value[1:]
        return "Formation professionnelle"

    # --------------------------------------------------------
    # PDF — MODELE PNG ALTIORA
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
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas as rl_canvas

        content = result["content"]
        details = content.get("details") or {}
        participant = result.get("participant") or {}
        numero = str(result.get("numero_unique", ""))
        template_path = (
            Path(__file__).resolve().parents[2]
            / "templates"
            / "attestations"
            / "Attestation de formation Altiora Prest (1).png"
        )
        logo_path = Path(__file__).resolve().parents[2] / "templates" / "logo_altiora_prest.png"
        if not template_path.is_file():
            raise FileNotFoundError(f"Modèle d’attestation PNG introuvable : {template_path}")
        if not logo_path.is_file():
            raise FileNotFoundError(f"Logo officiel ALTIORA PREST introuvable : {logo_path}")

        template = ImageReader(str(template_path))
        image_width, image_height = template.getSize()
        page_width, page_height = landscape(A4)
        # Conserver le ratio du modèle PNG et le centrer sur une page A4 paysage.
        image_draw_height = page_width * image_height / image_width
        image_offset_y = (page_height - image_draw_height) / 2
        pdf = rl_canvas.Canvas(str(pdf_path), pagesize=(page_width, page_height))
        pdf.drawImage(
            template, 0, image_offset_y, width=page_width, height=image_draw_height,
            preserveAspectRatio=True, mask="auto",
        )
        sx = page_width / image_width
        sy = image_draw_height / image_height

        def x(px: float) -> float:
            return px * sx

        def y_from_top(px: float) -> float:
            return page_height - image_offset_y - px * sy

        def cover(x0: float, y0: float, x1: float, y1: float, color) -> None:
            pdf.setFillColor(color)
            pdf.setStrokeColor(color)
            pdf.rect(x(x0), y_from_top(y1), x(x1 - x0), sy * (y1 - y0), fill=1, stroke=0)

        background_white = colors.HexColor("#FDFDFD")
        # Remplacer le logo intégré au PNG par l’image officielle du projet.
        cover(140, 40, 360, 222, background_white)
        # Nettoyer le slogan intégré sans recouvrir le séparateur vertical du modèle.
        cover(132, 222, 360, 248, background_white)
        cover(82, 228, 133, 241, background_white)
        cover(360, 225, 390, 245, background_white)
        official_logo = ImageReader(str(logo_path))
        pdf.drawImage(
            official_logo,
            x(154), y_from_top(228), width=x(190), height=sy * 184,
            preserveAspectRatio=True, anchor="c", mask="auto",
        )

        font_regular = "Helvetica"
        font_bold = "Helvetica-Bold"
        font_italic = "Helvetica-Oblique"
        for name, filename in (
            ("AttestationGeorgia", "georgia.ttf"),
            ("AttestationGeorgia-Bold", "georgiab.ttf"),
            ("AttestationGeorgia-Italic", "georgiai.ttf"),
        ):
            font_path = Path(r"C:\Windows\Fonts") / filename
            if font_path.is_file() and name not in pdfmetrics.getRegisteredFontNames():
                try:
                    pdfmetrics.registerFont(TTFont(name, str(font_path)))
                except Exception:
                    pass
        if "AttestationGeorgia" in pdfmetrics.getRegisteredFontNames():
            font_regular = "AttestationGeorgia"
        if "AttestationGeorgia-Bold" in pdfmetrics.getRegisteredFontNames():
            font_bold = "AttestationGeorgia-Bold"
        if "AttestationGeorgia-Italic" in pdfmetrics.getRegisteredFontNames():
            font_italic = "AttestationGeorgia-Italic"

        person_name = " ".join(
            str(value).strip()
            for value in (participant.get("prenom"), participant.get("nom"))
            if value
        ).strip()
        if not person_name:
            person_name = str(participant.get("nom") or "Participant").strip()

        def fitted_size(text: str, font: str, start: float, minimum: float, width_px: float) -> float:
            max_width = x(width_px)
            size = start
            while size > minimum and pdfmetrics.stringWidth(text, font, size) > max_width:
                size -= 0.5
            return size

        def wrap(text: str, font: str, size: float, max_width_px: float) -> list[str]:
            words = str(text).split()
            lines: list[str] = []
            current = ""
            max_width = x(max_width_px)
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and pdfmetrics.stringWidth(candidate, font, size) > max_width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                lines.append(current)
            return lines

        def draw_centered_lines(lines: list[str], center_px: float, baseline_px: float, font: str, size: float, leading: float) -> None:
            pdf.setFont(font, size)
            for index, line in enumerate(lines):
                pdf.drawCentredString(x(center_px), y_from_top(baseline_px + index * leading), line)

        # Le nom supérieur est retiré ; le bloc central est remonté pour équilibrer
        # l'espace libéré tout en gardant une seule occurrence du bénéficiaire.
        cover(394, 195, 1139, 241, background_white)
        cover(145, 250, 1390, 535, background_white)

        gold = colors.HexColor("#D4AF37")
        pdf.setStrokeColor(gold)
        pdf.setLineWidth(1.8)
        pdf.line(x(235), y_from_top(267), x(742), y_from_top(267))
        pdf.line(x(794), y_from_top(267), x(1301), y_from_top(267))
        pdf.saveState()
        pdf.translate(x(image_width / 2), y_from_top(267))
        pdf.rotate(45)
        pdf.setFillColor(gold)
        pdf.rect(-x(7), -x(7), x(14), x(14), fill=1, stroke=0)
        pdf.restoreState()

        intro = "La Direction d’ALTIORA PREST a le plaisir de reconnaître votre participation à la formation :"
        pdf.setFillColor(colors.HexColor("#0B1F4D"))
        intro_size = fitted_size(intro, font_bold, 18, 12, 1260)
        pdf.setFont(font_bold, intro_size)
        pdf.drawCentredString(x(image_width / 2), y_from_top(301), intro)

        # Intitulé court dérivé des contenus de formation vérifiés, jamais du titre d'offre.
        title = str(details.get("formation") or "Formation professionnelle").strip()
        pdf.setFillColor(colors.HexColor("#001736"))
        pdf.setStrokeColor(gold)
        pdf.setLineWidth(3)
        pdf.roundRect(x(205), y_from_top(381), x(1126), sy * 56, x(15), fill=1, stroke=1)
        pdf.setFillColor(colors.white)
        title_size = fitted_size(title, font_bold, 19, 9, 1080)
        title_lines = wrap(title, font_bold, title_size, 1080)
        if len(title_lines) > 2:
            title_size = fitted_size(" ".join(title_lines[:2]) + "…", font_bold, min(title_size, 12), 8, 1080)
            title_lines = wrap(title, font_bold, title_size, 1080)[:2]
            if len(" ".join(title_lines)) < len(title):
                title_lines[-1] = title_lines[-1].rstrip(".,;:") + "…"
        title_leading = title_size + 2
        title_first_baseline = 353 - (len(title_lines) - 1) * title_leading / 2
        draw_centered_lines(title_lines, image_width / 2, title_first_baseline, font_bold, title_size, title_leading)

        if result.get("metadata", {}).get("competencies_source") == "participation_only":
            taux = participant.get("taux_presence")
            taux_text = ""
            if taux not in (None, ""):
                try:
                    taux_text = f"Présence enregistrée : {float(str(taux).rstrip('%').strip()):g} %"
                except (TypeError, ValueError):
                    taux_text = f"Présence enregistrée : {str(taux).strip()}"
            commitment_lines = ["PRÉSENCE ET PARTICIPATION CONFIRMÉES"]
            if taux_text:
                commitment_lines.append(taux_text)
        else:
            commitment_lines = [
                "Votre implication et votre engagement tout au long de cette formation témoignent de votre volonté",
                "de développer vos compétences et de contribuer à l’excellence.",
            ]
        commitment_size = fitted_size(commitment_lines[0], font_bold, 16, 12, 1270)
        pdf.setFillColor(colors.HexColor("#0B1F4D"))
        draw_centered_lines(commitment_lines, image_width / 2, 453, font_bold, commitment_size, 25)

        # 3. Valeurs sous les libellés déjà imprimés sur le modèle.
        values = (
            (str(details.get("dates") or "—"), 168, 465),
            (str(details.get("lieu") or "—"), 645, 900),
            (numero or "—", 1138, 1400),
        )
        for value, left, right in values:
            cover(left, 604, right, 642, background_white)
            pdf.setFillColor(colors.HexColor("#0B1F4D"))
            size = fitted_size(value, font_regular, 12, 8, right - left - 12)
            pdf.setFont(font_regular, size)
            pdf.drawCentredString(x((left + right) / 2), y_from_top(624), value)

        # Recomposer la première ligne en une seule phrase centrée pour aligner
        # naturellement le nom à la formule de félicitations.
        cover(175, 660, 1388, 710, background_white)
        pdf.setFillColor(colors.HexColor("#0B1F4D"))
        congratulation = f"ALTIORA PREST adresse ses félicitations à {person_name}"
        congratulation_size = fitted_size(congratulation, font_italic, 18, 10, 1200)
        pdf.setFont(font_italic, congratulation_size)
        pdf.drawCentredString(x(image_width / 2), y_from_top(688), congratulation)

        # La signature figurant dans le PNG est un fac-similé. L'effacer pour
        # laisser un emplacement réellement disponible à la signature manuscrite.
        cover(1058, 850, 1314, 922, background_white)
        pdf.setStrokeColor(colors.HexColor("#0B1F4D"))
        pdf.setLineWidth(0.65)
        pdf.line(x(1080), y_from_top(914), x(1295), y_from_top(914))

        pdf.save()
        vlog(f"   ✅ PDF (modèle PNG Altiora) : {pdf_path.name}")
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
