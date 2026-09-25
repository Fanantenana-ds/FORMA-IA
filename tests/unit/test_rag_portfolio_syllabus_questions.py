# ============================================================
# TESTS — Étape G (portfolio, syllabus, questions)
# ============================================================
# Aucun réseau (faux LLM + faux fournisseur d'embeddings), aucune vraie
# base (faux dépôt), catalogue/HITL/registre redirigés vers tmp_path.
# ============================================================

import asyncio

import pytest

from app.services.rag import portfolio_service, syllabus_service
from app.services.rag.catalogue_service import Formation, Realisation
import app.orchestrator.rag_orchestrator as rag_orch_module
import app.services.rag.recherche_service as recherche_service_module
from app.orchestrator.rag_orchestrator import RagOrchestrator
from app.services.hitl import hitl_helper
from app.services.backend_sync import review_sync
from app.services.rag import catalogue_service as catalogue
from app.services.rag import registry_service as registre


def run(coro):
    return asyncio.run(coro)


# ============================================================
# PORTFOLIO — totaux Python purs (jamais touchés par le LLM)
# ============================================================

def _formation_test():
    return Formation(
        code="IA_FONDAMENTAUX", titre="IA Fondamentaux", domaine="IA", duree_jours=3,
        realisations=[
            Realisation(client="Ministère X", client_confidentiel=True, secteur_public="Administration", annee=2025, participants=18, attestation_bonne_execution=True),
            Realisation(client="Entreprise Y", client_confidentiel=False, annee=2026, participants=12, attestation_bonne_execution=False),
        ],
    )


def test_calculer_synthese_chiffree_totaux_exacts():
    synthese = portfolio_service.calculer_synthese_chiffree([_formation_test()])

    assert synthese["nb_formations_realisees"] == 2
    assert synthese["nb_participants_total"] == 30  # 18 + 12, jamais approximé
    assert synthese["nb_clients_distincts"] == 2
    assert synthese["periode_debut"] == 2025
    assert synthese["periode_fin"] == 2026


def test_tableau_recapitulatif_client_confidentiel_masque():
    tableau = portfolio_service.tableau_recapitulatif([_formation_test()])

    assert tableau[0]["client"] == "Administration"  # secteur, pas le nom réel
    assert tableau[1]["client"] == "Entreprise Y"


def test_lire_presentation_altiora_fichier_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio_service, "CHEMIN_PRESENTATION_ALTIORA", tmp_path / "n_existe_pas.yaml")
    assert portfolio_service.lire_presentation_altiora() == portfolio_service.TEXTE_A_COMPLETER_ALTIORA


def test_lire_presentation_altiora_fichier_present(tmp_path, monkeypatch):
    chemin = tmp_path / "presentation.yaml"
    chemin.write_text("presentation: |\n  ALTIORA PREST est un cabinet de formation.\n", encoding="utf-8")
    monkeypatch.setattr(portfolio_service, "CHEMIN_PRESENTATION_ALTIORA", chemin)
    assert "cabinet de formation" in portfolio_service.lire_presentation_altiora()


# ============================================================
# SYLLABUS — somme des durées vérifiée en Python
# ============================================================

def test_verifier_somme_durees_conforme():
    modules = [{"titre": "M1", "duree": "3h"}, {"titre": "M2", "duree": "4h"}]
    conforme, message = syllabus_service.verifier_somme_durees(modules, duree_totale_annoncee_jours=1)
    assert conforme is True
    assert "Conforme" in message


def test_verifier_somme_durees_ecart_detecte():
    modules = [{"titre": "M1", "duree": "2h"}]  # 2h vs 7h annoncées (1 jour)
    conforme, message = syllabus_service.verifier_somme_durees(modules, duree_totale_annoncee_jours=1)
    assert conforme is False
    assert "Écart détecté" in message


def test_verifier_somme_durees_en_jours():
    modules = [{"titre": "M1", "duree": "1 jour"}, {"titre": "M2", "duree": "2 jours"}]
    conforme, message = syllabus_service.verifier_somme_durees(modules, duree_totale_annoncee_jours=3)
    assert conforme is True


def test_verifier_somme_durees_non_reconnue_signalee():
    modules = [{"titre": "M1", "duree": "durée à préciser"}]
    conforme, message = syllabus_service.verifier_somme_durees(modules, duree_totale_annoncee_jours=1)
    assert conforme is False
    assert "M1" in message


# ============================================================
# ORCHESTRATEUR — intégration (portfolio/syllabus/questions)
# ============================================================

CATALOGUE_TEST = """
formations:
  - code: IA_FONDAMENTAUX
    titre: "Intelligence artificielle : les fondamentaux"
    domaine: "Intelligence artificielle"
    duree_jours: 2
    confidentiel: false
    realisations:
      - client: "Ministère X"
        client_confidentiel: true
        secteur_public: "Administration publique"
        annee: 2025
        participants: 18
        attestation_bonne_execution: true
"""


class FauxEmbeddingProvider:
    def __init__(self):
        self.modele_requete = "voyage-4-large"
        self.modele_document = "voyage-4-large"

    async def embed_query(self, texte, **kw):
        return [0.5] * 1024

    async def embed_documents(self, textes):
        return [[0.5] * 1024 for _ in textes]

    class config:
        tpm = 10_000


class FauxRepository:
    def modeles_presents(self, collection=None):
        return []

    def rechercher_par_similarite(self, vecteur, collection, top_k, **filtres):
        return []


@pytest.fixture
def chemin_catalogue(tmp_path):
    chemin = tmp_path / "catalogue.yaml"
    chemin.write_text(CATALOGUE_TEST, encoding="utf-8")
    return chemin


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path, chemin_catalogue):
    monkeypatch.setattr(catalogue, "CHEMIN_CATALOGUE_DEFAUT", chemin_catalogue)
    monkeypatch.setattr(rag_orch_module, "obtenir_formation", lambda code: catalogue.obtenir_formation(code, chemin_catalogue))
    monkeypatch.setattr(rag_orch_module, "charger_catalogue", lambda: catalogue.charger_catalogue(chemin_catalogue))
    monkeypatch.setattr(hitl_helper, "STORAGE_PATH", tmp_path / "hitl_reviews.json")
    monkeypatch.setattr(review_sync, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(registre, "CHEMIN_REGISTRE_DEFAUT", tmp_path / "index_registry.json")
    monkeypatch.setattr(rag_orch_module, "get_embedding_provider", lambda: FauxEmbeddingProvider())
    # recherche_service a sa PROPRE référence importée (from ... import
    # get_embedding_provider) : patcher rag_orch_module ne suffit pas, sinon
    # generer_fiche_reference/generer_contenu_pedagogique/generer_questions
    # (qui appellent recherche.rechercher()) déclencheraient un VRAI appel
    # réseau Voyage via le provider réel.
    monkeypatch.setattr(recherche_service_module, "get_embedding_provider", lambda: FauxEmbeddingProvider())
    monkeypatch.setattr(recherche_service_module, "CHEMIN_CACHE_DEFAUT", tmp_path / "query_cache.json")

    # Pas de LLM par défaut -> gabarits "[À compléter]", pas de plantage
    async def pas_de_llm(nom_prompt, contenu, max_tokens=2000):
        return None
    monkeypatch.setattr(rag_orch_module, "appeler_llm_json", pas_de_llm)


@pytest.fixture
def orchestrateur():
    return RagOrchestrator(repository=FauxRepository())


def test_generer_portfolio_cree_un_review_hitl(orchestrateur):
    resultat = run(orchestrateur.generer_portfolio())

    assert resultat["success"] is True
    assert resultat["_review_status"] == "pending_review"
    assert resultat["synthese_chiffree"]["nb_participants_total"] == 18
    assert resultat["presentation_altiora"] == portfolio_service.TEXTE_A_COMPLETER_ALTIORA


def test_generer_portfolio_llm_indisponible_donne_a_completer(orchestrateur):
    resultat = run(orchestrateur.generer_portfolio())
    fiche = resultat["fiches_reference"][0]
    assert fiche["objectifs"] == portfolio_service.TEXTE_A_COMPLETER
    assert fiche["contenus_cles"] == []


def test_exporter_portfolio_refuse_sans_approbation(orchestrateur):
    resultat = run(orchestrateur.generer_portfolio())
    with pytest.raises(ValueError, match="approuvé"):
        run(orchestrateur.exporter_portfolio(resultat["_review_id"]))


def test_exporter_portfolio_apres_approbation(orchestrateur, tmp_path, monkeypatch):
    from app.services.rag import rag_document_generator
    monkeypatch.setattr(rag_document_generator, "EXPORTS_DIR", tmp_path / "exports")

    resultat = run(orchestrateur.generer_portfolio())
    hitl_helper.approve_review(resultat["_review_id"])

    export = run(orchestrateur.exporter_portfolio(resultat["_review_id"]))

    assert export["success"] is True
    assert (tmp_path / "exports" / f"portfolio_{resultat['_review_id']}.docx").exists()


def test_generer_syllabus_verifie_les_durees_conforme(orchestrateur):
    # IA_FONDAMENTAUX dure 2 jours (catalogue de test) = 14h (2 x 7h/jour).
    modules = [{"titre": "Jour 1", "duree": "7h"}, {"titre": "Jour 2", "duree": "7h"}]
    resultat = run(orchestrateur.generer_syllabus("IA_FONDAMENTAUX", modules))

    assert resultat["success"] is True
    assert resultat["verification_durees_conforme"] is True
    assert resultat["_review_status"] == "pending_review"


def test_generer_syllabus_verifie_les_durees_ecart_signale_mais_pas_bloquant(orchestrateur):
    # 7h de programme vs 14h annoncées (2 jours) -> écart signalé, mais le
    # syllabus est quand même généré (le review HITL porte l'alerte).
    modules = [{"titre": "Introduction", "duree": "3h"}, {"titre": "Pratique", "duree": "4h"}]
    resultat = run(orchestrateur.generer_syllabus("IA_FONDAMENTAUX", modules))

    assert resultat["success"] is True
    assert resultat["verification_durees_conforme"] is False
    assert "Écart détecté" in resultat["verification_durees_message"]


def test_generer_syllabus_formation_introuvable(orchestrateur):
    with pytest.raises(ValueError, match="introuvable"):
        run(orchestrateur.generer_syllabus("INCONNUE", [{"titre": "x", "duree": "1h"}]))


def test_exporter_syllabus_refuse_sans_approbation(orchestrateur):
    resultat = run(orchestrateur.generer_syllabus("IA_FONDAMENTAUX", [{"titre": "M1", "duree": "1h"}]))
    with pytest.raises(ValueError, match="approuvé"):
        run(orchestrateur.exporter_syllabus(resultat["_review_id"]))


def test_exporter_syllabus_apres_approbation(orchestrateur, tmp_path, monkeypatch):
    from app.services.rag import rag_document_generator
    monkeypatch.setattr(rag_document_generator, "EXPORTS_DIR", tmp_path / "exports")

    resultat = run(orchestrateur.generer_syllabus("IA_FONDAMENTAUX", [{"titre": "M1", "duree": "1h"}]))
    hitl_helper.approve_review(resultat["_review_id"])

    export = run(orchestrateur.exporter_syllabus(resultat["_review_id"]))

    assert export["success"] is True
    assert (tmp_path / "exports" / f"syllabus_{resultat['_review_id']}.docx").exists()


def test_generer_questions_aucun_hitl(orchestrateur):
    resultat = run(orchestrateur.generer_questions("IA_FONDAMENTAUX"))

    assert resultat["success"] is True
    assert "_review_id" not in resultat  # pas de HITL (mission, usage interne)
    assert resultat["questions"] == []  # aucun contenu indexé (FauxRepository vide)


def test_generer_questions_formation_introuvable(orchestrateur):
    with pytest.raises(ValueError, match="introuvable"):
        run(orchestrateur.generer_questions("INCONNUE"))
