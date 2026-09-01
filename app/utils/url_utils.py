# app/utils/url_utils.py
# ============================================================
# NORMALISATION D'URL — partagée par tavily_service et
# validation_service pour garantir une déduplication cohérente.
# ============================================================

import re
from typing import Any


def normalize_url(url: Any) -> str:
    """Nettoie une URL brute (markdown, chevrons, point final)."""

    if not url:
        return ""

    clean = str(url).strip()

    # Markdown : [https://site.com](https://site.com)
    markdown_match = re.match(r"^\[.*?\]\((https?://[^)]+)\)$", clean)

    if markdown_match:
        clean = markdown_match.group(1)

    clean = clean.strip("<>")

    return clean.rstrip(".")