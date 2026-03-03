# =====================================================================
# FILE: ui/app.py
# DROP-IN REPLACEMENT (FIXED: /help + proper Flask route converters)
# =====================================================================

from importlib.metadata import files
import os
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from flask import Flask, render_template, request, jsonify, send_file

from core.search_api import search, get_document
from core.config import load_settings


def _log(settings, msg: str) -> None:
    log_dir = Path(settings.paths.log_folder)
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "ui_server.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def _is_allowed_path(path: str, roots: List[str]) -> bool:
    """
    Whitelist check: file path must be inside one of the configured root_locations.
    """
    try:
        p = os.path.normcase(os.path.abspath(path))
        for root in roots:
            r = os.path.normcase(os.path.abspath(root))
            # commonpath throws if drives differ; handled by except
            if os.path.commonpath([p, r]) == r:
                return True
    except Exception:
        pass
    return False


def create_app() -> Flask:
    settings = load_settings()

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    # ------------------------------------------------------------
    # HELP (FTS5 Zoekhulp)
    # URL: http://127.0.0.1:5000/help
    # ------------------------------------------------------------
    @app.route("/help", methods=["GET"])
    def help_page():
        return render_template("help_fts.html")

    # ------------------------------------------------------------
    # SEARCH UI
    # ------------------------------------------------------------
    @app.route("/", methods=["GET"])
    def index():
        q = request.args.get("q", "").strip()
        results = search(q) if q else []
        if q:
            _log(settings, f"SEARCH q='{q}' results={len(results)}")
        return render_template("search.html", query=q, results=results)

    # ------------------------------------------------------------
    # DOCUMENT DETAIL
    # ------------------------------------------------------------
    @app.route("/doc/<int:doc_id>", methods=["GET"])
    def doc_detail(doc_id: int):
        doc = get_document(doc_id)
        if not doc:
            return "Document not found", 404
        return render_template("detail.html", doc=doc)

    # ------------------------------------------------------------
    # PDF OPEN (SERVER-SIDE, ROBUST)
    # ------------------------------------------------------------
    @app.route("/pdf/<int:doc_id>", methods=["GET"])
    def open_pdf(doc_id: int):
        doc = get_document(doc_id)
        if not doc or not doc.get("path"):
            return "Document not found", 404

        path = doc["path"]
        if not _is_allowed_path(path, settings.paths.root_locations):
            return "Access denied", 403

        _log(settings, f"OPEN_PDF id={doc_id} path={path}")
        return send_file(path, as_attachment=False)

    # ------------------------------------------------------------
    # ZIP DOWNLOAD (MAX 25, WHITELIST, LOGGED)
    # ------------------------------------------------------------
    @app.route("/zip", methods=["POST"])
    def zip_download():
        data = request.get_json(silent=True) or {}
        files = data.get("files") or []

        if not files:
            return jsonify({"error": "Geen bestanden opgegeven"}), 400
        if len(files) > 25:
            return jsonify({"error": "Max 25 bestanden toegestaan"}), 400
        
        _log(settings, f"ZIP requested files={files}")

        mem = io.BytesIO()
        added, skipped = 0, 0

        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
            base_root = os.path.normcase(os.path.abspath(settings.paths.root_locations[0]))
            for f in files:
                f_abs = os.path.normcase(os.path.abspath(f))

                if not _is_allowed_path(f_abs, settings.paths.root_locations):
                    skipped += 1
                    continue

                if not os.path.exists(f_abs):
                    skipped += 1
                    continue

                rel = os.path.relpath(f_abs, start=base_root)
                z.write(f_abs, arcname=rel)
                added += 1            

            # base_root = settings.paths.root_locations[0]
            # for f in files:
            #     if not _is_allowed_path(f, settings.paths.root_locations):
            #         skipped += 1
            #         continue
            #     if not os.path.exists(f):
            #         skipped += 1
            #         continue

            #     rel = os.path.relpath(f, start=base_root)
            #     z.write(f, arcname=rel)
            #     added += 1

        mem.seek(0)
        _log(settings, f"ZIP files={len(files)} added={added} skipped={skipped}")
        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="documents.zip",
        )

    # ------------------------------------------------------------
    # METADATA JSON (OPTIONEEL, KLAAR VOOR CLIENT-SIDE)
    # ------------------------------------------------------------
    @app.route("/metadata", methods=["GET"])
    def metadata():
        import sqlite3

        conn = sqlite3.connect(settings.paths.index_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, path, title, tags, summary,
                   project_codes, sample_ids, dates, mtime, ctime
            FROM files
            ORDER BY mtime DESC
            LIMIT 5000
            """
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)


# # =====================================================================
# # FILE: ui/app.py
# # DROP-IN REPLACEMENT
# # =====================================================================

# import os
# import io
# import zipfile
# from datetime import datetime
# from pathlib import Path
# from typing import List

# from flask import Flask, render_template, request, jsonify, send_file

# from core.search_api import search, get_document
# from core.config import load_settings

# # ui/app.py
# from flask import render_template


# def _log(settings, msg: str) -> None:
#     log_dir = Path(settings.paths.log_folder)
#     log_dir.mkdir(parents=True, exist_ok=True)
#     with open(log_dir / "ui_server.log", "a", encoding="utf-8") as f:
#         f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


# def _is_allowed_path(path: str, roots: List[str]) -> bool:
#     try:
#         p = os.path.normcase(os.path.abspath(path))
#         for root in roots:
#             r = os.path.normcase(os.path.abspath(root))
#             if os.path.commonpath([p, r]) == r:
#                 return True
#     except Exception:
#         pass
#     return False


# def create_app() -> Flask:
#     settings = load_settings()

#     app = Flask(
#         __name__,
#         template_folder=os.path.join(os.path.dirname(__file__), "templates"),
#         static_folder=os.path.join(os.path.dirname(__file__), "static"),
#     )

#     # ------------------------------------------------------------
#     # SEARCH UI
#     # ------------------------------------------------------------
#     @app.route("/", methods=["GET"])
#     def index():
#         q = request.args.get("q", "").strip()
#         results = search(q) if q else []
#         if q:
#             _log(settings, f"SEARCH q='{q}' results={len(results)}")
#         return render_template("search.html", query=q, results=results)

#     # ------------------------------------------------------------
#     # DOCUMENT DETAIL
#     # ------------------------------------------------------------
#     @app.route("/doc/<int:doc_id>", methods=["GET"])
#     def doc_detail(doc_id: int):
#         doc = get_document(doc_id)
#         if not doc:
#             return "Document not found", 404
#         return render_template("detail.html", doc=doc)

#     # ------------------------------------------------------------
#     # PDF OPEN (SERVER-SIDE, ROBUST)
#     # ------------------------------------------------------------
#     @app.route("/pdf/<int:doc_id>", methods=["GET"])
#     def open_pdf(doc_id: int):
#         doc = get_document(doc_id)
#         if not doc or not doc.get("path"):
#             return "Document not found", 404

#         path = doc["path"]
#         if not _is_allowed_path(path, settings.paths.root_locations):
#             return "Access denied", 403

#         _log(settings, f"OPEN_PDF id={doc_id} path={path}")
#         return send_file(path, as_attachment=False)

#     # ------------------------------------------------------------
#     # ZIP DOWNLOAD (MAX 25, WHITELIST, LOGGED)
#     # ------------------------------------------------------------
#     @app.route("/zip", methods=["POST"])
#     def zip_download():
#         data = request.get_json(silent=True) or {}
#         files = data.get("files") or []

#         if not files:
#             return jsonify({"error": "Geen bestanden opgegeven"}), 400
#         if len(files) > 25:
#             return jsonify({"error": "Max 25 bestanden toegestaan"}), 400

#         mem = io.BytesIO()
#         added, skipped = 0, 0

#         with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
#             base_root = settings.paths.root_locations[0]
#             for f in files:
#                 if not _is_allowed_path(f, settings.paths.root_locations):
#                     skipped += 1
#                     continue
#                 if not os.path.exists(f):
#                     skipped += 1
#                     continue

#                 rel = os.path.relpath(f, start=base_root)
#                 z.write(f, arcname=rel)
#                 added += 1

#         mem.seek(0)
#         _log(settings, f"ZIP files={len(files)} added={added} skipped={skipped}")
#         return send_file(mem, mimetype="application/zip",
#                          as_attachment=True,
#                          download_name="documents.zip")

#     # ------------------------------------------------------------
#     # METADATA JSON (OPTIONEEL, KLAAR VOOR CLIENT-SIDE)
#     # ------------------------------------------------------------
#     @app.route("/metadata", methods=["GET"])
#     def metadata():
#         import sqlite3
#         conn = sqlite3.connect(settings.paths.index_db)
#         conn.row_factory = sqlite3.Row
#         rows = conn.execute("""
#             SELECT id, path, title, tags, summary,
#                    project_codes, sample_ids, dates, mtime, ctime
#             FROM files
#             ORDER BY mtime DESC
#             LIMIT 5000
#         """).fetchall()
#         conn.close()
#         return jsonify([dict(r) for r in rows])

#     return app


# if __name__ == "__main__":
#     app = create_app()
#     app.run(host="0.0.0.0", port=5000, debug=False)