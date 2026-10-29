"""로컬(SQLite) 버전 저장 확인.

local-sqlite/ 를 임시 폴더에 복사해 실제 서버를 띄우고, 화면과 같은 요청으로
추가·완료·삭제를 한 뒤 서버를 껐다 켜서 데이터가 남는지 확인한다.
(내 todo.db 는 건드리지 않음)

실행: .venv\\Scripts\\python tests\\verify_local.py
"""
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
results = []


def check(cond, label):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(app_dir, port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "run", "--port", str(port)],
        cwd=app_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            requests.get(base, timeout=1)
            return proc, base
        except requests.ConnectionError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("서버가 시작되지 않았습니다")


def stop(proc):
    proc.terminate()
    proc.wait(timeout=10)


def titles(base, query=""):
    html = requests.get(base + "/" + query, timeout=5).text
    return re.findall(r'<div class="title">(.*?)</div>', html)


def dump(db_path):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT t.id, t.title, t.due_date, t.created_at, t.completed_at,"
        " group_concat(g.name, ', ') FROM todos t"
        " LEFT JOIN todo_tags tt ON tt.todo_id = t.id LEFT JOIN tags g ON g.id = tt.tag_id"
        " GROUP BY t.id ORDER BY t.id"
    ).fetchall()
    con.close()
    print("  [todo.db 의 todos 테이블]")
    for r in rows:
        print("   ", r)
    return rows


work = Path(tempfile.mkdtemp()) / "local-sqlite"
shutil.copytree(ROOT / "local-sqlite", work, ignore=shutil.ignore_patterns("todo.db", "__pycache__"))
db_path = work / "todo.db"
port = free_port()

print("== 1회차 실행: 추가 / 완료 / 삭제 ==")
proc, base = start(work, port)
check(db_path.exists(), "서버 시작 시 todo.db 파일 생성")
for title, due, tags in [("보고서 작성", "2026-11-05", "업무, 긴급"),
                         ("운동하기", "", "건강"),
                         ("지울 항목", "", "")]:
    requests.post(base + "/todos", data={"title": title, "due_date": due, "tags": tags}, timeout=5)
check(titles(base) == ["보고서 작성", "운동하기", "지울 항목"], "추가 3건이 목록에 보임")

ids = {r[1]: r[0] for r in dump(db_path)}
requests.post(f"{base}/todos/{ids['운동하기']}/toggle", timeout=5)
check(titles(base, "?status=done") == ["운동하기"], "완료 표시 -> 완료 목록에 보임")
requests.post(f"{base}/todos/{ids['지울 항목']}/delete", timeout=5)
check("지울 항목" not in titles(base), "삭제 -> 목록에서 사라짐")
check(titles(base, "?tag=업무") == ["보고서 작성"], "태그 필터")
before = dump(db_path)

print("\n== 서버 종료 ==")
stop(proc)
try:
    requests.get(base, timeout=1)
    check(False, "서버가 꺼짐")
except requests.ConnectionError:
    check(True, "서버가 꺼짐 (접속 불가)")

print("\n== 2회차 실행: 다시 켜서 확인 ==")
proc, base = start(work, port)
after = dump(db_path)
check(after == before, "다시 켠 뒤 DB 내용이 끄기 전과 같음")
check(titles(base) == ["보고서 작성", "운동하기"], "다시 켠 뒤 목록에 그대로 보임")
check(titles(base, "?status=done") == ["운동하기"], "완료 상태와 완료일자 유지")
check(after[0][5] and set(after[0][5].split(", ")) == {"업무", "긴급"}, "태그 유지")
stop(proc)
shutil.rmtree(work.parent, ignore_errors=True)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
