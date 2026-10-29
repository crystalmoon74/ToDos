"""Supabase 버전 저장 확인 + RLS 확인.

1) 실제 백엔드 서버를 띄워 로그인 → 추가·완료·삭제 → 서버를 껐다 켜서 데이터가 남는지
2) Supabase에 저장된 행에 소유자(user_id)가 기록되는지
3) RLS: 로그인 안 한 요청(anon)과 다른 사용자(B)의 접근이 막히는지
   (백엔드를 거치지 않고 Supabase REST API를 직접 호출하는 공격 포함)

.env 의 SUPABASE_URL / SUPABASE_ANON_KEY 를 사용한다. 키는 출력하지 않는다.
실행할 때마다 테스트 사용자 2명(todo-test-*@example.com)이 생기며, 할 일 데이터는 끝에 지운다.
사용자는 Supabase 대시보드 Authentication → Users 에서 지울 수 있다.
Confirm email 이 켜져 있으면 가입 직후 로그인이 안 되므로 끄고 실행한다.

실행: .venv\\Scripts\\python tests\\verify_supabase.py
"""
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_ANON_KEY"]
REST = f"{URL}/rest/v1"
H = {"X-Requested-With": "fetch"}
results = []


def check(cond, label, detail=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label + (f"  -> {detail}" if detail and not cond else ""))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "run", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


def login(base, email, pw):
    s = requests.Session()
    s.headers.update(H)
    r = s.post(base + "/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    return s, r


def user_token(email, pw):
    """Supabase Auth에 직접 로그인해 사용자 토큰을 받는다 (공격자가 자기 토큰을 쓰는 상황)."""
    r = requests.post(f"{URL}/auth/v1/token?grant_type=password", headers={"apikey": KEY},
                      json={"email": email, "password": pw}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"], r.json()["user"]["id"]


def titles(s, base, query=""):
    return [t["title"] for t in s.get(base + "/api/todos" + query, timeout=15).json()]


run = secrets.token_hex(3)
email_a, email_b = (f"todo-test-{n}-{run}@example.com" for n in "ab")
pw = secrets.token_urlsafe(12)
port = free_port()
print("Supabase 프로젝트:", URL)
print("테스트 사용자:", email_a, email_b)

# ------------------------------------------------------------------
print("\n== 1. 저장 확인: 1회차 서버 실행 ==")
proc, base = start(port)
for email in (email_a, email_b):
    r = requests.post(base + "/api/auth/signup", json={"email": email, "password": pw}, headers=H, timeout=15)
    check(r.status_code == 200 and r.json().get("email") == email, f"가입 {email[:11]}..", r.text)
r = requests.post(base + "/api/auth/login", json={"email": email_a, "password": "wrong"}, headers=H, timeout=15)
check(r.status_code == 400, "틀린 비밀번호 거부")
check(requests.get(base + "/api/todos", timeout=15).status_code == 401, "로그인 없이 목록 요청 -> 401")
check(requests.post(base + "/api/todos", json={"title": "x"}, timeout=15).status_code in (401, 403),
      "CSRF 헤더 없는 쓰기 요청 거부")

A, r = login(base, email_a, pw)
check(r.status_code == 200, "A 로그인")
ids = {}
for title, due, tags in [("보고서 작성", "2026-11-05", "업무, 긴급"), ("운동하기", None, "건강"), ("지울 항목", None, "")]:
    r = A.post(base + "/api/todos", json={"title": title, "due_date": due, "tags": tags}, timeout=15)
    ids[title] = r.json().get("id")
check(sorted(titles(A, base)) == sorted(ids), "A 추가 3건이 목록에 보임")
check(A.patch(f"{base}/api/todos/{ids['운동하기']}", json={"completed": True}, timeout=15).ok, "A 완료 표시")
check(A.delete(f"{base}/api/todos/{ids['지울 항목']}", timeout=15).ok, "A 삭제")
before = A.get(base + "/api/todos", timeout=15).json()
check([t["title"] for t in before] == ["보고서 작성", "운동하기"], "추가·완료·삭제 반영")

print("\n== 서버 종료 ==")
stop(proc)
try:
    requests.get(base, timeout=1)
    check(False, "서버가 꺼짐")
except requests.ConnectionError:
    check(True, "서버가 꺼짐 (접속 불가)")

print("\n== 2회차 서버 실행: 새로 로그인해서 확인 ==")
proc, base = start(port)
A, r = login(base, email_a, pw)
after = A.get(base + "/api/todos", timeout=15).json()
check(after == before, "다시 켠 뒤 목록이 끄기 전과 같음 (제목, 마감일, 완료일자, 태그)")
check(after[1]["completed_at"] and after[0]["tags"] == ["긴급", "업무"], "완료일자와 태그 유지")

# ------------------------------------------------------------------
print("\n== 2. Supabase에 저장된 행 (A의 토큰으로 REST 직접 조회) ==")
a_tok, a_uid = user_token(email_a, pw)
b_tok, b_uid = user_token(email_b, pw)
ah = {"apikey": KEY, "Authorization": f"Bearer {a_tok}"}
rows = requests.get(f"{REST}/todos?select=id,user_id,title,due_date,created_at,completed_at&order=id",
                    headers=ah, timeout=15).json()
for row in rows:
    print("   ", row)
check(len(rows) == 2 and all(row["user_id"] == a_uid for row in rows), "행마다 소유자 user_id = A 가 기록됨")

# ------------------------------------------------------------------
print("\n== 3-1. RLS: 로그인 안 한 요청(anon 키만) ==")
anon = {"apikey": KEY, "Content-Type": "application/json"}
for rel in ("todos", "tags", "todo_tags", "todos_with_tags", "tag_counts"):
    r = requests.get(f"{REST}/{rel}?select=*", headers=anon, timeout=15)
    check(r.status_code in (401, 403) or (r.ok and r.json() == []), f"anon SELECT {rel} -> {r.status_code}", r.text)
r = requests.post(f"{REST}/todos", headers=anon, json={"title": "anon"}, timeout=15)
check(r.status_code in (401, 403), f"anon INSERT todos -> {r.status_code}", r.text)
r = requests.post(f"{REST}/rpc/create_todo", headers=anon, json={"p_title": "anon"}, timeout=15)
check(r.status_code in (401, 403, 404), f"anon rpc create_todo -> {r.status_code}", r.text)

print("\n== 3-2. RLS: 사용자 B가 A의 데이터에 접근 (백엔드 경유) ==")
B, r = login(base, email_b, pw)
a_id = ids["보고서 작성"]
check(B.get(base + "/api/todos", timeout=15).json() == [], "B 목록에 A의 할 일이 안 보임")
check(B.get(base + "/api/tags", timeout=15).json() == [], "B 태그에 A의 태그가 안 보임")
check(B.patch(f"{base}/api/todos/{a_id}", json={"completed": True}, timeout=15).status_code == 404, "B가 A의 할 일 완료 처리 -> 404")
check(B.delete(f"{base}/api/todos/{a_id}", timeout=15).status_code == 404, "B가 A의 할 일 삭제 -> 404")
r = B.post(base + "/api/todos", json={"title": "B의 할 일", "tags": "업무"}, timeout=15)
b_id = r.json().get("id")

print("\n== 3-3. RLS: 사용자 B가 자기 토큰으로 Supabase REST 직접 공격 (백엔드 우회) ==")
bh = {"apikey": KEY, "Authorization": f"Bearer {b_tok}", "Content-Type": "application/json",
      "Prefer": "return=representation"}
r = requests.get(f"{REST}/todos?id=eq.{a_id}", headers=bh, timeout=15)
check(r.ok and r.json() == [], "B SELECT A의 할 일 -> 빈 결과", r.text)
r = requests.patch(f"{REST}/todos?id=eq.{a_id}", headers=bh, json={"title": "hacked"}, timeout=15)
check(r.ok and r.json() == [], "B UPDATE A의 할 일 -> 0건", r.text)
r = requests.delete(f"{REST}/todos?id=eq.{a_id}", headers=bh, timeout=15)
check(r.ok and r.json() == [], "B DELETE A의 할 일 -> 0건", r.text)
r = requests.post(f"{REST}/todos", headers=bh, json={"title": "planted", "user_id": a_uid}, timeout=15)
check(r.status_code in (401, 403) and "row-level security" in r.text, "B가 A 명의로 INSERT -> RLS 차단", r.text)
r = requests.patch(f"{REST}/todos?id=eq.{b_id}", headers=bh, json={"user_id": a_uid}, timeout=15)
check(r.status_code in (401, 403) and "row-level security" in r.text, "B가 자기 할 일을 A에게 넘기기 -> RLS 차단", r.text)
b_tag = requests.get(f"{REST}/tags?select=id", headers=bh, timeout=15).json()[0]["id"]
r = requests.post(f"{REST}/todo_tags", headers=bh, json={"todo_id": a_id, "tag_id": b_tag}, timeout=15)
check(r.status_code in (401, 403), "B가 A의 할 일에 태그 연결 -> RLS 차단", r.text)
r = requests.post(f"{REST}/rpc/delete_todo", headers=bh, json={"p_id": a_id}, timeout=15)
check(r.ok and r.json() is False, "B rpc delete_todo(A의 할 일) -> false", r.text)
r = requests.get(f"{REST}/todos_with_tags?select=title", headers=bh, timeout=15)
check(r.ok and [x["title"] for x in r.json()] == ["B의 할 일"], "B 뷰 조회 -> 자기 것만", r.text)

check(A.get(base + "/api/todos", timeout=15).json() == after, "공격 후에도 A의 데이터 그대로")

# ------------------------------------------------------------------
print("\n== 정리 ==")
for s in (A, B):
    for t in s.get(base + "/api/todos", timeout=15).json():
        s.delete(f"{base}/api/todos/{t['id']}", timeout=15)
check(A.get(base + "/api/todos", timeout=15).json() == [] and B.get(base + "/api/todos", timeout=15).json() == [],
      "테스트 할 일 삭제 완료 (테스트 사용자는 대시보드에서 삭제)")
stop(proc)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
