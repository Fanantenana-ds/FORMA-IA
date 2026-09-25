# ============================================================
# TESTS — app/services/rag/recherche_service.py + query_cache_service.py
# (Étape D)
# ============================================================
# Aucun réseau (faux fournisseur d'embeddings), aucune vraie base (faux
# dépôt en mémoire), cache redirigé vers un fichier temporaire.
# ============================================================

import asyncio

import pytest

from app.services.rag import query_cache_service as cache
from app.services.rag import recherche_service as recherche
from app.services.rag.knowledge_repository import KnowledgeRepository


def run(coro):
    return asyncio.run(coro)


# ============================================================
# query_cache_service
# ============================================================

def test_normaliser_texte():
    assert cache.normaliser_texte("  Quels   SONT   les Fondamentaux  ?  ") == "quels sont les fondamentaux ?"


def test_cache_miss_puis_hit(tmp_path):
    chemin = tmp_path / "cache.json"
    assert cache.depuis_cache("une question", "voyage-4-large", chemin) is None

    cache.mettre_en_cache("une question", "voyage-4-large", [0.1, 0.2], chemin)

    assert cache.depuis_cache("une question", "voyage-4-large", chemin) == [0.1, 0.2]


def test_cache_insensible_a_la_casse_et_aux_espaces(tmp_path):
    chemin = tmp_path / "cache.json"
    cache.mettre_en_cache("Une Question   ", "voyage-4-large", [0.1], chemin)

    assert cache.depuis_cache("une   question", "voyage-4-large", chemin) == [0.1]


def test_cache_distingue_les_modeles(tmp_path):
    chemin = tmp_path / "cache.json"
    cache.mettre_en_cache("texte", "voyage-4-large", [0.1], chemin)

    assert cache.depuis_cache("texte", "voyage-4", chemin) is None


def test_obtenir_ou_calculer_hit_n_appelle_pas_voyage(tmp_path):
    chemin = tmp_path / "cache.json"
    cache.mettre_en_cache("texte", "voyage-4-large", [0.9], chemin)

    appels = {"n": 0}

    async def faux_embed(texte, **kw):
        appels["n"] += 1
        return [0.0]

    resultat = run(cache.obtenir_ou_calculer("texte", "voyage-4-large", faux_embed, chemin))

    assert resultat == [0.9]
    assert appels["n"] == 0


def test_obtenir_ou_calculer_miss_appelle_et_met_en_cache(tmp_path):
    chemin = tmp_path / "cache.json"
    appels = {"n": 0}

    async def faux_embed(texte, **kw):
        appels["n"] += 1
        return [0.5, 0.5]

    resultat = run(cache.obtenir_ou_calculer("nouvelle question", "voyage-4-large", faux_embed, chemin))

    assert resultat == [0.5, 0.5]
    assert appels["n"] == 1
    assert cache.depuis_cache("nouvelle question", "voyage-4-large", chemin) == [0.5, 0.5]


def test_taille_cache(tmp_path):
    chemin = tmp_path / "cache.json"
    assert cache.taille_cache(chemin) == 0
    cache.mettre_en_cache("a", "voyage-4-large", [0.1], chemin)
    cache.mettre_en_cache("b", "voyage-4-large", [0.2], chemin)
    assert cache.taille_cache(chemin) == 2


# ============================================================
# recherche_service — compatibilité de modèle
# ============================================================

class FauxRepositoryVide:
    def modeles_presents(self, collection=None):
        return []


class FauxRepositoryModele:
    def __init__(self, modeles):
        self._modeles = modeles

    def modeles_presents(self, collection=None):
        return self._modeles

    def rechercher_par_similarite(self, vecteur, collection, top_k, **filtres):
        return []


def test_verifier_compatibilite_base_vide_ne_leve_rien():
    recherche.verifier_compatibilite_avec_base("voyage-4-large", "support", FauxRepositoryVide())


def test_verifier_compatibilite_meme_famille_ok():
    recherche.verifier_compatibilite_avec_base("voyage-4", "support", FauxRepositoryModele(["voyage-4-large"]))


def test_verifier_compatibilite_famille_differente_refuse():
    with pytest.raises(recherche.IncompatibiliteModeleError):
        recherche.verifier_compatibilite_avec_base(
            "voyage-4-large", "support", FauxRepositoryModele(["un-modele-totalement-different"])
        )


# ============================================================
# recherche_service.rechercher() — bout en bout avec des faux
# ============================================================

class Ligne:
    def __init__(self, contenu, fichier="doc.pdf", formation_code="IA_FONDAMENTAUX",
                 formation_titre="IA", collection="support", page_debut=1, page_fin=1, type_support="pdf"):
        self.contenu = contenu
        self.fichier = fichier
        self.formation_code = formation_code
        self.formation_titre = formation_titre
        self.collection = collection
        self.page_debut = page_debut
        self.page_fin = page_fin
        self.type_support = type_support
        self.modele_embed = "voyage-4-large"


class FauxRepositoryRecherche:
    def __init__(self, resultats):
        self._resultats = resultats  # [(Ligne, distance)]
        self.derniers_filtres = None

    def modeles_presents(self, collection=None):
        return ["voyage-4-large"] if self._resultats else []

    def rechercher_par_similarite(self, vecteur, collection, top_k, **filtres):
        self.derniers_filtres = {"collection": collection, "top_k": top_k, **filtres}
        return self._resultats[:top_k]


@pytest.fixture(autouse=True)
def isole_embedding_provider(monkeypatch, tmp_path):
    class FauxProvider:
        modele_requete = "voyage-4-large"
        modele_document = "voyage-4-large"

        async def embed_query(self, texte, **kw):
            return [0.5, 0.5]

    monkeypatch.setattr(recherche, "get_embedding_provider", lambda: FauxProvider())
    monkeypatch.setattr(recherche, "CHEMIN_CACHE_DEFAUT", tmp_path / "cache.json")


def test_rechercher_filtre_par_seuil():
    resultats_bruts = [(Ligne("Contenu pertinent"), 0.1), (Ligne("Contenu peu pertinent"), 0.7)]
    repo = FauxRepositoryRecherche(resultats_bruts)

    resultats = run(recherche.rechercher("question", seuil_min=0.5, repository=repo))

    assert len(resultats) == 1
    assert resultats[0].contenu == "Contenu pertinent"
    assert resultats[0].score == pytest.approx(0.9)  # 1 - 0.1


def test_rechercher_aucun_resultat_au_dessus_du_seuil():
    resultats_bruts = [(Ligne("x"), 0.9)]  # score = 0.1, sous le seuil
    repo = FauxRepositoryRecherche(resultats_bruts)

    resultats = run(recherche.rechercher("question", seuil_min=0.5, repository=repo))

    assert resultats == []


def test_rechercher_transmet_les_filtres():
    repo = FauxRepositoryRecherche([])

    run(recherche.rechercher(
        "question", collection="support", formation_code="IA_FONDAMENTAUX",
        domaine="IA", annee=2026, type_support="pdf", top_k=3, repository=repo,
    ))

    assert repo.derniers_filtres == {
        "collection": "support", "top_k": 3, "formation_code": "IA_FONDAMENTAUX",
        "domaine": "IA", "annee": 2026, "type_support": "pdf",
    }


def test_rechercher_incompatibilite_modele_refuse():
    repo = FauxRepositoryModele(["une-autre-famille"])

    with pytest.raises(recherche.IncompatibiliteModeleError):
        run(recherche.rechercher("question", repository=repo))
