import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from app.services.hitl import create_review
from app.services.llm import LLMError, get_llm_provider
from app.utils.json_repair import repair_json

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CONFIG
# =============================================================================
PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "m3" / "offre_technique.yaml"
)

AGENT_ID = "agent_m3_technique"


# =============================================================================
# SERVICE
# =============================================================================

class OffreTechniqueGeneratorService:
    """
    Agent M3-1 — Génère la trame technique d'une offre de formation.

    Input  : TDR + session_info
    Output : JSON OffreTechniqueResponse + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [OffreTechniqueAgent] Service initialisé")

    # =========================================================================
    # PROMPT
    # =========================================================================

    def _load_prompt(self) -> dict[str, Any]:
        """Charge le prompt RTFCE depuis le YAML."""
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")

        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")

        vlog(f"✅ [OffreTechniqueAgent] Prompt chargé : {PROMPT_PATH.name}")
        return config

    def _build_system_prompt(self) -> str:
        """Construit le system prompt à partir du YAML RTFCE."""
        cfg = self.prompt_config
        return "\n".join([
            "=== RÔLE ===",
            cfg.get("role", "").strip(),
            "",
            "=== TÂCHE ===",
            cfg.get("tache", "").strip(),
            "",
            "=== FORMAT ===",
            cfg.get("format", "").strip(),
            "",
            "=== CONTEXTE ===",
            cfg.get("contexte", "").strip(),
            "",
            "=== RÈGLES STRICTES ===",
            cfg.get("regles", "") if isinstance(cfg.get("regles"), str)
            else "\n".join(f"- {r}" for r in cfg.get("regles", [])),
        ])

    def _build_user_prompt(
        self,
        tdr_data: dict[str, Any],
        session_info: dict[str, Any],
        feedback: str | None = None,
    ) -> str:
        """Construit le user prompt avec les données du TDR + session."""
        lines = [
            "Rédige une offre technique professionnelle pour répondre au TDR ci-dessous.",
            "Les données JSON fournies sont les seules sources factuelles autorisées.",
            "Si une information manque, indique 'À confirmer' ou laisse la liste vide.",
            "N'utilise jamais le titre de l'appel comme nom du client.",
            "",
            "=== TDR SOURCE ===",
            json.dumps(tdr_data, ensure_ascii=False, default=str),
            "",
            "=== DONNÉES DE SESSION SOURCE ===",
            json.dumps(session_info, ensure_ascii=False, default=str),
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ]
        references_portfolio = session_info.get("references_portfolio") or []
        if isinstance(references_portfolio, list) and references_portfolio:
            lignes_refs = []
            for reference in references_portfolio:
                if not isinstance(reference, dict):
                    continue
                intitule = self._source_text(reference.get("intitule"))
                if not intitule:
                    continue
                client = self._source_text(reference.get("client")) or "Client non précisé"
                annee = self._source_text(reference.get("annee")) or "année non précisée"
                lignes_refs.append(f"  - {intitule} ({client} — {annee})")
            if lignes_refs:
                lines[-1:-1] = [
                    "=== RÉFÉRENCES PORTFOLIO ALTIORA (à intégrer dans annexes.references) ===",
                    *lignes_refs,
                    "N'utilise que les références ci-dessus. Ne complète aucun client, résultat ou année qui n'est pas fourni.",
                    "",
                ]
        if feedback and feedback.strip():
            # Régénération après rejet HITL : le réviseur humain a demandé
            # des corrections (bloc placé avant la consigne de format).
            lines[-1:-1] = [
                "=== CORRECTIONS DEMANDÉES PAR LE RÉVISEUR HUMAIN ===",
                feedback.strip(),
                "Tiens compte de ces corrections dans cette nouvelle version.",
                "",
            ]
        return "\n".join(lines)

    @staticmethod
    def _source_text(*values: Any) -> str | None:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _hours_in_text(value: str) -> float | None:
        matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:h(?:eures?)?)\b", value.lower())
        return sum(float(match.replace(",", ".")) for match in matches) if matches else None

    def _apply_source_constraints(
        self,
        content: dict[str, Any],
        tdr_data: dict[str, Any],
        session_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace facts that must come from the TDR/session, never the LLM."""
        title = self._source_text(tdr_data.get("titre"), tdr_data.get("titre_formation"))
        client = self._source_text(
            session_info.get("client"), tdr_data.get("client"),
            tdr_data.get("client_organisme"), tdr_data.get("organisme"),
        )
        opportunity_title = self._source_text(session_info.get("titre"))
        client_key = re.sub(r"\W+", " ", client or "").strip().casefold()
        source_titles = {title, opportunity_title} - {None}
        if client and any(
            client_key == re.sub(r"\W+", " ", source_title).strip().casefold()
            for source_title in source_titles
        ):
            client = None

        if title:
            content["titre_offre"] = f"Offre technique — {title}"
        content["client"] = client or "À confirmer avec le client"
        presentation = content.setdefault("presentation_structure", {})
        if isinstance(presentation, dict):
            presentation["nom"] = "ALTIORA PREST"
            presentation["description"] = (
                "ALTIORA PREST est un cabinet de conseil et de formation basé à "
                "Antananarivo, Madagascar. La présente proposition répond au "
                "besoin décrit dans le TDR transmis."
            )
            presentation["domaines_expertise"] = ["Conseil", "Formation professionnelle"]

        need = content.setdefault("comprehension_besoin", {})
        if isinstance(need, dict):
            need["public_cible"] = self._source_text(
                tdr_data.get("public_cible"), tdr_data.get("public_beneficiaire")
            ) or "À confirmer avec le client"
            objectives = tdr_data.get("objectifs") or tdr_data.get("objectifs_specifiques")
            if isinstance(objectives, str):
                objectives = [objectives]
            if isinstance(objectives, list) and objectives:
                need["objectifs_client"] = objectives
            else:
                need["objectifs_client"] = ["Objectifs détaillés à confirmer à partir du TDR validé."]
            need["enjeux"] = tdr_data.get("enjeux", []) if isinstance(tdr_data.get("enjeux"), list) else []
            need["contraintes"] = (
                tdr_data.get("contraintes", [])
                if isinstance(tdr_data.get("contraintes"), list) else []
            )

        program = content.setdefault("programme", {})
        if isinstance(program, dict):
            duration = self._source_text(
                tdr_data.get("duree_totale"), tdr_data.get("duree"),
                f"{tdr_data['duree_jours']} jours" if tdr_data.get("duree_jours") else None,
            )
            if duration:
                program["duree_totale"] = duration
            total_hours = self._hours_in_text(duration or "")
            modules = program.get("modules")
            if total_hours and isinstance(modules, list):
                module_hours = [
                    self._hours_in_text(str(module.get("duree", "")))
                    for module in modules if isinstance(module, dict)
                ]
                if module_hours and all(module_hours) and sum(module_hours) != total_hours:
                    for module in modules:
                        if isinstance(module, dict):
                            module["duree"] = "À répartir selon le volume horaire total du TDR"
                    program["alerte_coherence_duree"] = (
                        "La répartition horaire générée ne correspondait pas au total du TDR ; "
                        "le détail doit être ajusté avant validation."
                    )

        # Do not present guessed dates, legal guarantees, or software stacks as facts.
        source_architecture = tdr_data.get("architecture_technique") or tdr_data.get("environnement_technique")
        content["architecture_technique"] = source_architecture if isinstance(source_architecture, dict) else None
        planning = content.setdefault("planning", {})
        if isinstance(planning, dict):
            planning["dates_proposees"] = tdr_data.get("dates_proposees", [])
            planning["jalons"] = tdr_data.get("jalons", [])
            planning["livrables"] = tdr_data.get("livrables", [])
        guarantees = content.setdefault("garanties", {})
        if isinstance(guarantees, dict):
            guarantees["qualite"] = self._source_text(tdr_data.get("engagement_qualite")) or (
                "Les critères de qualité et d’évaluation seront convenus avant contractualisation."
            )
            guarantees["suivi"] = self._source_text(tdr_data.get("suivi_post_formation"))
            guarantees["confidentialite"] = self._source_text(tdr_data.get("confidentialite")) or (
                "Les modalités de confidentialité seront précisées dans les documents contractuels."
            )

        resources = content.setdefault("ressources", {})
        trainer = resources.setdefault("formateur", {}) if isinstance(resources, dict) else {}
        if isinstance(trainer, dict):
            confirmed_name = self._source_text(session_info.get("formateur_confirme"))
            internal_assignment_confirmed = (
                session_info.get("formateur_interne_confirme") is True and bool(confirmed_name)
            )
            profile = self._source_text(
                tdr_data.get("formateur_profil"),
                tdr_data.get("profil_formateur"),
            )
            trainer["nom"] = (
                confirmed_name if internal_assignment_confirmed
                else "Formateur à mobiliser après attribution"
            )
            trainer["profil"] = profile or (
                "Profil et disponibilité à confirmer selon les critères du TDR."
            )
            trainer_expertise = tdr_data.get("competences_formateur_requises")
            trainer["expertise"] = (
                [item for item in trainer_expertise if isinstance(item, str) and item.strip()]
                if isinstance(trainer_expertise, list) else []
            )
            trainer["mode_mobilisation"] = (
                "Interne — affectation confirmée"
                if internal_assignment_confirmed
                else "À arbitrer : vérifier d'abord la disponibilité et l'adéquation du formateur interne ALTIORA ; sinon recruter après attribution."
            )
            if not internal_assignment_confirmed:
                annexes = content.setdefault("annexes", {})
                if isinstance(annexes, dict):
                    annexes["cv_formateur"] = "CV à joindre après désignation du formateur."

        # Les références réelles sont injectées explicitement depuis le portfolio.
        portfolio_refs = session_info.get("references_portfolio") or []
        if isinstance(portfolio_refs, list):
            portfolio_refs = [
                reference for reference in portfolio_refs
                if isinstance(reference, dict) and self._source_text(reference.get("intitule"))
            ]
            annexes = content.setdefault("annexes", {})
            if isinstance(annexes, dict):
                annexes["references"] = portfolio_refs
        return content

    # =========================================================================
    # GÉNÉRATION
    # =========================================================================

    async def generate(
        self,
        tdr_data: dict[str, Any],
        session_info: dict[str, Any],
        temperature: float = 0.4,
        max_tokens: int = 8000,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        """
        Génère la trame technique d'une offre.

        Args:
            tdr_data: Données du TDR (issu du M2).
            session_info: Informations de session.
            feedback: Corrections du réviseur humain (régénération après
                rejet HITL). Pris en compte uniquement par le LLM.

        Returns:
            Dict avec la trame technique + HITL review_id.
        """
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [OffreTechniqueAgent] Génération de l'offre technique...")
        vlog(f"   📋 TDR : {tdr_data.get('titre', 'N/A')}")
        vlog(f"   🏢 Client : {session_info.get('client', 'N/A')}")
        vlog("=" * 70)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(tdr_data, session_info, feedback)

        content = None
        source = "fallback_template"

        # ── ÉTAPE 1 : ESSAI LLM ──
        try:
            llm = get_llm_provider()
            response = await llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )

            raw = response["content"]
            finish = response["finish_reason"]

            vlog(f"✅ Réponse LLM ({len(raw)} chars, finish={finish})")

            if finish == "length":
                raise ValueError("Réponse LLM tronquée (finish_reason=length)")

            # Réparer + parser le JSON
            cleaned = self._repair_json(raw)
            data = json.loads(cleaned)
            data = self._normalize_output(data)

            # Valider + compléter
            self._validate_minimal(data)
            content = data
            source = "llm"
            vlog("   ✅ Contenu généré par LLM")

        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                f"Bascule sur le template Python."
            )
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        # ── ÉTAPE 2 : FALLBACK ──
        if content is None:
            content = self._generate_with_template(tdr_data, session_info)
            vlog("   ✅ Contenu généré par template Python (fallback)")

        content = self._apply_source_constraints(content, tdr_data, session_info)

        # ── ÉTAPE 3 : MÉTADONNÉES + HITL ──
        elapsed = round((datetime.now() - start).total_seconds(), 2)

        result = {
            "success": True,
            **content,
            "metadata": {
                "source": source,
                "generated_at": datetime.now().isoformat(),
                "duration_seconds": elapsed,
                "agent_id": AGENT_ID,
            },
        }
        opportunite_id = (
            session_info.get("opportunite_id")
            or tdr_data.get("opportunite_id")
            or ((tdr_data.get("_inputs") or {}).get("brief") or {}).get("opportunite_id")
        )
        if opportunite_id:
            result["opportunite_id"] = str(opportunite_id)

        # Injection des références portfolio RAG (C3 → M3)
        references_portfolio = session_info.get("references_portfolio") or []
        if references_portfolio:
            references_portfolio = [
                reference for reference in references_portfolio
                if isinstance(reference, dict) and self._source_text(reference.get("intitule"))
            ]
        if references_portfolio:
            annexes = result.setdefault("annexes", {})
            existing = annexes.get("references") or []
            # Déduplique par intitulé
            intitules_existants = {r.get("intitule", "") for r in existing if isinstance(r, dict)}
            nouvelles = [r for r in references_portfolio if r.get("intitule", "") not in intitules_existants]
            annexes["references"] = existing + nouvelles
            result["metadata"]["references_portfolio_injectees"] = len(nouvelles)
            vlog(f"   📎 {len(nouvelles)} référence(s) portfolio RAG injectée(s) dans l'offre.")

        if feedback and feedback.strip():
            # Le gabarit Python de secours ne sait pas exploiter le feedback
            result["metadata"]["feedback"] = feedback.strip()
            result["metadata"]["feedback_applied"] = source == "llm"

        # Créer le review HITL
        review_id = create_review(
            agent_id=AGENT_ID,
            data=result,
            summary=(
                f"Offre technique — {result.get('titre_offre', 'N/A')[:80]} "
                f"— à valider avant envoi client"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog("=" * 70)
        vlog(
            f"✅ [OffreTechniqueAgent] Terminé en {elapsed}s "
            f"(source={source}, review={review_id})"
        )
        vlog("=" * 70)

        return result

    # =========================================================================
    # REPAIR JSON
    # =========================================================================

    def _repair_json(self, raw: str) -> str:
        return repair_json(raw)
    def _normalize_output(self, data: Any) -> dict[str, Any]:
        """Normalise la structure LLM (liste → dict)."""
        if isinstance(data, list):
            dict_items = [item for item in data if isinstance(item, dict)]
            if not dict_items:
                raise ValueError(f"Liste sans objet : {str(data)[:300]}")
            if len(dict_items) == 1:
                data = dict_items[0]
            else:
                merged = {}
                for item in dict_items:
                    merged.update(item)
                data = merged

        if not isinstance(data, dict):
            raise ValueError(f"Attendu dict, reçu {type(data).__name__}")

        return data

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def _validate_minimal(self, data: dict[str, Any]) -> None:
        """Vérifie la présence des clés minimales."""
        required = [
            "titre_offre", "reference", "date_emission",
            "presentation_structure", "comprehension_besoin",
            "approche_methodologique", "programme",
            "ressources", "planning", "garanties",
            "points_forts", "conclusion",
        ]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    # =========================================================================
    # FALLBACK TEMPLATE
    # =========================================================================

    def _generate_with_template(
        self,
        tdr_data: dict[str, Any],
        session_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Template Python (fallback) — trame technique standard."""
        year = datetime.now().year
        titre = tdr_data.get("titre", "Formation professionnelle")
        duree_jours = tdr_data.get("duree_jours")
        raw_objectives = tdr_data.get("objectifs") or tdr_data.get("objectifs_specifiques")
        objectives = ([item for item in raw_objectives if isinstance(item, str) and item.strip()]
                      if isinstance(raw_objectives, list) else [raw_objectives.strip()]
                      if isinstance(raw_objectives, str) and raw_objectives.strip() else [])
        objectif = objectives[0] if objectives else None
        public = self._source_text(tdr_data.get("public_cible"), tdr_data.get("public_beneficiaire"))
        duree = self._source_text(tdr_data.get("duree_totale"), tdr_data.get("duree"))

        return {
            "titre_offre": f"Offre technique — {titre}",
            "reference": f"ALT-OFF-TECH-{year}-0001",
            "date_emission": datetime.now().strftime("%Y-%m-%d"),
            "presentation_structure": {
                "nom": "ALTIORA Prest",
                "description": (
                    "ALTIORA PREST est un cabinet de conseil et de formation "
                    "basé à Antananarivo, Madagascar. La présente proposition "
                    "répond au besoin décrit dans le TDR transmis."
                ),
                "domaines_expertise": ["Conseil", "Formation professionnelle"],
            },
            "comprehension_besoin": {
                "objectifs_client": objectives or [
                    "Objectifs détaillés à confirmer à partir du TDR validé."
                ],
                "enjeux": [],
                "public_cible": public or "À confirmer avec le client",
                "contraintes": [],
            },
            "approche_methodologique": {
                "pedagogie": "Pédagogie active par projets",
                "modalites": "Présentiel avec supports numériques",
                "outils_supports": [
                    "Slides interactifs",
                    "Exercices pratiques",
                    "Cas d'usage",
                ],
                "innovations": [
                    "Apprentissage par projet",
                    "Évaluation continue",
                ],
            },
            "architecture_technique": None,
            "programme": {
                "duree_totale": duree or (f"{duree_jours} jours" if duree_jours else "À confirmer avec le client"),
                "modules": [{
                    "numero": 1,
                    "titre": "Programme détaillé à finaliser à partir du TDR validé",
                    "duree": duree or (f"{duree_jours} jours" if duree_jours else "À confirmer"),
                    "objectifs": objectives,
                    "contenu": [],
                    "methode": "Méthodes et séquençage à valider avec le client.",
                }],
            },
            "ressources": {
                "formateur": {
                    "nom": "Formateur à mobiliser après attribution",
                    "profil": self._source_text(tdr_data.get("formateur_profil")) or "Profil à confirmer selon le TDR validé.",
                    "expertise": [],
                    "mode_mobilisation": "À arbitrer : vérifier d'abord la disponibilité et l'adéquation du formateur interne ALTIORA ; sinon recruter après attribution.",
                },
                "support_technique": None,
                "materiel": [],
            },
            "planning": {
                "dates_proposees": [],
                "jalons": [],
                "livrables": [],
            },
            "garanties": {
                "qualite": "Modalités qualité à valider avec le client.",
                "suivi": None,
                "confidentialite": "Les modalités de confidentialité seront précisées au contrat.",
            },
            "annexes": {
                "cv_formateur": "CV à joindre après désignation du formateur.",
                "references": session_info.get("references_portfolio") or [],
            },
            "points_forts": [],
            "conclusion": (
                "Cette proposition technique sera finalisée après confirmation des éléments signalés comme à préciser et validation humaine."
            ),
        }
