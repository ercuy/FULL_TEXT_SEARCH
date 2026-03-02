import sqlite3

from core.indexer import index_all
from core.search_api import search
from test.conftest import make_pdf


def test_fts5_available():
    cx = sqlite3.connect(":memory:")
    cx.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
    cx.close()


def test_index_then_search_basic(rig):
    """Happy path: indexeer PDF's in root en zoek op inhoud."""
    index_all()
    hits = search("PCR", limit=10)
    assert len(hits) >= 1
    assert any("doc1.pdf" in h["path"] for h in hits)


def test_metadata_quality_minimum(rig):
    """UX minimum: title + summary + tags + pattern-extractie."""
    index_all()
    hits = search("PCR", limit=10)
    assert hits, "Expected at least one hit for 'PCR'"

    doc = next(h for h in hits if "doc1.pdf" in h["path"])

    assert doc.get("title"), "title must not be empty"
    assert doc.get("summary"), "summary must not be empty"
    assert isinstance(doc.get("tags"), str), "tags must be a string"

    assert "QC" in (doc.get("tags") or ""), "synonym 'quality control' should yield tag QC"
    assert "PRJ-2026-01" in (doc.get("project_codes") or "")
    assert "SMP1234" in (doc.get("sample_ids") or "")


def test_non_recursive_scope(rig):
    """PDF in subfolder mag NIET geïndexeerd worden (non-recursive)."""
    sub = rig["docs"] / "sub"
    sub.mkdir()
    make_pdf(sub / "hidden.pdf", "HIDDEN_TOKEN")

    index_all()
    hits = search("HIDDEN_TOKEN", limit=10)
    assert len(hits) == 0


def test_exclusions(rig):
    """Excluded names mogen NIET geïndexeerd worden: ~$*.pdf, old_*.pdf, *_draft.pdf."""
    make_pdf(rig["docs"] / "~$temp.pdf", "EXCLUDED_TOKEN")
    make_pdf(rig["docs"] / "old_report.pdf", "EXCLUDED_TOKEN")
    make_pdf(rig["docs"] / "report_draft.pdf", "EXCLUDED_TOKEN")
    make_pdf(rig["docs"] / "valid.pdf", "VALID_TOKEN extra padding text zodat lengte > 20")
    # make_pdf(rig["docs"] / "valid.pdf", "VALID_TOKEN")

    index_all()

    hits_valid = search("VALID_TOKEN", limit=10)
    assert any("valid.pdf" in h["path"] for h in hits_valid)

    hits_excl = search("EXCLUDED_TOKEN", limit=50)
    assert len(hits_excl) == 0