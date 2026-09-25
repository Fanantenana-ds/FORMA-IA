# ============================================================
# TESTS — conversation_service.py (§5) + chat_log_service.py (§6)
# ============================================================

from app.services.rag import conversation_service as memoire
from app.services.rag import chat_log_service as journal


# ---- conversation_service ----

def test_conversation_nouvelle_est_vide(tmp_path):
    conv = memoire.charger_conversation("abc", tmp_path)
    assert conv.echanges == []
    assert conv.derniere_formation_code is None


def test_ajouter_echange_et_sauvegarder(tmp_path):
    conv = memoire.charger_conversation("abc", tmp_path)
    conv = memoire.ajouter_echange(conv, "utilisateur", "Bonjour")
    conv = memoire.ajouter_echange(conv, "assistant", "Bonjour, que puis-je faire pour vous ?")
    memoire.sauvegarder_conversation(conv, tmp_path)

    relue = memoire.charger_conversation("abc", tmp_path)
    assert len(relue.echanges) == 2
    assert relue.echanges[0].texte == "Bonjour"


def test_seuls_les_6_derniers_echanges_sont_gardes(tmp_path):
    conv = memoire.charger_conversation("abc", tmp_path)
    for i in range(10):
        conv = memoire.ajouter_echange(conv, "utilisateur", f"Message {i}")

    assert len(conv.echanges) == 6
    assert conv.echanges[-1].texte == "Message 9"
    assert conv.echanges[0].texte == "Message 4"


def test_derniere_formation_memorisee_pour_les_relances(tmp_path):
    conv = memoire.charger_conversation("abc", tmp_path)
    conv = memoire.ajouter_echange(conv, "assistant", "Voici le contenu.", formation_code="IA_FONDAMENTAUX")

    assert conv.derniere_formation_code == "IA_FONDAMENTAUX"

    # Un échange sans formation_code ne doit PAS effacer la mémoire (mission : relances)
    conv = memoire.ajouter_echange(conv, "utilisateur", "et le module 2 ?")
    assert conv.derniere_formation_code == "IA_FONDAMENTAUX"


# ---- chat_log_service ----

def test_enregistrer_et_relire(tmp_path):
    chemin = tmp_path / "chat_logs.jsonl"
    journal.enregistrer(
        question="Bonjour", type_detecte="conversationnel", formation_code=None,
        nb_sources=0, modele_requete=None, cache_utilise=False, duree_ms=12.3,
        statut="ok", chemin=chemin,
    )
    journal.enregistrer(
        question="Où est expliqué X ?", type_detecte="localisation", formation_code="IA_FONDAMENTAUX",
        nb_sources=2, modele_requete="voyage-4-large", cache_utilise=True, duree_ms=850.0,
        statut="ok", chemin=chemin,
    )

    lignes = journal.lire_toutes_les_lignes(chemin)

    assert len(lignes) == 2
    assert lignes[0]["type_detecte"] == "conversationnel"
    assert lignes[1]["cache_utilise"] is True


def test_journal_inexistant_retourne_liste_vide(tmp_path):
    assert journal.lire_toutes_les_lignes(tmp_path / "n_existe_pas.jsonl") == []
