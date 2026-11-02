# Todo 앱

## 개요
할 일을 추가·완료·조회하는 앱. 루트는 Supabase 버전(v2), `local-sqlite/`는 로컬 SQLite 버전(v1).
AI가 할 일 데이터를 다룰 때는 `local-sqlite/`의 CLI를 사용한다.

## 명령 (프로젝트 루트에서 실행)
- 목록: `.venv/Scripts/python local-sqlite/todo_cli.py list`
- 추가: `.venv/Scripts/python local-sqlite/todo_cli.py add "<내용>" [--due YYYY-MM-DD] [--tags 태그1,태그2]`
- 완료: `.venv/Scripts/python local-sqlite/todo_cli.py done <번호>`
- 오늘 완료 요약: `.venv/Scripts/python local-sqlite/todo_cli.py summary`
- 웹 화면(v1): `local-sqlite/run.bat` → http://127.0.0.1:5001

## 규칙
- 데이터는 `local-sqlite/todo.db`에 저장한다. 웹 화면과 CLI가 같은 파일을 쓴다.
- UI·출력 문구는 존댓말로.

## 하지 말 것
- `todo.db`(실데이터)를 직접 지우거나 덮어쓰지 말 것. 시험은 복사본에서 한다.
- `.env`의 키 값을 출력하거나 커밋하지 말 것.
