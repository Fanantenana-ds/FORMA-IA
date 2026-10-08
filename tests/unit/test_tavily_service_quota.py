# tests/unit/test_tavily_service_quota.py
# ============================================================
# Étape B (mission "Préparation soutenance") — TavilyService x quota
# ============================================================
# AVANT cette correction, TavilyService.search() ne comptait ni ne
# limitait AUCUN appel HTTP réel : compter les "requêtes" utilisateur ne
# suffit pas (jusqu'à 2 appels HTTP par recherche — principal + repli —
# plus des retries sur 5xx). Cette suite vérifie que CHAQUE appel HTTP
# réel est compté (retry et repli compris), qu'un cache hit ne compte
# JAMAIS, et que le plafond dur bloque manuel/collecte (jamais auto,
# protégé en amont par verifier_quota_auto).
#
# Aucun réseau réel : httpx.AsyncClient est remplacé globalement par un
# faux client qui rejoue des réponses fournies dans l'ordre. asyncio.sleep
# neutralisé (aucune vraie attente pendant les tests de retry).
# ============================================================

import asyncio

import httpx
import pytest

from app.services.veille import tavily_service as tavily_module
from app.services.veille import tavily_quota_service as quota
from app.services.veille.tavily_service import TavilyService
from app.services.veille.tavily_quota_service import QuotaTavilyDepasseError


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(quota, "QUOTA_PATH", tmp_path / "tavily_quota.json")
    monkeypatch.setattr(tavily_module, "TAVILY_API_KEY", "faux-cle-test")
    TavilyService._cache.clear()  # cache de CLASSE, partagé entre instances/tests


@pytest.fixture(autouse=True)
def pas_de_vraie_attente(monkeypatch):
    async def sleep_immediat(*a, **kw):
        return None
    monkeypatch.setattr(asyncio, "sleep", sleep_immediat)


class FauxReponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {"results": []}

    def json(self):
        return self._data

    def raise_for_status(self):
        raise httpx.HTTPStatusError("erreur serveur", request=None, response=self)


class FauxAsyncClient:
    """Rejoue les réponses (ou exceptions) fournies dans l'ordre — un
    élément consommé par appel .post()."""

    def __init__(self, reponses, appels, **kw):
        self._reponses = reponses
        self._appels = appels

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None):
        self._appels.append(json)
        item = self._reponses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def installer_faux_client(monkeypatch, reponses):
    appels = []
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FauxAsyncClient(reponses, appels))
    return appels


RESULTAT_PROPRE = {"title": "Titre", "url": "https://asako.mg/offre", "content": "texte propre"}


def test_recherche_reussie_du_premier_coup_compte_un_seul_appel(monkeypatch):
    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])

    resultats = asyncio.run(TavilyService().search("formation IA", categorie="manuel"))

    assert len(appels_http) == 1
    assert len(resultats) == 1
    assert quota.consommation("manuel") == 1
    assert quota.consommation("auto") == 0


def test_repli_declenche_un_deuxieme_appel_compte(monkeypatch):
    """0 résultat utile après filtrage à l'étape 'avec site:' -> repli
    'sans site:' -> 2 appels HTTP réels, tous deux comptés."""
    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": []}),                       # avec site: -> rien
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),          # repli -> un résultat propre
    ])

    resultats = asyncio.run(TavilyService().search("formation IA", categorie="manuel"))

    assert len(appels_http) == 2
    assert len(resultats) == 1
    assert quota.consommation("manuel") == 2


def test_retry_sur_5xx_est_compte_a_chaque_tentative(monkeypatch):
    """1ère tentative de l'étape 'avec site' échoue (5xx, compté), le
    retry réussit (compté aussi) -> 2 appels comptés, pas de repli requis."""
    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(500),
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])

    resultats = asyncio.run(TavilyService().search("formation IA", categorie="collecte"))

    assert len(appels_http) == 2
    assert len(resultats) == 1
    assert quota.consommation("collecte") == 2
    assert quota.consommation("manuel") == 0


def test_cache_hit_ne_declenche_ni_appel_http_ni_comptage(monkeypatch):
    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])
    service = TavilyService()

    asyncio.run(service.search("formation IA unique", categorie="manuel"))
    assert len(appels_http) == 1
    assert quota.consommation("manuel") == 1

    # 2e appel, même requête -> cache HIT : ni appel HTTP ni comptage supplémentaire
    resultat_cache = asyncio.run(service.search("formation IA unique", categorie="manuel"))
    assert len(appels_http) == 1
    assert quota.consommation("manuel") == 1
    assert len(resultat_cache) == 1


def test_categorie_auto_jamais_bloquee_par_le_plafond_dur(monkeypatch):
    """Le mode auto est protégé EN AMONT (verifier_quota_auto, une fois par
    passage) -- pas ici, appel par appel."""
    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "1")
    quota.enregistrer_appel("auto")  # total = 1 = plafond, déjà "atteint"

    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])

    resultats = asyncio.run(TavilyService().search("formation IA", categorie="auto"))

    assert len(appels_http) == 1  # aucune exception, l'appel a bien eu lieu
    assert len(resultats) == 1


def test_categorie_manuel_bloquee_au_plafond_dur(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "1")
    quota.enregistrer_appel("manuel")  # total = 1 = plafond

    appels_http = installer_faux_client(monkeypatch, [])  # ne doit JAMAIS être consommé

    with pytest.raises(QuotaTavilyDepasseError):
        asyncio.run(TavilyService().search("formation IA", categorie="manuel"))

    assert appels_http == []


def test_categorie_collecte_bloquee_au_plafond_dur(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "1")
    quota.enregistrer_appel("collecte")

    appels_http = installer_faux_client(monkeypatch, [])

    with pytest.raises(QuotaTavilyDepasseError):
        asyncio.run(TavilyService().search("formation IA", categorie="collecte"))

    assert appels_http == []


def test_cache_hit_jamais_bloque_meme_au_plafond_dur(monkeypatch):
    """Un cache hit ne coûte rien : il ne doit jamais être refusé, même
    plafond dur atteint."""
    appels_http = installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])
    service = TavilyService()
    asyncio.run(service.search("requete cachee", categorie="manuel"))

    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "1")  # déjà atteint (1 appel ci-dessus)

    resultat = asyncio.run(service.search("requete cachee", categorie="manuel"))
    assert len(resultat) == 1
    assert len(appels_http) == 1  # toujours 1 : le 2e appel était un cache hit


def test_categorie_par_defaut_est_manuel(monkeypatch):
    installer_faux_client(monkeypatch, [
        FauxReponse(200, {"results": [RESULTAT_PROPRE]}),
    ])

    asyncio.run(TavilyService().search("sans categorie explicite"))

    assert quota.consommation("manuel") == 1
    assert quota.consommation("auto") == 0
