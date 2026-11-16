import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.endpoints import vocal_ia
from app.services.vocal import transcription_service as service


@pytest.mark.parametrize("audio,mime,code", [(b"", "audio/webm", 400), (b"audio", "text/plain", 415), (b"x" * (service.MAX_AUDIO_BYTES + 1), "audio/webm", 413)], ids=["empty", "unsupported", "too-large"])
def test_audio_invalide_refuse_avant_appel_groq(audio, mime, code):
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.transcribe_audio(audio, mime))
    assert error.value.status_code == code


@pytest.mark.parametrize("status,body,expected", [(200, {"text": "Ouvre la veille marché"}, None), (200, {"text": ""}, 422), (429, {}, 429), (500, {}, 502)])
def test_groq_francais_quota_et_erreurs(monkeypatch, status, body, expected):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    post = AsyncMock(return_value=httpx.Response(status, json=body))
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return await post(*args, **kwargs)
    monkeypatch.setattr(service.httpx, "AsyncClient", Client)
    if expected:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.transcribe_audio(b"audio-test", "audio/webm;codecs=opus"))
        assert error.value.status_code == expected
    else:
        assert asyncio.run(service.transcribe_audio(b"audio-test", "audio/webm;codecs=opus")) == body["text"]
        assert post.call_args.kwargs["data"]["language"] == "fr"
        assert post.call_args.kwargs["files"]["file"][1] == b"audio-test"


def test_route_transcription_reutilise_session_et_contrat_multipart(monkeypatch):
    app = FastAPI(); app.include_router(vocal_ia.router)
    app.dependency_overrides[vocal_ia.verify_api_key] = lambda: None
    transcribe = AsyncMock(return_value="Explique la formation")
    monkeypatch.setattr(service, "transcribe_audio", transcribe)
    response = TestClient(app).post('/ia/vocal/transcrire', files={"audio": ("dictee.webm", b"audio-test", "audio/webm")})
    assert response.status_code == 200
    assert response.json()["texte"] == "Explique la formation"
    transcribe.assert_awaited_once_with(b"audio-test", "audio/webm")
