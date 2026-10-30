"""Tests sans réseau de l'orchestration vocal → RAG / actions métier."""

import asyncio

import app.services.vocal.assistant_vocal_service as module


def run(coro):
    return asyncio.run(coro)


def test_synthese_vocale_nettoie_markdown_et_reste_courte():
    resultat = module._voix_courte(
        "Pour exploiter **FORMA-IA**, commencez par la [Veille](https://example.test). "
        "Ensuite, préparez un *TDR* et une offre. Enfin, ce détail reste affiché à l'écran."
    )

    assert "*" not in resultat
    assert "https://" not in resultat
    assert "Enfin" not in resultat
    assert len(resultat) <= 260


class FauxRag:
    async def traiter_message(self, question, conversation_id=None):
        return {
            "conversation_id": conversation_id or "conv-test",
            "reponse": "La recherche vectorielle retrouve les passages les plus proches.",
            "sources": [{"fichier": "support-rag.pdf", "page": 4, "score": 0.91}],
            "suggestions": ["Donne un exemple"],
        }


def test_question_rag_reutilise_c3_et_restitue_les_sources(monkeypatch):
    async def routeur(*args, **kwargs):
        return {
            "intention": "question_rag", "confiance": 0.95, "parametres": {},
            "parametres_manquants": [], "reponse_vocale": "Je recherche dans les supports.",
            "action_frontend": "ouvrir_chat_rag", "prefill": {},
        }

    monkeypatch.setattr(module, "router_commande", routeur)
    monkeypatch.setattr(module, "get_chat_orchestrator", lambda: FauxRag())

    resultat = run(module.AssistantVocalService().traiter("Explique la recherche vectorielle", conversation_id="conv-1"))

    assert resultat["etat"] == "reponse_sourcee"
    assert resultat["conversation_id"] == "conv-1"
    assert resultat["sources"][0]["page"] == 4
    assert resultat["action_frontend"] == "ouvrir_chat_rag"
    assert "sources sont affichées" in resultat["texte_a_lire"]


def test_action_complete_transmet_commande_sans_fausse_confirmation(monkeypatch):
    async def routeur(*args, **kwargs):
        return {
            "intention": "creer_seance", "confiance": 0.93,
            "parametres": {"nom_formation": "Python", "date": "2026-10-29"},
            "parametres_manquants": [], "reponse_vocale": "Je prépare le formulaire.",
            "action_frontend": "ouvrir_formulaire_seance",
            "prefill": {"intitule": "Python", "dates": "2026-10-29"},
        }

    monkeypatch.setattr(module, "router_commande", routeur)
    resultat = run(module.AssistantVocalService().traiter("Crée une séance Python jeudi"))

    assert resultat["etat"] == "action_a_executer"
    assert resultat["action_frontend"] == "ouvrir_formulaire_seance"
    assert resultat["execution_demandee"] is True
    assert "créée" not in resultat["texte_a_lire"]


def test_faible_confiance_demande_reformulation(monkeypatch):
    async def routeur(*args, **kwargs):
        return {
            "intention": "creer_seance", "confiance": 0.32, "parametres": {},
            "parametres_manquants": [], "reponse_vocale": "", "action_frontend": "ouvrir_formulaire_seance",
            "prefill": {},
        }

    monkeypatch.setattr(module, "router_commande", routeur)
    resultat = run(module.AssistantVocalService().traiter("crée une..."))

    assert resultat["etat"] == "a_preciser"
    assert resultat["action_frontend"] is None


def test_aide_plateforme_est_distinguee_d_une_reponse_rag_non_sourcee(monkeypatch):
    async def routeur(*args, **kwargs):
        return {
            "intention": "question_rag", "confiance": 0.96, "parametres": {},
            "parametres_manquants": [], "reponse_vocale": "", "action_frontend": "ouvrir_chat_rag", "prefill": {},
        }

    class FauxGuide:
        async def traiter_message(self, question, conversation_id=None):
            return {
                "conversation_id": "conv-guide", "type_reponse": "aide_plateforme",
                "reponse": "Commencez par la veille, puis préparez le TDR.", "sources": [], "suggestions": [],
            }

    monkeypatch.setattr(module, "router_commande", routeur)
    monkeypatch.setattr(module, "get_chat_orchestrator", lambda: FauxGuide())
    resultat = run(module.AssistantVocalService().traiter("Comment utiliser cette plateforme ?"))

    assert resultat["etat"] == "reponse_plateforme"
    assert resultat["niveau_preuve"] == "connaissance_plateforme"
    assert "Commencez par la veille" in resultat["texte_affiche"]


def test_voix_ignore_code_et_tableaux():
    assert module._voix_courte("Voici le résultat.\n| Colonne | Valeur |\n```python\nsecret = 1\n```") == "Voici le résultat."


def test_precision_reprend_demande_en_cours(monkeypatch):
    seen=[]
    async def router(command, formations):
        seen.append(command)
        return {"intention":"creer_session","confiance":0.95,"parametres":{"nom_formation":"Python","date":"2026-11-05"},"parametres_manquants":[],"prefill":{},"reponse_vocale":"Vérification"}
    monkeypatch.setattr(module,"router_commande",router)
    result=run(module.AssistantVocalService().traiter("Le 5 novembre",contexte_action=["Crée une session Python"]))
    assert "Crée une session Python" in seen[0]
    assert "Le 5 novembre" in seen[0]
    assert result["prefill"]["date"]=="2026-11-05"
    assert result["action_frontend"]=="ouvrir_formulaire_session"


def test_veille_prepare_execution_et_pas_un_resultat_invente(monkeypatch):
    async def router(*args):
        return {"intention":"veille_marche","confiance":1,"parametres":{},"parametres_manquants":[],"prefill":{},"action_frontend":"lancer_veille","reponse_vocale":"Recherche"}
    monkeypatch.setattr(module,"router_commande",router)
    result=run(module.AssistantVocalService().traiter("Lance la veille"))
    assert result["execution_demandee"] is True
    assert result["action_frontend"]=="lancer_veille"
    assert "terminée" not in result["texte_affiche"]


def test_procedure_precise_non_sourcee_ne_devient_pas_guide_generique(monkeypatch):
    async def router(*args):
        return {"intention":"question_rag","confiance":1,"parametres":{},"parametres_manquants":[],"prefill":{},"reponse_vocale":""}
    class Chat:
        async def traiter_message(self,*args,**kwargs):
            return {"reponse":"Réponse inventée à ne pas diffuser","type_reponse":"aide_plateforme","sources":[]}
    monkeypatch.setattr(module,"router_commande",router)
    monkeypatch.setattr(module,"get_chat_orchestrator",lambda:Chat())
    result=run(module.AssistantVocalService().traiter("Comment valider les TDR ?"))
    assert result["etat"]=="reponse_sans_source"
    assert "inventée" not in result["texte_affiche"]
