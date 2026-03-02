import json
from pathlib import Path
import pytest

from reportlab.pdfgen import canvas


def make_pdf(path: Path, text: str) -> None:
    """Maak een kleine deterministische PDF met embedded tekst."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    y = 800
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 14
    c.save()


@pytest.fixture()
def rig(tmp_path):
    """
    Test rig:
    - Maakt tijdelijke PDF dataset (root-only, non-recursive)
    - Schrijft tijdelijke config/settings.json in project root
    - Herstelt originele settings.json na afloop (audit-proof voor je dev omgeving)
    """
    docs = tmp_path / "docs"
    scanned = tmp_path / "_gescand"
    db = tmp_path / "index.db"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    # 2 deterministische pdfs in ROOT (geen subfolders)
    make_pdf(
        docs / "doc1.pdf",
        "PCR calibratie\nPRJ-2026-01\nSMP1234\n2026-02-27\nquality control report",
    )
    make_pdf(
        docs / "doc2.pdf",
        "ISO audit procedure\nrapport toestel\nPRJ-2026-02\nSMP9999\n27/02/2026",
    )

    # tijdelijke settings.json in project/config
    cfg_dir = Path("config")
    cfg_dir.mkdir(exist_ok=True)
    cfg_path = cfg_dir / "settings.json"

    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None

    cfg = {
        "version": "1.0",
        "paths": {
            "root_locations": [str(docs)],
            "scanned_folder": str(scanned),
            "index_db": str(db),
            "log_folder": str(logs),
        },
        "file_handling": {
            "allowed_extensions": ["pdf"],
            "min_text_length": 20,
            "detect_scanned_pdf": {
                "check_text_length": True,
                "check_fonts": True,
                "check_xobjects": True,
            },
        },
        "tags": {
            "vocabulary": ["PCR", "QC", "calibratie", "audit", "ISO", "CO2", "sample", "project", "toestel", "procedure", "rapport"],
            "synonyms": {"quality control": "QC", "calibration": "calibratie", "instrument": "toestel", "report": "rapport"},
            "max_tags_per_document": 5,
        },
        "patterns": {
            "project_code": r"PRJ-[0-9]{4}-[0-9]{2}",
            "sample_id": r"SMP[0-9]{4}",
            "date": r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b",
        },
        "summaries": {"enabled": True, "max_sentences": 3, "use_ai_compression": False, "language_detection": True},
        "indexing": {"batch_size": 10, "fts5_enabled": True, "update_existing": True},
        "ui": {"type": "html", "preview_enabled": True, "filters_enabled": True, "max_results": 200},
    }

    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    yield {"docs": docs, "scanned": scanned, "db": db, "logs": logs}

    # restore settings.json
    if backup is None:
        try:
            cfg_path.unlink(missing_ok=True)
        except Exception:
            pass
    else:
        cfg_path.write_text(backup, encoding="utf-8")
