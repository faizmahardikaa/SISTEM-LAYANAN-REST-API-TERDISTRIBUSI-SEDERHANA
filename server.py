import argparse
import sqlite3
from contextlib import closing
from pathlib import Path
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "shared.db"


def connect_db():
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with closing(connect_db()) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((ROOT / "schema.sql").read_text())
        db.commit()


def create_app(server_id, port):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    def reply(message, status=200, **extra):
        return jsonify(message=message, server_id=server_id,
                       port=port, **extra), status

    @app.get("/health")
    def health():
        with closing(connect_db()) as db:
            db.execute("SELECT 1 FROM items LIMIT 1").fetchall()
        return reply("Layanan siap")

    @app.route("/api/data", methods=["GET", "POST"])
    def data():
        with closing(connect_db()) as db:
            if request.method == "GET":
                rows = db.execute("SELECT * FROM items ORDER BY id").fetchall()
                return reply("Data bersama berhasil dibaca",
                             data=[dict(row) for row in rows])
            body = request.get_json(silent=True)
            name = body.get("name") if isinstance(body, dict) else None
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                return reply("name wajib berupa teks 1-100 karakter", 400)
            with db:
                cur = db.execute(
                    "INSERT INTO items(name, created_by) VALUES (?, ?)",
                    (name.strip(), server_id))
                row = db.execute("SELECT * FROM items WHERE id = ?",
                                 (cur.lastrowid,)).fetchone()
            return reply("Data berhasil ditambahkan", 201, data=dict(row))

    @app.errorhandler(sqlite3.OperationalError)
    def database_unavailable(_error):
        return reply("Database sementara tidak tersedia", 503)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, choices=["A", "B"])
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    init_db()
    create_app(args.id, args.port).run(host="127.0.0.1", port=args.port,
                                     debug=False, use_reloader=False)
