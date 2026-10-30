"""Contrat HTTP du vocal avancé, sans LLM, RAG ou réseau."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import vocal_ia
from app.services.veille.access_service import verify_api_key


class FauxAssistant:
    async def traiter(self, texte, formations, conversation_id):
        return {
            "intention": "question_rag", "confiance": 0.94, "parametres": {},
            "parametres_manquants": [], "action_frontend": "ouvrir_chat_rag", "prefill": {},
            "conversation_id": conversation_id or "conv-42",
            "sources": [{"fichier": "guide.pdf", "page": 3, "score": 0.88}],
            "suggestions": ["Donne un exemple"],
            "texte_affiche": "Réponse documentée.",
            "texte_a_lire": "Réponse documentée. Les sources sont affichées à l'écran.",
            "etat": "reponse_sourcee", "niveau_preuve": "sourcee",
        }


def test_commande_vocale_retourne_le_contrat_rag(monkeypatch):
    app = FastAPI()
    app.include_router(vocal_ia.router)
    app.dependency_overrides[verify_api_key] = lambda: None
    monkeypatch.setattr(vocal_ia, "get_assistant_vocal_service", lambda: FauxAssistant())

    response = TestClient(app).post("/ia/vocal/commande", json={
        "texte": "Explique le RAG", "conversation_id": "conv-existante",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["etat"] == "reponse_sourcee"
    assert body["conversation_id"] == "conv-existante"
    assert body["sources"][0]["page"] == 3
    assert body["reponse_vocale"] == body["texte_a_lire"]
