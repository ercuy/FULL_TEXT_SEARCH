# =====================================================================
# BEGIN file: core/tagger.py
# =====================================================================
import re
from typing import Dict, Any, List

from .config import load_settings


def normalize_text(text: str) -> str:
    return text.lower()


def extract_tags(text: str) -> List[str]:
    """
    Regelgebaseerde tag-extractie op basis van vocabularium en synoniemen.
    """
    settings = load_settings()
    vocab = [v.lower() for v in settings.tags.vocabulary]
    synonyms = {k.lower(): v for k, v in settings.tags.synonyms.items()}

    norm = normalize_text(text)
    found = set()

    # Synoniemen eerst
    for syn, canonical in synonyms.items():
        if syn in norm:
            found.add(canonical)

    # Vocabulaire
    for term in vocab:
        if term in norm:
            # Gebruik originele vorm uit vocabularium
            for original in settings.tags.vocabulary:
                if original.lower() == term:
                    found.add(original)
                    break

    # Beperk aantal tags
    tags = sorted(found)
    return tags[: settings.tags.max_tags_per_document]


# def extract_patterns(text: str) -> Dict[str, Any]:
#     """
#     Regex-gebaseerde extractie van projectcodes, sample-ID's, datums.
#     """
#     settings = load_settings()
#     patterns = {
#         "project_code": settings.patterns.project_code,
#         "sample_id": settings.patterns.sample_id,
#         "date": settings.patterns.date,
#     }

#     result: Dict[str, Any] = {}
#     for key, pattern in patterns.items():
#         matches = re.findall(pattern, text)
#         if matches:
#             # Uniek maken, maar volgorde behouden
#             seen = set()
#             unique = []
#             for m in matches:
#                 val = m if isinstance(m, str) else m[0]
#                 if val not in seen:
#                     seen.add(val)
#                     unique.append(val)
#             result[key] = unique
#     return result



# core/tagger.py (PATCH: fix vroegtijdige return)
def extract_patterns(text: str) -> Dict[str, Any]:
    settings = load_settings()
    patterns = {
        "project_code": settings.patterns.project_code,
        "sample_id": settings.patterns.sample_id,
        "date": settings.patterns.date,
    }

    result: Dict[str, Any] = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            seen = set()
            unique = []
            for m in matches:
                val = m if isinstance(m, str) else m[0]
                if val not in seen:
                    seen.add(val)
                    unique.append(val)
            result[key] = unique

    return result