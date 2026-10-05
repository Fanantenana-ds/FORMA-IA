import re


def repair_json(raw: str) -> str:
    """
    Nettoie une réponse LLM pour en extraire un JSON valide.

    - Retire les blocs ```json ... ```
    - Supprime les caractères avant { ou [
    - Supprime les caractères après } ou ]
    - Gère les listes et les objets
    """
    if not raw:
        return raw
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```\s*$", "", raw)
    raw = raw.replace("\\'", "'").replace("\\/", "/")
    start = raw.find("{")
    if start == -1:
        start = raw.find("[")
    if start > 0:
        raw = raw[start:]
    last_brace = raw.rfind("}")
    last_bracket = raw.rfind("]")
    end = max(last_brace, last_bracket)
    if end > 0:
        raw = raw[:end + 1]
    return raw
