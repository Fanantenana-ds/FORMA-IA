import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.v1.endpoints import rag_ia
from app.services import hitl
from app.services.veille import result_context_service as context
from app.services.vocal import business_context_service as business


@pytest.fixture(autouse=True)
def clear_context():
    context._results.clear()
    yield
    context._results.clear()


def test_resultats_m1_sont_isoles_par_compte_et_copies():
    context.remember('user-a', {'status':'partial','opportunities':[{'title':'Formation IA','url':'https://example.org','score':52}], 'pending_sources':[{'url':'https://other.org'}]})
    assert context.latest('user-b') is None
    result=context.latest('user-a'); result['opportunities'].clear()
    assert len(context.latest('user-a')['opportunities'])==1
    context._results['user-a']=(0,result)
    assert context.latest('user-a') is None


def test_explication_m1_utilise_bilan_reel_et_reponse_orale_distincte(monkeypatch):
    context.remember('user-a', {'status':'partial','opportunities':[{'title':'Formation IA','url':'https://example.org','score':52}], 'pending_sources':[{'url':'https://other.org'}]})
    generate=AsyncMock(return_value={'content':'{"texte_affiche":"Le score connu est 52/100. Analyse partielle.","texte_a_lire":"Cette piste mérite une vérification. L’analyse reste partielle."}'})
    monkeypatch.setattr(business,'get_llm_provider',lambda:type('Provider',(),{'generate':generate})())
    result=asyncio.run(business.explain_market('Explique ces opportunités','user-a'))
    assert result['sources'][0]['url']=='https://example.org'
    assert result['texte_a_lire']!=result['texte_affiche']
    assert '52' in generate.call_args.kwargs['user_prompt']
    assert 'nombre_sources_restantes' in generate.call_args.kwargs['user_prompt']


def test_pas_de_bilan_n_est_pas_une_reponse_inventee():
    result=asyncio.run(business.explain_market('Explique ces opportunités','unknown-user'))
    assert result['sources']==[]
    assert result['niveau_preuve']=='sans_source'


def test_routage_contexte_ecran_et_question_documentaire():
    assert business.concerns_market_results('Explique les opportunités trouvées',None)
    assert business.concerns_market_results('Pourquoi ce score est faible ?','veille_marche')
    assert not business.concerns_market_results('Explique les marchés dans ce document','base_connaissances')
    assert not business.concerns_market_results('Lance la veille marché','veille_marche')


def test_histoire_c3_ne_donne_pas_acces_aux_reviews_autres_agents(monkeypatch):
    monkeypatch.setattr(hitl,'get_review',lambda _: {'agent_id':'agent_m2_tdr'})
    approve=Mock(); monkeypatch.setattr(hitl,'approve_review',approve)
    with pytest.raises(HTTPException) as error:
        asyncio.run(rag_ia.approuver_contenu_rag('review-test',rag_ia.ValidationRagRequest(reviewer_note='Relu')))
    assert error.value.status_code==404
    approve.assert_not_called()


def test_indexation_guides_n_accepte_pas_de_chemin_arbitraire():
    with pytest.raises(HTTPException) as error:
        asyncio.run(rag_ia.indexer_guides(rag_ia.IndexerGuidesRequest(noms=['../secret.md']),BackgroundTasks()))
    assert error.value.status_code==400


def test_indexation_guide_utilise_orchestrateur_et_background_existant(monkeypatch):
    prepare=Mock(return_value={'hash':'a'*64,'fichier':'guide.md','deja_indexe':False})
    ingest=AsyncMock()
    fake=type('Orchestrator',(),{'preparer_indexation':prepare,'ingerer_fichier':ingest})()
    monkeypatch.setattr(rag_ia,'get_rag_orchestrator',lambda:fake)
    tasks=BackgroundTasks()
    result=asyncio.run(rag_ia.indexer_guides(rag_ia.IndexerGuidesRequest(),tasks))
    assert result['data'][0]['statut']=='en_cours'
    assert len(tasks.tasks)==1
    assert tasks.tasks[0].args[2]=='aide_plateforme'
    ingest.assert_not_called()


def test_export_refuse_traversee_chemin():
    with pytest.raises(HTTPException) as error:
        asyncio.run(rag_ia.telecharger_export_rag('../portfolio_test.docx'))
    assert error.value.status_code==400
