# =====================================================================
# BEGIN file: core/search_api.py
# =====================================================================
# from typing import List, Dict, Any

# import sqlite3

# from .config import load_settings


# def _connect() -> sqlite3.Connection:
#     settings = load_settings()
#     conn = sqlite3.connect(settings.paths.index_db)
#     conn.row_factory = sqlite3.Row
#     return conn


# def search(query: str, limit: int = 50) -> List[Dict[str, Any]]:
#     """
#     Full-text search via FTS5 + ophalen metadata.
#     """
#     settings = load_settings()
#     limit = min(limit, settings.ui.max_results)

#     conn = _connect()
#     try:
#         cur = conn.cursor()
#         cur.execute(
#             """
#             SELECT f.id, f.path, f.title, f.tags, f.summary, f.dates,
#                    f.project_codes, f.sample_ids
#             FROM files f
#             JOIN files_fts ft ON f.id = ft.rowid
#             WHERE files_fts MATCH ?
#             ORDER BY rank
#             LIMIT ?
#             """,
#             (query, limit),
#         )
#         rows = cur.fetchall()
#         return [dict(r) for r in rows]
#     finally:
#         conn.close()

# core/search_api.py  (PATCH)
from typing import List, Dict, Any
import sqlite3
from .config import load_settings

def _connect() -> sqlite3.Connection:
    settings = load_settings()
    conn = sqlite3.connect(settings.paths.index_db)
    conn.row_factory = sqlite3.Row
    return conn

def search(query: str, limit: int = 500) -> List[Dict[str, Any]]:
    settings = load_settings()
    limit = min(limit, settings.ui.max_results)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT f.id, f.path, f.title, f.tags, f.summary, f.dates,
                f.project_codes, f.sample_ids,
                bm25(files_fts) AS score
            FROM files AS f
            JOIN files_fts AS ft ON f.id = ft.rowid
            WHERE files_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, limit),
    )
        # cur.execute(
        #     """
        #     SELECT f.id, f.path, f.title, f.tags, f.summary, f.dates,
        #            f.project_codes, f.sample_ids,
        #            bm25(ft) AS score
        #     FROM files f
        #     JOIN files_fts ft ON f.id = ft.rowid
        #     WHERE ft MATCH ?
        #     ORDER BY score
        #     LIMIT ?
        #     """,
        #     (query, limit),
        # )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_document(doc_id: int) -> Dict[str, Any]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, path, title, tags, summary, dates,
                   project_codes, sample_ids
            FROM files
            WHERE id = ?
            """,
            (doc_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()