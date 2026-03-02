import os
from pathlib import Path
from reportlab.pdfgen import canvas

from core.indexer import index_all
from core.search_api import search


def make_pdf(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    y = 800
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 14
    c.save()


def test_full_pipeline():
    # 1. Testdocumenten maken
    base = Path("C:/TEMP/fts_testdocs")
    make_pdf(base / "doc1.pdf",
             "PCR calibratie\nPRJ-2026-01\nSMP1234\n2026-02-27\nquality control report")
    make_pdf(base / "doc2.pdf",
             "ISO audit procedure\nrapport toestel\nPRJ-2026-02\nSMP9999\n27/02/2026")

    # 2. Index bouwen
    index_all()

    # 3. Zoeken
    results = search("PCR")

    # 4. Verwachtingen (DIT IS DE TEST)
    assert len(results) > 0
    assert any("doc1.pdf" in r["path"] for r in results)


def test_metadata_quality(rig):
    index_all()
    hits = search("PCR")
    doc = hits[0]

    assert doc["title"]
    assert doc["summary"]
    assert isinstance(doc["tags"], str)
    assert "PRJ-2026-01" in (doc.get("project_codes") or "")
    assert "SMP1234" in (doc.get("sample_ids") or "")