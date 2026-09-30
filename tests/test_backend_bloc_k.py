# tests/test_backend_bloc_k.py
# Tests Bloc K — DELETE /factures/{id} + GET /exports/comptable
#
# Isolation : db_isolee (transaction annulée), client_role pour les rôles.

import pytest


# =============================================================================
# HELPERS
# =============================================================================

def creer_facture(client, montant=500000.0, client_nom="TELMA SA"):
    r = client.post("/api/v1/factures", json={
        "client": client_nom, "montant": montant, "tva_taux": 20.0,
        "date_echeance": "2026-12-31",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# =============================================================================
# DELETE /factures/{id}
# =============================================================================

class TestSupprimerFacture:
    def test_direction_supprime_facture_ok(self, client_role):
        c = client_role(role="DIRECTION")
        fid = creer_facture(c)
        r = c.delete(f"/api/v1/factures/{fid}")
        assert r.status_code == 204

        # La facture n'existe plus
        r2 = c.get(f"/api/v1/factures/{fid}")
        assert r2.status_code == 404

    def test_suppression_cascade_paiements(self, client_role):
        """Supprimer une facture doit aussi supprimer ses paiements sans erreur FK."""
        c = client_role(role="DIRECTION")
        fid = creer_facture(c, montant=1000000.0)
        # Ajouter un paiement
        c.post(f"/api/v1/factures/{fid}/paiments", json={
            "montant": 200000.0, "date": "2026-11-01"
        })
        r = c.delete(f"/api/v1/factures/{fid}")
        assert r.status_code == 204

    def test_suppression_cascade_relances(self, client_role):
        """Supprimer une facture doit aussi supprimer ses relances sans erreur FK."""
        c = client_role(role="DIRECTION")
        fid = creer_facture(c)
        # Enregistrer une relance IA
        c.post(f"/api/v1/factures/{fid}/relances", json={
            "niveau": "1", "objet": "Rappel facture", "texte": "Votre facture est en retard.",
        })
        r = c.delete(f"/api/v1/factures/{fid}")
        assert r.status_code == 204

    def test_suppression_inexistant_404(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.delete("/api/v1/factures/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_comptable_refuse_suppression(self, client_role):
        """COMPTABLE peut créer mais pas supprimer (réservé DIRECTION)."""
        c_dir = client_role(role="DIRECTION")
        fid = creer_facture(c_dir)
        c_cpt = client_role(role="COMPTABLE")
        r = c_cpt.delete(f"/api/v1/factures/{fid}")
        assert r.status_code == 403

    def test_assistant_refuse_suppression(self, client_role):
        c_dir = client_role(role="DIRECTION")
        fid = creer_facture(c_dir)
        c_ass = client_role(role="ASSISTANT")
        r = c_ass.delete(f"/api/v1/factures/{fid}")
        assert r.status_code == 403


# =============================================================================
# GET /exports/comptable
# =============================================================================

class TestExportComptable:
    def test_export_csv_vide(self, client_role):
        """Export CSV sur base vide → en-tête seul, 200 OK."""
        c = client_role(role="DIRECTION")
        r = c.get("/api/v1/exports/comptable?format=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        assert ".csv" in r.headers["content-disposition"]
        # L'en-tête CSV doit être présent
        contenu = r.content.decode("utf-8-sig")
        assert "Numéro" in contenu
        assert "Statut" in contenu

    def test_export_csv_avec_factures(self, client_role):
        c = client_role(role="DIRECTION")
        creer_facture(c, client_nom="TELMA SA")
        creer_facture(c, client_nom="JIRAMA")
        r = c.get("/api/v1/exports/comptable?format=csv")
        assert r.status_code == 200
        contenu = r.content.decode("utf-8-sig")
        assert "TELMA SA" in contenu
        assert "JIRAMA" in contenu
        # 2 lignes données + 1 en-tête = 3 lignes minimum
        assert contenu.count("\n") >= 2

    def test_export_excel_ok(self, client_role):
        c = client_role(role="DIRECTION")
        creer_facture(c)
        r = c.get("/api/v1/exports/comptable?format=excel")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]
        assert ".xlsx" in r.headers["content-disposition"]
        # Vérification binaire : fichier xlsx commence par PK (ZIP)
        assert r.content[:2] == b"PK"

    def test_export_pdf_ok(self, client_role):
        c = client_role(role="DIRECTION")
        creer_facture(c)
        r = c.get("/api/v1/exports/comptable?format=pdf")
        assert r.status_code == 200
        assert "pdf" in r.headers["content-type"]
        assert ".pdf" in r.headers["content-disposition"]
        # Fichier PDF commence par %PDF
        assert r.content[:4] == b"%PDF"

    def test_export_filtre_statut(self, client_role):
        c = client_role(role="DIRECTION")
        creer_facture(c, client_nom="CLIENT_EMISE")
        r = c.get("/api/v1/exports/comptable?format=csv&statut=EMISE")
        assert r.status_code == 200
        contenu = r.content.decode("utf-8-sig")
        assert "CLIENT_EMISE" in contenu

    def test_export_filtre_client(self, client_role):
        c = client_role(role="DIRECTION")
        creer_facture(c, client_nom="ZANTEL")
        creer_facture(c, client_nom="PAOSITRA")
        r = c.get("/api/v1/exports/comptable?format=csv&client=ZANTEL")
        assert r.status_code == 200
        contenu = r.content.decode("utf-8-sig")
        assert "ZANTEL" in contenu
        assert "PAOSITRA" not in contenu

    def test_export_format_invalide(self, client_role):
        c = client_role(role="DIRECTION")
        r = c.get("/api/v1/exports/comptable?format=xml")
        assert r.status_code == 422

    def test_export_comptable_role_ok(self, client_role):
        """COMPTABLE peut accéder à l'export."""
        c = client_role(role="COMPTABLE")
        r = c.get("/api/v1/exports/comptable?format=csv")
        assert r.status_code == 200

    def test_export_assistant_refuse(self, client_role):
        """ASSISTANT ne peut pas accéder à l'export comptable."""
        c = client_role(role="ASSISTANT")
        r = c.get("/api/v1/exports/comptable?format=csv")
        assert r.status_code == 403

    def test_export_csv_colonnes_completes(self, client_role):
        """Vérifie que toutes les colonnes attendues sont présentes."""
        c = client_role(role="DIRECTION")
        creer_facture(c, montant=800000.0)
        r = c.get("/api/v1/exports/comptable?format=csv")
        contenu = r.content.decode("utf-8-sig")
        for col in ["Numéro", "Client", "Montant HT", "TVA", "Montant TTC", "Statut", "Encaissé", "Reste"]:
            assert col in contenu, f"Colonne manquante : {col}"
