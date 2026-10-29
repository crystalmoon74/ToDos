"""Todo 웹 앱 (Flask + SQLite)."""
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "todo.db"
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"

app = Flask(__name__)


# ---------- DB ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    # 스키마는 IF NOT EXISTS라서 매번 실행해도 기존 데이터는 그대로
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def parse_tags(raw):
    """'업무, 긴급,업무' -> ['업무', '긴급'] (공백 제거, 대소문자 무시 중복 제거)"""
    tags, seen = [], set()
    for name in raw.split(","):
        name = name.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            tags.append(name)
    return tags


# ---------- 템플릿 필터 ----------

@app.template_filter("localtime")
def localtime(value):
    """DB의 UTC 시각 문자열 -> 내 컴퓨터 시간 'YYYY-MM-DD HH:MM'"""
    if not value:
        return ""
    utc = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return utc.astimezone().strftime("%Y-%m-%d %H:%M")


# ---------- 화면 ----------

@app.get("/")
def index():
    status = request.args.get("status", "all")
    tag = request.args.get("tag", "").strip()

    where, params = [], []
    if status == "active":
        where.append("t.completed_at IS NULL")
    elif status == "done":
        where.append("t.completed_at IS NOT NULL")
    if tag:
        where.append(
            "t.id IN (SELECT tt2.todo_id FROM todo_tags tt2"
            " JOIN tags g2 ON g2.id = tt2.tag_id WHERE g2.name = ?)"
        )
        params.append(tag)

    sql = """
        SELECT t.*, group_concat(g.name, char(31)) AS tag_names
        FROM todos t
        LEFT JOIN todo_tags tt ON tt.todo_id = t.id
        LEFT JOIN tags g       ON g.id = tt.tag_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        GROUP BY t.id
        ORDER BY t.is_completed, t.due_date IS NULL, t.due_date, t.created_at DESC
    """
    db = get_db()
    todos = db.execute(sql, params).fetchall()
    all_tags = db.execute(
        "SELECT g.name, count(tt.todo_id) AS cnt FROM tags g"
        " JOIN todo_tags tt ON tt.tag_id = g.id GROUP BY g.id ORDER BY g.name"
    ).fetchall()

    return render_template(
        "index.html",
        todos=todos,
        all_tags=all_tags,
        status=status,
        tag=tag,
        today=date.today().isoformat(),
        error=request.args.get("error"),
    )


@app.post("/todos")
def add_todo():
    title = request.form.get("title", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    tags = parse_tags(request.form.get("tags", ""))
    if not title:
        return redirect(url_for("index", error="제목을 입력해 주세요."))

    db = get_db()
    try:
        with db:  # 할 일 + 태그를 한 트랜잭션으로
            todo_id = db.execute(
                "INSERT INTO todos (title, due_date) VALUES (?, ?)", (title, due_date)
            ).lastrowid
            for name in tags:
                db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
                db.execute(
                    "INSERT OR IGNORE INTO todo_tags (todo_id, tag_id)"
                    " SELECT ?, id FROM tags WHERE name = ?",
                    (todo_id, name),
                )
    except sqlite3.IntegrityError:
        return redirect(url_for("index", error="입력값이 올바르지 않습니다. 마감일 형식을 확인해 주세요."))
    return redirect(url_for("index"))


@app.post("/todos/<int:todo_id>/toggle")
def toggle_todo(todo_id):
    db = get_db()
    with db:
        cur = db.execute(
            "UPDATE todos SET completed_at = CASE WHEN completed_at IS NULL"
            " THEN datetime('now') ELSE NULL END WHERE id = ?",
            (todo_id,),
        )
    if cur.rowcount == 0:
        abort(404)
    return redirect(request.referrer or url_for("index"))


@app.post("/todos/<int:todo_id>/delete")
def delete_todo(todo_id):
    db = get_db()
    with db:
        db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        # 어느 할 일에도 안 쓰이는 태그 정리
        db.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM todo_tags)")
    return redirect(request.referrer or url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
