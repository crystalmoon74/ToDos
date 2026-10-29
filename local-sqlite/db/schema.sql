-- Todo 앱 SQLite 스키마 (v1)
-- 시각 값은 모두 UTC, 'YYYY-MM-DD HH:MM:SS' 형식 (SQLite datetime() 기본 형식)
-- 주의: 외래키는 연결마다 켜야 함 → 앱에서 연결 직후 `PRAGMA foreign_keys = ON;` 실행

PRAGMA foreign_keys = ON;

-- 할 일
CREATE TABLE IF NOT EXISTS todos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    description   TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),          -- 생성일자
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT    CHECK (completed_at IS NULL OR completed_at IS datetime(completed_at)), -- 완료일자 (NULL = 미완료)
    due_date      TEXT    CHECK (due_date IS NULL OR due_date IS date(due_date)),               -- 마감일 'YYYY-MM-DD'
    is_completed  INTEGER GENERATED ALWAYS AS (completed_at IS NOT NULL) VIRTUAL               -- 완료 여부 (자동 계산)
);

-- 태그 (이름 중복 불가, 대소문자 무시)
CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE CHECK (length(trim(name)) > 0),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 할 일 ↔ 태그 (다대다)
CREATE TABLE IF NOT EXISTS todo_tags (
    todo_id  INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
) WITHOUT ROWID;

-- 인덱스: 목록 필터/정렬, 태그별 조회
CREATE INDEX IF NOT EXISTS idx_todos_completed_at ON todos(completed_at);
CREATE INDEX IF NOT EXISTS idx_todos_due_date     ON todos(due_date);
CREATE INDEX IF NOT EXISTS idx_todo_tags_tag_id   ON todo_tags(tag_id);

-- 수정 시 updated_at 자동 갱신
CREATE TRIGGER IF NOT EXISTS trg_todos_updated_at
AFTER UPDATE ON todos
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE todos SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- 스키마 버전 (향후 마이그레이션용)
PRAGMA user_version = 1;
