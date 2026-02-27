# =====================================================================
# BEGIN file: core/scanner.py
# =====================================================================
import os
import shutil
from typing import Iterator, Dict, Any, List

from .config import load_settings
from .extractor import extract_text_basic, has_text_objects


def iter_files(root_locations: List[str], allowed_extensions: List[str]) -> Iterator[str]:
    for root in root_locations:
        if not os.path.exists(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                ext = os.path.splitext(name)[1].lower().lstrip(".")
                if ext in allowed_extensions:
                    yield os.path.join(dirpath, name)


def is_scanned_pdf(path: str, settings) -> bool:
    """
    Detecteer gescande PDF's op basis van:
    - tekstlengte
    - aanwezigheid van tekstobjecten/fonts
    """
    text = extract_text_basic(path, max_chars=2000)
    if settings.file_handling.detect_scanned_pdf.get("check_text_length", True):
        if len(text.strip()) < settings.file_handling.min_text_length:
            # Verdacht weinig tekst
            # Extra check op objectstructuur
            if settings.file_handling.detect_scanned_pdf.get("check_fonts", True) or \
               settings.file_handling.detect_scanned_pdf.get("check_xobjects", True):
                if not has_text_objects(path):
                    return True
    return False


def scan_and_classify() -> Iterator[Dict[str, Any]]:
    """
    Generator die alle PDF's doorloopt, gescande PDF's verplaatst,
    en digitale PDF's teruggeeft met basismetadata.
    """
    settings = load_settings()
    os.makedirs(settings.paths.scanned_folder, exist_ok=True)

    for path in iter_files(settings.paths.root_locations,
                           settings.file_handling.allowed_extensions):
        try:
            if is_scanned_pdf(path, settings):
                # Verplaats naar gescand-folder
                rel = os.path.relpath(path, start=settings.paths.root_locations[0])
                target = os.path.join(settings.paths.scanned_folder, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.move(path, target)
                print(f"[SCAN] Moved scanned PDF to {target}")
                continue

            stat = os.stat(path)
            yield {
                "path": path,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "ctime": stat.st_ctime,
            }
        except Exception as e:
            print(f"[SCAN][ERROR] {path}: {e}")