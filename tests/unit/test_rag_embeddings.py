# ============================================================
# TESTS — Étape B de la mission C3 (embeddings Voyage AI)
# ============================================================
# Aucun réseau réel (httpx.MockTransport), aucune vraie attente (horloge
# et fonction "dormir" injectables), clé jamais journalisée.
# Commande : venv\Scripts\python.exe -m pytest tests/unit/test_rag_embeddings.py -q --noconftest
# ============================================================

import json

import httpx
import pytest

from app.services.rag.rate_limiter import LimiteurDebit, DelaiDepasseError
from app.services.rag.embedding_provider import (
    ConfigurationVoyage,
    VoyageEmbeddingProvider,
    EmbeddingProviderError,
    construire_lots,
    estimer_tokens,
    famille_de,
    verifier_compatibilite_famille,
    traduire_erreur_voyage,
)


# ============================================================
# HORLOGE SIMULÉE
# ============================================================

class HorlogeSimulee:
    def __init__(self, depart: float = 0.0):
        self.t = depart

    def __call__(self) -> float:
        return self.t

    def avancer(self, secondes: float) -> None:
        self.t += secondes


async def dormir_instantane(secondes: float) -> None:
    """Remplace asyncio.sleep dans les tests : n'attend jamais réellement."""
    return None


def config_test(**overrides) -> ConfigurationVoyage:
    base = dict(
        cle_api="cle-de-test-jamais-reelle",
        modele_document="voyage-4-large",
        modele_requete="voyage-4-large",
        rpm=3,
        tpm=10_000,
        opt_out=False,
    )
    base.update(overrides)
    return ConfigurationVoyage(**base)


def transport_capturant(reponses):
    """MockTransport qui renvoie les réponses fournies dans l'ordre, une par
    appel, et mémorise chaque requête dans `appels`."""
    appels = []
    file = list(reponses)

    def handler(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        return file.pop(0)

    return httpx.MockTransport(handler), appels


def reponse_ok(vecteurs):
    return httpx.Response(200, json={"data": [{"embedding": v} for v in vecteurs]})


# ============================================================
# LIMITEUR DE DÉBIT
# ============================================================

def test_limiteur_respecte_rpm():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=2, tpm=100_000, horloge=horloge)

    limiteur.enregistrer_appel(10)
    limiteur.enregistrer_appel(10)

    assert limiteur.temps_attente(10) > 0  # 3e appel bloqué par le RPM


def test_limiteur_respecte_tpm():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=100, tpm=1000, horloge=horloge)

    limiteur.enregistrer_appel(900)

    assert limiteur.temps_attente(200) > 0  # dépasserait 1000 tokens/min


def test_limiteur_purge_fenetre_glissante():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=1, tpm=100_000, horloge=horloge)

    limiteur.enregistrer_appel(10)
    assert limiteur.temps_attente(10) > 0

    horloge.avancer(61)  # fenêtre de 60s dépassée

    assert limiteur.temps_attente(10) == 0


@pytest.mark.asyncio
async def test_attendre_puis_consommer_leve_delai_depasse():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=1, tpm=100_000, horloge=horloge)
    limiteur.enregistrer_appel(10)  # sature le RPM (attente ~60s)

    with pytest.raises(DelaiDepasseError) as exc_info:
        await limiteur.attendre_puis_consommer(
            10, attente_max_s=5.0, dormir=dormir_instantane,
        )
    assert exc_info.value.temps_restant_s > 5.0


@pytest.mark.asyncio
async def test_attendre_puis_consommer_mode_indexation_attend_sans_limite():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=1, tpm=100_000, horloge=horloge)
    limiteur.enregistrer_appel(10)

    attentes = []
    await limiteur.attendre_puis_consommer(
        10, attente_max_s=None, dormir=dormir_instantane,
        sur_attente=lambda s: attentes.append(s),
    )
    assert attentes and attentes[0] > 0  # a bien signalé une attente, sans lever d'erreur


# ============================================================
# CONSTRUCTION DES LOTS — par tokens, jamais un nombre fixe
# ============================================================

def test_construire_lots_respecte_80_pourcent_tpm():
    # ~700 tokens/texte (2800 caractères) ; tpm=10000 -> budget 8000/lot
    textes = ["x" * 2800] * 6  # 6 * 700 = 4200 tokens -> tient dans 1 lot de 8000
    lots = construire_lots(textes, tpm=10_000)
    for lot in lots:
        tokens_lot = sum(estimer_tokens(t) for t in lot)
        assert tokens_lot <= 8_000


def test_construire_lots_plusieurs_lots_si_depassement():
    textes = ["x" * 2800] * 20  # 20 * 700 = 14000 tokens -> plusieurs lots
    lots = construire_lots(textes, tpm=10_000)
    assert len(lots) > 1
    for lot in lots:
        assert sum(estimer_tokens(t) for t in lot) <= 8_000


def test_construire_lots_jamais_plus_de_1000_textes():
    textes = ["court"] * 1500
    lots = construire_lots(textes, tpm=1_000_000)
    for lot in lots:
        assert len(lot) <= 1000


def test_estimer_tokens_environ_4_caracteres():
    assert estimer_tokens("x" * 400) == 100


# ============================================================
# FAMILLES DE MODÈLES — compatibilité
# ============================================================

def test_famille_de_modele_connu():
    assert famille_de("voyage-4-large") == "voyage-4"
    assert famille_de("voyage-4-lite") == "voyage-4"


def test_famille_de_modele_inconnu():
    assert famille_de("voyage-3-large") is None
    assert famille_de("bge-m3") is None


def test_verifier_compatibilite_meme_famille_ok():
    verifier_compatibilite_famille("voyage-4-large", "voyage-4")  # ne lève rien


def test_verifier_compatibilite_hors_famille_refuse():
    # Une seule famille est définie à ce jour (voyage-4) : tout modèle qui
    # n'en fait pas partie est "inconnu" (pas "incompatible", puisqu'il n'y
    # a pas de 2e famille reconnue avec laquelle comparer). Le jour où une
    # 2e famille sera ajoutée, ce test devra utiliser un modèle de CETTE
    # famille pour exercer la branche "incompatibles".
    with pytest.raises(ValueError, match="inconnu"):
        verifier_compatibilite_famille("voyage-4-large", "voyage-3-large")


def test_verifier_compatibilite_modele_totalement_inconnu_refuse():
    with pytest.raises(ValueError, match="inconnu"):
        verifier_compatibilite_famille("bge-m3", "voyage-4-large")


# ============================================================
# ERREURS — TRADUITES, JAMAIS LA CLÉ
# ============================================================

def test_traduire_erreur_401():
    assert "Clé Voyage invalide" in traduire_erreur_voyage(401)


def test_traduire_erreur_402():
    assert "Moyen de paiement" in traduire_erreur_voyage(402)


def test_traduire_erreur_429():
    assert "Limite de débit" in traduire_erreur_voyage(429)


def test_traduire_erreur_5xx():
    assert "indisponible" in traduire_erreur_voyage(503)


def test_traduire_erreur_reseau():
    assert "injoignable" in traduire_erreur_voyage(None)


# ============================================================
# PROVIDER — modèles, retries, clé jamais journalisée
# ============================================================

@pytest.mark.asyncio
async def test_embed_documents_utilise_modele_document_et_input_type():
    transport, appels = transport_capturant([reponse_ok([[0.1] * 1024])])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(modele_document="voyage-4-large", modele_requete="voyage-4"),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    await provider.embed_documents(["un texte"])

    corps = json.loads(appels[0].content)
    assert corps["model"] == "voyage-4-large"
    assert corps["input_type"] == "document"
    await client.aclose()


@pytest.mark.asyncio
async def test_embed_query_utilise_modele_requete_et_input_type():
    transport, appels = transport_capturant([reponse_ok([[0.2] * 1024])])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(modele_document="voyage-4-large", modele_requete="voyage-4"),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    await provider.embed_query("une question", attente_max_s=None)

    corps = json.loads(appels[0].content)
    assert corps["model"] == "voyage-4"
    assert corps["input_type"] == "query"
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_sur_429_puis_succes():
    transport, appels = transport_capturant([
        httpx.Response(429, json={"error": "rate limited"}),
        reponse_ok([[0.3] * 1024]),
    ])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    resultat = await provider.embed_documents(["texte"])

    assert len(appels) == 2  # 1 échec + 1 retry réussi
    assert resultat == [[0.3] * 1024]
    await client.aclose()


@pytest.mark.asyncio
async def test_pas_de_retry_sur_401():
    transport, appels = transport_capturant([
        httpx.Response(401, json={"error": "invalid key"}),
    ])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    with pytest.raises(EmbeddingProviderError, match="Clé Voyage invalide"):
        await provider.embed_documents(["texte"])

    assert len(appels) == 1  # aucune tentative supplémentaire sur 401
    await client.aclose()


@pytest.mark.asyncio
async def test_pas_de_retry_sur_402():
    transport, appels = transport_capturant([
        httpx.Response(402, json={"error": "payment required"}),
    ])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    with pytest.raises(EmbeddingProviderError, match="Moyen de paiement"):
        await provider.embed_documents(["texte"])

    assert len(appels) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_abandon_apres_max_tentatives_sur_429_persistant():
    transport, appels = transport_capturant([
        httpx.Response(429, json={}), httpx.Response(429, json={}), httpx.Response(429, json={}),
    ])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    with pytest.raises(EmbeddingProviderError, match="Limite de débit"):
        await provider.embed_documents(["texte"])

    assert len(appels) == 3  # MAX_TENTATIVES
    await client.aclose()


@pytest.mark.asyncio
async def test_cle_jamais_dans_les_logs_ou_exceptions(caplog):
    cle_secrete = "voy-cle-ultra-secrete-123456"
    transport, appels = transport_capturant([httpx.Response(401, json={})])
    client = httpx.AsyncClient(transport=transport)
    provider = VoyageEmbeddingProvider(
        config=config_test(cle_api=cle_secrete),
        limiteur=LimiteurDebit(rpm=100, tpm=1_000_000, horloge=HorlogeSimulee()),
        client=client,
        dormir=dormir_instantane,
    )

    with caplog.at_level("DEBUG"):
        try:
            await provider.embed_documents(["texte"])
        except EmbeddingProviderError as exc:
            assert cle_secrete not in str(exc)

    assert cle_secrete not in caplog.text
    await client.aclose()


@pytest.mark.asyncio
async def test_embed_query_abandon_apres_5s_sans_attendre_reellement():
    horloge = HorlogeSimulee()
    limiteur = LimiteurDebit(rpm=1, tpm=1_000_000, horloge=horloge)
    limiteur.enregistrer_appel(10)  # sature le RPM : le prochain appel attendrait ~60s

    provider = VoyageEmbeddingProvider(
        config=config_test(),
        limiteur=limiteur,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: reponse_ok([[0.0] * 1024]))),
        dormir=dormir_instantane,
    )

    with pytest.raises(DelaiDepasseError):
        await provider.embed_query("une question", attente_max_s=5.0)


# ============================================================
# CONFIGURATION — lue depuis .env, choix de clé selon le profil
# ============================================================

def test_config_lit_les_limites_depuis_env(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "cle-dev-factice")
    monkeypatch.setenv("VOYAGE_KEY_PROFILE", "dev")
    monkeypatch.setenv("VOYAGE_RPM", "7")
    monkeypatch.setenv("VOYAGE_TPM", "12345")

    config = ConfigurationVoyage.depuis_env()

    assert config.rpm == 7
    assert config.tpm == 12345


def test_config_choisit_cle_selon_profil_soutenance(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "cle-dev-jamais-utilisee-ici")
    monkeypatch.setenv("VOYAGE_API_KEY_SOUTENANCE", "cle-soutenance-attendue")
    monkeypatch.setenv("VOYAGE_KEY_PROFILE", "soutenance")

    config = ConfigurationVoyage.depuis_env()

    assert config.cle_api == "cle-soutenance-attendue"


def test_config_cle_absente_leve_erreur_claire(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("VOYAGE_KEY_PROFILE", "dev")

    with pytest.raises(EmbeddingProviderError, match="VOYAGE_API_KEY"):
        ConfigurationVoyage.depuis_env()


def test_config_refuse_modele_hors_famille(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "x")
    monkeypatch.setenv("VOYAGE_KEY_PROFILE", "dev")
    monkeypatch.setenv("VOYAGE_MODEL_DOCUMENT", "voyage-4-large")
    monkeypatch.setenv("VOYAGE_MODEL_QUERY", "voyage-3-large")

    with pytest.raises(ValueError, match="inconnu"):
        ConfigurationVoyage.depuis_env()
