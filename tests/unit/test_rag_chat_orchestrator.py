# ============================================================
# TESTS — app/orchestrator/chat_orchestrator.py (Étape E, intégration)
# ============================================================
# Aucun réseau (faux fournisseur d'embeddings + faux LLM), aucune vraie
# base (faux dépôt en mémoire), catalogue/registre/mémoire/journal/cache
# redirigés vers tmp_path.
# ============================================================

import asyncio

import pytest

import app.orchestrator.chat_orchestrator as chat_module
from app.orchestrator.chat_orchestrator import ChatOrchestrator
from app.services.llm import LLMNotAvailableError
from app.services.rag import catalogue_service as catalogue
from app.services.rag import chat_log_service as journal
from app.services.rag import conversation_service as memoire
from app.services.rag import recherche_service as recherche
from app.services.rag import registry_service as registre
from app.services.rag import type_detection_service as detection

CATALOGUE_TEST = """
formations:
  - code: IA_FONDAMENTAUX
    titre: "Intelligence artificielle : les fondamentaux"
    domaine: "Intelligence artificielle"
    duree_jours: 3
    confidentiel: false
    realisations: []
"""


def run(coro):
    return asyncio.run(coro)


def test_accueil_plateforme_local_mais_question_metier_confiee_a_c3():
    assert chat_module._est_demande_generale_plateforme("Comment utiliser cette platforme ?") is True
    assert chat_module._est_demande_generale_plateforme(
        "Comment valider un TDR dans la plateforme FORMA-IA ?"
    ) is False


class Ligne:
    def __init__(self, contenu, fichier="doc.pdf", formation_code="IA_FONDAMENTAUX",
                 formation_titre="IA", collection="support", page_debut=3, page_fin=3, type_support="pdf"):
        self.contenu = contenu
        self.fichier = fichier
        self.formation_code = formation_code
        self.formation_titre = formation_titre
        self.collection = collection
        self.page_debut = page_debut
        self.page_fin = page_fin
        self.type_support = type_support
        self.modele_embed = "voyage-4-large"
        self.session_id = None
        self.module = None


class FauxRepository:
    def __init__(self, resultats=None):
        self._resultats = resultats or []

    def modeles_presents(self, collection=None):
        return ["voyage-4-large"] if self._resultats else []

    def rechercher_par_similarite(self, vecteur, collection, top_k, **filtres):
        return [(l, 0.1) for l in self._resultats][:top_k]  # distance basse = score haut


class FauxEmbeddingProvider:
    def __init__(self):
        self.appels = 0
        self.modele_requete = "voyage-4-large"
        self.modele_document = "voyage-4-large"

    async def embed_query(self, texte, **kw):
        self.appels += 1
        return [0.5] * 1024


class FauxLLM:
    def __init__(self, contenu_json='{"reponse": "Réponse générée par le faux LLM."}'):
        self.appels = 0
        self.contenu_json = contenu_json

    async def generate_with_retry(self, **kwargs):
        self.appels += 1
        return {"content": self.contenu_json}


@pytest.fixture
def chemin_catalogue(tmp_path):
    chemin = tmp_path / "catalogue.yaml"
    chemin.write_text(CATALOGUE_TEST, encoding="utf-8")
    return chemin


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path, chemin_catalogue):
    monkeypatch.setattr(catalogue, "CHEMIN_CATALOGUE_DEFAUT", chemin_catalogue)
    monkeypatch.setattr(chat_module.catalogue, "CHEMIN_CATALOGUE_DEFAUT", chemin_catalogue)
    monkeypatch.setattr(registre, "CHEMIN_REGISTRE_DEFAUT", tmp_path / "registry.json")
    monkeypatch.setattr(chat_module.registre, "CHEMIN_REGISTRE_DEFAUT", tmp_path / "registry.json")
    monkeypatch.setattr(memoire, "DOSSIER_CONVERSATIONS_DEFAUT", tmp_path / "conversations")
    monkeypatch.setattr(chat_module.memoire, "DOSSIER_CONVERSATIONS_DEFAUT", tmp_path / "conversations")
    monkeypatch.setattr(journal, "CHEMIN_JOURNAL_DEFAUT", tmp_path / "chat_logs.jsonl")
    monkeypatch.setattr(chat_module.journal, "CHEMIN_JOURNAL_DEFAUT", tmp_path / "chat_logs.jsonl")
    monkeypatch.setattr(recherche, "CHEMIN_CACHE_DEFAUT", tmp_path / "cache.json")
    monkeypatch.setattr(chat_module.rcache, "CHEMIN_CACHE_DEFAUT", tmp_path / "response_cache.json", raising=False)
    monkeypatch.setattr(chat_module.rcache, "depuis_cache", lambda *a, **kw: None)
    monkeypatch.setattr(chat_module.rcache, "mettre_en_cache", lambda *a, **kw: None)

    # Par défaut : aucun LLM disponible (force le repli par règles / gabarit).
    def pas_de_llm():
        raise LLMNotAvailableError("coupé pour les tests")
    monkeypatch.setattr(chat_module, "get_llm_provider", pas_de_llm)
    monkeypatch.setattr(detection, "get_llm_provider", pas_de_llm)


@pytest.fixture
def orchestrateur(monkeypatch):
    faux_provider = FauxEmbeddingProvider()
    monkeypatch.setattr(chat_module, "get_embedding_provider", lambda: faux_provider)
    monkeypatch.setattr(recherche, "get_embedding_provider", lambda: faux_provider)
    orch = ChatOrchestrator(repository=FauxRepository())
    orch._faux_provider = faux_provider  # pour inspection dans les tests
    return orch


# ============================================================
# CONVERSATIONNEL — jamais Voyage, jamais LLM (gabarit Python)
# ============================================================

def test_conversationnel_pur(orchestrateur):
    resultat = run(orchestrateur.traiter_message("bonjour"))
    assert resultat["type_reponse"] == "conversationnel"
    assert orchestrateur._faux_provider.appels == 0


def test_salutation_avec_question_n_est_jamais_conversationnel(orchestrateur):
    resultat = run(orchestrateur.traiter_message("bonjour, c'est quoi le deep learning ?"))
    assert resultat["type_reponse"] != "conversationnel"


# ============================================================
# CATALOGUE / INVENTAIRE — jamais Voyage, jamais LLM
# ============================================================

def test_catalogue_jamais_voyage_ni_llm(orchestrateur):
    registre.marquer_statut_special("h_cat", "doc.pdf", "IA_FONDAMENTAUX", "indexe", "ok")
    resultat = run(orchestrateur.traiter_message("quelles formations proposez-vous ?"))
    assert resultat["type_reponse"] == "catalogue"
    assert "Intelligence artificielle" in resultat["reponse"]
    assert orchestrateur._faux_provider.appels == 0


def test_inventaire_jamais_voyage_ni_llm(orchestrateur):
    registre.marquer_statut_special("h1", "doc.pdf", "IA_FONDAMENTAUX", "indexe", "ok")
    entree = registre.obtenir_entree("h1")
    entree.nb_chunks = 5
    registre.enregistrer_entree(entree)

    resultat = run(orchestrateur.traiter_message("combien de documents avez-vous indexés ?"))

    assert resultat["type_reponse"] == "inventaire"
    assert orchestrateur._faux_provider.appels == 0


# ============================================================
# LOCALISATION — Voyage oui, LLM non
# ============================================================

def test_localisation_utilise_voyage_pas_llm(orchestrateur, monkeypatch):
    faux_llm = FauxLLM()
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)
    orchestrateur.repository = FauxRepository([Ligne("Le surapprentissage survient quand...", page_debut=34)])

    resultat = run(orchestrateur.traiter_message("où est expliqué le surapprentissage ?", session_id="test-session"))

    assert resultat["type_reponse"] == "localisation"
    assert orchestrateur._faux_provider.appels >= 1
    assert faux_llm.appels <= 1  # localisation ne génère pas la réponse via LLM (suggestions dynamiques peuvent en faire 1)
    assert resultat["sources"][0]["page"] == 34


def test_localisation_mode_strict_si_rien_trouve(orchestrateur):
    orchestrateur.repository = FauxRepository([])  # aucun résultat
    resultat = run(orchestrateur.traiter_message("où est expliqué le surapprentissage ?", session_id="test-session"))
    assert "Aucun support ALTIORA" in resultat["reponse"]


# ============================================================
# QUESTION_FOND — Voyage oui, LLM oui, sourcé
# ============================================================

def test_question_fond_success(orchestrateur, monkeypatch):
    faux_llm = FauxLLM('{"reponse": "Le surapprentissage survient... [doc.pdf, p. 34]"}')
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)
    orchestrateur.repository = FauxRepository([Ligne("Extrait pertinent.", page_debut=34)])

    resultat = run(orchestrateur.traiter_message("qu'est-ce que le surapprentissage ?", session_id="test-session"))

    assert resultat["type_reponse"] == "question_fond"
    assert "[doc.pdf, p. 34]" in resultat["reponse"]
    assert faux_llm.appels >= 1  # 1 pour la réponse + 1 éventuel pour les suggestions dynamiques


def test_question_fond_mode_strict_si_rien_trouve(orchestrateur, monkeypatch):
    import app.orchestrator.chat_orchestrator as chat_module
    monkeypatch.setattr(chat_module.rcache, "depuis_cache", lambda *a, **kw: None)
    orchestrateur.repository = FauxRepository([])
    resultat = run(orchestrateur.traiter_message("qu'est-ce que le surapprentissage ?", session_id="test-session"))
    assert "Aucun support ALTIORA" in resultat["reponse"] or "Aucun extrait" in resultat["reponse"]


# ============================================================
# CONTENU_FORMATION — jamais Voyage, LLM oui, TOUS les supports
# ============================================================

def test_contenu_formation_utilise_tous_les_supports(orchestrateur, monkeypatch):
    faux_llm = FauxLLM()
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)

    for i, nom in enumerate(["support1.pptx", "support2.pdf", "support3.docx"]):
        registre.marquer_statut_special(f"h{i}", nom, "IA_FONDAMENTAUX", "indexe", "ok")
        e = registre.obtenir_entree(f"h{i}")
        e.resume = f"Résumé de {nom}"
        e.session_id = "test-session"
        registre.enregistrer_entree(e)

    resultat = run(orchestrateur.traiter_message(
        "donne moi le contenu de la formation IA fondamentaux", session_id="test-session",
    ))

    assert resultat["type_reponse"] == "contenu_formation"
    assert len(resultat["sources"]) == 3
    assert orchestrateur._faux_provider.appels == 0  # jamais Voyage
    assert resultat["formation_resolue"] == "IA_FONDAMENTAUX"


def test_contenu_formation_relance_garde_la_formation(orchestrateur):
    registre.marquer_statut_special("h1", "support1.pdf", "IA_FONDAMENTAUX", "indexe", "ok")
    e = registre.obtenir_entree("h1")
    e.resume = "Résumé."
    e.session_id = "test-session"
    registre.enregistrer_entree(e)

    premier = run(orchestrateur.traiter_message(
        "donne moi le contenu de la formation IA fondamentaux", conversation_id="conv-1",
        session_id="test-session",
    ))
    assert premier["formation_resolue"] == "IA_FONDAMENTAUX"

    # Relance sans nommer la formation : "et le module 2 ?" -> reste sur IA_FONDAMENTAUX
    second = run(orchestrateur.traiter_message(
        "et le contenu, donne le encore", conversation_id="conv-1",
        session_id="test-session",
    ))
    assert second["formation_resolue"] == "IA_FONDAMENTAUX"


def test_contenu_session_hors_catalogue_utilise_ses_supports(orchestrateur, monkeypatch):
    faux_llm = FauxLLM()
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)
    registre.marquer_statut_special("fid-hash", "support_fid.pdf", "FID-SESSION-2026", "indexe", "ok")
    entree = registre.obtenir_entree("fid-hash")
    entree.resume = "Résumé du support FID."
    entree.session_id = "session-fid"
    registre.enregistrer_entree(entree)

    def resolver_interdit(_message):
        raise AssertionError("La session sélectionnée ne doit pas dépendre du catalogue global.")

    monkeypatch.setattr(chat_module, "resoudre_formation", resolver_interdit)
    resultat = run(orchestrateur.traiter_message(
        "donne moi le resume du support actuel", session_id="session-fid",
    ))

    assert resultat["type_reponse"] == "contenu_formation"
    assert resultat["formation_resolue"] == "FID-SESSION-2026"
    assert resultat["sources"][0]["fichier"] == "support_fid.pdf"


def test_suggestions_chat_reprennent_les_modules_indexes_de_la_session():
    registre.marquer_statut_special("h-module1", "module1.pptx", "IA_FONDAMENTAUX", "indexe", "ok")
    entree = registre.obtenir_entree("h-module1")
    entree.session_id = "session-ia"
    entree.module = "MODULE 1 - Comprendre l’IA"
    registre.enregistrer_entree(entree)
    registre.marquer_statut_special("h-module2", "module2.pptx", "IA_FONDAMENTAUX", "indexe", "ok")
    entree = registre.obtenir_entree("h-module2")
    entree.session_id = "session-ia"
    entree.module = "MODULE 2 - Bases du prompting"
    registre.enregistrer_entree(entree)
    registre.marquer_statut_special("h-module3", "module3.pptx", "IA_FONDAMENTAUX", "indexe", "ok")
    entree = registre.obtenir_entree("h-module3")
    entree.session_id = "session-ia"
    entree.module = "MODULE 3 - Outils du quotidien"
    registre.enregistrer_entree(entree)

    suggestions = ChatOrchestrator._suggestions(
        "contenu_formation", session_id="session-ia", module="MODULE 1 - Comprendre l’IA",
    )

    assert suggestions == [
        "Résume le module « MODULE 2 - Bases du prompting »",
        "Quels exercices sont prévus dans « MODULE 2 - Bases du prompting » ?",
    ]
    suggestions_suivantes = ChatOrchestrator._suggestions(
        "synthese_thematique", session_id="session-ia", module="MODULE 2 - Bases du prompting",
    )
    assert suggestions_suivantes == [
        "Résume le module « MODULE 3 - Outils du quotidien »",
        "Quels exercices sont prévus dans « MODULE 3 - Outils du quotidien » ?",
    ]


def test_inventaire_session_inclut_support_sans_code_formation(orchestrateur):
    registre.marquer_statut_special("sans-code", "support_session.pdf", None, "indexe", "ok")
    entree = registre.obtenir_entree("sans-code")
    entree.session_id = "session-sans-code"
    entree.nb_chunks = 14
    registre.enregistrer_entree(entree)

    texte, sources = run(orchestrateur._repondre_inventaire(session_id="session-sans-code"))

    assert "support_session.pdf" in texte
    assert "Aucun support" not in texte
    assert sources == []


def test_synthese_dune_session_interroge_ses_supports_meme_sans_module(orchestrateur, monkeypatch):
    captured = {}

    async def fake_rechercher(*_args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(recherche, "rechercher", fake_rechercher)
    run(orchestrateur._repondre_synthese_thematique(
        "résume les supports", formation_code=None, session_id="session-ia", module=None,
    ))

    assert captured["collection"] == "support"
    assert captured["session_id"] == "session-ia"


def test_question_fond_reutilise_les_chunks_de_session_si_le_ranking_est_vide(orchestrateur, monkeypatch):
    contenu = "Le prompting structuré suit le cadre RTFCE : rôle, tâche, format, contexte et exemple."
    orchestrateur.repository.lister_chunks_session = lambda **kwargs: [
        {"contenu": contenu, "fichier": "module_prompting.pptx", "page_debut": 4,
         "formation_titre": "IA pour FID"}
    ]
    async def aucun_resultat(*_args, **_kwargs):
        return []
    monkeypatch.setattr(recherche, "rechercher", aucun_resultat)
    captured = {}
    async def reponse_sourcée(_prompt, contexte, **_kwargs):
        captured["contexte"] = contexte
        return {"reponse": "Question orale sur le cadre RTFCE [module_prompting.pptx, p. 4]."}
    monkeypatch.setattr(chat_module, "_appeler_llm_json", reponse_sourcée)

    texte, sources, _model, _cache = run(orchestrateur._repondre_question_fond(
        "Crée des exercices oraux à partir des supports", session_id="session-ia",
    ))

    assert "RTFCE" in captured["contexte"]
    assert "Question orale" in texte
    assert sources[0]["fichier"] == "module_prompting.pptx"


def test_question_module_utilise_ses_chunks_meme_si_voyage_renvoie_des_hits_hors_sujet(orchestrateur, monkeypatch):
    for hash_doc, fichier, module in (
        ("h-m1", "module1.pptx", "MODULE 1 - Comprendre l’IA"),
        ("h-m2", "module2.pptx", "MODULE 2 - Bases du prompting"),
    ):
        registre.marquer_statut_special(hash_doc, fichier, "IA_FONDAMENTAUX", "indexe", "ok")
        entree = registre.obtenir_entree(hash_doc)
        entree.session_id = "session-ia"
        entree.module = module
        registre.enregistrer_entree(entree)

    chunks = {
        "MODULE 1 - Comprendre l’IA": [{
            "contenu": "Atelier pratique : tester la fiabilité des réponses de l’IA.",
            "fichier": "module1.pptx", "page_debut": 6,
            "formation_titre": "IA pour FID", "module": "MODULE 1 - Comprendre l’IA",
        }],
        "MODULE 2 - Bases du prompting": [{
            "contenu": "Méthode RTFCE : rôle, tâche, format, contexte et exemple.",
            "fichier": "module2.pptx", "page_debut": 4,
            "formation_titre": "IA pour FID", "module": "MODULE 2 - Bases du prompting",
        }],
    }
    calls = []
    orchestrateur.repository.lister_chunks_session = lambda **kwargs: chunks[kwargs["module"]]

    async def recherche_hors_sujet(*_args, **_kwargs):
        calls.append("voyage")
        return [Ligne("Un passage générique sur les outils IA.", fichier="module2.pptx", page_debut=4)]

    captured = {}

    async def reponse_fondee(prompt, contexte, **_kwargs):
        captured.update(prompt=prompt, contexte=contexte)
        return {"reponse": "L’atelier consiste à tester la fiabilité des réponses de l’IA [module1.pptx, p. 6]."}

    monkeypatch.setattr(recherche, "rechercher", recherche_hors_sujet)
    monkeypatch.setattr(chat_module, "_appeler_llm_json", reponse_fondee)

    texte, sources, _modele, _cache = run(orchestrateur._repondre_question_fond(
        "Quels exercices sont prévus dans le module 1 ?", session_id="session-ia",
    ))

    assert "Atelier pratique" in captured["contexte"]
    assert "RTFCE" not in captured["contexte"]
    assert "voyage" not in calls
    assert captured["prompt"] == "reponse_question_fond.yaml"
    assert "atelier consiste" in texte.lower()
    assert sources[0]["fichier"] == "module1.pptx"


def test_synthese_module_ne_resume_pas_tous_les_modules(orchestrateur, monkeypatch):
    for hash_doc, fichier, module in (
        ("h-s1", "module1.pptx", "MODULE 1 - Comprendre l’IA"),
        ("h-s2", "module2.pptx", "MODULE 2 - Bases du prompting"),
    ):
        registre.marquer_statut_special(hash_doc, fichier, "IA_FONDAMENTAUX", "indexe", "ok")
        entree = registre.obtenir_entree(hash_doc)
        entree.session_id = "session-ia"
        entree.module = module
        registre.enregistrer_entree(entree)

    chunks = {
        "MODULE 1 - Comprendre l’IA": [{
            "contenu": "Le module présente les piliers de l’IA et un atelier pratique.",
            "fichier": "module1.pptx", "page_debut": 2,
            "formation_titre": "IA pour FID", "module": "MODULE 1 - Comprendre l’IA",
        }],
        "MODULE 2 - Bases du prompting": [{
            "contenu": "Le module détaille la méthode RTFCE.",
            "fichier": "module2.pptx", "page_debut": 3,
            "formation_titre": "IA pour FID", "module": "MODULE 2 - Bases du prompting",
        }],
    }
    orchestrateur.repository.lister_chunks_session = lambda **kwargs: chunks[kwargs["module"]]
    async def recherche_interdite(*_args, **_kwargs):
        raise AssertionError("Une synthèse d'un module précis doit utiliser ses chunks directs.")
    captured = {}
    async def reponse_fondee(prompt, contexte, **_kwargs):
        captured.update(prompt=prompt, contexte=contexte)
        return {"reponse": "Le module présente les piliers de l’IA [module1.pptx, p. 2]."}

    monkeypatch.setattr(recherche, "rechercher", recherche_interdite)
    monkeypatch.setattr(chat_module, "_appeler_llm_json", reponse_fondee)

    texte, sources, _modele, _cache = run(orchestrateur._repondre_synthese_thematique(
        "Résume le module 1", session_id="session-ia",
    ))

    assert "piliers de l’IA" in captured["contexte"]
    assert "RTFCE" not in captured["contexte"]
    assert captured["prompt"] == "reponse_question_fond.yaml"
    assert "piliers de l’IA" in texte
    assert sources[0]["fichier"] == "module1.pptx"


def test_route_synthese_direction_garde_la_session_selectionnee(orchestrateur, monkeypatch):
    captured = {}
    async def type_synthese(*_args, **_kwargs):
        return "synthese_thematique"
    async def reponse_synthese(message, conv, formation_code, session_id, module, allowed_session_ids, hide_references):
        captured.update(session_id=session_id, allowed_session_ids=allowed_session_ids)
        return "Résumé de la session.", [], None, False

    monkeypatch.setattr(chat_module, "detecter_type", type_synthese)
    monkeypatch.setattr(orchestrateur, "_repondre_synthese_thematique", reponse_synthese)

    run(orchestrateur.traiter_message(
        "résume les supports de cette session", session_id="session-direction",
        allowed_session_ids=None,
    ))

    assert captured == {"session_id": "session-direction", "allowed_session_ids": None}


def test_module_suivant_est_resolu_depuis_le_contexte_conversation(orchestrateur):
    for hash_doc, fichier, module in (
        ("h-next-1", "module1.pptx", "MODULE 1 - Comprendre l’IA"),
        ("h-next-2", "module2.pptx", "MODULE 2 - Bases du prompting"),
    ):
        registre.marquer_statut_special(hash_doc, fichier, "IA_FONDAMENTAUX", "indexe", "ok")
        entree = registre.obtenir_entree(hash_doc)
        entree.session_id = "session-ia"
        entree.module = module
        registre.enregistrer_entree(entree)
    conv = memoire.Conversation(conversation_id="conv-module")
    conv = memoire.ajouter_echange(
        conv, "utilisateur", "Résume le module 1", session_id="session-ia",
        module="MODULE 1 - Comprendre l’IA",
    )

    assert orchestrateur._module_demande(
        "Et le module suivant ?", "session-ia", None, conv,
    ) == "MODULE 2 - Bases du prompting"


def test_relance_pronominale_reprend_le_sujet_utilisateur_precedent():
    conv = memoire.Conversation(conversation_id="conv-pronom")
    conv = memoire.ajouter_echange(
        conv, "utilisateur", "Quelle est la différence entre IA et machine learning ?",
        session_id="session-ia",
    )
    assert "différence entre IA et machine learning" in ChatOrchestrator._requete_autonome(
        "Explique cela plus simplement", conv,
    )


def test_recherche_lexicale_de_session_precede_un_hit_vectoriel_non_pertinent(orchestrateur, monkeypatch):
    contenu = "La reconnaissance d’objets illustre le principe de l’apprentissage supervisé."
    orchestrateur.repository.lister_chunks_session = lambda **_kwargs: [{
        "contenu": contenu, "fichier": "module1.pptx", "page_debut": 3,
        "formation_titre": "IA pour FID", "module": "MODULE 1",
    }]
    async def recherche_interdite(*_args, **_kwargs):
        raise AssertionError("Un passage lexicalement pertinent doit éviter une recherche vectorielle hors sujet.")
    captured = {}
    async def reponse_sourcée(_prompt, contexte, **_kwargs):
        captured["contexte"] = contexte
        return {"reponse": "La reconnaissance d’objets illustre l’apprentissage supervisé [module1.pptx, diapo 3]."}
    monkeypatch.setattr(recherche, "rechercher", recherche_interdite)
    monkeypatch.setattr(chat_module, "_appeler_llm_json", reponse_sourcée)

    texte, sources, _modele, _cache = run(orchestrateur._repondre_question_fond(
        "Explique la reconnaissance d’objets", session_id="session-ia",
    ))

    assert "reconnaissance d’objets" in captured["contexte"]
    assert "apprentissage supervisé" in texte
    assert sources[0]["fichier"] == "module1.pptx"


def test_reponse_de_refus_ne_cache_pas_les_extraits_directs_trouves(orchestrateur, monkeypatch):
    contenu = "Le module présente les quatre piliers fonctionnels : percevoir, analyser, générer et assister."
    orchestrateur.repository.lister_chunks_session = lambda **_kwargs: [{
        "contenu": contenu, "fichier": "module1.pptx", "page_debut": 2,
        "formation_titre": "IA pour FID", "module": "MODULE 1",
    }]
    async def reponse_erronée(*_args, **_kwargs):
        return {"reponse": "Aucun support ALTIORA ne traite ce sujet."}
    monkeypatch.setattr(chat_module, "_appeler_llm_json", reponse_erronée)

    texte, sources, _modele, _cache = run(orchestrateur._repondre_question_fond(
        "Quels sont les piliers fonctionnels ?", session_id="session-ia",
    ))

    assert "passages indexés" in texte
    assert "Aucun support" not in texte
    assert sources[0]["fichier"] == "module1.pptx"


def test_repli_llm_presente_plusieurs_passages_indexes_avec_leurs_sources():
    chunks = [
        Ligne("Le module présente l’intelligence artificielle et ses usages.", fichier="module4.pptx", page_debut=1),
        Ligne("Il insiste sur la vérification humaine des réponses générées.", fichier="module4.pptx", page_debut=6),
    ]

    texte = ChatOrchestrator._reponse_brute_depuis_chunks(chunks)

    assert "synthèse fiable" in texte
    assert "l’intelligence artificielle et ses usages" in texte
    assert "vérification humaine des réponses" in texte
    assert "module4.pptx, diapo 1" in texte
    assert "module4.pptx, diapo 6" in texte


# ============================================================
# AIDE_PLATEFORME — mode strict tant que rien n'est indexé (Étape F pas encore faite)
# ============================================================

def test_aide_plateforme_mode_strict_avant_etape_f(orchestrateur):
    orchestrateur.repository = FauxRepository([])  # collection aide_plateforme vide
    resultat = run(orchestrateur.traiter_message("comment valider une relance de facture ?"))
    assert resultat["type_reponse"] == "aide_plateforme"
    # Sans RAG, le LLM répond avec le contexte plateforme (plus de mode strict pur)
    assert resultat["reponse"] != ""


# ============================================================
# HORS_SUJET — mode strict, jamais Voyage ni LLM
# ============================================================

def test_hors_sujet(orchestrateur, monkeypatch):
    faux_llm = FauxLLM()
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)
    monkeypatch.setattr(detection, "detecter_type_regles", lambda m: "hors_sujet")

    resultat = run(orchestrateur.traiter_message("qu'est-ce que la blockchain ?"))

    assert resultat["type_reponse"] == "hors_sujet"
    assert "Aucun support ALTIORA" in resultat["reponse"]
    assert orchestrateur._faux_provider.appels == 0
    assert faux_llm.appels == 0


# ============================================================
# JOURNAL — écrit à chaque message
# ============================================================

def test_journal_ecrit(orchestrateur, tmp_path):
    run(orchestrateur.traiter_message("bonjour"))

    lignes = journal.lire_toutes_les_lignes(tmp_path / "chat_logs.jsonl")
    assert len(lignes) == 1
    assert lignes[0]["type_detecte"] == "conversationnel"


# ============================================================
# MÉMOIRE — conversation_id généré, réutilisable
# ============================================================

def test_conversation_id_genere_et_reutilisable(orchestrateur):
    premier = run(orchestrateur.traiter_message("bonjour"))
    assert premier["conversation_id"]

    second = run(orchestrateur.traiter_message("merci", conversation_id=premier["conversation_id"]))
    assert second["conversation_id"] == premier["conversation_id"]
