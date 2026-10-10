# ============================================================
# TESTS — M2 TDR
# ============================================================
import pytest

from app.orchestrator.tdr_orchestrator import TdrOrchestrator
from app.services.hitl import hitl_helper


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def store_hitl_temporaire(monkeypatch, tmp_path):
    """Aucune review de test dans le vrai store data/hitl_reviews.json."""
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")


class TestTdrOrchestrator:
    """Tests pour l'orchestrateur TDR (generate())."""

    def setup_method(self):
        self.orchestrator = TdrOrchestrator()
        if not self.orchestrator.tdr_service:
            pytest.skip(
                "TDRService indisponible (GROQ_API_KEY absente en environnement de test) "
                "- tests a activer une fois un mock ou une cle de test fournis par l'equipe"
            )

    @pytest.mark.asyncio
    async def test_generer_tdr_success(self):
        """Test de génération de TDR avec brief valide"""
        brief = {
            "client": "Ministère de la Santé",
            "objectifs": "Former 50 agents à l'IA médicale",
            "public": "Agents de santé",
            "duree": "5 jours",
            "format": "Présentiel",
            "budget": "150 000 000 Ar",
        }

        resultat = await self.orchestrator.generate(brief)

        assert resultat["success"] is True
        assert resultat["data"]["titre"] == "TDR Formation IA médicale"
        assert resultat["files"] == {"docx": "tdr_test.docx", "pdf": "tdr_test.pdf"}
        assert resultat["error"] is None

    @pytest.mark.asyncio
    async def test_generer_tdr_missing_field(self):
        """Test de génération de TDR avec champ manquant"""
        brief = {
            "client": "Ministère de la Santé",
            "objectifs": "Former 50 agents à l'IA médicale"
            # manque public, duree
        }

        resultat = await self.orchestrator.generate(brief)

        assert resultat["success"] is False
        assert resultat["error"] is not None

    @pytest.mark.asyncio
    async def test_generer_tdr_empty_fields(self):
        """Test de génération de TDR avec champ vide"""
        brief = {
            "client": "",
            "objectifs": "Former 50 agents",
            "public": "Agents",
            "duree": "5 jours"
        }

        resultat = await self.orchestrator.generate(brief)

        assert resultat["success"] is False
        assert "vide" in resultat["error"].lower() or "manquant" in resultat["error"].lower()