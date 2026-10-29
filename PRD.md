# PRD: Todo 앱

## v1: 로컬 Todo 앱
- **무엇:** 내 컴퓨터에서 도는 Todo(할 일) 앱
- **기본 기능(CRUD):** 할 일 추가 / 목록 보기 / 완료 표시 / 삭제
- **저장:** 데이터는 내 컴퓨터의 SQLite에 저장 (껐다 켜도 남기)
- **추가 기능:** 생성일자, 완료일자, Due Date, Tags (여러 개 넣을 수 있음)
- **규칙:** 무료 도구만 사용

## v2: Supabase 전환 + 로그인 (현재 버전)
- **저장소 변경:** 로컬 SQLite 대신 Supabase(무료 클라우드 Postgres)에 저장
- **백엔드 전용 DB 접근:** 화면(프론트) 코드는 Supabase를 직접 호출하지 않고 백엔드 API에만 요청. DB 접근은 백엔드 코드에서만
- **키 관리:** 접속 키는 백엔드에서만 사용하고 `.env`로 분리
- **RLS:** 행 수준 보안을 켜서 허용된 접근만 가능
- **로그인:** Supabase Auth로 로그인하고, 할 일마다 소유 사용자를 기록
- **권한:** 로그인한 사용자는 자기 할 일만 조회·추가·수정·삭제 (RLS 정책으로 강제)
- **배포:** 백엔드를 Render 같은 클라우드 서비스에 올릴 수 있도록 준비

## 구현 상태
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
