import sqlite3

from core.indexer import index_all
from core.search_api import search
from test.conftest import _make_pdf
# from test.conftest import _make_pdf


def test_fts5_available():
    cx = sqlite3.connect(":memory:")
    cx.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
    cx.close()

def test_rigid_pipeline_index_then_search(rig):
    # 1) indexeer alles
    index_all()

    # 2) zoek op PCR (moet doc1 raken)
    hits = search("PCR", limit=10)
    assert len(hits) >= 1
    assert any("doc1.pdf" in h["path"] for h in hits)

    # 3) synonyms: "quality control" => QC tag verwacht in doc1
    doc1 = next(h for h in hits if "doc1.pdf" in h["path"])
    assert "QC" in (doc1.get("tags") or "")

    # 4) pattern extractie: project + sample moeten er zijn (na fix in tagger.py)
    assert "PRJ-2026-01" in (doc1.get("project_codes") or "")
    assert "SMP1234" in (doc1.get("sample_ids") or "")


def test_non_recursive_scope(rig):
    # maak subfolder met pdf
    sub = rig["docs"] / "sub"
    sub.mkdir()
    _make_pdf(sub / "hidden.pdf", "PCR should NOT be indexed")

    index_all()
    hits = search("hidden")
    assert len(hits) == 0 