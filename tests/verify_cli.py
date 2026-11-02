"""로컬(SQLite) 버전 CLI(todo_cli.py) 확인.

local-sqlite/ 를 임시 폴더에 복사(todo.db 제외)해 빈 DB에서 CLI 명령
list / add / done / summary 를 실제로 실행하고, 출력·종료 코드·DB 내용과
웹 화면(같은 todo.db) 반영 여부를 확인한다. (내 todo.db 는 건드리지 않음)

실행: .venv\\Scripts\\python tests\\verify_cli.py
"""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REAL_DB = ROOT / "local-sqlite" / "todo.db"
results = []


def check(cond, label):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def cli(app_dir, *args):
    p = subprocess.run(
        [sys.executable, "todo_cli.py", *args], cwd=app_dir,
        capture_output=True, text=True, encoding="utf-8",
    )
    out = (p.stdout + p.stderr).strip()
    print(f"  $ todo_cli.py {' '.join(args)}   (종료 코드 {p.returncode})")
    for line in out.splitlines():
        print(f"    {line}")
    return p.returncode, out


def main():
    real_before = sha(REAL_DB)
    tmp = Path(tempfile.mkdtemp(prefix="verify_cli_"))
    app_dir = tmp / "local-sqlite"
    shutil.copytree(ROOT / "local-sqlite", app_dir,
                    ignore=shutil.ignore_patterns("todo.db", "__pycache__", "backup"))
    today = date.today().isoformat()
    try:
        print("== 1. 빈 DB에서 목록 ==")
        code, out = cli(app_dir, "list")
        check(code == 0 and out == "할 일이 없습니다.", "빈 목록 -> '할 일이 없습니다.'")
        check((app_dir / "todo.db").exists(), "실행 시 todo.db 생성 (app.py 스키마 재사용)")

        print("\n== 2. 추가 ==")
        code, out = cli(app_dir, "add", "보고서 작성", "--due", "2026-11-05", "--tags", "업무, 긴급,업무")
        check(code == 0 and out == "추가했습니다: 1. 보고서 작성", "마감일·태그 포함 추가")
        code, out = cli(app_dir, "add", "운동하기", "--tags", "건강")
        check(code == 0 and out == "추가했습니다: 2. 운동하기", "태그만 포함 추가")
        code, out = cli(app_dir, "add", "   ")
        check(code != 0 and "제목을 입력해 주세요." in out, "빈 제목 거부")
        code, out = cli(app_dir, "add", "잘못된 마감", "--due", "2026-13-40")
        check(code != 0 and "마감일 형식" in out, "잘못된 마감일 거부")

        print("\n== 3. 완료 ==")
        code, out = cli(app_dir, "done", "2")
        check(code == 0 and out == "완료했습니다: 2. 운동하기", "완료 처리")
        code, out = cli(app_dir, "done", "2")
        check(code == 0 and "이미 완료된 할 일입니다" in out, "이미 완료된 할 일 다시 완료 -> 안내만")
        code, out = cli(app_dir, "done", "99")
        check(code != 0 and "99번 할 일이 없습니다." in out, "없는 번호 거부")

        print("\n== 4. 목록 / 요약 ==")
        code, out = cli(app_dir, "list")
        lines = out.splitlines()
        check(code == 0 and lines == [
            "[ ] 1. 보고서 작성  (마감 2026-11-05)  #업무, 긴급",
            "[x] 2. 운동하기  #건강",
        ], "미완료 먼저, 마감일·태그 표시 (중복 태그 '업무' 1번만)")
        code, out = cli(app_dir, "summary")
        lines = out.splitlines()
        check(code == 0 and lines[0] == f"오늘({today}) 완료 1건 / 남은 할 일 1건", "요약 건수")
        check(len(lines) == 2 and lines[1].startswith("- 2. 운동하기 ("), "요약에 오늘 완료한 할 일 표시")

        print("\n== 5. DB 내용 ==")
        with sqlite3.connect(app_dir / "todo.db") as conn:
            rows = conn.execute(
                "SELECT t.id, t.title, t.due_date, t.completed_at IS NOT NULL,"
                " group_concat(g.name, ', ') FROM todos t"
                " LEFT JOIN todo_tags tt ON tt.todo_id = t.id LEFT JOIN tags g ON g.id = tt.tag_id"
                " GROUP BY t.id ORDER BY t.id"
            ).fetchall()
        print("  [todo.db: id, 제목, 마감일, 완료 여부, 태그]")
        for r in rows:
            print(f"    {r}")
        check(len(rows) == 2, "거부된 입력은 저장되지 않음 (2건만)")

        print("\n== 6. 웹 화면과 같은 DB 사용 ==")
        sys.path.insert(0, str(app_dir))
        import app as webapp  # 복사본의 app.py (복사본 todo.db 사용)
        html = webapp.app.test_client().get("/").get_data(as_text=True)
        check("보고서 작성" in html and "운동하기" in html, "CLI로 추가한 할 일이 웹 화면(/)에 보임")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n== 7. 실데이터 보호 ==")
    check(sha(REAL_DB) == real_before, "내 local-sqlite/todo.db 변경 없음")

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
