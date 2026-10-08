# tests/test_backend_blocs_l_m.py
# Tests Blocs L + M — CRUD Offres, Salles, Projets, EDT, Budget
# Isolation : db_isolee (transaction annulée), client_role pour les rôles.

import pytest


# =============================================================================
# HELPERS
# =============================================================================

def creer_offre(client, titre="Offre IA 2026", offre_client="JIRAMA"):
    r = client.post("/api/v1/offres", json={
        "titre": titre, "client": offre_client, "tva_taux": 20.0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def creer_salle(client, nom="Salle A"):
    r = client.post("/api/v1/salles", json={
        "nom": nom, "capacite": 20, "tarif_journalier": 50000.0, "disponible": True,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def creer_projet(client, titre="Projet IA"):
    r = client.post("/api/v1/projets", json={
        "titre": titre, "client": "TELMA", "date_debut": "2026-10-01", "date_fin": "2026-10-05",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# =============================================================================
# BLOC L — CRUD /offres
# =============================================================================

class TestOffres:
    def test_creer_offre_ok(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.post("/api/v1/offres", json={
            "titre": "Offre formation DevOps",
            "client": "TELMA SA",
            "description": "Formation DevOps 5 jours",
            "montant_ht": 1500000.0,
            "tva_taux": 20.0,
            "statut": "BROUILLON",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["titre"] == "Offre formation DevOps"
        assert body["montant_ttc"] == pytest.approx(1800000.0, rel=1e-3)
        assert body["statut"] == "BROUILLON"

    def test_creer_offre_sans_montant(self, client_role):
        """Un montant null est autorisé (trame non encore générée)."""
        c = client_role(role="DIRECTION")
        r = c.post("/api/v1/offres", json={"titre": "Offre vide", "client": "CLI"})
        assert r.status_code == 201
        assert r.json()["montant_ht"] is None
        assert r.json()["montant_ttc"] == 0.0

    def test_lister_offres(self, client_role):
        c = client_role(role="DIRECTION")
        creer_offre(c, titre="Offre 1", offre_client="TELMA")
        creer_offre(c, titre="Offre 2", offre_client="JIRAMA")
        r = c.get("/api/v1/offres")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_filtre_statut_offres(self, client_role):
        c = client_role(role="DIRECTION")
        creer_offre(c)  # BROUILLON par défaut
        r = c.get("/api/v1/offres?statut=BROUILLON")
        assert r.status_code == 200
        assert all(o["statut"] == "BROUILLON" for o in r.json())

    def test_filtre_client_offres(self, client_role):
        c = client_role(role="DIRECTION")
        creer_offre(c, offre_client="ZANTEL")
        creer_offre(c, offre_client="PAOSITRA")
        r = c.get("/api/v1/offres?client=ZANTEL")
        assert r.status_code == 200
        assert all("ZANTEL" in o["client"].upper() for o in r.json())

    def test_get_offre_ok(self, client_role):
        c = client_role(role="DIRECTION")
        oid = creer_offre(c)
        r = c.get(f"/api/v1/offres/{oid}")
        assert r.status_code == 200
        assert r.json()["id"] == oid

    def test_get_offre_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.get("/api/v1/offres/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_patch_offre_ok(self, client_role):
        c = client_role(role="DIRECTION")
        oid = creer_offre(c)
        r = c.patch(f"/api/v1/offres/{oid}", json={"statut": "ENVOYEE", "montant_ht": 2000000.0})
        assert r.status_code == 200
        assert r.json()["statut"] == "ENVOYEE"
        assert r.json()["montant_ht"] == pytest.approx(2000000.0)

    def test_patch_offre_trame(self, client_role):
        """Simule la mise à jour par la route IA (trame_technique)."""
        c = client_role(role="DIRECTION")
        oid = creer_offre(c)
        r = c.patch(f"/api/v1/offres/{oid}", json={"trame_technique": "## Méthodologie\n..."})
        assert r.status_code == 200
        assert r.json()["trame_technique"].startswith("## Méthodologie")

    def test_supprimer_offre_ok(self, client_role):
        c = client_role(role="DIRECTION")
        oid = creer_offre(c)
        r = c.delete(f"/api/v1/offres/{oid}")
        assert r.status_code == 204
        assert c.get(f"/api/v1/offres/{oid}").status_code == 404

    def test_assistant_peut_creer_offre(self, client_role):
        c = client_role(role="ASSISTANT")
        r = c.post("/api/v1/offres", json={"titre": "Test", "client": "CLI"})
        assert r.status_code == 201

    def test_comptable_refuse_creation_offre(self, client_role):
        c = client_role(role="COMPTABLE")
        r = c.post("/api/v1/offres", json={"titre": "Test", "client": "CLI"})
        assert r.status_code == 403

    def test_assistant_refuse_suppression_offre(self, client_role):
        c_dir = client_role(role="DIRECTION")
        oid = creer_offre(c_dir)
        c_ass = client_role(role="ASSISTANT")
        r = c_ass.delete(f"/api/v1/offres/{oid}")
        assert r.status_code == 403

    def test_put_offre_remplace_tous_champs(self, client_role):
        """PUT écrase tous les champs, y compris ceux non fournis qui reviennent à leur défaut."""
        c = client_role(role="DIRECTION")
        oid = creer_offre(c, titre="Offre initiale", offre_client="TELMA")
        # PATCH ajoute une description
        c.patch(f"/api/v1/offres/{oid}", json={"description": "Desc initiale", "montant_ht": 500000.0})
        # PUT sans description → description doit être None
        r = c.put(f"/api/v1/offres/{oid}", json={
            "titre": "Offre remplacée",
            "client": "JIRAMA",
            "tva_taux": 20.0,
            "statut": "EN_ATTENTE",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["titre"] == "Offre remplacée"
        assert body["client"] == "JIRAMA"
        assert body["statut"] == "EN_ATTENTE"
        assert body["description"] is None
        assert body["montant_ht"] is None

    def test_put_offre_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.put("/api/v1/offres/00000000-0000-0000-0000-000000000000", json={
            "titre": "X", "client": "Y", "tva_taux": 20.0, "statut": "BROUILLON",
        })
        assert r.status_code == 404

    def test_put_offre_comptable_refuse(self, client_role):
        c_dir = client_role(role="DIRECTION")
        oid = creer_offre(c_dir)
        c_cpt = client_role(role="COMPTABLE")
        r = c_cpt.put(f"/api/v1/offres/{oid}", json={
            "titre": "X", "client": "Y", "tva_taux": 20.0, "statut": "BROUILLON",
        })
        assert r.status_code == 403

    def test_put_offre_champ_requis_manquant(self, client_role):
        """PUT sans `titre` doit retourner 422."""
        c = client_role(role="DIRECTION")
        oid = creer_offre(c)
        r = c.put(f"/api/v1/offres/{oid}", json={"client": "TELMA", "tva_taux": 20.0})
        assert r.status_code == 422


# =============================================================================
# BLOC M — CRUD /salles
# =============================================================================

class TestSalles:
    def test_creer_salle_ok(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.post("/api/v1/salles", json={
            "nom": "Salle Conférence", "capacite": 30,
            "tarif_journalier": 80000.0, "equipements": "Vidéoprojecteur, WiFi",
        })
        assert r.status_code == 201
        assert r.json()["nom"] == "Salle Conférence"
        assert r.json()["disponible"] is True

    def test_lister_salles(self, client_role):
        c = client_role(role="DIRECTION")
        creer_salle(c, "Salle A")
        creer_salle(c, "Salle B")
        r = c.get("/api/v1/salles")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_filtre_disponible(self, client_role):
        c = client_role(role="DIRECTION")
        sid = creer_salle(c, "Salle Dispo")
        c.patch(f"/api/v1/salles/{sid}", json={"disponible": False})
        r = c.get("/api/v1/salles?disponible=true")
        assert r.status_code == 200
        assert all(s["disponible"] is True for s in r.json())

    def test_patch_salle_ok(self, client_role):
        c = client_role(role="DIRECTION")
        sid = creer_salle(c)
        r = c.patch(f"/api/v1/salles/{sid}", json={"disponible": False, "capacite": 50})
        assert r.status_code == 200
        assert r.json()["disponible"] is False
        assert r.json()["capacite"] == 50

    def test_get_salle_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.get("/api/v1/salles/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_supprimer_salle_ok(self, client_role):
        c = client_role(role="DIRECTION")
        sid = creer_salle(c)
        r = c.delete(f"/api/v1/salles/{sid}")
        assert r.status_code == 204
        assert c.get(f"/api/v1/salles/{sid}").status_code == 404

    def test_put_salle_remplace_tous_champs(self, client_role):
        """PUT écrase tous les champs ; disponible repasse à True (défaut) si non fourni."""
        c = client_role(role="DIRECTION")
        sid = creer_salle(c, nom="Salle initiale")
        # PATCH rend la salle indisponible
        c.patch(f"/api/v1/salles/{sid}", json={"disponible": False, "adresse": "Rue A"})
        # PUT sans adresse ni disponible → adresse=None, disponible=True (défaut)
        r = c.put(f"/api/v1/salles/{sid}", json={
            "nom": "Salle remplacée",
            "capacite": 50,
            "tarif_journalier": 120000.0,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["nom"] == "Salle remplacée"
        assert body["capacite"] == 50
        assert body["adresse"] is None
        assert body["disponible"] is True

    def test_put_salle_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.put("/api/v1/salles/00000000-0000-0000-0000-000000000000", json={"nom": "X"})
        assert r.status_code == 404

    def test_put_salle_champ_requis_manquant(self, client_role):
        """PUT sans `nom` doit retourner 422."""
        c = client_role(role="DIRECTION")
        sid = creer_salle(c)
        r = c.put(f"/api/v1/salles/{sid}", json={"capacite": 10})
        assert r.status_code == 422

    def test_put_salle_assistant_autorise(self, client_role):
        c_dir = client_role(role="DIRECTION")
        sid = creer_salle(c_dir)
        c_ass = client_role(role="ASSISTANT")
        r = c_ass.put(f"/api/v1/salles/{sid}", json={"nom": "Salle ASSISTANT"})
        assert r.status_code == 200
        assert r.json()["nom"] == "Salle ASSISTANT"


# =============================================================================
# BLOC M — CRUD /projets
# =============================================================================

class TestProjets:
    def test_creer_projet_ok(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.post("/api/v1/projets", json={
            "titre": "Formation Python", "client": "TELMA",
            "date_debut": "2026-10-01", "date_fin": "2026-10-05",
        })
        assert r.status_code == 201
        assert r.json()["statut"] == "BROUILLON"
        assert r.json()["titre"] == "Formation Python"

    def test_lister_projets(self, client_role):
        c = client_role(role="DIRECTION")
        creer_projet(c, "P1")
        creer_projet(c, "P2")
        r = c.get("/api/v1/projets")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_filtre_statut_projets(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        c.patch(f"/api/v1/projets/{pid}", json={"statut": "EN_COURS"})
        r = c.get("/api/v1/projets?statut=EN_COURS")
        assert r.status_code == 200
        assert all(p["statut"] == "EN_COURS" for p in r.json())

    def test_patch_projet_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.patch(f"/api/v1/projets/{pid}", json={"statut": "EN_COURS", "notes": "Validé par direction"})
        assert r.status_code == 200
        assert r.json()["statut"] == "EN_COURS"

    def test_supprimer_projet_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.delete(f"/api/v1/projets/{pid}")
        assert r.status_code == 204
        assert c.get(f"/api/v1/projets/{pid}").status_code == 404

    def test_assistant_refuse_suppression_projet(self, client_role):
        c_dir = client_role(role="DIRECTION")
        pid = creer_projet(c_dir)
        c_ass = client_role(role="ASSISTANT")
        r = c_ass.delete(f"/api/v1/projets/{pid}")
        assert r.status_code == 403

    def test_put_projet_remplace_tous_champs(self, client_role):
        """PUT écrase tous les champs ; notes revient à None si non fourni."""
        c = client_role(role="DIRECTION")
        pid = creer_projet(c, titre="Projet initial")
        # PATCH ajoute des notes
        c.patch(f"/api/v1/projets/{pid}", json={"notes": "Notes initiales", "statut": "EN_COURS"})
        # PUT sans notes → notes doit être None, statut revient à BROUILLON
        r = c.put(f"/api/v1/projets/{pid}", json={
            "titre": "Projet remplacé",
            "client": "TELMA",
            "date_debut": "2026-11-01",
            "date_fin": "2026-11-10",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["titre"] == "Projet remplacé"
        assert body["client"] == "TELMA"
        assert body["statut"] == "BROUILLON"
        assert body["notes"] is None

    def test_put_projet_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.put("/api/v1/projets/00000000-0000-0000-0000-000000000000", json={"titre": "X"})
        assert r.status_code == 404

    def test_put_projet_champ_requis_manquant(self, client_role):
        """PUT sans `titre` doit retourner 422."""
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.put(f"/api/v1/projets/{pid}", json={"client": "TELMA"})
        assert r.status_code == 422

    def test_put_projet_assistant_autorise(self, client_role):
        c_dir = client_role(role="DIRECTION")
        pid = creer_projet(c_dir)
        c_ass = client_role(role="ASSISTANT")
        r = c_ass.put(f"/api/v1/projets/{pid}", json={
            "titre": "Projet par ASSISTANT",
            "statut": "EN_COURS",
        })
        assert r.status_code == 200
        assert r.json()["titre"] == "Projet par ASSISTANT"


# =============================================================================
# BLOC M — EDT /projets/{id}/edt
# =============================================================================

class TestEdtSessions:
    def test_ajouter_edt_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.post(f"/api/v1/projets/{pid}/edt", json={
            "date": "2026-10-01", "heure_debut": "08:00:00",
            "heure_fin": "12:00:00", "module": "Introduction Python",
        })
        assert r.status_code == 201
        assert r.json()["module"] == "Introduction Python"
        assert r.json()["projet_id"] == pid

    def test_lister_edt(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        c.post(f"/api/v1/projets/{pid}/edt", json={"date": "2026-10-01", "module": "Jour 1"})
        c.post(f"/api/v1/projets/{pid}/edt", json={"date": "2026-10-02", "module": "Jour 2"})
        r = c.get(f"/api/v1/projets/{pid}/edt")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_edt_projet_inexistant(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.post("/api/v1/projets/00000000-0000-0000-0000-000000000000/edt",
                   json={"date": "2026-10-01"})
        assert r.status_code == 404

    def test_supprimer_edt_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r_add = c.post(f"/api/v1/projets/{pid}/edt", json={"date": "2026-10-01"})
        edt_id = r_add.json()["id"]
        r_del = c.delete(f"/api/v1/projets/{pid}/edt/{edt_id}")
        assert r_del.status_code == 204
        assert len(c.get(f"/api/v1/projets/{pid}/edt").json()) == 0

    def test_cascade_edt_sur_suppression_projet(self, client_role):
        """Supprimer un projet supprime ses séances EDT sans erreur FK."""
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        c.post(f"/api/v1/projets/{pid}/edt", json={"date": "2026-10-01"})
        r = c.delete(f"/api/v1/projets/{pid}")
        assert r.status_code == 204


# =============================================================================
# BLOC M — Budget /projets/{id}/budget
# =============================================================================

class TestBudget:
    def test_creer_budget_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.post(f"/api/v1/projets/{pid}/budget", json={
            "cout_formateur": 400000.0,
            "cout_salle": 100000.0,
            "cout_supports": 50000.0,
        })
        assert r.status_code == 201
        body = r.json()
        assert body["cout_total"] == pytest.approx(550000.0)
        assert body["valide"] is False

    def test_budget_total_calcule_auto(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.post(f"/api/v1/projets/{pid}/budget", json={
            "cout_formateur": 300000.0, "cout_salle": 80000.0, "cout_supports": 20000.0,
        })
        assert r.json()["cout_total"] == pytest.approx(400000.0)

    def test_budget_idempotent(self, client_role):
        """Deux POST sur le même projet mettent à jour le budget existant."""
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        c.post(f"/api/v1/projets/{pid}/budget", json={"cout_formateur": 100000.0})
        r2 = c.post(f"/api/v1/projets/{pid}/budget", json={"cout_formateur": 200000.0})
        assert r2.status_code == 201
        assert r2.json()["cout_formateur"] == pytest.approx(200000.0)

    def test_budget_valide(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.post(f"/api/v1/projets/{pid}/budget", json={
            "cout_formateur": 500000.0, "valide": True,
        })
        assert r.json()["valide"] is True
        assert r.json()["valide_par"] is not None

    def test_get_budget_ok(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        c.post(f"/api/v1/projets/{pid}/budget", json={"cout_formateur": 300000.0})
        r = c.get(f"/api/v1/projets/{pid}/budget")
        assert r.status_code == 200
        assert r.json()["cout_formateur"] == pytest.approx(300000.0)

    def test_get_budget_404(self, client_role):
        c = client_role(role="DIRECTION")
        pid = creer_projet(c)
        r = c.get(f"/api/v1/projets/{pid}/budget")
        assert r.status_code == 404
