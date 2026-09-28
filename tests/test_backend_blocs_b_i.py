# tests/test_backend_blocs_b_i.py
# Tests des routes Backend ajoutées dans les Blocs B à I
# (Sessions PATCH/DELETE, Séances CRUD, Présences, Participants CRUD,
#  Inscriptions, Factures PATCH/filtres, Auth users, RH)

import pytest


# =============================================================================
# HELPERS
# =============================================================================

def creer_session(client, titre="Test Session"):
    r = client.post("/api/v1/sessions", json={
        "titre": titre, "date_debut": "2026-10-01", "date_fin": "2026-10-03"
    })
    assert r.status_code == 201
    return r.json()["id"]


def creer_seance(client, session_id, date="2026-10-01"):
    r = client.post(f"/api/v1/sessions/{session_id}/seances", json={
        "date": date, "theme": "Thème test", "duree": "8h"
    })
    assert r.status_code == 201
    return r.json()["id"]


def creer_participant(client, nom="Rakoto"):
    r = client.post("/api/v1/participants", json={"nom": nom, "email": f"{nom.lower()}@test.mg"})
    assert r.status_code == 201
    return r.json()["id"]


def creer_facture(client):
    r = client.post("/api/v1/factures", json={
        "client": "TELMA SA", "montant": 1000000.0, "tva_taux": 20.0,
        "date_echeance": "2026-12-31"
    })
    assert r.status_code == 201
    return r.json()["id"]


# =============================================================================
# SESSIONS — PATCH / DELETE / FILTRES
# =============================================================================

def test_patch_session(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client, titre="Session initiale")

    r = client.patch(f"/api/v1/sessions/{session_id}", json={"titre": "Session modifiée"})
    assert r.status_code == 200
    assert r.json()["titre"] == "Session modifiée"


def test_patch_session_date_invalide(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)

    r = client.patch(f"/api/v1/sessions/{session_id}", json={
        "date_debut": "2026-10-05", "date_fin": "2026-10-01"
    })
    assert r.status_code == 422


def test_patch_session_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    r = client.patch("/api/v1/sessions/00000000-0000-0000-0000-000000000000",
                     json={"titre": "X"})
    assert r.status_code == 404


def test_delete_session(client_role):
    client = client_role(role="DIRECTION")
    session_id = creer_session(client)

    r = client.delete(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 204

    r = client.get(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 404


def test_delete_session_cascade_seances(client_role):
    """Supprimer une session supprime aussi ses séances."""
    client = client_role(role="DIRECTION")
    session_id = creer_session(client)
    creer_seance(client, session_id)

    r = client.delete(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 204


def test_delete_session_role_non_autorise(client_role):
    client_dir = client_role(role="DIRECTION")
    session_id = creer_session(client_dir)

    client_form = client_role(role="FORMATEUR")
    r = client_form.delete(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 403


def test_lister_sessions_filtre_client(client_role):
    client = client_role(role="DIRECTION")
    client.post("/api/v1/sessions", json={"titre": "Sess TELMA", "date_debut": "2026-10-01",
                                          "date_fin": "2026-10-02", "client": "TELMA"})
    client.post("/api/v1/sessions", json={"titre": "Sess JIRAMA", "date_debut": "2026-10-01",
                                          "date_fin": "2026-10-02", "client": "JIRAMA"})

    r = client.get("/api/v1/sessions?client=TELMA")
    assert r.status_code == 200
    sessions = r.json()
    assert all("TELMA" in (s.get("client") or "") for s in sessions)


# =============================================================================
# SÉANCES — PATCH / DELETE
# =============================================================================

def test_patch_seance(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    seance_id = creer_seance(client, session_id)

    r = client.patch(f"/api/v1/sessions/seances/{seance_id}", json={"theme": "Nouveau thème"})
    assert r.status_code == 200
    assert r.json()["theme"] == "Nouveau thème"


def test_patch_seance_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    r = client.patch("/api/v1/sessions/seances/00000000-0000-0000-0000-000000000000",
                     json={"theme": "X"})
    assert r.status_code == 404


def test_delete_seance(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    seance_id = creer_seance(client, session_id)

    r = client.delete(f"/api/v1/sessions/seances/{seance_id}")
    assert r.status_code == 204


def test_delete_seance_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    r = client.delete("/api/v1/sessions/seances/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# =============================================================================
# PRÉSENCES — GET liste / PATCH correction
# =============================================================================

def test_lister_presences_seance_vide(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    seance_id = creer_seance(client, session_id)

    r = client.get(f"/api/v1/sessions/seances/{seance_id}/presences")
    assert r.status_code == 200
    assert r.json() == []


def test_lister_presences_seance_inexistante(client_authenticated):
    r = client_authenticated.get(
        "/api/v1/sessions/seances/00000000-0000-0000-0000-000000000000/presences"
    )
    assert r.status_code == 404


def test_patch_presence(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    seance_id = creer_seance(client, session_id)
    participant_id = creer_participant(client)

    presence_id = client.post(
        f"/api/v1/sessions/seances/{seance_id}/presences",
        json={"participant_id": participant_id, "statut": "PRESENT"}
    ).json()["id"]

    r = client.patch(f"/api/v1/sessions/seances/presences/{presence_id}",
                     json={"statut": "ABSENT"})
    assert r.status_code == 200
    assert r.json()["statut"] == "ABSENT"


def test_patch_presence_inexistante(client_role):
    client = client_role(role="FORMATEUR")
    r = client.patch("/api/v1/sessions/seances/presences/00000000-0000-0000-0000-000000000000",
                     json={"statut": "ABSENT"})
    assert r.status_code == 404


# =============================================================================
# PARTICIPANTS — PATCH / DELETE
# =============================================================================

def test_patch_participant(client_role):
    client = client_role(role="FORMATEUR")
    participant_id = creer_participant(client, "Andry")

    r = client.patch(f"/api/v1/participants/{participant_id}",
                     json={"entreprise": "ORANGE Madagascar"})
    assert r.status_code == 200
    assert r.json()["entreprise"] == "ORANGE Madagascar"


def test_patch_participant_inexistant(client_role):
    client = client_role(role="FORMATEUR")
    r = client.patch("/api/v1/participants/00000000-0000-0000-0000-000000000000",
                     json={"nom": "X"})
    assert r.status_code == 404


def test_delete_participant(client_role):
    client = client_role(role="DIRECTION")
    participant_id = creer_participant(client)

    r = client.delete(f"/api/v1/participants/{participant_id}")
    assert r.status_code == 204

    r = client.get(f"/api/v1/participants/{participant_id}")
    assert r.status_code == 404


def test_delete_participant_role_non_autorise(client_role):
    client_dir = client_role(role="DIRECTION")
    participant_id = creer_participant(client_dir)

    client_form = client_role(role="FORMATEUR")
    r = client_form.delete(f"/api/v1/participants/{participant_id}")
    assert r.status_code == 403


# =============================================================================
# INSCRIPTIONS
# =============================================================================

def test_inscrire_et_lister_participants_session(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    p1 = creer_participant(client, "Participant Un")
    p2 = creer_participant(client, "Participant Deux")

    r = client.post(f"/api/v1/sessions/{session_id}/inscrire",
                    json={"participant_id": p1})
    assert r.status_code == 201

    r = client.post(f"/api/v1/sessions/{session_id}/inscrire",
                    json={"participant_id": p2})
    assert r.status_code == 201

    r = client.get(f"/api/v1/sessions/{session_id}/participants")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_inscrire_doublon_retourne_409(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    participant_id = creer_participant(client)

    client.post(f"/api/v1/sessions/{session_id}/inscrire",
                json={"participant_id": participant_id})

    r = client.post(f"/api/v1/sessions/{session_id}/inscrire",
                    json={"participant_id": participant_id})
    assert r.status_code == 409


def test_desinscrire_participant(client_role):
    client = client_role(role="FORMATEUR")
    session_id = creer_session(client)
    participant_id = creer_participant(client)

    client.post(f"/api/v1/sessions/{session_id}/inscrire",
                json={"participant_id": participant_id})

    r = client.delete(f"/api/v1/sessions/{session_id}/inscrire/{participant_id}")
    assert r.status_code == 204


# =============================================================================
# FACTURES — PATCH + FILTRES
# =============================================================================

def test_patch_facture(client_role):
    client = client_role(role="COMPTABLE")
    facture_id = creer_facture(client)

    r = client.patch(f"/api/v1/factures/{facture_id}",
                     json={"client": "JIRAMA SA"})
    assert r.status_code == 200
    assert r.json()["client"] == "JIRAMA SA"


def test_patch_facture_inexistante(client_role):
    client = client_role(role="COMPTABLE")
    r = client.patch("/api/v1/factures/00000000-0000-0000-0000-000000000000",
                     json={"client": "X"})
    assert r.status_code == 404


def test_lister_factures_filtre_statut(client_role):
    client = client_role(role="COMPTABLE")
    creer_facture(client)

    r = client.get("/api/v1/factures?statut=EMISE")
    assert r.status_code == 200
    data = r.json()
    assert all(f["statut"] == "EMISE" for f in data)


def test_lister_factures_filtre_client(client_role):
    client = client_role(role="COMPTABLE")
    creer_facture(client)

    r = client.get("/api/v1/factures?client=TELMA")
    assert r.status_code == 200
    for f in r.json():
        assert "TELMA" in f["client"].upper()


def test_lister_factures_pagination(client_role):
    client = client_role(role="COMPTABLE")
    for i in range(3):
        client.post("/api/v1/factures", json={
            "client": f"Client {i}", "montant": 500000.0, "tva_taux": 20.0,
            "date_echeance": "2026-12-31"
        })

    r = client.get("/api/v1/factures?skip=0&limit=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


# =============================================================================
# AUTH — GESTION UTILISATEURS (DIRECTION)
# =============================================================================

def test_lister_utilisateurs(client_role):
    client = client_role(role="DIRECTION")
    r = client.get("/api/v1/auth/users")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_lister_utilisateurs_role_non_autorise(client_role):
    client = client_role(role="FORMATEUR")
    r = client.get("/api/v1/auth/users")
    assert r.status_code == 403


def test_get_utilisateur_inexistant(client_role):
    client = client_role(role="DIRECTION")
    r = client.get("/api/v1/auth/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_patch_utilisateur_email_duplique(client_role):
    """Modifier l'email d'un user avec un email déjà pris doit retourner 400."""
    client = client_role(role="DIRECTION")

    u1 = client.post("/api/v1/auth/register", json={
        "nom": "Alice", "email": "alice@test.mg",
        "password": "Passw0rd!", "role": "ASSISTANT"
    }).json()

    u2 = client.post("/api/v1/auth/register", json={
        "nom": "Bob", "email": "bob@test.mg",
        "password": "Passw0rd!", "role": "ASSISTANT"
    }).json()

    r = client.patch(f"/api/v1/auth/users/{u2['id']}",
                     json={"email": "alice@test.mg"})
    assert r.status_code == 400


def test_delete_utilisateur_inexistant(client_role):
    client = client_role(role="DIRECTION")
    r = client.delete("/api/v1/auth/users/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# =============================================================================
# RH — FORMATEURS / CANDIDATS / ENTRETIENS
# =============================================================================

def test_creer_et_lister_formateur(client_role):
    client = client_role(role="DIRECTION")
    r = client.post("/api/v1/rh/formateurs", json={
        "nom": "Razafy", "specialite": "DevOps", "tarif_journalier": 150000.0
    })
    assert r.status_code == 201
    formateur_id = r.json()["id"]

    r = client.get("/api/v1/rh/formateurs?specialite=DevOps")
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()]
    assert formateur_id in ids


def test_patch_et_delete_formateur(client_role):
    client = client_role(role="DIRECTION")
    formateur_id = client.post("/api/v1/rh/formateurs", json={"nom": "Tovon"}).json()["id"]

    r = client.patch(f"/api/v1/rh/formateurs/{formateur_id}",
                     json={"statut": "INACTIF"})
    assert r.status_code == 200
    assert r.json()["statut"] == "INACTIF"

    r = client.delete(f"/api/v1/rh/formateurs/{formateur_id}")
    assert r.status_code == 204


def test_creer_candidat_et_entretien(client_role):
    client = client_role(role="DIRECTION")
    candidat_id = client.post("/api/v1/rh/candidats", json={
        "nom": "Fiderana", "poste_vise": "Formateur IA"
    }).json()["id"]

    r = client.post(f"/api/v1/rh/candidats/{candidat_id}/entretiens", json={
        "date_entretien": "2026-10-15T09:00:00Z",
        "interviewers": "Directeur RH,Responsable Technique"
    })
    assert r.status_code == 201
    entretien_id = r.json()["id"]

    r = client.get(f"/api/v1/rh/candidats/{candidat_id}/entretiens")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = client.get(f"/api/v1/rh/entretiens/{entretien_id}")
    assert r.status_code == 200
    assert r.json()["id"] == entretien_id


def test_patch_entretien(client_role):
    client = client_role(role="DIRECTION")
    candidat_id = client.post("/api/v1/rh/candidats", json={
        "nom": "Hery", "poste_vise": "Data Engineer"
    }).json()["id"]

    entretien_id = client.post(f"/api/v1/rh/candidats/{candidat_id}/entretiens", json={}).json()["id"]

    r = client.patch(f"/api/v1/rh/entretiens/{entretien_id}",
                     json={"decision": "RECRUTER"})
    assert r.status_code == 200
    assert r.json()["decision"] == "RECRUTER"


def test_delete_candidat_cascade_entretiens(client_role):
    client = client_role(role="DIRECTION")
    candidat_id = client.post("/api/v1/rh/candidats", json={
        "nom": "Lova", "poste_vise": "Formateur"
    }).json()["id"]

    client.post(f"/api/v1/rh/candidats/{candidat_id}/entretiens", json={})

    r = client.delete(f"/api/v1/rh/candidats/{candidat_id}")
    assert r.status_code == 204

    r = client.get(f"/api/v1/rh/candidats/{candidat_id}")
    assert r.status_code == 404


def test_delete_entretien(client_role):
    client = client_role(role="DIRECTION")
    candidat_id = client.post("/api/v1/rh/candidats", json={
        "nom": "Tahina", "poste_vise": "Formateur"
    }).json()["id"]

    entretien_id = client.post(f"/api/v1/rh/candidats/{candidat_id}/entretiens", json={}).json()["id"]

    r = client.delete(f"/api/v1/rh/entretiens/{entretien_id}")
    assert r.status_code == 204


def test_get_entretien_inexistant(client_authenticated):
    r = client_authenticated.get("/api/v1/rh/entretiens/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
