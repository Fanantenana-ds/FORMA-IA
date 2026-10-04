"""
Tests — app/services/veille/validation_service.py

Couvre :
- quality_filter : tous les cas de rejet + cas passant
- normalize_opportunity : is_actionable, conversions, extraction employeur URL
- deduplicate : doublons URL, doublons titre, liste vide
- validate_against_schema : valide, Pydantic KO (bypass gracieux)
- fallback_response : structure retournée
- _extract_employer_from_url : chaque plateforme connue + URL sans match
"""

import pytest

from app.services.veille.validation_service import (
    _extract_employer_from_url,
    _flag_ambiguous_organizer,
    deduplicate,
    fallback_response,
    normalize_opportunity,
    quality_filter,
    validate_against_schema,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def opportunite_valide(**kwargs):
    """Retourne une opportunité qui passe quality_filter par défaut."""
    base = {
        "title": "Développeur Python recrute senior",
        "summary": "Nous recrutons un développeur Python senior pour une mission data.",
        "organizer": "Société XYZ",
        "opportunity_type": "emploi",
        "url": "https://codeko.tech/jobs/societe-xyz-developer",
        "confidence": 0.8,
    }
    base.update(kwargs)
    return base


# ──────────────────────────────────────────────
# quality_filter
# ──────────────────────────────────────────────

class TestQualityFilter:
    def test_passe_si_tout_ok(self):
        assert quality_filter(opportunite_valide()) is True

    def test_rejete_si_title_vide(self):
        assert quality_filter(opportunite_valide(title="")) is False

    def test_rejete_si_summary_vide(self):
        assert quality_filter(opportunite_valide(summary="")) is False

    def test_rejete_si_confidence_faible(self):
        assert quality_filter(opportunite_valide(confidence=0.1)) is False

    def test_rejete_si_confidence_zero(self):
        assert quality_filter(opportunite_valide(confidence=0)) is False

    def test_rejete_si_type_non_actionnable(self):
        assert quality_filter(opportunite_valide(opportunity_type="article")) is False
        assert quality_filter(opportunite_valide(opportunity_type="guide")) is False
        assert quality_filter(opportunite_valide(opportunity_type="rapport")) is False

    def test_rejete_si_url_listing(self):
        assert quality_filter(opportunite_valide(url="/emploi/liste")) is False
        assert quality_filter(opportunite_valide(url="/jobs/search")) is False
        assert quality_filter(opportunite_valide(url="http://site.com?page=2")) is False

    def test_rejete_si_titre_generique(self):
        assert quality_filter(opportunite_valide(title="offres d'emploi disponibles")) is False
        assert quality_filter(opportunite_valide(title="liste des offres")) is False

    def test_rejete_si_aucun_mot_cle_action(self):
        opp = opportunite_valide(title="Page d'accueil", summary="Bienvenue sur notre site web.")
        assert quality_filter(opp) is False

    def test_rejete_si_pas_organizer_pour_type_requis(self):
        opp = opportunite_valide(organizer="", opportunity_type="emploi")
        assert quality_filter(opp) is False

    def test_passe_sans_organizer_pour_type_non_requis(self):
        opp = opportunite_valide(organizer="", opportunity_type="autre")
        # autre n'est pas dans TYPES_REQUIRING_ORGANIZER
        assert quality_filter(opp) is True

    def test_confidence_comme_string(self):
        """confidence peut arriver sous forme de string depuis le LLM."""
        assert quality_filter(opportunite_valide(confidence="0.1")) is False
        assert quality_filter(opportunite_valide(confidence="0.9")) is True


# ──────────────────────────────────────────────
# normalize_opportunity
# ──────────────────────────────────────────────

class TestNormalizeOpportunity:
    def test_retourne_none_si_pas_dict(self):
        assert normalize_opportunity("pas un dict") is None
        assert normalize_opportunity(None) is None
        assert normalize_opportunity(42) is None

    def test_is_actionable_false_retourne_none(self):
        opp = opportunite_valide(is_actionable=False)
        assert normalize_opportunity(opp) is None

    def test_is_actionable_string_false_retourne_none(self):
        for val in ("false", "False", "no", "0"):
            opp = opportunite_valide(is_actionable=val)
            assert normalize_opportunity(opp) is None, f"Attendu None pour is_actionable={val!r}"

    def test_is_actionable_none_devient_true(self):
        opp = opportunite_valide()
        opp.pop("is_actionable", None)
        result = normalize_opportunity(opp)
        assert result["is_actionable"] is True

    def test_defaults_ajoutes(self):
        opp = {"title": "Test", "summary": "Résumé", "url": "http://x.com"}
        result = normalize_opportunity(opp)
        assert result is not None
        assert result["budget"] == "Non précisé"
        assert result["deadline"] is None
        assert result["flags"] == []

    def test_confidence_convertie_en_float(self):
        opp = opportunite_valide(confidence="0.75")
        result = normalize_opportunity(opp)
        assert isinstance(result["confidence"], float)
        assert result["confidence"] == 0.75

    def test_score_converti_en_int(self):
        opp = opportunite_valide(score="12.7")
        result = normalize_opportunity(opp)
        assert isinstance(result["score"], int)
        assert result["score"] == 12

    def test_organizer_plateforme_remplace_par_employeur_url(self):
        opp = opportunite_valide(
            organizer="Codeko",
            url="https://codeko.tech/jobs/altiora-developer",
        )
        result = normalize_opportunity(opp)
        # L'organizer plateforme doit être remplacé par le nom extrait de l'URL
        assert result["organizer"] != "Codeko"

    def test_organizer_non_plateforme_non_modifie(self):
        opp = opportunite_valide(organizer="Cabinet Conseils RH")
        result = normalize_opportunity(opp)
        assert result["organizer"] == "Cabinet Conseils RH"


# ──────────────────────────────────────────────
# _extract_employer_from_url
# ──────────────────────────────────────────────

class TestExtractEmployeurDepuisUrl:
    def test_portaljob(self):
        url = "https://portaljob-madagascar.com/emploi/view/altiora-developer-python"
        result = _extract_employer_from_url(url)
        assert result is not None
        assert "Altiora" in result

    def test_job2mada(self):
        url = "https://job2mada.com/jobs/entreprise-abc-fullstack"
        result = _extract_employer_from_url(url)
        assert result is not None

    def test_codeko(self):
        url = "https://codeko.tech/jobs/societe-xyz-developpeur"
        result = _extract_employer_from_url(url)
        assert result is not None

    def test_asako(self):
        url = "https://asako.mg/annonces/123-cabinet-conseil-developer"
        result = _extract_employer_from_url(url)
        assert result is not None

    def test_url_inconnue_retourne_none(self):
        assert _extract_employer_from_url("https://linkedin.com/jobs/123") is None

    def test_url_vide_retourne_none(self):
        assert _extract_employer_from_url("") is None

    def test_url_none_retourne_none(self):
        assert _extract_employer_from_url(None) is None


# ──────────────────────────────────────────────
# deduplicate
# ──────────────────────────────────────────────

class TestDeduplicate:
    def test_liste_vide(self):
        assert deduplicate([]) == []

    def test_sans_doublon(self):
        opps = [
            {"url": "http://a.com", "title": "Offre A"},
            {"url": "http://b.com", "title": "Offre B"},
        ]
        assert len(deduplicate(opps)) == 2

    def test_doublon_url(self):
        opps = [
            {"url": "http://a.com", "title": "Offre A"},
            {"url": "http://a.com", "title": "Offre A bis"},
        ]
        result = deduplicate(opps)
        assert len(result) == 1
        assert result[0]["title"] == "Offre A"

    def test_doublon_titre(self):
        opps = [
            {"url": "http://a.com", "title": "Développeur Python"},
            {"url": "http://b.com", "title": "Développeur Python"},
        ]
        result = deduplicate(opps)
        assert len(result) == 1

    def test_doublon_titre_casse_differente(self):
        opps = [
            {"url": "http://a.com", "title": "DÉVELOPPEUR PYTHON"},
            {"url": "http://b.com", "title": "développeur python"},
        ]
        result = deduplicate(opps)
        assert len(result) == 1

    def test_conserve_ordre_premier_vu(self):
        opps = [
            {"url": "http://a.com", "title": "Premier"},
            {"url": "http://b.com", "title": "Deuxième"},
            {"url": "http://a.com", "title": "Doublon du premier"},
        ]
        result = deduplicate(opps)
        assert len(result) == 2
        assert result[0]["title"] == "Premier"


# ──────────────────────────────────────────────
# validate_against_schema
# ──────────────────────────────────────────────

class TestValidateAgainstSchema:
    def test_bypass_gracieux_si_champ_manquant(self):
        """Si la validation Pydantic échoue, l'opportunité est retournée telle quelle."""
        opp = {"title": "Offre incomplète"}  # champs obligatoires manquants
        result = validate_against_schema(opp)
        # Bypass gracieux : retourne quand même le dict
        assert result is not None
        assert result["title"] == "Offre incomplète"

    def test_retourne_dict_model_dump_si_valide(self):
        """Une opportunité complète est validée et retournée comme dict."""
        opp = {
            "title": "Développeur Python",
            "summary": "Nous recrutons.",
            "url": "https://codeko.tech/jobs/dev",
            "source": "codeko",
            "organizer": "Société ABC",
            "opportunity_type": "emploi",
            "domain": "informatique",
            "score": 15,
            "confidence": 0.8,
            "is_actionable": True,
            "budget": "Non précisé",
            "deadline": None,
            "source_site": "codeko.tech",
            "source_priority": None,
            "flags": [],
        }
        result = validate_against_schema(opp)
        assert result is not None
        assert result["title"] == "Développeur Python"


# ──────────────────────────────────────────────
# fallback_response
# ──────────────────────────────────────────────

class TestFallbackResponse:
    def test_structure_retournee(self):
        result = fallback_response([{"a": 1}, {"b": 2}])
        assert result["opportunities"] == []
        assert result["total"] == 0
        assert result["status"] == "degraded"
        assert result["statistics"]["raw_results"] == 2
        assert result["statistics"]["final"] == 0

    def test_liste_vide(self):
        result = fallback_response([])
        assert result["statistics"]["raw_results"] == 0


# ──────────────────────────────────────────────
# _flag_ambiguous_organizer
# ──────────────────────────────────────────────

class TestFlagAmbiguousOrganizer:
    def test_ajoute_flag_si_source_egal_organizer_et_plateforme(self):
        # "recrute" et "hiring" sont exclus par la logique → utiliser un source
        # qui contient le nom de la plateforme sans ces mots-clés
        opp = {
            "source": "asako.mg",
            "organizer": "asako.mg",
            "source_site": "asako.mg",
            "title": "Offre data scientist",
        }
        _flag_ambiguous_organizer(opp)
        assert "organizer_unclear" in opp.get("flags", [])

    def test_pas_de_flag_si_source_vide(self):
        opp = {"source": "", "organizer": "Société", "source_site": "", "title": "Offre"}
        _flag_ambiguous_organizer(opp)
        assert opp.get("flags", []) == []

    def test_pas_de_flag_si_hiring_dans_source(self):
        opp = {
            "source": "linkedin hiring",
            "organizer": "linkedin hiring",
            "source_site": "linkedin",
            "title": "Offre",
        }
        _flag_ambiguous_organizer(opp)
        assert opp.get("flags", []) == []
