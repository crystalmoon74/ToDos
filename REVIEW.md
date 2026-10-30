# 코드 리뷰: ToDos (Flask + Supabase)

- 대상 저장소: https://github.com/crystalmoon74/ToDos (`main`, 커밋 `0beee78`)
- 리뷰 날짜: 2026-10-30
- 리뷰 범위: `app.py`, `supabase_client.py`, `db/schema.sql`, `static/app.js`, `README.md`, `VERIFICATION.md`
- 방법: 코드 읽기 + 배포 사이트(https://todos-g3b4.onrender.com/) 접속 확인. 저장소 코드는 실행하지 않았습니다.

---

## 요약

요구사항(v1 로컬 SQLite, v2 Supabase 전환 + 로그인 + RLS + 배포)을 모두 충족하는 완성도 높은 앱입니다.
특히 **"화면은 백엔드만 호출하고, 키와 토큰은 서버에만"** 이라는 구조와, **RLS 검증 기록(35/35 통과)** 이 인상적입니다.

치명적인 보안 문제는 없습니다. 아래 지적은 대부분 **공개 서비스로 운영할 때 필요한 방어 장치**와 **작은 버그**입니다.

| 심각도 | 개수 | 항목 |
| --- | --- | --- |
| 🔴 중간 | 4 | #1 로그인 시도 제한 없음, #2 입력 길이 제한 없음, #3 데모 계정 공개, #4 대량 가입 가능 |
| 🟡 낮음 | 4 | #5 토큰 무효 시 로그인 화면으로 안 넘어감, #6 수정 기능 부족, #7 목록 전체 조회, #8 마감 판단 기준 |
| ⚪ 운영 | 2 | #9 Render 첫 접속 지연, #10 Windows 전용 실행 안내 |

**이번 Pull Request에 포함할 수정:** #2, #5 (+ 여유가 되면 #1)

---

## 👍 잘된 점

1. **브라우저에 키가 없음.** `static/app.js`는 `/api/*`만 호출하고, Supabase 주소·키는 서버(`.env`)에만 있습니다.
2. **토큰을 HttpOnly 쿠키에 보관.** 페이지의 JS가 토큰을 읽을 수 없어 XSS에 강합니다. (`app.py:28`)
3. **잘못된 키 차단.** secret / service_role 키를 넣으면 서버가 시작을 거부합니다. (`supabase_client.py` `assert_not_secret_key`)
4. **촘촘한 RLS.** 조회·추가·수정·삭제마다 정책을 나눴고, `todo_tags`는 할 일과 태그가 **둘 다 내 것**일 때만 연결됩니다. `anon` 권한도 회수해서 이중으로 잠갔습니다.
5. **트랜잭션 처리.** 할 일 + 태그 추가(`create_todo`), 삭제 + 안 쓰는 태그 정리(`delete_todo`)를 DB 함수 하나로 처리합니다. 모두 `security invoker`라 RLS가 그대로 적용됩니다.
6. **데이터 정합성.** `is_completed`를 `completed_at`에서 자동 계산(generated column)해서 두 값이 어긋날 수 없습니다.
7. **CSRF 방어.** 쓰기 요청에 `X-Requested-With: fetch` 헤더를 요구하고, 쿠키는 `SameSite=Lax`입니다.
8. **XSS 안전.** 화면 출력이 모두 `textContent`라 사용자가 입력한 HTML이 실행되지 않습니다.
9. **검증 기록.** `VERIFICATION.md`에 스크립트, 출력 원문, 결과까지 남아 있어 누구나 다시 확인할 수 있습니다.
10. **커밋 기록에 키 없음.** 전체 커밋 기록에서 secret 키, JWT, `SECRET_KEY` 값을 검색했고 0건이었습니다.

---

## 🔴 중간

### #1 로그인·가입 시도 제한이 없음 — `app.py:124`, `app.py:137`

`/api/auth/login`, `/api/auth/signup`을 횟수 제한 없이 호출할 수 있습니다.

로그인을 서버가 대신 처리하므로 Supabase 입장에서는 **모든 사용자의 요청이 Render 서버 IP 하나**에서 옵니다. 그래서:
- 비밀번호 대입 공격을 IP 단위로 막기 어렵습니다.
- 누군가 공격하면 Supabase의 IP 제한이 서버 IP에 걸려 **정상 사용자도 모두 로그인할 수 없게** 될 수 있습니다.

**제안:** `Flask-Limiter`로 접속자 IP 기준 제한을 겁니다. Render는 프록시 뒤에서 동작하므로 `ProxyFix`로 실제 접속자 IP를 읽어야 합니다.

```python
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")

@app.post("/api/auth/login")
@limiter.limit("10/minute;50/hour")
def login(): ...
```

### #2 입력 길이 제한이 없음 — `db/schema.sql:13`, `db/schema.sql:26`, `app.py:212`, `app.py:197`

제목과 태그 이름은 "비어 있지 않음"만 검사합니다. 최대 길이, 태그 개수, 요청 크기 제한이 없어서 수 MB짜리 제목이나 태그 수천 개를 넣을 수 있습니다.
화면이 깨지고, Supabase 무료 요금제 용량(500MB)을 빠르게 채울 수 있습니다.

**제안 (이번 PR에 포함):** DB와 서버 양쪽에서 막습니다.
- DB: 제목 200자, 태그 이름 30자 `check` 제약 추가. 기존 DB에도 다시 실행할 수 있게 `drop constraint if exists` → `add constraint` 형태로 작성.
- 서버: `MAX_CONTENT_LENGTH`(16KB), 제목 200자, 태그 10개·각 30자 검사 → 넘으면 400과 안내 문구. 요청이 너무 크면 413도 JSON으로 응답.
- 화면: 입력칸에 `maxlength`를 추가해 사용자가 미리 알 수 있게.

### #3 데모 계정 비밀번호가 공개 저장소에 있음 — `README.md:12`

의도한 공용 계정이지만, 누구나 로그인해서 데이터를 지우거나 부적절한 내용을 쓸 수 있습니다. 시연 직전에 누가 망쳐 두면 곤란합니다.

**제안:** 시연 전 데이터를 다시 채우는 스크립트를 두거나, 채점 기간이 끝나면 계정을 지우세요. 또는 README에서 빼고 채점자에게만 따로 전달하는 방법도 있습니다.

### #4 가짜 계정 대량 가입 가능 — `README.md:75`

README가 테스트용으로 *Confirm email* 끄기를 안내합니다. 꺼 둔 상태로 배포하면 없는 이메일로 계정을 무한히 만들 수 있습니다.

**제안:** 배포 프로젝트에서는 *Confirm email*을 켜 두거나, Supabase의 CAPTCHA(hCaptcha / Turnstile) 보호를 켜세요. #1의 가입 횟수 제한도 도움이 됩니다.

---

## 🟡 낮음

### #5 토큰이 무효가 되면 로그인 화면으로 안 넘어감 — `app.py:59-62`, `static/app.js:13`

```python
if exc.status in (401, 403):
    return jsonify(error="권한이 없습니다."), 403
```

Supabase가 401(토큰 무효)을 돌려줘도 서버는 **403**으로 바꿔 응답합니다. 그런데 화면은 **401일 때만** 로그인 화면을 띄웁니다(`static/app.js:13`).
그래서 다른 기기에서 로그아웃했거나 토큰이 취소된 경우, 로그인 화면이 아니라 "권한이 없습니다"만 계속 뜹니다. 사용자가 직접 로그아웃해야 풀립니다.

**제안 (이번 PR에 포함):** 401은 세션을 비우고 401 그대로 돌려줍니다.

```python
if exc.status == 401:
    session.clear()
    return jsonify(error="로그인이 만료되었습니다. 다시 로그인해 주세요."), 401
if exc.status == 403:
    return jsonify(error="권한이 없습니다."), 403
```

### #6 수정(Update) 기능이 완료 표시뿐 — `app.py:228`

`PATCH /api/todos/<id>`는 `completed`만 받습니다. 제목, 마감일, 태그는 수정할 수 없고, DB의 `description` 칸은 화면에서 쓰이지 않습니다.
과제의 CRUD 중 U(Update)를 엄격하게 보면 지적받을 수 있습니다.

**제안:** 제목·마감일·태그 수정을 받도록 확장합니다. 태그는 `create_todo`처럼 DB 함수(`update_todo_tags`)로 한 번에 처리하면 깔끔합니다. (범위가 커서 이번 PR에서는 제외)

### #7 목록을 한 번에 전부 불러옴 — `app.py` `list_todos`

페이지 나누기(`limit`/`offset`)가 없습니다. 과제 규모에서는 문제없지만, 항목이 수천 개가 되면 느려집니다.

### #8 "마감 지남"을 브라우저 시간으로 판단 — `static/app.js:92`, `static/app.js:134`

기기 시계나 시간대가 다르면 판단이 달라집니다. 서버(또는 DB 뷰)에서 `Asia/Seoul` 기준으로 계산해 내려주면 일관됩니다.

---

## ⚪ 운영

### #9 Render 무료 요금제 첫 접속 지연

리뷰 중 실제로 접속했을 때 첫 응답까지 **약 32초** 걸렸습니다. 시연 전에 미리 한 번 접속해 깨워 두세요.

### #10 Windows 전용 실행 안내 — `README.md`, `run.bat`

`.venv\Scripts\python` 기준이라 macOS·Linux에서는 그대로 따라 할 수 없습니다. `.venv/bin/python` 명령을 같이 적어 주면 좋습니다.

### 참고: `debug=True` — `app.py:247`

`python app.py`로 직접 실행할 때만 쓰이고 `127.0.0.1`에만 열리므로 지금은 안전합니다. Render는 gunicorn으로 실행되어 영향이 없습니다.
다만 실수로 서버에서 `app.py`를 직접 실행하면 Werkzeug 디버거가 열리므로, `debug=os.environ.get("FLASK_DEBUG") == "1"`처럼 환경변수로 켜는 방식을 권합니다.

---

## Pull Request 계획

| 브랜치 | 내용 | 수정 파일 |
| --- | --- | --- |
| `fix/limits-and-auth` | #2 입력 길이 제한 | `db/schema.sql`, `app.py`, `static/index.html` |
| | #5 401 처리 | `app.py` |
| | (선택) #1 로그인·가입 시도 제한 | `app.py`, `requirements.txt` |

- `db/schema.sql`은 기존처럼 **여러 번 실행해도 안전**하게 작성합니다. 배포 DB에는 PR을 합친 뒤 SQL Editor에서 한 번 다시 실행하면 됩니다.
- 기존 동작(로그인, 추가, 완료, 삭제, 태그 필터)은 바뀌지 않습니다.
- PR 설명에 확인 방법(긴 제목 400, 토큰 무효 시 401 → 로그인 화면)을 함께 적겠습니다.
