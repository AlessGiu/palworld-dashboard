import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g

DB_PATH = os.environ.get("TASKS_DB_PATH", "/data/tasks.sqlite")
COLUMNS = ("todo", "doing", "done")

app = Flask(__name__)


def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            column_name TEXT NOT NULL DEFAULT 'todo',
            position INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "column": row["column_name"],
        "position": row["position"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/tasks", methods=["OPTIONS"])
@app.route("/tasks/<int:task_id>", methods=["OPTIONS"])
def options_handler(task_id=None):
    return "", 204


@app.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db()
    rows = db.execute("SELECT * FROM tasks ORDER BY column_name, position, id").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title requis"}), 400
    column = data.get("column") if data.get("column") in COLUMNS else "todo"
    description = (data.get("description") or "").strip()

    db = get_db()
    max_pos = db.execute(
        "SELECT COALESCE(MAX(position), -1) AS m FROM tasks WHERE column_name = ?", (column,)
    ).fetchone()["m"]
    ts = now_iso()
    cur = db.execute(
        "INSERT INTO tasks (title, description, column_name, position, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, column, max_pos + 1, ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.route("/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    data = request.get_json(force=True, silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    title = row["title"]
    description = row["description"]
    column = row["column_name"]
    position = row["position"]

    if "title" in data:
        title = (data.get("title") or "").strip() or title
    if "description" in data:
        description = data.get("description") or ""
    if "column" in data and data.get("column") in COLUMNS:
        column = data.get("column")
    if "position" in data:
        try:
            position = int(data.get("position"))
        except (TypeError, ValueError):
            pass
    else:
        if "column" in data and column != row["column_name"]:
            max_pos = db.execute(
                "SELECT COALESCE(MAX(position), -1) AS m FROM tasks WHERE column_name = ?", (column,)
            ).fetchone()["m"]
            position = max_pos + 1

    db.execute(
        "UPDATE tasks SET title=?, description=?, column_name=?, position=?, updated_at=? WHERE id=?",
        (title, description, column, position, now_iso(), task_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
