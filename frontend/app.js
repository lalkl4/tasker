// TaskFlow — фронт на ванильном JS, общается с /api/*

const state = {
  projects: [],
  tasks: [],
  activeProject: null, // null = все проекты
  query: "",
};

const STATUS_LABEL = { todo: "К выполнению", doing: "В работе", done: "Готово" };
const NEXT = { todo: "doing", doing: "done", done: "todo" };
const PREV = { doing: "todo", done: "doing" };

const $ = (sel) => document.querySelector(sel);

// ---------- HTTP ----------

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body.detail ?? msg;
      if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join(", ");
    } catch {}
    throw new Error(msg);
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

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

// ---------- загрузка ----------

async function refresh() {
  const params = new URLSearchParams();
  if (state.activeProject !== null) params.set("project_id", state.activeProject);
  if (state.query) params.set("q", state.query);

  const [projects, tasks, stats] = await Promise.all([
    api("/api/projects"),
    api(`/api/tasks?${params}`),
    api("/api/stats"),
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
  const meta = [`<span class="chip"><span class="dot" style="background:${escape(t.project_color)}"></span>${escape(t.project_name)}</span>`];
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

// ---------- события ----------

$("#projects").addEventListener("click", async (e) => {
  const delBtn = e.target.closest("[data-del]");
  if (delBtn) {
    const id = Number(delBtn.dataset.del);
    const project = state.projects.find((p) => p.id === id);
    if (!confirm(`Удалить проект «${project.name}» и все его задачи (${project.total})?`)) return;
    await api(`/api/projects/${id}`, { method: "DELETE" });
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
    const project = await api("/api/projects", {
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
    await api("/api/tasks", {
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
    await api(`/api/tasks/${move.dataset.move}`, {
      method: "PATCH",
      body: JSON.stringify({ status: move.dataset.to }),
    });
    return refresh();
  }

  const del = e.target.closest("[data-del-task]");
  if (del) {
    await api(`/api/tasks/${del.dataset.delTask}`, { method: "DELETE" });
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
    await api(`/api/tasks/${task.id}`, {
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

refresh().catch((err) => toast(`Не удалось загрузить данные: ${err.message}`));
