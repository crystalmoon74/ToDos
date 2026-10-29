-- Todo 앱 Supabase(Postgres) 스키마 (v2)
-- 실행 방법: Supabase 대시보드 → SQL Editor → 이 파일 전체를 붙여넣고 Run
-- 다시 실행해도 안전하도록 IF NOT EXISTS / OR REPLACE / DROP ... IF EXISTS 를 사용

-- =========================================================
-- 테이블
-- =========================================================

-- 할 일 (user_id = 소유 사용자, 비워 두면 로그인한 사용자로 자동 기록)
create table if not exists public.todos (
    id            bigint generated always as identity primary key,
    user_id       uuid        not null default auth.uid() references auth.users(id) on delete cascade,
    title         text        not null check (length(trim(title)) > 0),
    description   text,
    created_at    timestamptz not null default now(),   -- 생성일자
    updated_at    timestamptz not null default now(),
    completed_at  timestamptz,                          -- 완료일자 (NULL = 미완료)
    due_date      date,                                 -- 마감일
    is_completed  boolean generated always as (completed_at is not null) stored
);

-- 태그 (사용자별로 따로 관리, 같은 사용자 안에서 대소문자 무시 중복 금지)
create table if not exists public.tags (
    id          bigint generated always as identity primary key,
    user_id     uuid        not null default auth.uid() references auth.users(id) on delete cascade,
    name        text        not null check (length(trim(name)) > 0),
    created_at  timestamptz not null default now()
);
create unique index if not exists tags_user_name_key on public.tags (user_id, lower(name));

-- 할 일 ↔ 태그 (다대다)
create table if not exists public.todo_tags (
    todo_id  bigint not null references public.todos(id) on delete cascade,
    tag_id   bigint not null references public.tags(id)  on delete cascade,
    primary key (todo_id, tag_id)
);

create index if not exists todos_user_id_idx      on public.todos (user_id);
create index if not exists todos_due_date_idx     on public.todos (due_date);
create index if not exists todo_tags_tag_id_idx   on public.todo_tags (tag_id);

-- 수정 시 updated_at 자동 갱신
create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = '' as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

drop trigger if exists todos_set_updated_at on public.todos;
create trigger todos_set_updated_at
before update on public.todos
for each row execute function public.set_updated_at();

-- =========================================================
-- RLS (행 수준 보안): 로그인한 사용자는 자기 데이터만
-- 정책이 모두 "to authenticated" 라서 로그인 안 한 요청(anon)은 아무것도 못 함
-- =========================================================

alter table public.todos     enable row level security;
alter table public.tags      enable row level security;
alter table public.todo_tags enable row level security;

-- todos
drop policy if exists "todos: select own" on public.todos;
drop policy if exists "todos: insert own" on public.todos;
drop policy if exists "todos: update own" on public.todos;
drop policy if exists "todos: delete own" on public.todos;
create policy "todos: select own" on public.todos for select to authenticated
    using (user_id = (select auth.uid()));
create policy "todos: insert own" on public.todos for insert to authenticated
    with check (user_id = (select auth.uid()));
create policy "todos: update own" on public.todos for update to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));          -- 다른 사용자에게 넘기기 금지
create policy "todos: delete own" on public.todos for delete to authenticated
    using (user_id = (select auth.uid()));

-- tags
drop policy if exists "tags: select own" on public.tags;
drop policy if exists "tags: insert own" on public.tags;
drop policy if exists "tags: update own" on public.tags;
drop policy if exists "tags: delete own" on public.tags;
create policy "tags: select own" on public.tags for select to authenticated
    using (user_id = (select auth.uid()));
create policy "tags: insert own" on public.tags for insert to authenticated
    with check (user_id = (select auth.uid()));
create policy "tags: update own" on public.tags for update to authenticated
    using (user_id = (select auth.uid()))
    with check (user_id = (select auth.uid()));
create policy "tags: delete own" on public.tags for delete to authenticated
    using (user_id = (select auth.uid()));

-- todo_tags: 연결하는 할 일과 태그가 둘 다 내 것이어야 함
drop policy if exists "todo_tags: select own" on public.todo_tags;
drop policy if exists "todo_tags: insert own" on public.todo_tags;
drop policy if exists "todo_tags: delete own" on public.todo_tags;
create policy "todo_tags: select own" on public.todo_tags for select to authenticated
    using (exists (select 1 from public.todos t where t.id = todo_id and t.user_id = (select auth.uid())));
create policy "todo_tags: insert own" on public.todo_tags for insert to authenticated
    with check (
        exists (select 1 from public.todos t where t.id = todo_id and t.user_id = (select auth.uid()))
        and exists (select 1 from public.tags g where g.id = tag_id and g.user_id = (select auth.uid()))
    );
create policy "todo_tags: delete own" on public.todo_tags for delete to authenticated
    using (exists (select 1 from public.todos t where t.id = todo_id and t.user_id = (select auth.uid())));

-- =========================================================
-- 조회용 뷰 (security_invoker = 조회하는 사용자의 RLS가 그대로 적용됨)
-- =========================================================

create or replace view public.todos_with_tags with (security_invoker = true) as
select t.id, t.user_id, t.title, t.description, t.created_at, t.updated_at,
       t.completed_at, t.due_date, t.is_completed,
       coalesce(array_agg(g.name order by g.name) filter (where g.id is not null), '{}') as tags
from public.todos t
left join public.todo_tags tt on tt.todo_id = t.id
left join public.tags g       on g.id = tt.tag_id
group by t.id;

create or replace view public.tag_counts with (security_invoker = true) as
select g.name, count(*) as cnt
from public.tags g
join public.todo_tags tt on tt.tag_id = g.id
group by g.id, g.name;

-- =========================================================
-- 함수 (security invoker = 호출한 사용자 권한으로 실행 → RLS 적용, 한 트랜잭션)
-- =========================================================

-- 할 일 추가 + 태그 연결
create or replace function public.create_todo(p_title text, p_due_date date default null, p_tags text[] default '{}')
returns bigint
language plpgsql security invoker set search_path = '' as $$
declare
    v_todo_id bigint;
    v_name    text;
begin
    insert into public.todos (title, due_date) values (trim(p_title), p_due_date)
    returning id into v_todo_id;

    foreach v_name in array coalesce(p_tags, '{}') loop
        v_name := trim(v_name);
        continue when v_name = '';
        insert into public.tags (name) values (v_name)
        on conflict (user_id, lower(name)) do nothing;
        insert into public.todo_tags (todo_id, tag_id)
        select v_todo_id, g.id from public.tags g
        where g.user_id = auth.uid() and lower(g.name) = lower(v_name)
        on conflict do nothing;
    end loop;

    return v_todo_id;
end;
$$;

-- 할 일 삭제 + 더 이상 안 쓰는 내 태그 정리. 삭제했으면 true
create or replace function public.delete_todo(p_id bigint)
returns boolean
language plpgsql security invoker set search_path = '' as $$
begin
    delete from public.todos where id = p_id;
    if not found then
        return false;
    end if;
    delete from public.tags g
    where g.user_id = auth.uid()
      and not exists (select 1 from public.todo_tags tt where tt.tag_id = g.id);
    return true;
end;
$$;

-- 로그인한 사용자만 함수 실행 가능
revoke execute on function public.create_todo(text, date, text[]) from public, anon;
revoke execute on function public.delete_todo(bigint)            from public, anon;
grant  execute on function public.create_todo(text, date, text[]) to authenticated;
grant  execute on function public.delete_todo(bigint)            to authenticated;

-- 로그인한 사용자에게 테이블/뷰 권한 부여 (어떤 행이 보이는지는 위 RLS 정책이 결정)
-- 프로젝트의 "새 테이블 자동 노출" 설정이 꺼져 있어도 동작하도록 명시
grant usage on schema public to authenticated;
grant select, insert, update, delete on public.todos, public.tags, public.todo_tags to authenticated;
grant select on public.todos_with_tags, public.tag_counts to authenticated;

-- 로그인 안 한 요청은 테이블/뷰 자체에 접근 불가 (RLS에 더한 이중 잠금)
revoke all on public.todos, public.tags, public.todo_tags, public.todos_with_tags, public.tag_counts from anon;

-- API(PostgREST)가 새 테이블/함수를 바로 인식하도록 갱신
notify pgrst, 'reload schema';
