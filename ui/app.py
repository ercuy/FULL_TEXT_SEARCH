# =====================================================================
# BEGIN file: ui/app.py
# =====================================================================
import os
from flask import Flask, render_template, request

from core.search_api import search, get_document
from core.config import load_settings


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    @app.route("/", methods=["GET"])
    def index():
        q = request.args.get("q", "").strip()
        results = []
        if q:
            results = search(q)
        return render_template("search.html", query=q, results=results)

    @app.route("/doc/<int:doc_id>", methods=["GET"])
    def doc_detail(doc_id: int):
        doc = get_document(doc_id)
        if not doc:
            return "Document not found", 404
        return render_template("detail.html", doc=doc)

    return app


if __name__ == "__main__":
    settings = load_settings()
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)