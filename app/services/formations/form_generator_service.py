import os
import re
import json
import yaml
import copy
import logging
from pathlib import Path
from typing import Dict, Any

from openai import AsyncOpenAI

from app.services.hitl import create_review

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "m5" / "form_generation.yaml"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


class FormGeneratorService:
    """Agent 1 — Génère les 4 formulaires Google Forms d'une session."""

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("❌ GROQ_API_KEY manquant.")

        self.client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        self.model = GROQ_MODEL
        self.prompt_config = self._load_prompt()
        vlog(f"✅ FormGeneratorService initialisé (model={self.model})")

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

    def _build_user_prompt(self, session_info: Dict[str, Any]) -> str:
        lines = [
            "Génère UNIQUEMENT 3 sections : inscription, test_avant, satisfaction.",
            "",
            "⚠️  NE GÉNÈRE PAS la section test_apres (elle sera dérivée).",
            "",
            "⚠️  RÈGLES DE FORMATAGE JSON :",
            "   1. Guillemets DOUBLES (\"...\") uniquement.",
            "   2. N'échappe JAMAIS les apostrophes : écris \"l'IA\" pas \"l\\'IA\".",
            "   3. Le champ du texte s'appelle \"label\" (pas \"question\").",
            "   4. Options = chaînes simples : [\"A. ...\", \"B. ...\"]",
            "   5. IDs : ins_XX, av_XX, sat_XX.",
            "   6. correct_answer : UNIQUEMENT la lettre (A, B, C, D).",
            "",
            "- Titre : " + session_info.get("titre", "N/A"),
            "- Domaine : " + session_info.get("domaine", "N/A"),
            "- Niveau cible : " + session_info.get("niveau_cible", "N/A"),
            "- Date début : " + session_info.get("date_debut", "N/A"),
            "- Date fin : " + session_info.get("date_fin", "N/A"),
            "- Lieu : " + session_info.get("lieu", "N/A"),
            "- Formateur : " + session_info.get("formateur", "N/A"),
            "- Max participants : " + str(session_info.get("max_participants", "N/A")),
            "- Public cible : " + session_info.get("public_cible", "N/A"),
        ]
        supports = session_info.get("supports_resume")
        if supports:
            lines.append("")
            lines.append("=== SUPPORTS (résumé) ===")
            lines.append(str(supports)[:2000])
        lines.append("")
        lines.append(
            "Retourne UNIQUEMENT ce JSON (3 sections) :\n"
            "{\n"
            '  "inscription": {"title": "...", "questions": [...]},\n'
            '  "test_avant": {"title": "...", "duration_minutes": 20, "questions": [...]},\n'
            '  "satisfaction": {"title": "...", "questions": [...]},\n'
            '  "metadata": {"domaine": "...", "niveau_cible": "...", "nombre_questions_test": 15, "langue": "fr"}\n'
            "}"
        )
        return "\n".join(lines)

    # --------------------------------------------------------
    # GÉNÉRATION
    # --------------------------------------------------------
    async def generate(
        self,
        session_info: Dict[str, Any],
        temperature: float = 0.4,
        max_tokens: int = 10000,
    ) -> Dict[str, Any]:
        vlog("🚀 [FormGeneratorAgent] Génération des formulaires...")
        vlog(f"   → Titre : {session_info.get('titre', 'N/A')}")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(session_info)
        raw_content = ""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            raw_content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            vlog(f"✅ Réponse Groq ({len(raw_content)} chars, finish={finish_reason})")

            if finish_reason == "length":
                raise ValueError("❌ Réponse IA tronquée (finish_reason=length).")

            cleaned = self._repair_json(raw_content)
            data = json.loads(cleaned)
            data = self._normalize_llm_output(data)
            data["test_apres"] = self._derive_test_apres(data.get("test_avant", {}))
            self._validate_minimal(data)

            # ⏳ HITL — Créer un review
            review_id = create_review(
                agent_id="agent_1_forms",
                data=data,
                summary=(
                    f"4 formulaires — "
                    f"{len(data['test_avant']['questions'])} questions de test — "
                    f"à valider avant Google Forms"
                ),
                criticity="critical",
            )
            data["_review_id"] = review_id
            data["_review_status"] = "pending_review"

            n_av = len(data["test_avant"]["questions"])
            vlog(f"✅ Formulaires générés : {n_av} questions (review={review_id})")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON invalide : {e}")
            logger.error(f"   Début réponse : {raw_content[:500]}")
            raise ValueError(f"Réponse IA non-JSON : {e}")
        except Exception as e:
            logger.error(f"❌ Erreur FormGeneratorService : {e}")
            raise

    # --------------------------------------------------------
    # RÉGÉNÉRATION AVEC FEEDBACK (HITL)
    # --------------------------------------------------------
    async def regenerate(
        self,
        session_info: Dict[str, Any],
        previous_generation: Dict[str, Any],
        feedback: str,
        temperature: float = 0.5,
        max_tokens: int = 10000,
    ) -> Dict[str, Any]:
        vlog("🔁 [FormGeneratorAgent] Régénération avec feedback...")
        vlog(f"   💬 Feedback : {feedback[:200]}")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_regenerate_prompt(
            session_info, previous_generation, feedback
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            raw_content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            vlog(f"✅ Réponse Groq ({len(raw_content)} chars, finish={finish_reason})")

            if finish_reason == "length":
                raise ValueError("❌ Réponse IA tronquée.")

            cleaned = self._repair_json(raw_content)
            data = json.loads(cleaned)
            data = self._normalize_llm_output(data)
            data["test_apres"] = self._derive_test_apres(data.get("test_avant", {}))
            self._validate_minimal(data)

            # ⏳ HITL — Créer un review après régénération
            review_id = create_review(
                agent_id="agent_1_forms",
                data=data,
                summary=f"Régénéré après feedback : {feedback[:80]}",
                criticity="critical",
            )
            data["_review_id"] = review_id
            data["_review_status"] = "pending_review"

            n_av = len(data["test_avant"]["questions"])
            vlog(f"✅ Régénération OK : {n_av} questions (review={review_id})")
            return data

        except Exception as e:
            logger.error(f"❌ Erreur régénération : {e}")
            raise

    def _build_regenerate_prompt(
        self,
        session_info: Dict[str, Any],
        previous_generation: Dict[str, Any],
        feedback: str,
    ) -> str:
        prev_summary = {
            "inscription_questions": len(previous_generation.get("inscription", {}).get("questions", [])),
            "test_avant_questions": len(previous_generation.get("test_avant", {}).get("questions", [])),
            "satisfaction_questions": len(previous_generation.get("satisfaction", {}).get("questions", [])),
        }
        base_prompt = self._build_user_prompt(session_info)
        return "\n".join([
            "⚠️  RÉGÉNÉRATION AVEC FEEDBACK HUMAIN",
            "",
            "=== GÉNÉRATION PRÉCÉDENTE (résumé) ===",
            json.dumps(prev_summary, ensure_ascii=False, indent=2),
            "",
            "=== FEEDBACK HUMAIN ===",
            feedback,
            "",
            "=== INSTRUCTIONS ===",
            "1. Prends en compte le feedback.",
            "2. Garde la même structure JSON.",
            "3. Ne duplique pas les erreurs précédentes.",
            "",
            "=" * 50,
            "",
            base_prompt,
        ])

    # --------------------------------------------------------
    # REPAIR JSON
    # --------------------------------------------------------
    def _repair_json(self, raw: str) -> str:
        if not raw:
            return raw
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw)
        raw = raw.replace("\\'", "'")
        raw = raw.replace("\\/", "/")
        start = raw.find("{")
        if start == -1:
            start = raw.find("[")
        if start > 0:
            raw = raw[start:]
        last_brace = raw.rfind("}")
        last_bracket = raw.rfind("]")
        end = max(last_brace, last_bracket)
        if end > 0:
            raw = raw[:end + 1]
        vlog("   🔧 JSON réparé")
        return raw

    # --------------------------------------------------------
    # NORMALISATION
    # --------------------------------------------------------
    def _normalize_llm_output(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, list):
            logger.warning(f"⚠️  LLM a retourné une liste [{len(data)}] → fusion")
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
        for section in ("inscription", "test_avant", "test_apres", "satisfaction"):
            if section in data and isinstance(data[section], dict):
                data[section] = self._normalize_section(data[section])
        return data

    def _normalize_section(self, section: Dict[str, Any]) -> Dict[str, Any]:
        questions = section.get("questions", [])
        if not isinstance(questions, list):
            return section
        normalized = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            if "question" in q and "label" not in q:
                q["label"] = q.pop("question")
            opts = q.get("options")
            if isinstance(opts, list):
                new_opts = []
                for o in opts:
                    if isinstance(o, str):
                        new_opts.append(o)
                    elif isinstance(o, dict):
                        label = o.get("label") or o.get("value") or o.get("text") or ""
                        new_opts.append(str(label))
                q["options"] = new_opts
            q.setdefault("required", True)
            normalized.append(q)
        section["questions"] = normalized
        return section

    # --------------------------------------------------------
    # DÉRIVATION test_apres
    # --------------------------------------------------------
    def _derive_test_apres(self, test_avant: Dict[str, Any]) -> Dict[str, Any]:
        if not test_avant or "questions" not in test_avant:
            return {"title": "Test APRÈS", "questions": []}
        apres = copy.deepcopy(test_avant)
        apres["title"] = apres.get("title", "Test AVANT").replace("AVANT", "APRÈS")
        apres["description"] = "Évaluation sommative après formation."
        for q in apres.get("questions", []):
            old_id = q.get("id", "")
            if old_id.startswith("av_"):
                q["id"] = "ap_" + old_id[3:]
        vlog(f"   🔄 test_apres dérivé ({len(apres['questions'])} questions)")
        return apres

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------
    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        required = ["inscription", "test_avant", "test_apres", "satisfaction"]
        for section in required:
            if section not in data:
                raise ValueError(f"❌ Section manquante : '{section}'")
            if "questions" not in data[section]:
                raise ValueError(f"❌ 'questions' manquant dans '{section}'")
            if not isinstance(data[section]["questions"], list):
                raise ValueError(f"❌ 'questions' doit être une liste dans '{section}'")
        n_av = len(data["test_avant"]["questions"])
        n_ap = len(data["test_apres"]["questions"])
        if n_av != n_ap:
            logger.warning(f"⚠️  test_avant ({n_av}) ≠ test_apres ({n_ap})")
        else:
            vlog(f"✅ Cohérence AVANT/APRÈS : {n_av} questions")