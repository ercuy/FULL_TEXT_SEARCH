# =====================================================================
# BEGIN file: core/extractor.py
# =====================================================================
from typing import Optional
import re

import pypdf


def extract_text_basic(path: str, max_chars: Optional[int] = None) -> str:
    """
    Eenvoudige tekstextractie uit PDF.
    Audit-proof: geen stille fouten, altijd string terug.
    """
    try:
        reader = pypdf.PdfReader(path)
        texts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            texts.append(t)
            if max_chars is not None and sum(len(x) for x in texts) >= max_chars:
                break
        result = "\n".join(texts)
        if max_chars is not None:
            return result[:max_chars]
        return result
    except Exception as e:
        print(f"[EXTRACT][ERROR] {path}: {e}")
        return ""


def has_text_objects(path: str) -> bool:
    """
    Heuristiek: controleer of er tekstobjecten/fonts aanwezig zijn.
    Voor eenvoud: als extract_text_basic > 0, beschouwen we als tekst-PDF.
    Voor meer diepgang kan PyMuPDF gebruikt worden, maar hier houden we het compact.
    """
    text = extract_text_basic(path, max_chars=500)
    return len(text.strip()) > 0


def detect_language(text: str) -> str:
    """
    Zeer eenvoudige taalheuristiek NL/EN.
    Voor echte detectie kan langdetect gebruikt worden, maar we houden het licht.
    """
    nl_markers = ["de ", "het ", "een ", "rapport", "kalibratie", "kalibreren", "monster"]
    en_markers = ["the ", "report", "calibration", "sample", "quality"]

    nl_score = sum(text.lower().count(m) for m in nl_markers)
    en_score = sum(text.lower().count(m) for m in en_markers)

    if nl_score >= en_score:
        return "nl"
    return "en"


def extract_title(text: str) -> str:
    """
    Neem de eerste niet-lege regel als titel.
    """
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""