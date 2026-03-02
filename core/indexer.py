# =====================================================================
# BEGIN file: core/indexer.py
# =====================================================================
import os
import sqlite3
from typing import Dict, Any, List

from .config import load_settings
from .scanner import scan_and_classify
from .extractor import extract_text_basic, extract_title
from .tagger import extract_tags, extract_patterns
from .summarizer import summarize_with_language


SCHEMA_METADATA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    size INTEGER,
    mtime REAL,
    ctime REAL,
    title TEXT,
    tags TEXT,
    project_codes TEXT,
    sample_ids TEXT,
    dates TEXT,
    summary TEXT
);
"""

SCHEMA_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
USING fts5(
    content,
    tags,
    summary,
    path,
    tokenize = "porter"
);
"""


def _connect_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    settings = load_settings()
    conn = _connect_db(settings.paths.index_db)
    with conn:
        conn.execute(SCHEMA_METADATA)
        if settings.indexing.fts5_enabled:
            conn.execute(SCHEMA_FTS)
    conn.close()
    print("[INDEX] Database initialized")


def _upsert_file(conn: sqlite3.Connection, record: Dict[str, Any]) -> int:
    """
    Upsert in metadata-tabel, retourneer id.
    """
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO files (path, size, mtime, ctime, title, tags,
                           project_codes, sample_ids, dates, summary)
        VALUES (:path, :size, :mtime, :ctime, :title, :tags,
                :project_codes, :sample_ids, :dates, :summary)
        ON CONFLICT(path) DO UPDATE SET
            size=excluded.size,
            mtime=excluded.mtime,
            ctime=excluded.ctime,
            title=excluded.title,
            tags=excluded.tags,
            project_codes=excluded.project_codes,
            sample_ids=excluded.sample_ids,
            dates=excluded.dates,
            summary=excluded.summary
        """,
        record,
    )
    conn.commit()
    return cur.lastrowid or cur.execute(
        "SELECT id FROM files WHERE path = ?", (record["path"],)
    ).fetchone()[0]


# def _update_fts(conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
#     conn.execute(
#         """
#         INSERT INTO files_fts (rowid, content, tags, summary, path)
#         VALUES (
#             (SELECT id FROM files WHERE path = :path),
#             :content,
#             :tags,
#             :summary,
#             :path
#         )
#         ON CONFLICT(rowid) DO UPDATE SET
#             content=excluded.content,
#             tags=excluded.tags,
#             summary=excluded.summary,
#             path=excluded.path
#         """,
#         record,
#     )
#     conn.commit()

# core/indexer.py  (PATCH: vervang _update_fts)
def _update_fts(conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
    # haal id uit metadata-table
    row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
    if not row:
        return
    doc_id = row[0]

    # delete bestaande FTS-row (FTS5 command)
    conn.execute("INSERT INTO files_fts(files_fts, rowid) VALUES('delete', ?)", (doc_id,))

    # insert nieuwe content
    conn.execute(
        """
        INSERT INTO files_fts(rowid, content, tags, summary, path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (doc_id, record["content"], record["tags"], record["summary"], record["path"]),
    )
    conn.commit()


def index_all() -> None:
    settings = load_settings()
    init_db()
    conn = _connect_db(settings.paths.index_db)

    batch: List[Dict[str, Any]] = []
    batch_size = settings.indexing.batch_size

    for meta in scan_and_classify():
        path = meta["path"]
        print(f"[INDEX] Processing {path}")
        text = extract_text_basic(path)
        if len(text.strip()) < settings.file_handling.min_text_length:
            print(f"[INDEX][SKIP] Too little text in {path}")
            continue

        title = extract_title(text)
        tags = extract_tags(text)
        patterns = extract_patterns(text)
        summary = summarize_with_language(text, max_sentences=settings.summaries.max_sentences)

        record = {
            "path": path,
            "size": meta["size"],
            "mtime": meta["mtime"],
            "ctime": meta["ctime"],
            "title": title,
            "tags": ",".join(tags),
            "project_codes": ",".join(patterns.get("project_code", [])),
            "sample_ids": ",".join(patterns.get("sample_id", [])),
            "dates": ",".join(patterns.get("date", [])),
            "summary": summary,
            "content": text,
        }

        batch.append(record)

        if len(batch) >= batch_size:
            _flush_batch(conn, batch, settings)
            batch.clear()

    if batch:
        _flush_batch(conn, batch, settings)

    conn.close()
    print("[INDEX] Completed indexing")


def _flush_batch(conn: sqlite3.Connection, batch: List[Dict[str, Any]], settings) -> None:
    for rec in batch:
        try:
            _upsert_file(conn, rec)
            if settings.indexing.fts5_enabled:
                _update_fts(conn, rec)
        except Exception as e:
            print(f"[INDEX][ERROR] {rec['path']}: {e}")