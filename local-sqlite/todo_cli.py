"""Todo 명령줄 진입점. 웹 앱(app.py)과 같은 todo.db를 사용합니다.

사용법:
    python todo_cli.py list
    python todo_cli.py add "<내용>" [--due YYYY-MM-DD] [--tags 업무,긴급]
    python todo_cli.py done <번호>
    python todo_cli.py summary
"""
import argparse
import sqlite3
import sys
from datetime import date

# app.py의 DB 경로·스키마 초기화·태그 파싱·시각 변환을 그대로 재사용
from app import DB_PATH, localtime, parse_tags

# Windows 콘솔에서도 한글이 깨지지 않도록
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cmd_list(conn, _args):
    rows = conn.execute(
        """
        SELECT t.*, group_concat(g.name, ', ') AS tag_names
        FROM todos t
        LEFT JOIN todo_tags tt ON tt.todo_id = t.id
        LEFT JOIN tags g       ON g.id = tt.tag_id
        GROUP BY t.id
        ORDER BY t.is_completed, t.due_date IS NULL, t.due_date, t.created_at DESC
        """
    ).fetchall()
    if not rows:
        print("할 일이 없습니다.")
        return
    for t in rows:
        line = f"[{'x' if t['is_completed'] else ' '}] {t['id']}. {t['title']}"
        if t["due_date"]:
            line += f"  (마감 {t['due_date']})"
        if t["tag_names"]:
            line += f"  #{t['tag_names']}"
        print(line)


def cmd_add(conn, args):
    title = args.title.strip()
    if not title:
        sys.exit("제목을 입력해 주세요.")
    try:
        with conn:  # 할 일 + 태그를 한 트랜잭션으로 (app.py add_todo와 동일)
            todo_id = conn.execute(
                "INSERT INTO todos (title, due_date) VALUES (?, ?)", (title, args.due)
            ).lastrowid
            for name in parse_tags(args.tags):
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
                conn.execute(
                    "INSERT OR IGNORE INTO todo_tags (todo_id, tag_id)"
                    " SELECT ?, id FROM tags WHERE name = ?",
                    (todo_id, name),
                )
    except sqlite3.IntegrityError:
        sys.exit("입력값이 올바르지 않습니다. 마감일 형식(YYYY-MM-DD)을 확인해 주세요.")
    print(f"추가했습니다: {todo_id}. {title}")


def cmd_done(conn, args):
    with conn:
        row = conn.execute("SELECT title, completed_at FROM todos WHERE id = ?", (args.id,)).fetchone()
        if row is None:
            sys.exit(f"{args.id}번 할 일이 없습니다.")
        if row["completed_at"]:
            print(f"이미 완료된 할 일입니다: {args.id}. {row['title']}")
            return
        conn.execute("UPDATE todos SET completed_at = datetime('now') WHERE id = ?", (args.id,))
    print(f"완료했습니다: {args.id}. {row['title']}")


def cmd_summary(conn, _args):
    # completed_at은 UTC로 저장되므로 내 컴퓨터 시간 기준 날짜로 바꿔서 '오늘'을 판단
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT id, title, completed_at FROM todos WHERE completed_at IS NOT NULL ORDER BY completed_at"
    ).fetchall()
    done_today = [r for r in rows if localtime(r["completed_at"]).startswith(today)]
    remaining = conn.execute("SELECT count(*) FROM todos WHERE completed_at IS NULL").fetchone()[0]

    print(f"오늘({today}) 완료 {len(done_today)}건 / 남은 할 일 {remaining}건")
    for r in done_today:
        print(f"- {r['id']}. {r['title']} ({localtime(r['completed_at'])[11:]})")


def main():
    parser = argparse.ArgumentParser(prog="todo_cli.py", description="Todo 명령줄 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="할 일 목록")
    p_add = sub.add_parser("add", help="할 일 추가")
    p_add.add_argument("title")
    p_add.add_argument("--due", default=None, help="마감일 YYYY-MM-DD")
    p_add.add_argument("--tags", default="", help="쉼표로 구분한 태그")
    p_done = sub.add_parser("done", help="할 일 완료 처리")
    p_done.add_argument("id", type=int)
    sub.add_parser("summary", help="오늘 완료 요약")

    args = parser.parse_args()
    handlers = {"list": cmd_list, "add": cmd_add, "done": cmd_done, "summary": cmd_summary}
    with connect() as conn:
        handlers[args.command](conn, args)


if __name__ == "__main__":
    main()
