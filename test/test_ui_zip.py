import io
import zipfile

from core.indexer import index_all
from ui.app import create_app


def test_zip_endpoint_happy_path(rig):
    """ZIP endpoint levert een zip met gekozen PDFs (max 25)."""
    index_all()
    app = create_app()
    client = app.test_client()

    files = [str(rig["docs"] / "doc1.pdf"), str(rig["docs"] / "doc2.pdf")]
    resp = client.post("/zip", json={"files": files})

    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"

    z = zipfile.ZipFile(io.BytesIO(resp.data))
    names = set(z.namelist())
    assert "doc1.pdf" in names
    assert "doc2.pdf" in names


def test_zip_enforces_limit(rig):
    app = create_app()
    client = app.test_client()

    files = [str(rig["docs"] / "doc1.pdf")] * 26
    resp = client.post("/zip", json={"files": files})
    assert resp.status_code == 400


def test_zip_rejects_outside_root(rig, tmp_path):
    """Pad buiten root_locations mag niet in zip belanden (whitelist)."""
    index_all()
    app = create_app()
    client = app.test_client()

    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    files = [str(rig["docs"] / "doc1.pdf"), str(outside)]
    resp = client.post("/zip", json={"files": files})

    assert resp.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(resp.data))
    names = set(z.namelist())

    assert "doc1.pdf" in names
    assert all("outside.pdf" not in n for n in names)
