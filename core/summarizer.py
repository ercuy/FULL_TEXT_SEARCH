# =====================================================================
# BEGIN file: core/summarizer.py
# =====================================================================
from typing import List

from .extractor import detect_language


def _split_sentences(text: str) -> List[str]:
    """
    Zeer eenvoudige zinssegmentatie.
    Genoeg voor technische rapporten.
    """
    raw = text.replace("\n", " ")
    parts = [p.strip() for p in raw.split(".") if p.strip()]
    return [p + "." for p in parts]


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Extractieve samenvatting: neem de eerste zinnen die inhoudelijk lijken.
    Geen AI, volledig deterministisch.
    """
    if not text.strip():
        return ""

    sentences = _split_sentences(text)
    if not sentences:
        return ""

    # Eenvoudige heuristiek: neem de eerste zinnen die langer zijn dan X
    filtered = [s for s in sentences if len(s) > 40]
    if not filtered:
        filtered = sentences

    summary = " ".join(filtered[:max_sentences])
    return summary


def summarize_with_language(text: str, max_sentences: int = 3) -> str:
    """
    Voor nu: zelfde samenvatting, taal alleen relevant voor eventuele toekomstige AI.
    """
    _ = detect_language(text)
    return summarize_text(text, max_sentences=max_sentences)