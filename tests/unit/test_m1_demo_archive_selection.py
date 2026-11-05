"""La démo ne présente que des avis publiés, capturés et sourcés."""

import json
from datetime import date, timedelta

from app.api.v1 import routes_veille
from app.services.veille import demo_mode_service


def test_archive_ecarte_les_avis_futurs(tmp_path, monkeypatch):
    today = date.today()
    base = {
        "title": "Avis public",
        "date_publication": today.isoformat(),
        "date_capture": today.isoformat(),
        "date_limite": (today + timedelta(days=10)).isoformat(),
        "source_url": "https://example.org/avis-public",
    }
    archive = [
        {**base, "reference": "actuel"},
        {**base, "reference": "capture-future", "date_capture": (today + timedelta(days=1)).isoformat()},
        {**base, "reference": "publication-future", "date_publication": (today + timedelta(days=1)).isoformat()},
    ]
    path = tmp_path / "archive.json"
    path.write_text(json.dumps(archive), encoding="utf-8")
    monkeypatch.setattr(demo_mode_service, "ARCHIVE_REELLE_PATH", path)

    visible = demo_mode_service.charger_opportunites_demo_reelles()
    assert [item["reference"] for item in visible] == ["actuel"]


def test_selection_aleatoire_garde_les_avis_fermes_sourcables_et_exclut_contacts(monkeypatch):
    archive = [
        {"title": "Avis A", "source_url": "https://example.org/a", "is_actionable": True},
        {"title": "Avis B", "source_url": "https://example.org/b", "is_actionable": True},
        {"title": "Contact privé", "source_url": None, "is_actionable": True},
        {"title": "Clos", "source_url": "https://example.org/clos", "is_actionable": False},
    ]
    monkeypatch.setattr(routes_veille, "charger_opportunites_demo_reelles", lambda: archive)
    visibles = routes_veille._opportunites_demo_visibles(3)
    assert {item["title"] for item in visibles} == {"Avis A", "Avis B", "Clos"}
    assert all(item.get("source_url") or item.get("url") for item in visibles)


def test_archive_demo_contient_avis_pnud_informatique_verifiable():
    with demo_mode_service.ARCHIVE_REELLE_PATH.open(encoding="utf-8") as fichier:
        archive = json.load(fichier)
    avis = next(item for item in archive if item.get("reference") == "UNDP-MDG-00895 / PRC0196300")
    assert avis["domain"] == "informatique"
    assert avis["source_site"] == "procurement-notices.undp.org"
    assert avis["source_url"].startswith("https://procurement-notices.undp.org/")
    assert avis["is_synthetic"] is False
    assert avis["date_limite"] == "2026-11-20"
