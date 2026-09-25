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
from app.services.rag import catalogue_service as catalogue
from app.services.rag import registry_service as registre
from app.services.rag import conversation_service as memoire
from app.services.rag import chat_log_service as journal
from app.services.rag import recherche_service as recherche
from app.services.rag import type_detection_service as detection
from app.services.llm import LLMNotAvailableError

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

    resultat = run(orchestrateur.traiter_message("où est expliqué le surapprentissage ?"))

    assert resultat["type_reponse"] == "localisation"
    assert orchestrateur._faux_provider.appels >= 1
    assert faux_llm.appels == 0  # localisation n'appelle jamais le LLM
    assert resultat["sources"][0]["page"] == 34


def test_localisation_mode_strict_si_rien_trouve(orchestrateur):
    orchestrateur.repository = FauxRepository([])  # aucun résultat
    resultat = run(orchestrateur.traiter_message("où est expliqué le surapprentissage ?"))
    assert "Aucun support ALTIORA" in resultat["reponse"]


# ============================================================
# QUESTION_FOND — Voyage oui, LLM oui, sourcé
# ============================================================

def test_question_fond_success(orchestrateur, monkeypatch):
    faux_llm = FauxLLM('{"reponse": "Le surapprentissage survient... [doc.pdf, p. 34]"}')
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: faux_llm)
    orchestrateur.repository = FauxRepository([Ligne("Extrait pertinent.", page_debut=34)])

    resultat = run(orchestrateur.traiter_message("qu'est-ce que le surapprentissage ?"))

    assert resultat["type_reponse"] == "question_fond"
    assert "[doc.pdf, p. 34]" in resultat["reponse"]
    assert faux_llm.appels == 1


def test_question_fond_mode_strict_si_rien_trouve(orchestrateur):
    orchestrateur.repository = FauxRepository([])
    resultat = run(orchestrateur.traiter_message("qu'est-ce que le surapprentissage ?"))
    assert "Aucun support ALTIORA" in resultat["reponse"]


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
        registre.enregistrer_entree(e)

    resultat = run(orchestrateur.traiter_message("donne moi le contenu de la formation IA fondamentaux"))

    assert resultat["type_reponse"] == "contenu_formation"
    assert len(resultat["sources"]) == 3
    assert orchestrateur._faux_provider.appels == 0  # jamais Voyage
    assert resultat["formation_resolue"] == "IA_FONDAMENTAUX"


def test_contenu_formation_relance_garde_la_formation(orchestrateur):
    registre.marquer_statut_special("h1", "support1.pdf", "IA_FONDAMENTAUX", "indexe", "ok")
    e = registre.obtenir_entree("h1")
    e.resume = "Résumé."
    registre.enregistrer_entree(e)

    premier = run(orchestrateur.traiter_message(
        "donne moi le contenu de la formation IA fondamentaux", conversation_id="conv-1",
    ))
    assert premier["formation_resolue"] == "IA_FONDAMENTAUX"

    # Relance sans nommer la formation : "et le module 2 ?" -> reste sur IA_FONDAMENTAUX
    second = run(orchestrateur.traiter_message(
        "et le contenu, donne le encore", conversation_id="conv-1",
    ))
    assert second["formation_resolue"] == "IA_FONDAMENTAUX"


# ============================================================
# AIDE_PLATEFORME — mode strict tant que rien n'est indexé (Étape F pas encore faite)
# ============================================================

def test_aide_plateforme_mode_strict_avant_etape_f(orchestrateur):
    orchestrateur.repository = FauxRepository([])  # collection aide_plateforme vide
    resultat = run(orchestrateur.traiter_message("comment valider une relance de facture ?"))
    assert resultat["type_reponse"] == "aide_plateforme"
    assert "Aucun support ALTIORA" in resultat["reponse"]


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
