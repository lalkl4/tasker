// Tasker — веб-клиент. Работает с тем же API v1, что и мобильное приложение.

const API = "/api/v1";
const TOKEN_KEY = "tasker.token";

const state = {
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
  server: null,      // ответ /.well-known/tasker
  projects: [],
  tasks: [],
  activeProject: null,
  query: "",
  mode: "login",     // login | register
};

const STATUS_LABEL = { todo: "К выполнению", doing: "В работе", done: "Готово" };
const NEXT = { todo: "doing", doing: "done", done: "todo" };
const PREV = { doing: "todo", done: "doing" };

const $ = (sel) => document.querySelector(sel);

// ---------- HTTP ----------

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const res = await fetch(API + path, { ...options, headers });

  if (res.status === 401) {
    // Токен протух или отозван — возвращаем на экран входа
    logout("Сессия истекла, войдите заново");
    throw new ApiError("Не авторизован", 401);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body.detail ?? msg;
      if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join(", ");
    } catch {}
    throw new ApiError(msg, res.status);
  }
  return res.status === 204 ? null : res.json();
}

let toastTimer;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 2600);
}

const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escape = (s) => String(s).replace(/[&<>"']/g, (c) => ENTITIES[c]);

// ---------- вход ----------

async function loadServerInfo() {
  try {
    state.server = await (await fetch("/.well-known/tasker")).json();
    $("#auth-server").textContent =
      `${state.server.product} ${state.server.server_version} · API ${state.server.api_versions.join(", ")}`;
    if (!state.server.registration_open) {
      $("#auth-closed").hidden = false;
      $(".auth-switch").hidden = true;
    }
  } catch {
    $("#auth-server").textContent = "Сервер не отвечает";
  }
}

function setMode(mode) {
  state.mode = mode;
  const isRegister = mode === "register";
  $("#auth-subtitle").textContent = isRegister
    ? "Создание учётной записи на этом сервере"
    : "Вход в свой трекер задач";
  $("#auth-submit").textContent = isRegister ? "Зарегистрироваться" : "Войти";
  $("#auth-name-row").hidden = !isRegister;
  $("#auth-switch-text").textContent = isRegister
    ? "Уже есть учётная запись?"
    : "Ещё нет учётной записи?";
  $("#auth-switch").textContent = isRegister ? "Войти" : "Зарегистрироваться";
  $("#auth-password").autocomplete = isRegister ? "new-password" : "current-password";
  $("#auth-error").hidden = true;
}

function showAuth() {
  $("#auth").hidden = false;
  $("#app").hidden = true;
  loadServerInfo();
  setMode("login");
}

function showApp() {
  $("#auth").hidden = true;
  $("#app").hidden = false;
  $("#user-name").textContent = state.user?.display_name || state.user?.email || "";
}

function logout(message) {
  state.token = null;
  state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  showAuth();
  if (message) toast(message);
}

$("#auth-switch").addEventListener("click", (e) => {
  e.preventDefault();
  setMode(state.mode === "login" ? "register" : "login");
});

$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#auth-error");
  err.hidden = true;

  const body = {
    email: $("#auth-email").value.trim(),
    password: $("#auth-password").value,
  };
  if (state.mode === "register") {
    body.display_name = $("#auth-name").value.trim();
  }

  const btn = $("#auth-submit");
  btn.disabled = true;
  try {
    const path = state.mode === "register" ? "/auth/register" : "/auth/login";
    const res = await api(path, { method: "POST", body: JSON.stringify(body) });
    state.token = res.access_token;
    state.user = res.user;
    localStorage.setItem(TOKEN_KEY, state.token);
    $("#auth-password").value = "";
    showApp();
    await refresh();
  } catch (e2) {
    err.textContent = e2.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
  }
});

$("#logout").addEventListener("click", () => logout("Вы вышли"));

// ---------- загрузка данных ----------

async function refresh() {
  const params = new URLSearchParams();
  if (state.activeProject !== null) params.set("project_id", state.activeProject);
  if (state.query) params.set("q", state.query);

  const [projects, tasks, stats] = await Promise.all([
    api("/projects"),
    api(`/tasks?${params}`),
    api("/stats"),
  ]);

  state.projects = projects;
  state.tasks = tasks;
  renderProjects();
  renderStats(stats);
  renderBoard();
}

// ---------- рендер ----------

function renderProjects() {
  const total = state.projects.reduce((sum, p) => sum + p.total, 0);
  const items = [
    `<li class="${state.activeProject === null ? "active" : ""}" data-id="all">
       <span class="dot" style="background:#8b93a7"></span>
       <span class="pname">Все проекты</span>
       <span class="pcount">${total}</span>
     </li>`,
    ...state.projects.map(
      (p) => `
      <li class="${state.activeProject === p.id ? "active" : ""}" data-id="${p.id}">
        <span class="dot" style="background:${escape(p.color)}"></span>
        <span class="pname" title="${escape(p.name)}">${escape(p.name)}</span>
        <span class="pcount">${p.done}/${p.total}</span>
        <button class="del-project" data-del="${p.id}" title="Удалить проект">×</button>
      </li>`
    ),
  ];
  $("#projects").innerHTML = items.join("");
}

function renderStats(s) {
  const cards = [
    ["Всего задач", s.total, ""],
    ["В работе", s.doing, ""],
    ["Просрочено", s.overdue, s.overdue > 0 ? "warn" : ""],
    ["Готово за 7 дней", s.done_last_7d, "ok"],
  ];
  $("#stats").innerHTML = cards
    .map(([label, value, cls]) => `<div class="stat ${cls}"><b>${value}</b><span>${label}</span></div>`)
    .join("");
}

function renderBoard() {
  const today = new Date().toISOString().slice(0, 10);
  for (const status of ["todo", "doing", "done"]) {
    const tasks = state.tasks.filter((t) => t.status === status);
    $(`#count-${status}`).textContent = tasks.length;
    $(`#col-${status}`).innerHTML =
      tasks.length === 0
        ? `<div class="empty">Пусто</div>`
        : tasks.map((t) => card(t, today)).join("");
  }
}

function card(t, today) {
  const overdue = t.due_date && t.status !== "done" && t.due_date < today;
  const meta = [
    `<span class="chip"><span class="dot" style="background:${escape(t.project_color)}"></span>${escape(t.project_name)}</span>`,
  ];
  if (t.due_date) {
    meta.push(`<span class="chip ${overdue ? "overdue" : ""}">📅 ${escape(t.due_date)}</span>`);
  }

  const back = PREV[t.status]
    ? `<button data-move="${t.id}" data-to="${PREV[t.status]}">←</button>`
    : "";
  const forward = `<button data-move="${t.id}" data-to="${NEXT[t.status]}">${
    t.status === "done" ? "↺ Вернуть" : `→ ${STATUS_LABEL[NEXT[t.status]]}`
  }</button>`;

  return `
    <article class="card p${t.priority} ${t.status === "done" ? "done" : ""}">
      <div class="title">${escape(t.title)}</div>
      ${t.notes ? `<div class="notes">${escape(t.notes)}</div>` : ""}
      <div class="meta">${meta.join("")}</div>
      <div class="actions">
        ${back}${forward}
        <button data-edit="${t.id}">✎</button>
        <button class="danger" data-del-task="${t.id}">🗑</button>
      </div>
    </article>`;
}

// ---------- действия ----------

$("#projects").addEventListener("click", async (e) => {
  const delBtn = e.target.closest("[data-del]");
  if (delBtn) {
    const id = Number(delBtn.dataset.del);
    const project = state.projects.find((p) => p.id === id);
    if (!confirm(`Удалить проект «${project.name}» и все его задачи (${project.total})?`)) return;
    await api(`/projects/${id}`, { method: "DELETE" });
    if (state.activeProject === id) state.activeProject = null;
    toast("Проект удалён");
    return refresh();
  }

  const li = e.target.closest("li[data-id]");
  if (!li) return;
  state.activeProject = li.dataset.id === "all" ? null : Number(li.dataset.id);
  refresh();
});

$("#project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#project-name").value.trim();
  if (!name) return;
  try {
    const project = await api("/projects", {
      method: "POST",
      body: JSON.stringify({ name, color: $("#project-color").value }),
    });
    $("#project-name").value = "";
    state.activeProject = project.id;
    toast("Проект создан");
    refresh();
  } catch (err) {
    toast(err.message);
  }
});

$("#task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("#task-title").value.trim();
  if (!title) return;

  const projectId = state.activeProject ?? state.projects[0]?.id;
  if (!projectId) return toast("Сначала создайте проект");

  try {
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        title,
        priority: Number($("#task-priority").value),
        due_date: $("#task-due").value || null,
      }),
    });
    $("#task-title").value = "";
    $("#task-due").value = "";
    refresh();
  } catch (err) {
    toast(err.message);
  }
});

$(".board").addEventListener("click", async (e) => {
  const move = e.target.closest("[data-move]");
  if (move) {
    await api(`/tasks/${move.dataset.move}`, {
      method: "PATCH",
      body: JSON.stringify({ status: move.dataset.to }),
    });
    return refresh();
  }

  const del = e.target.closest("[data-del-task]");
  if (del) {
    await api(`/tasks/${del.dataset.delTask}`, { method: "DELETE" });
    toast("Задача удалена");
    return refresh();
  }

  const edit = e.target.closest("[data-edit]");
  if (edit) {
    const task = state.tasks.find((t) => t.id === Number(edit.dataset.edit));
    const title = prompt("Название задачи:", task.title);
    if (title === null) return;
    const notes = prompt("Заметки:", task.notes);
    if (notes === null) return;
    await api(`/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: title.trim() || task.title, notes }),
    });
    refresh();
  }
});

let searchTimer;
$("#search").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const value = e.target.value.trim();
  searchTimer = setTimeout(() => {
    state.query = value;
    refresh();
  }, 250);
});

// ---------- старт ----------

(async function start() {
  if (!state.token) return showAuth();
  try {
    state.user = await api("/auth/me");
    showApp();
    await refresh();
  } catch (err) {
    if (err.status !== 401) {
      showAuth();
      toast(`Не удалось подключиться: ${err.message}`);
    }
  }
})();
