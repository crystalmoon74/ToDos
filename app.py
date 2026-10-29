"""Todo 웹 앱 백엔드 (Flask + Supabase).

브라우저는 이 서버의 /api/* 만 호출하고, Supabase 접속 키와 사용자 토큰은 서버에만 있다.
DB 호출은 로그인한 사용자의 토큰으로 하므로 Supabase RLS가 "자기 할 일만" 을 강제한다.
"""
import os
import time
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, session

from supabase_client import Supabase, SupabaseError

load_dotenv()


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"환경변수 {name} 이(가) 없습니다. .env 파일을 확인하세요 (.env.example 참고).")
    return value


supa = Supabase(require_env("SUPABASE_URL"), require_env("SUPABASE_ANON_KEY"))

app = Flask(__name__, static_folder="static", static_url_path="")
app.config.update(
    SECRET_KEY=require_env("SECRET_KEY"),       # 세션 쿠키 서명용
    SESSION_COOKIE_HTTPONLY=True,               # 화면 JS에서 쿠키(토큰) 못 읽음
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),  # Render(HTTPS)에서는 HTTPS 전용 쿠키
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

AUTH_ERRORS = {
    "invalid_credentials": "이메일 또는 비밀번호가 올바르지 않습니다.",
    "email_not_confirmed": "이메일 인증을 마친 뒤 로그인해 주세요.",
    "user_already_exists": "이미 가입된 이메일입니다.",
    "weak_password": "비밀번호가 너무 약합니다. 6자 이상으로 입력해 주세요.",
    "validation_failed": "이메일 형식이 올바르지 않습니다.",
    "over_email_send_rate_limit": "잠시 후 다시 시도해 주세요 (이메일 발송 제한).",
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


@app.errorhandler(ApiError)
def handle_api_error(exc):
    return jsonify(error=exc.message), exc.status


@app.errorhandler(SupabaseError)
def handle_supabase_error(exc):
    app.logger.warning("Supabase error %s %s: %s", exc.status, exc.code, exc.message)
    if exc.status in (401, 403):
        return jsonify(error="권한이 없습니다."), 403
    if exc.status >= 500:
        return jsonify(error="서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."), 502
    return jsonify(error="요청을 처리할 수 없습니다. 입력값을 확인해 주세요."), 400


@app.before_request
def block_cross_site_writes():
    # 다른 사이트가 몰래 요청을 보내는 것(CSRF) 방지: 쓰기 요청은 우리 화면(app.js)이 붙이는 헤더가 있어야 함.
    # 다른 사이트는 이 헤더를 붙이면 브라우저의 CORS 검사에 막힌다.
    if request.path.startswith("/api/") and request.method in ("POST", "PATCH", "DELETE"):
        if request.headers.get("X-Requested-With") != "fetch":
            raise ApiError(403, "잘못된 요청입니다.")


# ---------- 세션 / 토큰 ----------

def save_auth(data):
    session.clear()
    session.permanent = True
    session["access_token"] = data["access_token"]
    session["refresh_token"] = data["refresh_token"]
    session["expires_at"] = data.get("expires_at") or int(time.time()) + data.get("expires_in", 3600)
    session["email"] = data["user"]["email"]


def access_token():
    """로그인 사용자의 access token. 만료 1분 전이면 refresh token으로 갱신."""
    if "access_token" not in session:
        raise ApiError(401, "로그인이 필요합니다.")
    if session["expires_at"] - 60 < time.time():
        try:
            save_auth(supa.refresh(session["refresh_token"]))
        except SupabaseError:
            session.clear()
            raise ApiError(401, "로그인이 만료되었습니다. 다시 로그인해 주세요.")
    return session["access_token"]


def credentials():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        raise ApiError(400, "이메일과 비밀번호를 입력해 주세요.")
    return email, password


def auth_error(exc):
    return ApiError(400 if exc.status < 500 else 502, AUTH_ERRORS.get(exc.code, exc.message))


# ---------- 화면 ----------

@app.get("/")
def index():
    return app.send_static_file("index.html")


# ---------- Auth API ----------

@app.post("/api/auth/signup")
def signup():
    email, password = credentials()
    try:
        data = supa.sign_up(email, password)
    except SupabaseError as exc:
        raise auth_error(exc)
    if data and data.get("access_token"):  # 이메일 인증을 끈 프로젝트면 바로 로그인
        save_auth(data)
        return jsonify(email=session["email"])
    return jsonify(needs_confirmation=True)


@app.post("/api/auth/login")
def login():
    email, password = credentials()
    try:
        save_auth(supa.sign_in(email, password))
    except SupabaseError as exc:
        raise auth_error(exc)
    return jsonify(email=session["email"])


@app.post("/api/auth/logout")
def logout():
    token = session.get("access_token")
    session.clear()
    if token:
        try:
            supa.sign_out(token)
        except SupabaseError:
            pass  # 이미 만료된 토큰이어도 로컬 로그아웃은 완료
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    if "access_token" not in session:
        return jsonify(email=None)
    access_token()  # 필요하면 갱신
    return jsonify(email=session["email"])


# ---------- Todo API ----------

TODO_COLUMNS = "id,title,description,created_at,updated_at,completed_at,due_date,is_completed,tags"


def pg_array_literal(value):
    return '{"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"}'


@app.get("/api/todos")
def list_todos():
    params = {
        "select": TODO_COLUMNS,
        "order": "is_completed.asc,due_date.asc.nullslast,created_at.desc",
    }
    status = request.args.get("status", "all")
    if status == "active":
        params["is_completed"] = "is.false"
    elif status == "done":
        params["is_completed"] = "is.true"
    tag = request.args.get("tag", "").strip()
    if tag:
        params["tags"] = "cs." + pg_array_literal(tag)
    return jsonify(supa.select(access_token(), "todos_with_tags", params))


@app.get("/api/tags")
def list_tags():
    return jsonify(supa.select(access_token(), "tag_counts", {"select": "name,cnt", "order": "name"}))


def parse_tags(raw):
    """'업무, 긴급,업무' 또는 ['업무', ...] -> ['업무', '긴급'] (대소문자 무시 중복 제거)"""
    items = raw.split(",") if isinstance(raw, str) else raw or []
    tags, seen = [], set()
    for name in items:
        name = str(name).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            tags.append(name)
    return tags


@app.post("/api/todos")
def create_todo():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    if not title:
        raise ApiError(400, "제목을 입력해 주세요.")
    due_date = body.get("due_date") or None
    if due_date:
        try:
            due_date = date.fromisoformat(due_date).isoformat()
        except (TypeError, ValueError):
            raise ApiError(400, "마감일 형식이 올바르지 않습니다.")
    todo_id = supa.rpc(access_token(), "create_todo", {
        "p_title": title, "p_due_date": due_date, "p_tags": parse_tags(body.get("tags")),
    })
    return jsonify(id=todo_id), 201


@app.patch("/api/todos/<int:todo_id>")
def update_todo(todo_id):
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("completed"), bool):
        raise ApiError(400, "completed(true/false)가 필요합니다.")
    completed_at = datetime.now(timezone.utc).isoformat() if body["completed"] else None
    rows = supa.update(access_token(), "todos", {"id": f"eq.{todo_id}"}, {"completed_at": completed_at})
    if not rows:  # 없거나 남의 할 일 (RLS가 걸러냄)
        raise ApiError(404, "할 일을 찾을 수 없습니다.")
    return jsonify(ok=True)


@app.delete("/api/todos/<int:todo_id>")
def delete_todo(todo_id):
    if not supa.rpc(access_token(), "delete_todo", {"p_id": todo_id}):
        raise ApiError(404, "할 일을 찾을 수 없습니다.")
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
