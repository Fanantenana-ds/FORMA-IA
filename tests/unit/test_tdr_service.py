"""
Tests — app/services/tdr/tdr_service.py (TDRService)

Couvre :
- _build_prompt : remplacement correct des placeholders
- _extract_json : JSON direct, JSON dans du texte, JSON invalide
- generate : brief vide, réponse LLM vide, réponse LLM valide
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


FAKE_PROMPT = (
    "Client : {client}\n"
    "Objectifs : {objectifs}\n"
    "Public : {public}\n"
    "Durée : {duree}\n"
    "Format : {format}\n"
    "Budget : {budget}\n"
    "Lieu : {lieu}\n"
)

FAKE_TDR_JSON = {
    "titre": "Formation Python",
    "sections": ["Contexte", "Objectifs"],
}


@pytest.fixture
def service(tmp_path, monkeypatch):
    """Crée un TDRService avec un prompt YAML minimal — sans appel LLM réel."""
    yaml_dir = tmp_path / "prompts" / "m2"
    yaml_dir.mkdir(parents=True)
    yaml_file = yaml_dir / "tdr.yaml"
    yaml_file.write_text(
        "role: |\n  Rôle fictif\ntask: |\n  Client : {client}\n  Objectifs : {objectifs}\n  Public : {public}\n  Durée : {duree}\n  Format : {format}\n  Budget : {budget}\n  Lieu : {lieu}\n",
        encoding="utf-8",
    )

    fake_llm = MagicMock()

    with (
        patch("app.services.tdr.tdr_service.TDR_YAML_PATH", yaml_file),
        patch("app.services.tdr.tdr_service.get_llm_provider", return_value=fake_llm),
    ):
        from app.services.tdr.tdr_service import TDRService
        svc = TDRService()

    svc.llm = fake_llm
    return svc


# ──────────────────────────────────────────────
# _build_prompt
# ──────────────────────────────────────────────

class TestBuildPrompt:
    def test_remplace_tous_les_placeholders(self, service):
        brief = {
            "client": "Ministère",
            "objectifs": "Former 50 agents",
            "public": "Agents RH",
            "duree": "3 jours",
            "format": "Présentiel",
            "budget": "5 000 000 Ar",
            "lieu": "Antananarivo",
        }
        prompt = service._build_prompt(brief)

        assert "Ministère" in prompt
        assert "Former 50 agents" in prompt
        assert "Agents RH" in prompt
        assert "3 jours" in prompt
        assert "Présentiel" in prompt
        assert "5 000 000 Ar" in prompt
        assert "Antananarivo" in prompt

    def test_valeurs_par_defaut_si_brief_vide(self, service):
        prompt = service._build_prompt({})

        assert "Non précisé" in prompt

    def test_aucune_accolade_residuelle(self, service):
        """Aucun placeholder {xxx} ne doit rester dans le prompt après build."""
        import re
        prompt = service._build_prompt({"client": "Test"})
        assert not re.search(r"\{[a-z]+\}", prompt)


# ──────────────────────────────────────────────
# _extract_json
# ──────────────────────────────────────────────

class TestExtractJson:
    def test_json_direct(self, service):
        content = json.dumps(FAKE_TDR_JSON)
        result = service._extract_json(content)
        assert result["titre"] == "Formation Python"

    def test_json_dans_texte(self, service):
        content = f"Voici le résultat :\n```json\n{json.dumps(FAKE_TDR_JSON)}\n```"
        result = service._extract_json(content)
        assert result is not None
        assert result["titre"] == "Formation Python"

    def test_json_invalide_retourne_none(self, service):
        result = service._extract_json("Pas du JSON du tout")
        assert result is None

    def test_chaine_vide_retourne_none(self, service):
        result = service._extract_json("")
        assert result is None

    def test_json_avec_accolades_imbriquees(self, service):
        content = json.dumps({"a": {"b": "c"}, "list": [1, 2, 3]})
        result = service._extract_json(content)
        assert result["a"]["b"] == "c"


# ──────────────────────────────────────────────
# generate
# ──────────────────────────────────────────────

class TestGenerate:
    def test_brief_vide_retourne_none(self, service):
        result = run(service.generate({}))
        assert result is None

    def test_brief_none_retourne_none(self, service):
        result = run(service.generate(None))
        assert result is None

    def test_reponse_llm_vide_retourne_none(self, service):
        service.llm.generate_with_retry = AsyncMock(return_value={"content": ""})
        result = run(service.generate({"client": "Test"}))
        assert result is None

    def test_reponse_llm_json_invalide_retourne_none(self, service):
        service.llm.generate_with_retry = AsyncMock(
            return_value={"content": "Pas du JSON"}
        )
        result = run(service.generate({"client": "Test"}))
        assert result is None

    def test_reponse_llm_valide(self, service):
        service.llm.generate_with_retry = AsyncMock(
            return_value={"content": json.dumps(FAKE_TDR_JSON)}
        )
        result = run(service.generate({"client": "Ministère", "objectifs": "Former"}))

        assert result is not None
        assert result["titre"] == "Formation Python"
        assert result["client"] == "Ministère"
        assert "generation_time_seconds" in result
        assert result["ai_provider"] == "groq"

    def test_exception_llm_retourne_none(self, service):
        service.llm.generate_with_retry = AsyncMock(side_effect=RuntimeError("Groq down"))
        result = run(service.generate({"client": "Test"}))
        assert result is None
