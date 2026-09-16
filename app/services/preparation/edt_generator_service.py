import os
import re
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.services.llm import get_llm_provider, LLMError

logger = logging.getLogger(__name__)

VERBOSE = os.getenv("VERBOSE_LOGS", "true").lower() == "true"


def vlog(msg: str, level: str = "info") -> None:
    if VERBOSE:
        getattr(logger, level)(msg)


# =============================================================================
# CONFIG
# =============================================================================
PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts" / "m_prep" / "edt_generation.yaml"
)


# =============================================================================
# SERVICE
# =============================================================================

class EDTGeneratorService:
    """
    Service de génération de l'emploi du temps.

    Input  : modules + dates + formateur + salle
    Output : EDT structuré (jours + sessions + pauses)
    """

    def __init__(self):
        self.prompt_config = self._load_prompt()
        vlog("✅ [EDTGenerator] Service initialisé")

    # =========================================================================
    # PROMPT
    # =========================================================================

    def _load_prompt(self) -> Dict[str, Any]:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(f"❌ Prompt introuvable : {PROMPT_PATH}")

        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict) or not config:
            raise ValueError(f"❌ YAML vide ou invalide : {PROMPT_PATH}")

        vlog(f"✅ [EDTGenerator] Prompt chargé : {PROMPT_PATH.name}")
        return config

    def _build_system_prompt(self) -> str:
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
        titre_formation: str,
        modules: List[Dict[str, Any]],
        dates: List[str],
        formateur: Optional[Dict[str, Any]],
        salle: Optional[Dict[str, Any]],
    ) -> str:
        lines = [
            f"Génère l'emploi du temps de la formation : {titre_formation}",
            "",
            "=== FORMATION ===",
            f"- Titre : {titre_formation}",
            f"- Nombre de jours : {len(dates)}",
            f"- Nombre de modules : {len(modules)}",
            "",
            "=== MODULES ===",
        ]
        for i, m in enumerate(modules, start=1):
            lines.append(f"  {i}. {m.get('titre', 'N/A')} — {m.get('duree', 'N/A')}")

        lines.append("")
        lines.append("=== DATES ===")
        for d in dates:
            lines.append(f"  - {d}")

        if formateur:
            lines.append("")
            lines.append("=== FORMATEUR ===")
            lines.append(f"- Nom : {formateur.get('nom', 'N/A')}")
            lines.append(f"- Spécialité : {formateur.get('specialite', 'N/A')}")

        if salle:
            lines.append("")
            lines.append("=== SALLE ===")
            lines.append(f"- Nom : {salle.get('nom', 'N/A')}")
            lines.append(f"- Adresse : {salle.get('adresse', 'N/A')}")

        lines.append("")
        lines.append("Retourne UNIQUEMENT le JSON valide, sans texte autour.")
        return "\n".join(lines)

    # =========================================================================
    # GÉNÉRATION
    # =========================================================================

    async def generate(
        self,
        titre_formation: str,
        modules: List[Dict[str, Any]],
        dates: List[str],
        formateur: Optional[Dict[str, Any]] = None,
        salle: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        max_tokens: int = 30000,
    ) -> Dict[str, Any]:
        """
        Génère l'emploi du temps d'une formation.

        Returns:
            Dict avec l'EDT complet (jours, sessions, pauses, résumé).
        """
        start = datetime.now()
        vlog("=" * 70)
        vlog("🚀 [EDTGenerator] Génération de l'emploi du temps...")
        vlog(f"   📋 Formation : {titre_formation}")
        vlog(f"   📅 Jours     : {len(dates)}")
        vlog(f"   📚 Modules   : {len(modules)}")
        vlog("=" * 70)

        content = None
        source = "fallback_template"

        # ── ESSAI LLM ──
                # ── ESSAI LLM (désactivé — fallback Python suffit) ──
        use_llm = os.getenv("EDT_USE_LLM", "false").lower() == "true"

        if use_llm:
            try:
                llm = get_llm_provider()
                system_prompt = self._build_system_prompt()
                user_prompt = self._build_user_prompt(
                    titre_formation, modules, dates, formateur, salle
                )

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
                    raise ValueError("Réponse LLM tronquée")

                cleaned = self._repair_json(raw)
                data = json.loads(cleaned)
                data = self._normalize_output(data)

                # Validation minimale
                self._validate_minimal(data)
                content = data
                source = "llm"
                vlog("   ✅ EDT généré par LLM")

            except (LLMError, json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    f"   ⚠️  LLM indisponible ({type(e).__name__}: {e}). "
                    f"Bascule sur le template Python."
                )
            except Exception as e:
                logger.exception(f"   ❌ Erreur inattendue LLM : {e}")
        else:
            vlog("   ℹ️  LLM désactivé (EDT_USE_LLM=false) → fallback Python direct")
            
        # ── FALLBACK ──
        if content is None:
            content = self._generate_with_template(
                titre_formation, modules, dates, formateur, salle
            )
            vlog("   ✅ EDT généré par template Python (fallback)")

        # ── Métadonnées ──
        elapsed = round((datetime.now() - start).total_seconds(), 2)
        content["success"] = True
        content["metadata"] = {
            "source": source,
            "generated_at": datetime.now().isoformat(),
            "duration_seconds": elapsed,
            "agent_id": "agent_preparation",
        }

        vlog("=" * 70)
        vlog(f"✅ [EDTGenerator] EDT terminé en {elapsed}s (source={source})")
        vlog(f"   📊 Jours : {len(content.get('jours', []))}")
        vlog(f"   📊 Sessions : {sum(len(j.get('sessions', [])) for j in content.get('jours', []))}")
        vlog("=" * 70)

        return content

    # =========================================================================
    # REPAIR + NORMALIZE
    # =========================================================================

    def _repair_json(self, raw: str) -> str:
        if not raw:
            return raw
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```\s*$", "", raw)
        raw = raw.replace("\\'", "'").replace("\\/", "/")
        start = raw.find("{")
        if start > 0:
            raw = raw[start:]
        end = raw.rfind("}")
        if end > 0:
            raw = raw[:end + 1]
        return raw

    def _normalize_output(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, list):
            items = [x for x in data if isinstance(x, dict)]
            if not items:
                raise ValueError(f"Liste sans objet : {str(data)[:300]}")
            data = items[0] if len(items) == 1 else {
                k: v for item in items for k, v in item.items()
            }
        if not isinstance(data, dict):
            raise ValueError(f"Attendu dict, reçu {type(data).__name__}")
        return data

    def _validate_minimal(self, data: Dict[str, Any]) -> None:
        required = ["titre_formation", "duree_totale_jours", "jours"]
        for k in required:
            if k not in data:
                raise ValueError(f"Clé manquante : '{k}'")
        if not isinstance(data["jours"], list) or not data["jours"]:
            raise ValueError("'jours' doit être une liste non vide")

    # =========================================================================
    # FALLBACK TEMPLATE
    # =========================================================================

    def _generate_with_template(
        self,
        titre_formation: str,
        modules: List[Dict[str, Any]],
        dates: List[str],
        formateur: Optional[Dict[str, Any]],
        salle: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Template Python (fallback) — EDT standard."""

        jours = []
        module_idx = 0
        num_modules = len(modules)

        for jour_num, date_str in enumerate(dates, start=1):
            # Distribuer les modules sur les jours
            modules_par_jour = max(1, num_modules // len(dates))
            modules_jour = modules[
                module_idx:module_idx + modules_par_jour
            ] or [{"titre": f"Module {i+1}", "duree": "3h"} for i in range(2)]
            module_idx += modules_par_jour

            # Construire les sessions
            sessions = []

            # Session matin 1
            sessions.append({
                "id": f"s_{jour_num:02d}_01",
                "heure_debut": "08:30",
                "heure_fin": "10:00",
                "module": modules_jour[0].get("titre", "Module 1"),
                "type": "cours",
                "duree_minutes": 90,
                "formateur": (formateur or {}).get("nom", "N/A"),
                "salle": (salle or {}).get("nom", "N/A"),
                "objectifs": ["Comprendre les concepts", "Identifier les cas d'usage"],
            })

            # Session matin 2
            sessions.append({
                "id": f"s_{jour_num:02d}_02",
                "heure_debut": "10:15",
                "heure_fin": "12:00",
                "module": (
                    modules_jour[1].get("titre", "Module 2")
                    if len(modules_jour) > 1 else "Atelier pratique"
                ),
                "type": "atelier",
                "duree_minutes": 105,
                "formateur": (formateur or {}).get("nom", "N/A"),
                "salle": (salle or {}).get("nom", "N/A"),
                "objectifs": ["Pratiquer", "Appliquer"],
            })

            # Session après-midi 1
            sessions.append({
                "id": f"s_{jour_num:02d}_03",
                "heure_debut": "13:30",
                "heure_fin": "15:00",
                "module": "Approfondissement",
                "type": "cours",
                "duree_minutes": 90,
                "formateur": (formateur or {}).get("nom", "N/A"),
                "salle": (salle or {}).get("nom", "N/A"),
                "objectifs": ["Approfondir", "Analyser"],
            })

            # Session après-midi 2
            sessions.append({
                "id": f"s_{jour_num:02d}_04",
                "heure_debut": "15:15",
                "heure_fin": "17:00",
                "module": "Projet pratique",
                "type": "projet",
                "duree_minutes": 105,
                "formateur": (formateur or {}).get("nom", "N/A"),
                "salle": (salle or {}).get("nom", "N/A"),
                "objectifs": ["Appliquer au projet", "Consolider"],
            })

            pauses = [
                {"heure_debut": "10:00", "heure_fin": "10:15", "type": "pause"},
                {"heure_debut": "12:00", "heure_fin": "13:30", "type": "dejeuner"},
                {"heure_debut": "15:00", "heure_fin": "15:15", "type": "pause"},
            ]

            jours.append({
                "numero": jour_num,
                "date": date_str,
                "jour_semaine": None,
                "sessions": sessions,
                "pauses": pauses,
            })

        total_sessions = sum(len(j["sessions"]) for j in jours)
        total_minutes = sum(
            s["duree_minutes"] for j in jours for s in j["sessions"]
        )

        return {
            "titre_formation": titre_formation,
            "duree_totale_jours": len(dates),
            "nombre_modules": num_modules,
            "formateur": formateur or {"nom": "N/A", "specialite": None},
            "salle": salle or {"nom": "N/A", "adresse": None},
            "jours": jours,
            "resume_hebdomadaire": {
                "total_heures": round(total_minutes / 60, 1),
                "total_sessions": total_sessions,
                "modules_couverts": num_modules,
                "charge_journaliere_moyenne": round(
                    total_minutes / 60 / len(dates), 1
                ) if dates else 0,
            },
            "notes": [
                "Horaires adaptables selon contraintes logistiques",
                "Prévoir 15 min avant chaque session pour l'installation",
            ],
        }