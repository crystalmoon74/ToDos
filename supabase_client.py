"""Supabase REST 호출 모음 (Auth + PostgREST). 백엔드에서만 사용."""
import base64
import json

import requests

TIMEOUT = 10  # 초


class SupabaseError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


def assert_not_secret_key(key):
    """RLS를 우회하는 secret/service_role 키는 이 앱에 쓰면 안 됨."""
    if key.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_ANON_KEY에 secret 키가 들어 있습니다. publishable(또는 anon) 키를 넣으세요.")
    parts = key.split(".")
    if len(parts) == 3:  # legacy JWT 키
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            role = json.loads(base64.urlsafe_b64decode(payload)).get("role")
        except ValueError:
            return
        if role == "service_role":
            raise RuntimeError("SUPABASE_ANON_KEY에 service_role 키가 들어 있습니다. anon 키를 넣으세요.")


class Supabase:
    def __init__(self, url, key):
        assert_not_secret_key(key)
        self.url = url.rstrip("/")
        self.key = key

    def _request(self, method, path, access_token=None, params=None, json_body=None, prefer=None):
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if prefer:
            headers["Prefer"] = prefer
        try:
            res = requests.request(
                method, self.url + path, headers=headers, params=params, json=json_body, timeout=TIMEOUT
            )
        except requests.RequestException as exc:
            raise SupabaseError(502, "Supabase에 연결할 수 없습니다.") from exc

        data = res.json() if res.content else None
        if not res.ok:
            data = data if isinstance(data, dict) else {}
            message = (
                data.get("msg") or data.get("message") or data.get("error_description")
                or data.get("error") or res.reason
            )
            code = data.get("error_code") or data.get("code")
            raise SupabaseError(res.status_code, message, code)
        return data

    # ---------- Auth ----------

    def sign_up(self, email, password):
        return self._request("POST", "/auth/v1/signup", json_body={"email": email, "password": password})

    def sign_in(self, email, password):
        return self._request(
            "POST", "/auth/v1/token", params={"grant_type": "password"},
            json_body={"email": email, "password": password},
        )

    def refresh(self, refresh_token):
        return self._request(
            "POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
            json_body={"refresh_token": refresh_token},
        )

    def sign_out(self, access_token):
        self._request("POST", "/auth/v1/logout", access_token=access_token)

    # ---------- DB (PostgREST, 사용자 토큰으로 호출 → RLS 적용) ----------

    def select(self, access_token, table, params):
        return self._request("GET", f"/rest/v1/{table}", access_token, params=params)

    def update(self, access_token, table, params, values):
        return self._request(
            "PATCH", f"/rest/v1/{table}", access_token, params=params, json_body=values,
            prefer="return=representation",
        )

    def rpc(self, access_token, function, args):
        return self._request("POST", f"/rest/v1/rpc/{function}", access_token, json_body=args)
