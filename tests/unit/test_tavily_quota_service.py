# tests/unit/test_tavily_quota_service.py
# ============================================================
# Étape B (mission "Préparation soutenance") — quota Tavily, module pur
# ============================================================
# Aucun réseau, aucun fichier réel touché : QUOTA_PATH redirigé vers
# tmp_path pour chaque test.
# ============================================================

import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.services.veille import tavily_quota_service as quota


@pytest.fixture(autouse=True)
def isole(monkeypatch, tmp_path):
    monkeypatch.setattr(quota, "QUOTA_PATH", tmp_path / "tavily_quota.json")
    for nom in (
        "TAVILY_QUOTA_MENSUEL", "TAVILY_BUDGET_AUTO", "TAVILY_QUOTA_PLAFOND_DUR",
        "VEILLE_AUTO_MAX_RUNS_PER_DAY", "TAVILY_QUOTA_RESET_DAY",
    ):
        monkeypatch.delenv(nom, raising=False)


def dt(annee, mois, jour, heure=12):
    return datetime(annee, mois, jour, heure, 0, 0, tzinfo=timezone.utc)


# ============================================================
# Configuration — valeurs par défaut (mission Étape B point 2)
# ============================================================

def test_valeurs_par_defaut():
    cfg = quota.config()
    assert cfg == {
        "quota_mensuel": 1000, "budget_auto": 600, "plafond_dur": 980,
        "max_runs_par_jour": 2, "jour_reset": 1,
    }


def test_configuration_surchargeable_par_env(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_MENSUEL", "500")
    monkeypatch.setenv("VEILLE_AUTO_MAX_RUNS_PER_DAY", "5")

    cfg = quota.config()
    assert cfg["quota_mensuel"] == 500
    assert cfg["max_runs_par_jour"] == 5


# ============================================================
# Comptage des appels — par catégorie
# ============================================================

def test_enregistrer_appel_incremente_la_bonne_categorie():
    quota.enregistrer_appel("auto", dt(2026, 9, 26))
    quota.enregistrer_appel("auto", dt(2026, 9, 26))
    quota.enregistrer_appel("manuel", dt(2026, 9, 26))

    assert quota.consommation("auto", dt(2026, 9, 26)) == 2
    assert quota.consommation("manuel", dt(2026, 9, 26)) == 1
    assert quota.consommation("collecte", dt(2026, 9, 26)) == 0
    assert quota.consommation(None, dt(2026, 9, 26)) == 3


def test_categorie_inconnue_retombe_sur_manuel():
    quota.enregistrer_appel("inexistante", dt(2026, 9, 26))
    assert quota.consommation("manuel", dt(2026, 9, 26)) == 1


# ============================================================
# Bascule de mois (période calendaire)
# ============================================================

def test_bascule_de_mois_reinitialise_les_appels():
    quota.enregistrer_appel("auto", dt(2026, 9, 30))
    assert quota.consommation(None, dt(2026, 9, 30)) == 1

    # Un mois plus tard : compteur d'appels repart à zéro
    assert quota.consommation(None, dt(2026, 10, 1)) == 0
    quota.enregistrer_appel("manuel", dt(2026, 10, 1))
    assert quota.consommation(None, dt(2026, 10, 1)) == 1
    # L'ancien mois n'est pas affecté rétroactivement (juste écrasé au prochain accès)


def test_jour_reset_personnalise_decale_la_periode(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_RESET_DAY", "15")

    quota.enregistrer_appel("manuel", dt(2026, 9, 14))  # avant le 15 -> période "2026-08"
    quota.enregistrer_appel("manuel", dt(2026, 9, 20))  # après le 15 -> période "2026-09" (remise à zéro)

    assert quota.consommation(None, dt(2026, 9, 20)) == 1


# ============================================================
# Runs/jour (mode auto)
# ============================================================

def test_runs_par_jour_comptes_independamment_des_appels():
    quota.enregistrer_run_auto(dt(2026, 9, 26))
    quota.enregistrer_run_auto(dt(2026, 9, 26))
    quota.enregistrer_run_auto(dt(2026, 9, 27))

    assert quota.runs_aujourd_hui(dt(2026, 9, 26, 23)) == 2
    assert quota.runs_aujourd_hui(dt(2026, 9, 27, 1)) == 1


def test_nettoyage_runs_de_plus_de_30_jours():
    quota.enregistrer_run_auto(dt(2026, 8, 1))   # sera vieux de > 30 jours au 2e appel
    quota.enregistrer_run_auto(dt(2026, 9, 26))  # déclenche le nettoyage

    assert quota.runs_aujourd_hui(dt(2026, 8, 1)) == 0  # nettoyé
    assert quota.runs_aujourd_hui(dt(2026, 9, 26)) == 1


# ============================================================
# verifier_quota_auto — les 3 conditions (OU)
# ============================================================

def test_verifier_quota_auto_ok_par_defaut():
    autorise, raison = quota.verifier_quota_auto(dt(2026, 9, 26))
    assert autorise is True and raison is None


def test_verifier_quota_auto_refuse_si_runs_du_jour_atteints():
    quota.enregistrer_run_auto(dt(2026, 9, 26))
    quota.enregistrer_run_auto(dt(2026, 9, 26))  # = max_runs_par_jour (2)

    autorise, raison = quota.verifier_quota_auto(dt(2026, 9, 26))
    assert autorise is False
    assert "2 passage" in raison


def test_verifier_quota_auto_refuse_si_budget_auto_atteint(monkeypatch):
    monkeypatch.setenv("TAVILY_BUDGET_AUTO", "3")
    for _ in range(3):
        quota.enregistrer_appel("auto", dt(2026, 9, 26))

    autorise, raison = quota.verifier_quota_auto(dt(2026, 9, 26))
    assert autorise is False
    assert "Budget Tavily du mode auto" in raison


def test_verifier_quota_auto_refuse_si_plafond_dur_atteint(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "3")
    quota.enregistrer_appel("manuel", dt(2026, 9, 26))
    quota.enregistrer_appel("collecte", dt(2026, 9, 26))
    quota.enregistrer_appel("auto", dt(2026, 9, 26))  # total = 3 = plafond

    autorise, raison = quota.verifier_quota_auto(dt(2026, 9, 26))
    assert autorise is False
    assert "Plafond dur" in raison


# ============================================================
# plafond_dur_atteint — mode manuel/collecte
# ============================================================

def test_plafond_dur_non_atteint_par_defaut():
    assert quota.plafond_dur_atteint(dt(2026, 9, 26)) is False


def test_plafond_dur_atteint_quelle_que_soit_la_categorie(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_PLAFOND_DUR", "2")
    quota.enregistrer_appel("manuel", dt(2026, 9, 26))
    quota.enregistrer_appel("auto", dt(2026, 9, 26))

    assert quota.plafond_dur_atteint(dt(2026, 9, 26)) is True


# ============================================================
# Seuils de journalisation 80% / 95%
# ============================================================

def test_avertissement_80_pourcent(monkeypatch, caplog):
    monkeypatch.setenv("TAVILY_QUOTA_MENSUEL", "10")
    with caplog.at_level(logging.WARNING, logger="app.services.veille.tavily_quota_service"):
        for _ in range(8):  # 80%
            quota.enregistrer_appel("manuel", dt(2026, 9, 26))

    assert any("Quota Tavily élevé" in m for m in caplog.messages)
    assert not any("critique" in m for m in caplog.messages)


def test_erreur_95_pourcent(monkeypatch, caplog):
    monkeypatch.setenv("TAVILY_QUOTA_MENSUEL", "20")
    with caplog.at_level(logging.WARNING, logger="app.services.veille.tavily_quota_service"):
        for _ in range(19):  # 95%
            quota.enregistrer_appel("manuel", dt(2026, 9, 26))

    assert any("critique" in m for m in caplog.messages)


# ============================================================
# etat_pour_route (GET /ia/veille/quota)
# ============================================================

def test_etat_pour_route_structure_complete():
    quota.enregistrer_appel("auto", dt(2026, 9, 26))
    quota.enregistrer_appel("manuel", dt(2026, 9, 26))
    quota.enregistrer_run_auto(dt(2026, 9, 26))

    etat = quota.etat_pour_route(dt(2026, 9, 26))

    assert etat["periode"] == "2026-09"
    assert etat["appels_par_categorie"] == {"auto": 1, "manuel": 1, "collecte": 0}
    assert etat["total_appels"] == 2
    assert etat["restant"] == 998
    assert etat["runs_auto_aujourd_hui"] == 1
    assert etat["avertissement"] is None
    assert etat["configuration"]["quota_mensuel"] == 1000


def test_etat_pour_route_avertissement_critique(monkeypatch):
    monkeypatch.setenv("TAVILY_QUOTA_MENSUEL", "10")
    for _ in range(10):
        quota.enregistrer_appel("manuel", dt(2026, 9, 26))

    etat = quota.etat_pour_route(dt(2026, 9, 26))
    assert etat["avertissement"] == "critique"
    assert etat["restant"] == 0
