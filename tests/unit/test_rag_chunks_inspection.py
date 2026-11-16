from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.models.historique_analyse

from app.models.knowledge_base import KnowledgeBase
from app.services.rag import knowledge_repository as repository


def test_inspection_lit_chunks_persistes_sans_vecteur_et_pagine(monkeypatch):
    engine=create_engine('sqlite:///:memory:')
    KnowledgeBase.__table__.create(engine)
    factory=sessionmaker(bind=engine)
    monkeypatch.setattr(repository,'SessionLocal',factory)
    with factory() as db:
        for i in range(3):
            db.add(KnowledgeBase(doc_hash='a'*64,collection='support',chunk_index=i,contenu=f'Passage réellement enregistré {i}',fichier='support.pdf',page_debut=i+1,embedding=[0.1]*1024,modele_embed='voyage-4-large'))
        db.commit()
    result=repository.KnowledgeRepository().lister_chunks_document('a'*64,offset=1,limit=1,collection='support')
    assert result['total']==3
    assert result['data'][0]['chunk_index']==1
    assert result['data'][0]['contenu']=='Passage réellement enregistré 1'
    assert 'embedding' not in result['data'][0]
    assert repository.KnowledgeRepository().lister_chunks_document('b'*64)['total']==0
    engine.dispose()
