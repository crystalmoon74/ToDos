# Todo 앱 DB 설계 (Supabase Postgres)

스키마 파일: [schema.sql](schema.sql). Supabase SQL Editor에서 한 번 실행합니다. 다시 실행해도 안전합니다.

## 구조

```
auth.users 1 ──< todos 1 ──< todo_tags >── 1 tags >── 1 auth.users
```

- `auth.users`: Supabase Auth가 관리하는 사용자 테이블 (직접 만들지 않음)
- 할 일과 태그는 모두 `user_id`로 주인을 기록합니다. 비워 두면 DB가 `auth.uid()`(로그인한 사용자)로 자동으로 채웁니다.
- 사용자를 삭제하면 그 사용자의 할 일과 태그도 함께 삭제됩니다.

## 테이블

### todos
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | bigint identity PK | 자동 증가 |
| user_id | uuid | **소유 사용자**, 기본값 `auth.uid()` |
| title | text | 제목 (공백만 있으면 거부) |
| description | text | 메모 (선택) |
| created_at | timestamptz | 생성일자 |
| updated_at | timestamptz | 트리거로 자동 갱신 |
| completed_at | timestamptz | 완료일자, NULL이면 미완료 |
| due_date | date | 마감일 |
| is_completed | boolean (계산 컬럼) | `completed_at IS NOT NULL` |

### tags
`id`, `user_id`, `name`, `created_at`. `(user_id, lower(name))`이 유일하므로 **사용자마다** 태그를 따로 갖고, 같은 사용자 안에서는 대소문자만 다른 이름이 중복되지 않습니다.

### todo_tags
`(todo_id, tag_id)` PK. 할 일이나 태그가 삭제되면 연결도 함께 삭제됩니다.

## RLS (행 수준 보안)

세 테이블 모두 RLS를 켰고, 정책은 전부 `to authenticated`(로그인한 사용자 전용)입니다.

| 테이블 | 조회 | 추가 | 수정 | 삭제 |
|---|---|---|---|---|
| todos | 내 것만 | `user_id`가 나일 때만 | 내 것만, 남에게 넘기기 금지 | 내 것만 |
| tags | 내 것만 | 내 것으로만 | 내 것만 | 내 것만 |
| todo_tags | 내 할 일의 연결만 | 할 일과 태그가 **둘 다** 내 것일 때만 | (해당 없음) | 내 할 일의 연결만 |

로그인하지 않은 요청(`anon`)은 정책이 없어서 아무것도 못 하고, 테이블 권한도 `revoke`해서 이중으로 막았습니다.

## 뷰와 함수

뷰와 함수 모두 `security_invoker` 방식이라, **호출한 사용자의 RLS가 그대로 적용**됩니다. 관리자 권한으로 우회하지 않습니다.

| 이름 | 역할 |
|---|---|
| `todos_with_tags` (뷰) | 할 일 + 태그 이름 배열. 목록 화면용 |
| `tag_counts` (뷰) | 태그별 할 일 수. 태그 바용 |
| `create_todo(title, due_date, tags[])` | 할 일 추가 + 태그 생성·연결을 한 트랜잭션으로 처리 |
| `delete_todo(id)` | 할 일 삭제 + 안 쓰이게 된 내 태그 정리 |

함수는 로그인한 사용자만 실행할 수 있습니다.

## 백엔드가 DB에 접근하는 방식

1. 사용자가 로그인하면 백엔드가 Supabase Auth에서 받은 토큰을 서버 서명 쿠키(HttpOnly)에 보관합니다.
2. DB를 호출할 때 `apikey: <publishable/anon 키>` 헤더와 `Authorization: Bearer <사용자 토큰>` 헤더를 함께 보냅니다. 그러면 Supabase가 이 요청을 "그 사용자"로 인식해 RLS를 적용합니다.
3. RLS를 우회하는 secret/service_role 키는 쓰지 않으며, 그런 키를 넣으면 앱이 시작을 거부합니다.
