// 화면 코드: 이 앱의 백엔드(/api/*)만 호출한다. Supabase 주소/키는 여기 없다.

const state = { status: "all", tag: "", mode: "login" };
const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    showAuth(data.error);
    throw new Error(data.error);
  }
  if (!res.ok) throw new Error(data.error || "요청에 실패했습니다.");
  return data;
}

function showMessage(el, text, kind = "error") {
  el.textContent = text || "";
  el.className = `message ${kind}`;
  el.hidden = !text;
}

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

// ---------- 로그인 ----------

function showAuth(message) {
  $("loading").hidden = true;
  $("todo-view").hidden = true;
  $("auth-view").hidden = false;
  showMessage($("auth-message"), message);
}

function setAuthMode(mode) {
  state.mode = mode;
  const login = mode === "login";
  $("auth-submit").textContent = login ? "로그인" : "회원가입";
  $("auth-switch-text").textContent = login ? "계정이 없나요?" : "이미 계정이 있나요?";
  $("auth-switch").textContent = login ? "회원가입" : "로그인";
  $("auth-form").password.autocomplete = login ? "current-password" : "new-password";
  showMessage($("auth-message"), "");
}

$("auth-switch").addEventListener("click", () => setAuthMode(state.mode === "login" ? "signup" : "login"));

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const creds = { email: form.email.value, password: form.password.value };
  $("auth-submit").disabled = true;
  try {
    const data = await api("POST", `/api/auth/${state.mode}`, creds);
    if (data.needs_confirmation) {
      setAuthMode("login");
      showMessage($("auth-message"), "가입 확인 메일을 보냈습니다. 메일의 링크를 누른 뒤 로그인해 주세요.", "info");
      return;
    }
    form.reset();
    showTodos(data.email);
  } catch (err) {
    showMessage($("auth-message"), err.message);
  } finally {
    $("auth-submit").disabled = false;
  }
});

$("logout").addEventListener("click", async () => {
  await api("POST", "/api/auth/logout").catch(() => {});
  setAuthMode("login");
  showAuth();
});

// ---------- 할 일 ----------

function showTodos(email) {
  $("loading").hidden = true;
  $("auth-view").hidden = true;
  $("todo-view").hidden = false;
  $("user-email").textContent = email;
  showMessage($("todo-message"), "");
  refresh();
}

const localToday = () => new Date().toLocaleDateString("sv-SE"); // YYYY-MM-DD
const fmt = (iso) => new Date(iso).toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "short" });

async function refresh() {
  const params = new URLSearchParams({ status: state.status });
  if (state.tag) params.set("tag", state.tag);
  try {
    const [todos, tags] = await Promise.all([api("GET", `/api/todos?${params}`), api("GET", "/api/tags")]);
    renderTags(tags);
    renderList(todos);
  } catch (err) {
    showMessage($("todo-message"), err.message);
  }
}

function setTag(tag) {
  state.tag = tag;
  refresh();
}

function renderTags(tags) {
  const bar = $("tag-bar");
  bar.replaceChildren();
  if (state.tag) {
    bar.append(el("button", { type: "button", className: "tag clear", textContent: `× ${state.tag}`, onclick: () => setTag("") }));
  }
  for (const t of tags) {
    if (t.name === state.tag) continue;
    bar.append(el("button", { type: "button", className: "tag", onclick: () => setTag(t.name) },
      [`#${t.name} `, el("small", { textContent: t.cnt })]));
  }
}

function renderList(todos) {
  const list = $("list");
  list.replaceChildren();
  if (!todos.length) {
    list.append(el("li", { className: "empty", textContent: "할 일이 없습니다." }));
    return;
  }
  const today = localToday();
  for (const t of todos) {
    const overdue = t.due_date && !t.is_completed && t.due_date < today;
    const meta = [];
    if (t.due_date) meta.push(el("span", { className: "due", textContent: `마감 ${t.due_date}${overdue ? " (지남)" : ""}` }));
    meta.push(el("span", { textContent: `생성 ${fmt(t.created_at)}` }));
    if (t.completed_at) meta.push(el("span", { textContent: `완료 ${fmt(t.completed_at)}` }));

    const body = el("div", { className: "body" }, [
      el("div", { className: "title", textContent: t.title }),
      el("div", { className: "meta" }, meta),
    ]);
    if (t.tags.length) {
      body.append(el("div", { className: "item-tags" },
        t.tags.map((name) => el("button", { type: "button", className: "tag", textContent: `#${name}`, onclick: () => setTag(name) }))));
    }

    list.append(el("li", { className: [t.is_completed && "done", overdue && "overdue"].filter(Boolean).join(" ") }, [
      el("button", {
        type: "button", className: "check", textContent: t.is_completed ? "✓" : "",
        title: t.is_completed ? "완료 취소" : "완료 표시",
        onclick: () => mutate(() => api("PATCH", `/api/todos/${t.id}`, { completed: !t.is_completed })),
      }),
      body,
      el("button", {
        type: "button", className: "delete", textContent: "삭제",
        onclick: () => confirm("삭제할까요?") && mutate(() => api("DELETE", `/api/todos/${t.id}`)),
      }),
    ]));
  }
}

async function mutate(action) {
  try {
    await action();
    showMessage($("todo-message"), "");
  } catch (err) {
    showMessage($("todo-message"), err.message);
  }
  refresh();
}

$("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const todo = { title: form.title.value, due_date: form.due_date.value || null, tags: form.tags.value };
  await mutate(async () => {
    await api("POST", "/api/todos", todo);
    form.reset();
    form.title.focus();
  });
});

$("filters").addEventListener("click", (e) => {
  const status = e.target.dataset.status;
  if (!status) return;
  state.status = status;
  for (const b of $("filters").children) b.classList.toggle("on", b === e.target);
  refresh();
});

// ---------- 시작 ----------

api("GET", "/api/me")
  .then((data) => (data.email ? showTodos(data.email) : showAuth()))
  .catch((err) => showAuth(err.message));
