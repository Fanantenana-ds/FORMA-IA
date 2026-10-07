from app.utils.json_repair import repair_json
import os
import re
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.services.llm import get_llm_provider, LLMError
from app.services.hitl import create_review

logger = logging.getLogger(__name__)
VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m4" / "rh_contrat_formateur.yaml"
AGENT_ID = "agent_m4_contrat"

def _next_reference() -> str:
    import random
    now = datetime.now()
    # timestamp + random suffix → évite les doublons après redémarrage
    suffix = int(now.timestamp()) % 10000 * 10 + random.randint(0, 9)
    return f"ALT-CONT-FORM-{now.year}-{suffix:05d}"


class ContratFormateurService:
    """
    Agent M4-4 — Génération de contrats de prestation formateur.

    Input  : infos formateur + infos session (dates, formation, tarif)
    Output : JSON contrat complet (texte_complet prêt à imprimer) + HITL review_id
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [ContratFormateurAgent] Service initialisé")

    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")
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
        formateur: Dict[str, Any],
        session: Dict[str, Any],
    ) -> str:
        return "\n".join([
            "Génère le contrat de prestation pour ce formateur :",
            "",
            "=== FORMATEUR ===",
            f"- Nom complet : {formateur.get('nom', 'N/A')}",
            f"- Adresse : {formateur.get('adresse', 'N/A')}",
            f"- Téléphone : {formateur.get('telephone', 'N/A')}",
            f"- Email : {formateur.get('email', 'N/A')}",
            f"- Tarif journalier : {formateur.get('tarif_journalier', 0)} MGA",
            "",
            "=== SESSION DE FORMATION ===",
            f"- Titre : {session.get('titre', 'N/A')}",
            f"- Dates : {', '.join(session.get('dates', []))}",
            f"- Nombre de jours : {session.get('nb_jours', 1)}",
            f"- Lieu : {session.get('lieu', 'Antananarivo')}",
            f"- Nombre de participants : {session.get('nb_participants', 0)}",
            f"- Description mission : {session.get('description', '')}",
            "",
            "Retourne UNIQUEMENT le JSON valide, sans texte autour.",
        ])

    async def generate(
        self,
        formateur: Dict[str, Any],
        session: Dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        nom_formateur = formateur.get("nom", "Formateur")
        titre_session = session.get("titre", "Formation")

        start = datetime.now()
        vlog("=" * 70)
        vlog(f"🚀 [ContratFormateurAgent] Génération contrat — {nom_formateur}")
        vlog(f"   📋 Session : {titre_session}")
        vlog("=" * 70)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(formateur, session)
        content = None
        source = "fallback_template"

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
            if response["finish_reason"] == "length":
                raise ValueError("Réponse LLM tronquée")
            data = json.loads(self._repair_json(raw))
            self._validate_minimal(data)
            content = data
            source = "llm"
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). Bascule fallback.")
        except Exception as e:
            logger.exception(f"   ❌ Erreur inattendue LLM : {e}")

        if content is None:
            content = self._generate_fallback(formateur, session)

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

        tarif = formateur.get("tarif_journalier", 0)
        nb_jours = session.get("nb_jours", 1)
        total = tarif * nb_jours

        review_id = create_review(
            agent_id=AGENT_ID,
            data=result,
            summary=(
                f"Contrat formateur — {nom_formateur} — {titre_session} "
                f"— {nb_jours}j × {tarif:,} MGA = {total:,} MGA"
            ),
            criticity="critical",
        )
        result["_review_id"] = review_id
        result["_review_status"] = "pending_review"

        vlog(f"✅ [ContratFormateurAgent] Terminé en {elapsed}s (source={source})")
        return result

    def _repair_json(self, raw: str) -> str:
        return repair_json(raw)
    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        for k in ("parties", "remuneration", "texte_complet"):
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")

    def _generate_fallback(
        self, formateur: Dict[str, Any], session: Dict[str, Any]
    ) -> Dict[str, Any]:
        nom = formateur.get("nom", "M./Mme Formateur")
        titre = session.get("titre", "Formation professionnelle")
        tarif = formateur.get("tarif_journalier", 0)
        nb_jours = session.get("nb_jours", 1)
        total = tarif * nb_jours
        ref = _next_reference()
        today = datetime.now().strftime("%Y-%m-%d")

        texte = (
            f"CONTRAT DE PRESTATION DE SERVICE N° {ref}\n"
            f"Date : {today}\n\n"
            f"ENTRE :\n"
            f"ALTIORA PREST, représentée par M. RANAIVOSOA Sandamampianina, Co-gérant,\n"
            f"ci-après dénommé « LE COMMANDITAIRE »\n\n"
            f"ET :\n"
            f"{nom}, ci-après dénommé « LE PRESTATAIRE »\n\n"
            f"IL EST CONVENU CE QUI SUIT :\n\n"
            f"Article 1 — Objet\n"
            f"Le Commanditaire confie au Prestataire une mission de formation intitulée "
            f"« {titre} ».\n\n"
            f"Article 2 — Durée et calendrier\n"
            f"La mission se déroulera sur {nb_jours} jour(s) selon les dates convenues.\n\n"
            f"Article 3 — Rémunération\n"
            f"La rémunération est fixée à {tarif:,} MGA par jour, soit un total de "
            f"{total:,} MGA pour l'ensemble de la mission.\n\n"
            f"Article 4 — Obligations du Prestataire\n"
            f"- Assurer la prestation aux dates convenues\n"
            f"- Préparer les supports pédagogiques\n"
            f"- Respecter la confidentialité des données participants\n\n"
            f"Article 5 — Obligations du Commanditaire\n"
            f"- Mettre à disposition la salle et le matériel nécessaires\n"
            f"- Procéder au paiement dans les 30 jours suivant la prestation\n\n"
            f"Article 6 — Propriété intellectuelle\n"
            f"Les supports créés pour cette mission restent la propriété du Prestataire, "
            f"avec licence d'usage accordée au Commanditaire.\n\n"
            f"Fait à Antananarivo, le {today}\n\n"
            f"Pour ALTIORA PREST : _______________\n"
            f"Pour le Prestataire : _______________"
        )

        return {
            "reference_contrat": ref,
            "date_contrat": today,
            "parties": {
                "commanditaire": {
                    "nom": "ALTIORA PREST",
                    "adresse": "Antananarivo, Madagascar",
                    "representant": "M. RANAIVOSOA Sandamampianina — Co-gérant",
                },
                "prestataire": {
                    "nom": nom,
                    "adresse": formateur.get("adresse"),
                    "telephone": formateur.get("telephone"),
                    "email": formateur.get("email"),
                },
            },
            "objet": f"Mission de formation — {titre}",
            "prestation": {
                "formation": titre,
                "dates": session.get("dates", []),
                "lieu": session.get("lieu", "Antananarivo"),
                "duree_jours": nb_jours,
                "nb_participants": session.get("nb_participants", 0),
                "description_mission": session.get("description", ""),
            },
            "remuneration": {
                "tarif_journalier": tarif,
                "nb_jours": nb_jours,
                "total_brut": total,
                "devise": "MGA",
                "conditions_paiement": "Virement bancaire dans les 30 jours suivant la prestation",
            },
            "obligations_prestataire": [
                "Assurer la prestation aux dates convenues",
                "Préparer des supports pédagogiques de qualité",
                "Respecter la confidentialité des données participants",
            ],
            "obligations_commanditaire": [
                "Mettre à disposition la salle et le matériel nécessaires",
                "Procéder au paiement dans les délais convenus",
            ],
            "propriete_intellectuelle": (
                "Les supports créés pour cette mission restent la propriété du Prestataire, "
                "avec licence d'usage non-exclusive accordée au Commanditaire."
            ),
            "resiliation": (
                "Toute résiliation doit être notifiée par écrit 7 jours à l'avance. "
                "En cas de résiliation par le Commanditaire, les jours déjà préparés sont dus."
            ),
            "texte_complet": texte,
        }
