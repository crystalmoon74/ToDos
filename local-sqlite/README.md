# v1: 로컬 SQLite 버전

PRD v1(내 컴퓨터에서 도는 Todo 앱, SQLite 저장)으로 처음 만든 버전입니다. 현재 버전(루트 폴더)은 이 버전을 Supabase로 전환한 것이고, 로컬 저장 확인을 위해 v1을 그대로 보관합니다.

- 로그인 없이 바로 씁니다. 데이터는 이 폴더의 `todo.db` 파일 하나에 저장됩니다 (git에는 올리지 않음).
- 기능: 할 일 추가(제목, 마감일, 태그 여러 개), 목록, 완료 표시와 취소, 삭제, 전체/진행 중/완료 필터, 태그 필터
- 화면은 서버가 HTML을 만들어 보내는 방식(Flask 템플릿)입니다.

## 실행

`run.bat`을 더블클릭하면 http://127.0.0.1:5001 이 열립니다. (현재 버전과 동시에 띄울 수 있도록 포트를 5001로 했습니다.)

```
..\.venv\Scripts\python app.py
```

## 파일
| 경로 | 설명 |
|---|---|
| `app.py` | Flask 앱 (SQLite 직접 접근) |
| `db/schema.sql` | SQLite 스키마. 앱이 시작할 때 자동 실행 (`IF NOT EXISTS`라 기존 데이터 유지) |
| `templates/index.html`, `static/style.css` | 화면 |

저장 확인 방법과 결과는 [../VERIFICATION.md](../VERIFICATION.md)에 있습니다.
