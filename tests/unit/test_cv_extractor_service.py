# tests/unit/test_cv_extractor_service.py
# ============================================================
# Tests unitaires — CvExtractorService
# ============================================================

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rh.cv_extractor_service import (
    MethodeExtraction,
    SEUIL_TEXTE_MIN,
    _texte_brut,
    _docx,
    extraire_texte_cv,
)

# =============================================================================
# HELPERS
# =============================================================================

TEXTE_SUFFISANT = "A" * (SEUIL_TEXTE_MIN + 50)
TEXTE_COURT = "A" * 10


def _mock_llm_lisible(lisible: bool):
    """Patch _valider_lisibilite pour retourner lisible ou non."""
    return patch(
        "app.services.rh.cv_extractor_service._valider_lisibilite",
        new=AsyncMock(return_value=lisible),
    )


# =============================================================================
# TEXTE BRUT
# =============================================================================

class TestTextebrut:
    def test_utf8(self):
        contenu = "Jean Dupont développeur".encode("utf-8")
        assert "Jean Dupont" in _texte_brut(contenu)

    def test_latin1(self):
        contenu = "Expérience formateur".encode("latin-1")
        assert "formateur" in _texte_brut(contenu)

    def test_vide(self):
        assert _texte_brut(b"") == ""


# =============================================================================
# EXTRACTION TXT
# =============================================================================

class TestExtractionTxt:
    @pytest.mark.asyncio
    async def test_txt_lisible(self):
        contenu = TEXTE_SUFFISANT.encode("utf-8")
        with _mock_llm_lisible(True):
            texte, methode, lisible = await extraire_texte_cv(contenu, "cv.txt")
        assert methode == MethodeExtraction.TEXTE_BRUT
        assert lisible is True
        assert len(texte) >= SEUIL_TEXTE_MIN

    @pytest.mark.asyncio
    async def test_txt_vide(self):
        texte, methode, lisible = await extraire_texte_cv(b"", "cv.txt")
        assert methode == MethodeExtraction.ECHEC
        assert lisible is False


# =============================================================================
# FORMAT NON SUPPORTÉ
# =============================================================================

class TestFormatInconnu:
    @pytest.mark.asyncio
    async def test_extension_inconnue(self):
        texte, methode, lisible = await extraire_texte_cv(b"data", "cv.xyz")
        assert methode == MethodeExtraction.ECHEC
        assert lisible is False
        assert "non supporté" in texte


# =============================================================================
# PDF — cascade
# =============================================================================

class TestExtractionPdf:
    @pytest.mark.asyncio
    async def test_pymupdf4llm_gagne_car_plus_long(self):
        """pymupdf4llm retourne plus de chars → il est sélectionné."""
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_SUFFISANT + "X"),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert methode == MethodeExtraction.PYMUPDF4LLM
        assert lisible is True

    @pytest.mark.asyncio
    async def test_pdfplumber_gagne_car_plus_long(self):
        """pdfplumber retourne plus de chars → il est sélectionné."""
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_SUFFISANT + "X"),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert methode == MethodeExtraction.PDFPLUMBER
        assert lisible is True

    @pytest.mark.asyncio
    async def test_fallback_tesseract_si_pdf_court(self):
        """Si pymupdf4llm + pdfplumber insuffisants → Tesseract."""
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_SUFFISANT),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert methode == MethodeExtraction.TESSERACT

    @pytest.mark.asyncio
    async def test_fallback_groq_vision_si_tesseract_court(self):
        """Si Tesseract insuffisant → Groq Vision."""
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._groq_vision", new=AsyncMock(return_value=TEXTE_SUFFISANT)),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert methode == MethodeExtraction.GROQ_VISION

    @pytest.mark.asyncio
    async def test_echec_total_pdf(self):
        """Toutes les méthodes retournent texte court → ECHEC."""
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._groq_vision", new=AsyncMock(return_value=TEXTE_COURT)),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert methode == MethodeExtraction.ECHEC
        assert lisible is False


# =============================================================================
# IMAGE
# =============================================================================

class TestExtractionImage:
    @pytest.mark.asyncio
    async def test_image_tesseract_suffisant(self):
        with (
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_SUFFISANT),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"\xff\xd8", "cv.jpg")
        assert methode == MethodeExtraction.TESSERACT
        assert lisible is True

    @pytest.mark.asyncio
    async def test_image_fallback_groq_vision(self):
        with (
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._groq_vision", new=AsyncMock(return_value=TEXTE_SUFFISANT)),
            _mock_llm_lisible(True),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"\xff\xd8", "cv.png")
        assert methode == MethodeExtraction.GROQ_VISION

    @pytest.mark.asyncio
    async def test_image_echec_total(self):
        with (
            patch("app.services.rh.cv_extractor_service._tesseract", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service._groq_vision", new=AsyncMock(return_value=TEXTE_COURT)),
        ):
            texte, methode, lisible = await extraire_texte_cv(b"\xff\xd8", "cv.jpg")
        assert methode == MethodeExtraction.ECHEC
        assert lisible is False


# =============================================================================
# VALIDATION LISIBILITÉ
# =============================================================================

class TestValidationLisibilite:
    @pytest.mark.asyncio
    async def test_texte_valide_marque_lisible(self):
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_SUFFISANT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            _mock_llm_lisible(True),
        ):
            _, _, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert lisible is True

    @pytest.mark.asyncio
    async def test_texte_invalide_marque_non_lisible(self):
        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_SUFFISANT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            _mock_llm_lisible(False),
        ):
            _, _, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert lisible is False

    @pytest.mark.asyncio
    async def test_erreur_llm_suppose_lisible(self):
        """Si la validation LLM plante → on suppose OUI pour ne pas bloquer."""
        import asyncio as _asyncio

        async def _to_thread_mock(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch("app.services.rh.cv_extractor_service._pymupdf4llm", return_value=TEXTE_SUFFISANT),
            patch("app.services.rh.cv_extractor_service._pdfplumber", return_value=TEXTE_COURT),
            patch("app.services.rh.cv_extractor_service.asyncio.to_thread", side_effect=_to_thread_mock),
            patch(
                "app.services.rh.cv_extractor_service._valider_lisibilite",
                new=AsyncMock(side_effect=Exception("LLM down")),
            ),
        ):
            _, _, lisible = await extraire_texte_cv(b"%PDF", "cv.pdf")
        assert lisible is True
