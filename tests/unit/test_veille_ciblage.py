# ============================================================
# TESTS — M1 ciblage des sources (aucun appel réseau)
# ============================================================
import asyncio

from app.orchestrator import veille_orchestrator as vo
from app.services.veille import prefilter_service as pf
from app.services.veille import tavily_service as ts


def run(coro):
    return asyncio.run(coro)


# ---- Tavily : domaines et bruit ----

def test_domaines_lus_depuis_env():
    assert ts._domains_from_env(" armp.mg , UNDP.org ,, ") == ["armp.mg", "undp.org"]


def test_domaines_par_defaut_si_env_vide():
    assert ts._domains_from_env("") == ts._DEFAULT_TRUSTED_DOMAINS
    assert ts._domains_from_env(None) == ts._DEFAULT_TRUSTED_DOMAINS


def test_bruit_mots_entiers_uniquement():
    # en sous-chaîne, "war" rejetait "software" et "spa" rejetait "espace"
    assert not ts.contains_noise("Formation software engineering, espace de travail")
    assert ts.contains_noise("Cours de yoga à Antananarivo")


def test_sante_et_universite_ne_sont_plus_du_bruit():
    assert not ts.contains_noise(
        "Ministère de la Santé : appel d'offres formation IA, Université d'Antananarivo"
    )


# ---- Préfiltre : doublons, listings vides, CV, bonus marché ----

def _res(title, url, content="contenu"):
    return {"title": title, "url": url, "content": content}


def test_doublons_retires():
    results = [
        _res("A", "https://x.mg/1"),
        _res("A bis", "https://x.mg/1/"),          # même URL
        _res("Même", "https://x.mg/2", "texte identique"),
        _res("Même", "https://x.mg/3", "texte identique"),  # même titre + contenu
    ]
    assert sorted(r["url"] for r in pf.rank_results(results, "q")) == [
        "https://x.mg/1", "https://x.mg/2",
    ]


def test_listing_vide_et_cv_rejetes():
    results = [
        _res("Offres", "https://p.mg/emploi", "0 Offres d'emplois trouvées. Aucune offre"),
        _res("Profil", "https://p.mg/cv/12345"),
        _res("Utile", "https://p.mg/annonce/9"),
    ]
    assert [r["title"] for r in pf.rank_results(results, "q")] == ["Utile"]


def test_appel_d_offres_classe_en_premier():
    results = [
        _res("Offre emploi CDI", "https://a.mg/1", "recrutement CDI"),
        _res("Avis", "https://b.mg/2", "Avis d'appel d'offres : formation IA"),
    ]
    assert pf.rank_results(results, "formation IA")[0]["title"] == "Avis"


# ---- Orchestrateur : pause entre appels LLM ----

def test_pause_llm_attend_le_reste(monkeypatch):
    attentes = []

    async def faux_sleep(s):
        attentes.append(s)

    monkeypatch.setattr(vo, "VEILLE_PAUSE_LLM_S", 5.0)
    monkeypatch.setattr(vo.asyncio, "sleep", faux_sleep)
    horloge = {"t": 100.0}
    monkeypatch.setattr(vo.time, "monotonic", lambda: horloge["t"])

    orch = vo.VeilleOrchestrator.__new__(vo.VeilleOrchestrator)
    run(orch._respecter_pause_llm())   # 1er appel : pas d'attente
    horloge["t"] = 102.0
    run(orch._respecter_pause_llm())   # 2 s plus tard : attend 3 s

    assert attentes == [3.0]


def test_pause_llm_desactivee_par_defaut(monkeypatch):
    attentes = []

    async def faux_sleep(s):
        attentes.append(s)

    monkeypatch.setattr(vo, "VEILLE_PAUSE_LLM_S", 0.0)
    monkeypatch.setattr(vo.asyncio, "sleep", faux_sleep)

    orch = vo.VeilleOrchestrator.__new__(vo.VeilleOrchestrator)
    run(orch._respecter_pause_llm())
    run(orch._respecter_pause_llm())

    assert attentes == []


# ---- E : extrait utile du texte brut ----

def test_extrait_sans_texte_brut_garde_le_snippet():
    assert ts.extrait_utile("court", None, maximum=500) == "court"


def test_extrait_centre_sur_le_repere_d_avis():
    raw = ("menu accueil contact " * 50) + "Date limite de dépôt des offres : 15/11/2026. Budget 80M Ar."
    extrait = ts.extrait_utile("Avis formation IA", raw, maximum=400)
    assert len(extrait) <= 400
    assert "Date limite" in extrait and extrait.startswith("Avis formation IA")


# ---- A / budget : toutes les sources du lot sont montrées au LLM ----

def _service_llm():
    from app.services.veille.llm_analysis_service import LLMAnalysisService
    return LLMAnalysisService.__new__(LLMAnalysisService)


def test_toutes_les_sources_sont_dans_le_prompt():
    results = [_res(f"T{i}", f"https://x.mg/{i}", "x" * 3000) for i in range(1, 9)]
    texte = _service_llm()._build_source_blocks(results)
    assert texte.count("===== RESULTAT") == 8


def test_titres_nettoyes_dans_le_prompt():
    texte = _service_llm()._build_source_blocks([_res("Agence\n\n\n  AFD", "https://afd.fr/1")])
    assert "TITRE: Agence AFD" in texte


def test_rejets_journalises(caplog):
    from app.services.veille.llm_analysis_service import LLMAnalysisService
    caplog.set_level("INFO")
    LLMAnalysisService._log_rejets(
        {"rejets": [{"resultat": 1, "raison": "expiré le 2024-11-28"}, "invalide"]},
        [_res("Avis ARMP", "https://armp.mg/1")],
    )
    assert "Avis ARMP → expiré le 2024-11-28" in caplog.text
