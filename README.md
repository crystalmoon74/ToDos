# Todo

로그인해서 쓰는 할 일 앱입니다. Python(Flask) 백엔드와 Supabase(무료 클라우드 Postgres + Auth)로 만들었습니다.

**🌐 접속 주소: https://todos-g3b4.onrender.com/**
(Render 무료 요금제라 한동안 접속이 없으면 잠들고, 첫 접속 때 깨어나는 데 30~60초쯤 걸립니다.)

**🔑 데모 계정** (누구나 쓰는 공용 계정입니다. 개인 정보는 입력하지 마세요)

| 이메일 | 비밀번호 |
|---|---|
| `demo@example.com` | `Demo-uj9MQYeQDl` |

직접 가입해서 나만의 계정으로 써도 됩니다. 계정마다 자기 할 일만 보입니다.

**✅ 저장·보안 확인 기록:** 로컬(SQLite)과 Supabase 각각의 저장 확인, 클라우드 전환 기록, RLS 시험 결과는 [VERIFICATION.md](VERIFICATION.md)에 있습니다.

## PRD (요구사항)

> 같은 내용이 [PRD.md](PRD.md)에도 있습니다. 수정할 때는 두 파일을 함께 고쳐 주세요.

### v1: 로컬 Todo 앱
- **무엇:** 내 컴퓨터에서 도는 Todo(할 일) 앱
- **기본 기능(CRUD):** 할 일 추가 / 목록 보기 / 완료 표시 / 삭제
- **저장:** 데이터는 내 컴퓨터의 SQLite에 저장 (껐다 켜도 남기)
- **추가 기능:** 생성일자, 완료일자, Due Date, Tags (여러 개 넣을 수 있음)
- **규칙:** 무료 도구만 사용

### v2: Supabase 전환 + 로그인 (현재 버전)
- **저장소 변경:** 로컬 SQLite 대신 Supabase(무료 클라우드 Postgres)에 저장
- **백엔드 전용 DB 접근:** 화면(프론트) 코드는 Supabase를 직접 호출하지 않고 백엔드 API에만 요청. DB 접근은 백엔드 코드에서만
- **키 관리:** 접속 키는 백엔드에서만 사용하고 `.env`로 분리
- **RLS:** 행 수준 보안을 켜서 허용된 접근만 가능
- **로그인:** Supabase Auth로 로그인하고, 할 일마다 소유 사용자를 기록
- **권한:** 로그인한 사용자는 자기 할 일만 조회·추가·수정·삭제 (RLS 정책으로 강제)
- **배포:** 백엔드를 Render 같은 클라우드 서비스에 올릴 수 있도록 준비

### 구현 상태
| 요구사항 | 상태 | 구현 위치 |
|---|---|---|
| 추가 / 목록 / 완료 표시 / 삭제 | ✅ | `app.py` `/api/todos`, `static/app.js` |
| 생성일자, 완료일자, Due Date | ✅ | `todos.created_at`, `completed_at`, `due_date` |
| 태그 여러 개 | ✅ | `tags`, `todo_tags` 테이블 (사용자별 태그) |
| Supabase 저장 | ✅ | `db/schema.sql`, `supabase_client.py` |
| 프론트는 백엔드 API만 호출 | ✅ | `static/app.js` (Supabase 주소/키 없음) |
| 접속 키는 `.env`, 백엔드에서만 | ✅ | `.env` (git 제외), secret 키 사용 시 시작 거부 |
| RLS + 자기 할 일만 | ✅ | `db/schema.sql` 정책 (실제 Supabase에서 다른 사용자의 접근 차단 검증) |
| Supabase Auth 로그인, 소유자 기록 | ✅ | `/api/auth/*`, `todos.user_id` |
| 무료 도구만 | ✅ | Flask, Supabase Free, Render Free |
| 클라우드 배포 | ✅ | Render Web Service (https://todos-g3b4.onrender.com/) |

## 구조

```
브라우저 (static/)  ──/api/*──▶  Flask 백엔드 (app.py)  ──▶  Supabase (Auth + Postgres, RLS)
   키 없음                       .env 의 키 + 사용자 토큰
```

- 화면 코드는 백엔드 `/api/*`만 호출합니다. Supabase 주소와 키는 브라우저에 전달되지 않습니다.
- 로그인 토큰은 서버가 서명한 HttpOnly 쿠키에 담기므로, 페이지의 JS에서 읽을 수 없습니다.
- DB 접근은 로그인한 사용자의 토큰으로 이뤄지고, Supabase RLS가 "자기 할 일만"을 DB에서 강제합니다. 자세한 내용은 [db/DB_DESIGN.md](db/DB_DESIGN.md)에 있습니다.

## 기능
- 회원가입 / 로그인 / 로그아웃 (Supabase Auth, 이메일 + 비밀번호)
- 할 일 추가 (제목, 마감일, 태그 여러 개), 목록, 완료 표시와 취소, 삭제
- 전체 / 진행 중 / 완료 필터, 태그 필터, 마감 지난 항목 강조

## 처음 설정 (한 번만)

1. https://supabase.com 에서 무료 프로젝트를 만듭니다.
2. 대시보드 **SQL Editor**에서 [db/schema.sql](db/schema.sql) 전체를 붙여넣고 **Run**합니다.
3. `.env.example`을 복사해 `.env`를 만들고 세 값을 채웁니다.
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`: 대시보드 **Project Settings → API Keys**의 Project URL과 publishable(또는 anon) 키
   - `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"` 로 만든 값
4. (선택) 테스트를 빨리 하려면 **Authentication → Sign In / Providers → Email**에서 *Confirm email*을 끕니다. 켜 두면 가입 후 메일의 링크를 눌러야 로그인할 수 있습니다.

## 실행

`run.bat`을 더블클릭하면 http://127.0.0.1:5000 이 열립니다. 터미널에서 직접 실행하려면:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/auth/signup` | `{email, password}` |
| POST | `/api/auth/login` | `{email, password}` |
| POST | `/api/auth/logout` | |
| GET | `/api/me` | 로그인한 사용자 이메일 (없으면 `null`) |
| GET | `/api/todos?status=all\|active\|done&tag=이름` | 내 할 일 목록 |
| GET | `/api/tags` | 내 태그와 개수 |
| POST | `/api/todos` | `{title, due_date?, tags?}` |
| PATCH | `/api/todos/<id>` | `{completed: true\|false}` |
| DELETE | `/api/todos/<id>` | |

쓰기 요청(POST/PATCH/DELETE)에는 `X-Requested-With: fetch` 헤더가 있어야 합니다. 다른 사이트가 몰래 요청을 보내는 것(CSRF)을 막기 위한 장치입니다.

## 파일 구성
| 경로 | 설명 |
|---|---|
| `app.py` | 백엔드 API, 로그인 세션 |
| `supabase_client.py` | Supabase Auth / DB 호출 |
| `static/` | 화면 (index.html, app.js, style.css) |
| `db/schema.sql` | Supabase 테이블, RLS 정책, 뷰, 함수 |
| `PRD.md` | 요구사항(PRD)과 구현 상태 |
| `VERIFICATION.md` | 로컬·Supabase 저장 확인, 클라우드 전환, RLS 확인 기록 |
| `tests/` | 확인 스크립트 (`verify_local.py`, `verify_supabase.py`) |
| `docs/results/` | 확인 스크립트 출력 원문 |
| `local-sqlite/` | v1 로컬 SQLite 버전 (로컬 저장 확인용 보관) |
| `.env.example` | 환경변수 견본 (`.env`는 git에 올리지 않음) |
| `requirements.txt` | Python 패키지 (배포 시 gunicorn 사용) |
