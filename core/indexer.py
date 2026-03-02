# =====================================================================
# BEGIN file: core/indexer.py
# =====================================================================

# =====================================================================
# FILE: core/indexer.py
# =====================================================================

import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, Any, List

from .config import load_settings
from .scanner import scan_and_classify
from .extractor import extract_text_basic
from .tagger import extract_tags, extract_patterns
from .summarizer import summarize_with_language


# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------
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
    summary TEXT,
    search_text TEXT
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


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _connect_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """
    Zorgt dat een kolom bestaat (migratie-proof).
    - We checken PRAGMA table_info.
    - Als de kolom ontbreekt, voeren we 1x ALTER TABLE uit.
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(ddl)
        conn.commit()


def _make_search_text(raw_text: str, max_words: int = 400) -> str:
    """
    Maak een zoek-anker tekst (deterministisch):
    - enkel woorden met letters (geen cijfers)
    - minimum 3 letters
    - lowercased
    - capped op max_words
    Waarom: betere recall/precision dan 'summary' voor FTS.
    """
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", raw_text)
    tokens = [t.lower() for t in tokens][:max_words]
    return " ".join(tokens)


# ---------------------------------------------------------------------
# Init DB
# ---------------------------------------------------------------------
def init_db() -> None:
    settings = load_settings()
    conn = _connect_db(settings.paths.index_db)
    with conn:
        conn.execute(SCHEMA_METADATA)
        if settings.indexing.fts5_enabled:
            conn.execute(SCHEMA_FTS)

        # Migratie voor bestaande DB's (als search_text kolom nog ontbreekt)
        _ensure_column(
            conn,
            table="files",
            column="search_text",
            ddl="ALTER TABLE files ADD COLUMN search_text TEXT",
        )

    conn.close()
    print("[INDEX] Database initialized")


# ---------------------------------------------------------------------
# Upsert metadata
# ---------------------------------------------------------------------
def _upsert_file(conn: sqlite3.Connection, record: Dict[str, Any]) -> int:
    """
    Upsert in metadata-tabel, retourneer id.
    Belangrijk: search_text wordt ook bewaard (handig voor inspectie/debug).
    """
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO files (
            path, size, mtime, ctime, title, tags,
            project_codes, sample_ids, dates, summary, search_text
        )
        VALUES (
            :path, :size, :mtime, :ctime, :title, :tags,
            :project_codes, :sample_ids, :dates, :summary, :search_text
        )
        ON CONFLICT(path) DO UPDATE SET
            size=excluded.size,
            mtime=excluded.mtime,
            ctime=excluded.ctime,
            title=excluded.title,
            tags=excluded.tags,
            project_codes=excluded.project_codes,
            sample_ids=excluded.sample_ids,
            dates=excluded.dates,
            summary=excluded.summary,
            search_text=excluded.search_text
        """,
        record,
    )
    conn.commit()

    row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------
# Update FTS (portable)
# ---------------------------------------------------------------------
def _update_fts(conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
    """
    Update FTS5 row voor dit document.
    We gebruiken hier bewust:
    - DELETE FROM files_fts WHERE rowid=?
    - INSERT INTO files_fts(...)
    Dit is het meest portable en voorkomt "SQL logic error" varianten.
    """
    row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
    if not row:
        return
    doc_id = row[0]

    conn.execute("DELETE FROM files_fts WHERE rowid = ?", (doc_id,))
    conn.execute(
        """
        INSERT INTO files_fts(rowid, content, tags, summary, path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            record["search_text"],
            record["tags"],
            record["summary"],
            record["path"],
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------
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

        # Titel: enkel bestandsnaam (zonder folder, zonder extensie)
        title = Path(path).stem

        tags = extract_tags(text)
        patterns = extract_patterns(text)
        summary = summarize_with_language(text, max_sentences=settings.summaries.max_sentences)

        search_text = _make_search_text(text, max_words=400)

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
            "search_text": search_text,
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


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    index_all()

# # =====================================================================
# # BEGIN file: core/indexer.py
# # =====================================================================

# # =====================================================================
# # FILE: core/indexer.py
# # =====================================================================

# import os
# import re
# import sqlite3
# from typing import Dict, Any, List

# from .config import load_settings
# from .scanner import scan_and_classify
# from .extractor import extract_text_basic, extract_title
# from .tagger import extract_tags, extract_patterns
# from .summarizer import summarize_with_language


# # ---------------------------------------------------------------------
# # Schema
# # ---------------------------------------------------------------------
# SCHEMA_METADATA = """
# CREATE TABLE IF NOT EXISTS files (
#     id INTEGER PRIMARY KEY,
#     path TEXT UNIQUE NOT NULL,
#     size INTEGER,
#     mtime REAL,
#     ctime REAL,
#     title TEXT,
#     tags TEXT,
#     project_codes TEXT,
#     sample_ids TEXT,
#     dates TEXT,
#     summary TEXT,
#     search_text TEXT
# );
# """

# SCHEMA_FTS = """
# CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
# USING fts5(
#     content,
#     tags,
#     summary,
#     path,
#     tokenize = "porter"
# );
# """


# # ---------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------
# def _connect_db(db_path: str) -> sqlite3.Connection:
#     os.makedirs(os.path.dirname(db_path), exist_ok=True)
#     conn = sqlite3.connect(db_path)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     conn.execute("PRAGMA synchronous=NORMAL;")
#     return conn


# def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
#     """
#     Zorgt dat een kolom bestaat (migratie-proof).
#     - We checken PRAGMA table_info.
#     - Als de kolom ontbreekt, voeren we 1x ALTER TABLE uit.
#     """
#     cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
#     if column not in cols:
#         conn.execute(ddl)
#         conn.commit()


# def _make_search_text(raw_text: str, max_words: int = 400) -> str:
#     """
#     Maak een zoek-anker tekst (deterministisch):
#     - enkel woorden met letters (geen cijfers)
#     - minimum 3 letters
#     - lowercased
#     - capped op max_words
#     Waarom: betere recall/precision dan 'summary' voor FTS.
#     """
#     tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", raw_text)
#     tokens = [t.lower() for t in tokens][:max_words]
#     return " ".join(tokens)


# # ---------------------------------------------------------------------
# # Init DB
# # ---------------------------------------------------------------------
# def init_db() -> None:
#     settings = load_settings()
#     conn = _connect_db(settings.paths.index_db)
#     with conn:
#         conn.execute(SCHEMA_METADATA)
#         if settings.indexing.fts5_enabled:
#             conn.execute(SCHEMA_FTS)

#         # Migratie voor bestaande DB's (als search_text kolom nog ontbreekt)
#         _ensure_column(
#             conn,
#             table="files",
#             column="search_text",
#             ddl="ALTER TABLE files ADD COLUMN search_text TEXT",
#         )

#     conn.close()
#     print("[INDEX] Database initialized")


# # ---------------------------------------------------------------------
# # Upsert metadata
# # ---------------------------------------------------------------------
# def _upsert_file(conn: sqlite3.Connection, record: Dict[str, Any]) -> int:
#     """
#     Upsert in metadata-tabel, retourneer id.
#     Belangrijk: search_text wordt ook bewaard (handig voor inspectie/debug).
#     """
#     cur = conn.cursor()
#     cur.execute(
#         """
#         INSERT INTO files (
#             path, size, mtime, ctime, title, tags,
#             project_codes, sample_ids, dates, summary, search_text
#         )
#         VALUES (
#             :path, :size, :mtime, :ctime, :title, :tags,
#             :project_codes, :sample_ids, :dates, :summary, :search_text
#         )
#         ON CONFLICT(path) DO UPDATE SET
#             size=excluded.size,
#             mtime=excluded.mtime,
#             ctime=excluded.ctime,
#             title=excluded.title,
#             tags=excluded.tags,
#             project_codes=excluded.project_codes,
#             sample_ids=excluded.sample_ids,
#             dates=excluded.dates,
#             summary=excluded.summary,
#             search_text=excluded.search_text
#         """,
#         record,
#     )
#     conn.commit()

#     row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
#     return row[0] if row else 0


# # ---------------------------------------------------------------------
# # Update FTS (portable)
# # ---------------------------------------------------------------------
# def _update_fts(conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
#     """
#     Update FTS5 row voor dit document.
#     We gebruiken hier bewust:
#     - DELETE FROM files_fts WHERE rowid=?
#     - INSERT INTO files_fts(...)
#     Dit is het meest portable en voorkomt "SQL logic error" varianten.
#     """
#     row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
#     if not row:
#         return
#     doc_id = row[0]

#     conn.execute("DELETE FROM files_fts WHERE rowid = ?", (doc_id,))
#     conn.execute(
#         """
#         INSERT INTO files_fts(rowid, content, tags, summary, path)
#         VALUES (?, ?, ?, ?, ?)
#         """,
#         (
#             doc_id,
#             record["search_text"],  # <-- hier zit de 'paar honderd woorden zonder cijfers'
#             record["tags"],
#             record["summary"],
#             record["path"],
#         ),
#     )
#     conn.commit()


# # ---------------------------------------------------------------------
# # Indexing
# # ---------------------------------------------------------------------
# def index_all() -> None:
#     settings = load_settings()
#     init_db()
#     conn = _connect_db(settings.paths.index_db)

#     batch: List[Dict[str, Any]] = []
#     batch_size = settings.indexing.batch_size

#     for meta in scan_and_classify():
#         path = meta["path"]
#         print(f"[INDEX] Processing {path}")

#         text = extract_text_basic(path)
#         if len(text.strip()) < settings.file_handling.min_text_length:
#             print(f"[INDEX][SKIP] Too little text in {path}")
#             continue

#         title = extract_title(text)
#         tags = extract_tags(text)
#         patterns = extract_patterns(text)
#         summary = summarize_with_language(text, max_sentences=settings.summaries.max_sentences)

#         search_text = _make_search_text(text, max_words=400)

#         record = {
#             "path": path,
#             "size": meta["size"],
#             "mtime": meta["mtime"],
#             "ctime": meta["ctime"],
#             "title": title,
#             "tags": ",".join(tags),
#             "project_codes": ",".join(patterns.get("project_code", [])),
#             "sample_ids": ",".join(patterns.get("sample_id", [])),
#             "dates": ",".join(patterns.get("date", [])),
#             "summary": summary,
#             "search_text": search_text,
#         }

#         batch.append(record)

#         if len(batch) >= batch_size:
#             _flush_batch(conn, batch, settings)
#             batch.clear()

#     if batch:
#         _flush_batch(conn, batch, settings)

#     conn.close()
#     print("[INDEX] Completed indexing")


# def _flush_batch(conn: sqlite3.Connection, batch: List[Dict[str, Any]], settings) -> None:
#     for rec in batch:
#         try:
#             _upsert_file(conn, rec)
#             if settings.indexing.fts5_enabled:
#                 _update_fts(conn, rec)
#         except Exception as e:
#             print(f"[INDEX][ERROR] {rec['path']}: {e}")


# # ---------------------------------------------------------------------
# # Entry point
# # ---------------------------------------------------------------------
# if __name__ == "__main__":
#     index_all()



# import os
# import sqlite3
# from typing import Dict, Any, List

# from .config import load_settings
# from .scanner import scan_and_classify
# from .extractor import extract_text_basic, extract_title
# from .tagger import extract_tags, extract_patterns
# from .summarizer import summarize_with_language


# SCHEMA_METADATA = """
# CREATE TABLE IF NOT EXISTS files (
#     id INTEGER PRIMARY KEY,
#     path TEXT UNIQUE NOT NULL,
#     size INTEGER,
#     mtime REAL,
#     ctime REAL,
#     title TEXT,
#     tags TEXT,
#     project_codes TEXT,
#     sample_ids TEXT,
#     dates TEXT,
#     summary TEXT
# );
# """

# SCHEMA_FTS = """
# CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
# USING fts5(
#     content,
#     tags,
#     summary,
#     path,
#     tokenize = "porter"
# );
# """


# def _connect_db(db_path: str) -> sqlite3.Connection:
#     os.makedirs(os.path.dirname(db_path), exist_ok=True)
#     conn = sqlite3.connect(db_path)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     conn.execute("PRAGMA synchronous=NORMAL;")
#     return conn


# def init_db() -> None:
#     settings = load_settings()
#     conn = _connect_db(settings.paths.index_db)
#     with conn:
#         conn.execute(SCHEMA_METADATA)
#         if settings.indexing.fts5_enabled:
#             conn.execute(SCHEMA_FTS)
#     conn.close()
#     print("[INDEX] Database initialized")


# def _upsert_file(conn: sqlite3.Connection, record: Dict[str, Any]) -> int:
#     """
#     Upsert in metadata-tabel, retourneer id.
#     """
#     cur = conn.cursor()
#     cur.execute(
#         """
#         INSERT INTO files (path, size, mtime, ctime, title, tags,
#                            project_codes, sample_ids, dates, summary)
#         VALUES (:path, :size, :mtime, :ctime, :title, :tags,
#                 :project_codes, :sample_ids, :dates, :summary)
#         ON CONFLICT(path) DO UPDATE SET
#             size=excluded.size,
#             mtime=excluded.mtime,
#             ctime=excluded.ctime,
#             title=excluded.title,
#             tags=excluded.tags,
#             project_codes=excluded.project_codes,
#             sample_ids=excluded.sample_ids,
#             dates=excluded.dates,
#             summary=excluded.summary
#         """,
#         record,
#     )
#     conn.commit()
#     return cur.lastrowid or cur.execute(
#         "SELECT id FROM files WHERE path = ?", (record["path"],)
#     ).fetchone()[0]


# # core/indexer.py  (PATCH: vervang _update_fts)
# def _update_fts(conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
#     # haal id uit metadata-table
#     row = conn.execute("SELECT id FROM files WHERE path = ?", (record["path"],)).fetchone()
#     if not row:
#         return
#     doc_id = row[0]

#     # 1) verwijder bestaande entry (portable)
#     conn.execute("DELETE FROM files_fts WHERE rowid = ?", (doc_id,))

#     # 2) insert nieuwe content
#     conn.execute(
#         """
#         INSERT INTO files_fts(rowid, content, tags, summary, path)
#         VALUES (?, ?, ?, ?, ?)
#         """,
#         (doc_id, record["content"], record["tags"], record["summary"], record["path"]),
#     )
#     conn.commit()


# def index_all() -> None:
#     settings = load_settings()
#     init_db()
#     conn = _connect_db(settings.paths.index_db)

#     batch: List[Dict[str, Any]] = []
#     batch_size = settings.indexing.batch_size

#     for meta in scan_and_classify():
#         path = meta["path"]
#         print(f"[INDEX] Processing {path}")
#         text = extract_text_basic(path)
#         if len(text.strip()) < settings.file_handling.min_text_length:
#             print(f"[INDEX][SKIP] Too little text in {path}")
#             continue

#         title = extract_title(text)
#         tags = extract_tags(text)
#         patterns = extract_patterns(text)
#         summary = summarize_with_language(text, max_sentences=settings.summaries.max_sentences)

#         record = {
#             "path": path,
#             "size": meta["size"],
#             "mtime": meta["mtime"],
#             "ctime": meta["ctime"],
#             "title": title,
#             "tags": ",".join(tags),
#             "project_codes": ",".join(patterns.get("project_code", [])),
#             "sample_ids": ",".join(patterns.get("sample_id", [])),
#             "dates": ",".join(patterns.get("date", [])),
#             "summary": summary,
#             "content": text,
#         }

#         batch.append(record)

#         if len(batch) >= batch_size:
#             _flush_batch(conn, batch, settings)
#             batch.clear()

#     if batch:
#         _flush_batch(conn, batch, settings)

#     conn.close()
#     print("[INDEX] Completed indexing")


# def _flush_batch(conn: sqlite3.Connection, batch: List[Dict[str, Any]], settings) -> None:
#     for rec in batch:
#         try:
#             _upsert_file(conn, rec)
#             if settings.indexing.fts5_enabled:
#                 _update_fts(conn, rec)
#         except Exception as e:
#             print(f"[INDEX][ERROR] {rec['path']}: {e}")




# if __name__ == "__main__":
#     index_all()