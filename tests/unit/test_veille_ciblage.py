# ============================================================
# TESTS — M1 ciblage des sources (aucun appel réseau)
# ============================================================
import asyncio
from datetime import date, datetime

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


# ---- Garde-fous déterministes (après le LLM) ----

AUJOURD_HUI = datetime(2026, 10, 12)


def test_echeance_passee_rejetee():
    assert vo.echeance_depassee("2024-11-28", AUJOURD_HUI)
    assert vo.echeance_depassee("2026-10-11T23:59:00", AUJOURD_HUI)


def test_echeance_future_absente_ou_illisible_acceptee():
    assert not vo.echeance_depassee("2026-10-12", AUJOURD_HUI)
    assert not vo.echeance_depassee(None, AUJOURD_HUI)
    assert not vo.echeance_depassee("dans 3 semaines", AUJOURD_HUI)


def test_mention_madagascar():
    assert vo.mentionne_madagascar({"title": "Formation IA", "organizer": "Ministère, Antananarivo"})
    assert vo.mentionne_madagascar({"title": "Avis", "url": "https://www.armp.mg/avis/12"})
    assert not vo.mentionne_madagascar({"title": "Avis", "url": "https://img.mgx.com/a"})


def test_cas_reel_emme_hdm4_rejete():
    """Faux positif du 12/10/2026 : accepté par le LLM (score 75),
    alors qu'il est expiré et sans mention de Madagascar."""
    opp = {
        "title": "MISSION DE FORMATION ET D'ACCOMPAGNEMENT SUR LES LOGICIELS EMME, HDM-4",
        "organizer": "Agence Française de Développement (AFD)",
        "url": "https://afd.dgmarket.com/tenders/adminShowBuyer.do?buyerId=6696755",
        "deadline": "2024-11-28",
    }
    assert vo.echeance_depassee(opp["deadline"], AUJOURD_HUI)
    assert not vo.mentionne_madagascar(opp)


# ---- Découpage des pages de liste en avis individuels ----

PAGE_ARMP = (
    "## Avis spécifiques Source des données : e-GP "
    "| MINISTERE DES TRAVAUX PUBLICS ----------------------------- "
    "Ref: 011-2026/MTP/PRMP Mode: ACO | Entretien et réparation de routes "
    "| MINISTERE DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE "
    "----------------------------- Ref: 012-2026/METFP/SG | Formation des formateurs en informatique "
    "| COMMUNE URBAINE D'ANTANANARIVO ----------------------------- "
    "Ref: 045-2024/CUA | Fourniture de bureau"
)

PAGE_DGMARKET = (
    "Avis publiés par l'acheteur "
    "| Nov 28, 2024 | | Appel d'offres | MISSION DE FORMATION EMME, HDM-4 | Madagascar "
    "| Mar 20, 2026 | | Appel d'offres | Formation IA pour agents publics | Madagascar "
    "| Sep 02, 2026 | | Appel à Manifestation d'Intérêt | Consultant data | Madagascar"
)


def test_page_armp_decoupee_et_avis_anciens_ecartes():
    avis = ts.decouper_liste_avis("Site ARMP", "https://armp.mg/avis", PAGE_ARMP, annee_courante=2026)
    assert len(avis) == 2                                   # l'avis 2024 est écarté
    assert "METFP" in avis[1]["content"]
    assert avis[0]["url"] != avis[1]["url"]                 # pas fusionnés par le dédoublonnage


def test_tableau_dgmarket_decoupe_garde_les_avis_recents():
    # 10/09/2026 : Sep 02 (8 j) gardé ; Mar 20 (174 j) et Nov 28, 2024 écartés
    avis = ts.decouper_liste_avis(
        "AFD - dgMarket", "https://dgmarket.com/x", PAGE_DGMARKET,
        aujourd_hui=date(2026, 9, 10),
    )
    assert [a["content"][:12] for a in avis] == ["Sep 02, 2026"]
    assert "Consultant data" in avis[0]["title"]


def test_dates_de_publication_francaises_et_anglaises():
    assert ts.date_publication("Aou 13, 2026 | Appel") == date(2026, 8, 13)
    assert ts.date_publication("Sept 16, 2026 |") == date(2026, 9, 16)
    assert ts.date_publication("Juil 2, 2026 |") == date(2026, 7, 2)
    assert ts.date_publication("Jun 15, 2026 |") == date(2026, 6, 15)
    assert ts.date_publication("MINISTERE Ref: 012-2026") is None


def test_page_simple_non_decoupee():
    assert ts.decouper_liste_avis("Avis", "https://a.mg", "Un seul avis, Ref: 1-2026", annee_courante=2026) is None
    assert ts.decouper_liste_avis("Avis", "https://a.mg", None) is None


def test_filtre_tavily_remplace_la_liste_par_ses_avis():
    service = ts.TavilyService.__new__(ts.TavilyService)
    resultats = service._resultats_page(
        {"raw_content": PAGE_ARMP}, "Site ARMP", "https://armp.mg/avis", "snippet",
    )
    assert len(resultats) == 2


def test_avis_de_resultats_rejetes_avant_le_llm():
    results = [
        _res("AVIS DE PUBLICATION DE RÉSULTATS - PSO N° OF 78/2024", "https://d.com/1",
             "Acquisition de véhicules"),
        _res("Avis d'attribution définitive", "https://d.com/2"),
        _res("TDR formation réseau", "https://armp.mg/3",
             "Résultats attendus : agents formés à l'administration réseau"),
    ]
    assert [r["title"] for r in pf.rank_results(results, "q")] == ["TDR formation réseau"]
