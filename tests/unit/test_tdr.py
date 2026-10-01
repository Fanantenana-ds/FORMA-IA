# ============================================================
# TESTS — M2 TDR
# ============================================================
import pytest

from app.orchestrator.tdr_orchestrator import TdrOrchestrator


class TestTdrOrchestrator:
    """Tests pour l'orchestrateur TDR"""

    def setup_method(self):
        self.orchestrator = TdrOrchestrator()

    @pytest.mark.asyncio
    async def test_generer_tdr_success(self):
        """Test de génération de TDR avec brief valide"""
        brief = {
            "client": "Ministère de la Santé",
            "objectifs": "Former 50 agents à l'IA médicale",
            "public": "Agents de santé",
            "duree": "5 jours",
            "format": "Présentiel",
            "budget": "150 000 000 Ar"
        }

        resultat = await self.orchestrator.generate(brief)

        assert resultat["success"] is True
        assert "tdr" in resultat["data"]
        assert "documents" in resultat["data"]

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