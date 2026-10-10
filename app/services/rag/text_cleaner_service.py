# app/services/rag/text_cleaner_service.py
# ============================================================
# SERVICE — Nettoyage du texte
# ============================================================

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


# Patterns de bruit
_NOISE_PATTERNS = [
    r"Page \d+ (sur|of) \d+",
    r"^\s*\d+\s*$",                    # Numéros seuls
    r"Confidentiel.*?\n",
    r"Tous droits réservés.*?\n",
    r"©.*?\n",
]


def clean_text(text: str) -> str:
    """
    Nettoie le texte brut extrait d'un document.
    """
    if not text:
        return ""
    
    original_len = len(text)
    
    # 1. Normalisation Unicode (NFC)
    text = unicodedata.normalize("NFC", text)
    
    # 2. Suppression des caractères de contrôle
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)
    
    # 3. Suppression des zero-width
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    
    # 4. Suppression du bruit
    for pattern in _NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    
    # 5. Espaces multiples → un seul
    text = re.sub(r"[ \t]+", " ", text)
    
    # 6. Sauts de ligne multiples → 2 max
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # 7. Trim final
    text = text.strip()
    
    logger.info(
        f"🧹 Nettoyage : {original_len} → {len(text)} chars "
        f"(-{original_len - len(text)})"
    )
    
    return text