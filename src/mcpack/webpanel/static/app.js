"use strict";
// mcpack web paneli — tek dosya, bağımlılıksız.
// Güvenlik: sunucudan gelen HİÇBİR metin innerHTML ile basılmaz (konsol
// satırları, oyuncu/pack adları, loglar) — her şey textContent/DOM ile.

const GB_PRESETS = [1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32];
const PLAYER_RE = /^[A-Za-z0-9_]{1,16}$/;
const CONSOLE_MAX = 5000;
const QUICK = ["time set day", "time set night", "weather clear", "save-all", "list", "difficulty peaceful"];
const COMMANDS = ["say ", "tell ", "give ", "tp ", "gamemode ", "gamerule ", "time set ", "weather ", "difficulty ",
  "op ", "deop ", "kick ", "ban ", "pardon ", "whitelist add ", "whitelist remove ", "list", "save-all", "stop", "seed",
  "effect give ", "kill ", "summon ", "xp add ", "locate structure "];
const LOADER_GLYPH = { vanilla: "🌱", fabric: "🧵", quilt: "🧶", forge: "🔨", neoforge: "🔥" };
const LOADER_COLOR = { vanilla: "#7d8798", fabric: "#dbb36b", quilt: "#c873d6", forge: "#6b8cff", neoforge: "#f08a4b" };

const state = {
  servers: [], currentId: null, current: null, socket: null, socketRetry: 0,
  consoleLines: [], selectedPlayer: null, history: [], historyIndex: 0,
  authRequired: false, logAfter: 0, logPaused: false, logEntries: [], activeTab: "console",
};
let STR = {};

// -- yardımcılar ------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function t(key, params) {
  let text = STR[key] || key;
  if (params) for (const [k, v] of Object.entries(params)) text = text.split(`{${k}}`).join(String(v));
  return text;
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
}

function toast(text, kind = "info") {
  const node = el("div", { class: `toast ${kind}`, text });
  $("toasts").append(node);
  setTimeout(() => node.remove(), kind === "error" ? 8000 : 4000);
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (resp.status === 401) { showLogin(); throw new Error(t("webpanel.error.login_required")); }
  let data = null;
  try { data = await resp.json(); } catch { /* boş gövde */ }
  if (!resp.ok) {
    const msg = (data && data.detail) || `HTTP ${resp.status}`;
    toast(typeof msg === "string" ? msg : JSON.stringify(msg), "error");
    throw new Error(msg);
  }
  return data;
}

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = el("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function stamp() { return new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19); }

// -- i18n -------------------------------------------------------------------
async function loadStrings() {
  const data = await (await fetch("/api/strings", { credentials: "same-origin" })).json();
  STR = data.strings || {};
  $("html-root").lang = data.lang || "tr";
  document.title = t("webpanel.app_title");
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = t(n.dataset.i18nTitle); });
}

// -- kimlik doğrulama ---------------------------------------------------------
function showLogin() { $("app").classList.add("hidden"); $("login-screen").classList.remove("hidden"); $("login-password").focus(); }
function showApp() { $("login-screen").classList.add("hidden"); $("app").classList.remove("hidden"); }

async function boot() {
  await loadStrings();
  buildStatic();
  const status = await (await fetch("/api/auth/status", { credentials: "same-origin" })).json();
  state.authRequired = status.auth_required;
  $("btn-logout").classList.toggle("hidden", !status.auth_required);
  const badge = $("network-badge");
  badge.textContent = status.auth_required ? t("webpanel.badge.network_exposed") : t("webpanel.badge.local_only");
  badge.className = `chip ${status.auth_required ? "warning" : "accent"}`;
  if (status.authenticated) { showApp(); await loadServers(); await restoreFromHash(); } else showLogin();
  setInterval(() => { if (!$("app").classList.contains("hidden")) loadServers(true); }, 5000);
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resp = await fetch("/api/auth/login", {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: $("login-password").value }),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    $("login-error").textContent = data.detail || t("webpanel.error.wrong_password");
    $("login-error").classList.remove("hidden");
    return;
  }
  $("login-error").classList.add("hidden");
  $("login-password").value = "";
  showApp();
  await loadServers();
  await restoreFromHash();
});

// URL karması (#pack=<id>&tab=<sekme>): sayfa yenilenince seçim korunur,
// belirli bir sunucuya doğrudan bağlantı verilebilir.
function writeHash() {
  if (!state.currentId) return;
  history.replaceState(null, "", `#pack=${encodeURIComponent(state.currentId)}&tab=${state.activeTab}`);
}
async function restoreFromHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  const id = params.get("pack");
  const tab = params.get("tab");
  if (tab && document.querySelector(`.tab[data-tab="${CSS.escape(tab)}"]`)) state.activeTab = tab;
  if (id && state.servers.some((s) => s.id === id)) await selectServer(id);
}

$("btn-logout").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  closeSocket(); showLogin();
});

// -- statik parçalar ----------------------------------------------------------
function buildStatic() {
  const quick = $("quick-commands");
  for (const cmd of QUICK) quick.append(el("button", { class: "btn chip-btn", text: cmd, type: "button", onclick: () => sendCommand(cmd) }));
  const list = $("command-list");
  for (const c of COMMANDS) list.append(el("option", { value: c }));
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
}

// -- sunucu listesi -----------------------------------------------------------
async function loadServers(silent) {
  let servers;
  try { servers = await api("/api/servers"); } catch { return; }
  state.servers = servers;
  renderServerList();
  if (state.currentId && silent) {
    const s = servers.find((x) => x.id === state.currentId);
    if (s && (s.running !== state.current?.running || s.state !== state.current?.state)) refreshServer();
  }
}

function renderServerList() {
  const q = $("server-search").value.trim().toLowerCase();
  const list = $("server-list");
  list.replaceChildren();
  const items = state.servers.filter((s) => !q || s.name.toLowerCase().includes(q) || s.minecraft.includes(q));
  if (!items.length) { list.append(el("p", { class: "muted small", text: t("webpanel.servers.none") })); return; }
  items.sort((a, b) => (b.running - a.running) || a.name.localeCompare(b.name));
  for (const s of items) {
    const badge = el("span", { class: "badge", text: LOADER_GLYPH[s.loader] || "❓" });
    badge.style.background = LOADER_COLOR[s.loader] || "#7d8798";
    list.append(el("button", {
      class: `server-item${s.id === state.currentId ? " active" : ""}`, type: "button",
      onclick: () => selectServer(s.id),
    }, [
      badge,
      el("span", { class: "info" }, [
        el("div", { class: "name", text: s.name }),
        el("div", { class: "sub", text: `${s.loader} · MC ${s.minecraft} · ${t(`webpanel.state.${s.state}`)}` }),
      ]),
      el("span", { class: `status-dot${s.running ? " on" : ""}` }),
    ]));
  }
}
$("server-search").addEventListener("input", renderServerList);

async function selectServer(id) {
  state.currentId = id;
  state.selectedPlayer = null;
  closeSidebar();
  renderServerList();
  $("empty-state").classList.add("hidden");
  $("server-view").classList.remove("hidden");
  await refreshServer();
  resetConsole([]);
  connectConsole();
  switchTab(state.activeTab);
}

async function refreshServer() {
  if (!state.currentId) return;
  const s = await api(`/api/servers/${state.currentId}`);
  state.current = s;
  $("server-name").textContent = s.name;
  $("server-meta").textContent = `${s.loader}${s.loader_version ? " " + s.loader_version : ""} · Minecraft ${s.minecraft}`;
  const pill = $("status-pill");
  pill.replaceChildren(el("span", { class: "dot" }), s.running ? t("webpanel.status.running") : t("webpanel.status.stopped"));
  pill.className = `chip ${s.running ? "success" : ""}`;
  const st = $("state-pill");
  st.textContent = t(`webpanel.state.${s.state}`);
  st.className = `chip ${s.state === "ready" ? "accent" : s.state === "needs_install" ? "warning" : ""}`;
  $("btn-prepare").disabled = s.running;
  $("btn-install").classList.toggle("hidden", s.state !== "needs_install");
  $("btn-install").disabled = s.running;
  $("btn-start").disabled = s.running || s.state !== "ready";
  $("btn-stop").disabled = !s.running;
  $("command-input").disabled = !s.running;
  $("btn-send-command").disabled = !s.running;
  const mods = s.mods.map((m) => m.name).join(", ");
  $("mods-bar").textContent = `${t("webpanel.mods_bar.title", { count: s.mods.length })}${mods ? " — " + mods : ""}` +
    (s.mods_excluded_count ? `  ${t("webpanel.mods_bar.excluded", { count: s.mods_excluded_count })}` : "");
  renderSettings(s);
  if (!s.running) renderPlayers([]);
}

// -- eylem düğmeleri ------------------------------------------------------------
async function busy(button, fn) {
  button.disabled = true;
  try { await fn(); } catch { /* toast zaten gösterildi */ } finally { await refreshServer().catch(() => {}); loadServers(true); }
}
$("btn-prepare").addEventListener("click", (e) => busy(e.currentTarget, async () => {
  toast(t("webpanel.toast.preparing"));
  await api(`/api/servers/${state.currentId}/prepare`, { method: "POST" });
  toast(t("webpanel.toast.prepared"), "success");
}));
$("btn-install").addEventListener("click", (e) => busy(e.currentTarget, async () => {
  toast(t("webpanel.toast.installing"));
  const data = await api(`/api/servers/${state.currentId}/install`, { method: "POST" });
  (data.output || []).forEach((l) => appendLine(l));
  toast(t("webpanel.toast.installed"), "success");
}));
$("btn-start").addEventListener("click", (e) => busy(e.currentTarget, async () => {
  const s = state.current;
  if (!s.eula_accepted) {
    if (!confirm(t("webpanel.eula.confirm"))) return;
    await api(`/api/servers/${state.currentId}/settings`, {
      method: "PUT",
      body: JSON.stringify({ memory_mb: s.memory_mb, selected_world: s.selected_world, eula_accepted: true, use_optimized_flags: s.use_optimized_flags }),
    });
  }
  toast(t("webpanel.toast.starting"));
  await api(`/api/servers/${state.currentId}/start`, { method: "POST" });
  resetConsole([]);
  connectConsole();
}));
$("btn-stop").addEventListener("click", (e) => {
  if (!confirm(t("webpanel.confirm.stop"))) return;
  busy(e.currentTarget, async () => {
    toast(t("webpanel.toast.stopping"));
    await api(`/api/servers/${state.currentId}/stop`, { method: "POST" });
  });
});

// -- sekmeler ---------------------------------------------------------------------
function switchTab(name) {
  state.activeTab = name;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", p.id === `pane-${name}`));
  writeHash();
  if (name === "players") refreshPlayers();
  if (name === "properties") loadProperties();
  if (name === "logs") pollLogs(true);
  if (name === "diagnostics") loadDiagnostics();
}

// -- konsol -----------------------------------------------------------------------
function lineLevel(text) {
  const m = text.match(/(?:\/|\s)(INFO|WARN|WARNING|ERROR|FATAL|SEVERE)\]/);
  if (m) return ["ERROR", "FATAL", "SEVERE"].includes(m[1]) ? 2 : (m[1].startsWith("WARN") ? 1 : 0);
  if (/^(Exception|Caused by|\tat |java\.)/.test(text)) return 2;
  return 0;
}
function lineClass(text) {
  const lvl = lineLevel(text);
  if (lvl === 2) return "error";
  if (lvl === 1) return "warn";
  if (/\]:?\s*<[^>]+>/.test(text)) return "chat";
  if (/joined the game|left the game|lost connection/.test(text)) return "join";
  if (text.startsWith("> ")) return "cmd";
  return "";
}

function renderLine(text, cls) {
  const node = el("div", { class: `line ${cls || lineClass(text)}` });
  const q = $("console-find").value;
  if (q && text.toLowerCase().includes(q.toLowerCase())) {
    let rest = text;
    const lower = q.toLowerCase();
    while (rest) {
      const i = rest.toLowerCase().indexOf(lower);
      if (i < 0) { node.append(rest); break; }
      node.append(rest.slice(0, i), el("mark", { text: rest.slice(i, i + q.length) }));
      rest = rest.slice(i + q.length);
    }
  } else node.textContent = text;
  return node;
}

function passes(text) {
  const need = Number($("console-filter").value);
  return need === 0 || lineLevel(text) >= need;
}

function appendLine(text, cls) {
  state.consoleLines.push(text);
  if (state.consoleLines.length > CONSOLE_MAX) state.consoleLines.splice(0, state.consoleLines.length - CONSOLE_MAX);
  const view = $("console");
  if (passes(text)) {
    view.append(renderLine(text, cls));
    while (view.childElementCount > CONSOLE_MAX) view.firstChild.remove();
    if ($("auto-scroll").checked) view.scrollTop = view.scrollHeight;
  }
  $("console-count").textContent = t("webpanel.console.lines", { count: state.consoleLines.length });
}

function resetConsole(lines) {
  state.consoleLines = [];
  $("console").replaceChildren();
  lines.forEach((l) => appendLine(l));
  $("console-count").textContent = t("webpanel.console.lines", { count: state.consoleLines.length });
}

function rerenderConsole() {
  const view = $("console");
  const frag = document.createDocumentFragment();
  state.consoleLines.filter(passes).forEach((l) => frag.append(renderLine(l)));
  view.replaceChildren(frag);
  view.scrollTop = view.scrollHeight;
}
$("console-filter").addEventListener("change", rerenderConsole);
let findTimer = null;
$("console-find").addEventListener("input", () => { clearTimeout(findTimer); findTimer = setTimeout(rerenderConsole, 200); });
$("btn-clear-console").addEventListener("click", () => resetConsole([]));
$("btn-copy-console").addEventListener("click", async () => {
  await navigator.clipboard?.writeText(state.consoleLines.join("\n"));
  toast(t("webpanel.console.copied"), "success");
});
$("btn-download-console").addEventListener("click", () =>
  download(`${state.current?.name || "server"}-console-${stamp()}.log`, state.consoleLines.join("\n") + "\n"));

function closeSocket() {
  if (state.socket) { state.socket.onclose = null; state.socket.close(); state.socket = null; }
}

function connectConsole() {
  closeSocket();
  if (!state.currentId) return;
  const id = state.currentId;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/servers/${id}/console`);
  state.socket = ws;
  let first = true;
  ws.onopen = () => { state.socketRetry = 0; $("conn-status").textContent = `● ${t("webpanel.connection.live")}`; };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (first) { resetConsole([]); first = false; }
    if (msg.type === "line") appendLine(msg.text);
    else if (msg.type === "exited") { appendLine(t("webpanel.console.process_exited"), "sys"); refreshServer(); loadServers(true); }
    else if (msg.type === "error") $("conn-status").textContent = "";
  };
  ws.onclose = (ev) => {
    if (state.socket !== ws) return;
    state.socket = null;
    if (ev.code === 4401) { showLogin(); return; }
    if (state.current?.running) {
      $("conn-status").textContent = t("webpanel.connection.lost");
      const delay = Math.min(10000, 1000 * 2 ** state.socketRetry++);
      setTimeout(() => { if (state.currentId === id) connectConsole(); }, delay);
    } else $("conn-status").textContent = "";
  };
}

async function sendCommand(text) {
  if (!text || !state.currentId) return;
  appendLine(`> ${text}`, "cmd");
  await api(`/api/servers/${state.currentId}/command`, { method: "POST", body: JSON.stringify({ text }) }).catch(() => {});
}
$("command-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("command-input");
  const text = input.value.trim().replace(/^\//, "");
  if (!text) return;
  if (state.history[state.history.length - 1] !== text) state.history.push(text);
  state.historyIndex = state.history.length;
  input.value = "";
  sendCommand(text);
});
$("command-input").addEventListener("keydown", (e) => {
  if (!state.history.length || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
  e.preventDefault();
  state.historyIndex = e.key === "ArrowUp" ? Math.max(0, state.historyIndex - 1) : Math.min(state.history.length, state.historyIndex + 1);
  $("command-input").value = state.history[state.historyIndex] || "";
});

// -- oyuncular --------------------------------------------------------------------
async function refreshPlayers() {
  if (!state.current?.running) { renderPlayers([]); return; }
  try { renderPlayers((await api(`/api/servers/${state.currentId}/players`)).players); } catch { /* toast */ }
}
setInterval(() => { if (state.activeTab === "players" && state.current?.running && !document.hidden) refreshPlayers(); }, 6000);

function renderPlayers(players) {
  const list = $("players-list");
  list.replaceChildren();
  if (!state.current?.running) list.append(el("p", { class: "muted small", text: t("webpanel.players.running_required") }));
  else if (!players.length) list.append(el("p", { class: "muted small", text: t("webpanel.players.none_online") }));
  for (const name of players) {
    list.append(el("button", { class: `list-item${name === state.selectedPlayer ? " active" : ""}`, type: "button", text: name, onclick: () => selectPlayer(name, players) }));
  }
  if (state.selectedPlayer && !players.includes(state.selectedPlayer)) selectPlayer(null, players);
}
$("btn-refresh-players").addEventListener("click", refreshPlayers);

function selectPlayer(name, players) {
  state.selectedPlayer = name;
  $("players-empty").classList.toggle("hidden", !!name);
  $("players-detail-body").classList.toggle("hidden", !name);
  $("player-name").textContent = name || "—";
  document.querySelector("#inventory-table tbody").replaceChildren();
  document.querySelector("#ender-table tbody").replaceChildren();
  if (players) renderPlayersSelectionOnly();
}
function renderPlayersSelectionOnly() {
  document.querySelectorAll("#players-list .list-item").forEach((b) => b.classList.toggle("active", b.textContent === state.selectedPlayer));
}

document.querySelectorAll("[data-action]").forEach((b) => b.addEventListener("click", async () => {
  const p = state.selectedPlayer;
  if (!p || !PLAYER_RE.test(p)) return;
  const action = b.dataset.action;
  if (action === "kill" && !confirm(t("webpanel.confirm.kill", { player: p }))) return;
  let body;
  if (action === "damage") body = JSON.stringify({ amount: Number($("p-damage-amount").value) || 4 });
  if (action === "hunger") body = JSON.stringify({ duration_s: Number($("p-hunger-seconds").value) || 30 });
  await api(`/api/servers/${state.currentId}/players/${encodeURIComponent(p)}/${action}`, { method: "POST", body }).catch(() => null);
  toast(t("webpanel.toast.player_action_sent", { player: p, action: b.textContent }), "success");
}));
document.querySelectorAll("[data-cmd]").forEach((b) => b.addEventListener("click", () => {
  const p = state.selectedPlayer;
  if (p && PLAYER_RE.test(p)) sendCommand(b.dataset.cmd.replace("{p}", p));
}));

function fillItems(tableId, items, withCategory) {
  const body = document.querySelector(`#${tableId} tbody`);
  body.replaceChildren(...items.map((i) => el("tr", {}, [
    el("td", { text: withCategory ? i.category : String(i.slot) }),
    el("td", { text: i.item_id.replace(/^minecraft:/, "") }),
    el("td", { text: String(i.count) }),
  ])));
}
$("btn-view-inventory").addEventListener("click", async () => {
  if (!state.selectedPlayer) return;
  const data = await api(`/api/servers/${state.currentId}/players/${encodeURIComponent(state.selectedPlayer)}/inventory`).catch(() => null);
  if (data) fillItems("inventory-table", data.items, true);
});
$("btn-view-ender").addEventListener("click", async () => {
  if (!state.selectedPlayer) return;
  const data = await api(`/api/servers/${state.currentId}/players/${encodeURIComponent(state.selectedPlayer)}/ender-chest`).catch(() => null);
  if (data) fillItems("ender-table", data.items, false);
});

// -- çalışma ayarları ---------------------------------------------------------------
function renderSettings(s) {
  const preset = $("mem-preset");
  preset.replaceChildren();
  for (const gb of GB_PRESETS) {
    if (s.max_safe_memory_mb && gb * 1024 > s.max_safe_memory_mb) continue;
    preset.append(el("option", { value: String(gb * 1024), text: `${gb} GB` }));
  }
  preset.append(el("option", { value: "custom", text: t("webpanel.memory.custom") }));
  const match = [...preset.options].find((o) => o.value === String(s.memory_mb));
  preset.value = match ? match.value : "custom";
  $("mem-custom").value = s.memory_mb;
  if (s.max_safe_memory_mb) $("mem-custom").max = s.max_safe_memory_mb;
  $("mem-custom").classList.toggle("hidden", preset.value !== "custom");
  $("memory-info").textContent = s.system_memory_mb
    ? t("webpanel.memory.info", { total_gb: (s.system_memory_mb / 1024).toFixed(1), max_gb: (s.max_safe_memory_mb / 1024).toFixed(1) })
    : t("webpanel.memory.unknown");
  const world = $("world-select");
  world.replaceChildren(el("option", { value: "", text: t("webpanel.world.none") }), ...s.worlds.map((w) => el("option", { value: w, text: w })));
  world.value = s.selected_world || "";
  $("optimized-flags").checked = s.use_optimized_flags;
}
$("mem-preset").addEventListener("change", (e) => $("mem-custom").classList.toggle("hidden", e.target.value !== "custom"));
$("btn-save-settings").addEventListener("click", async () => {
  const preset = $("mem-preset").value;
  const memory = preset === "custom" ? Number($("mem-custom").value) : Number(preset);
  await api(`/api/servers/${state.currentId}/settings`, {
    method: "PUT",
    body: JSON.stringify({
      memory_mb: memory, selected_world: $("world-select").value || null,
      eula_accepted: state.current.eula_accepted, use_optimized_flags: $("optimized-flags").checked,
    }),
  }).catch(() => null);
  toast(t("webpanel.toast.settings_saved"), "success");
  refreshServer();
});

// -- server.properties ----------------------------------------------------------------
async function loadProperties() {
  const data = await api(`/api/servers/${state.currentId}/properties`).catch(() => null);
  if (!data) return;
  const grid = $("properties-grid");
  grid.replaceChildren();
  for (const p of data.known) {
    const value = data.values[p.key] ?? p.default;
    let input;
    if (p.type === "bool") { input = el("input", { type: "checkbox" }); input.checked = value === "true"; }
    else if (p.type === "choice") { input = el("select", {}, p.choices.map((c) => el("option", { value: c, text: c }))); input.value = value; }
    else if (p.type === "int") input = el("input", { type: "number", value });
    else input = el("input", { type: "text", value });
    input.dataset.key = p.key;
    input.dataset.type = p.type;
    grid.append(el("label", {}, [p.label, el("span", { class: "key", text: p.key })]), input);
  }
}
$("btn-save-properties").addEventListener("click", async () => {
  const values = {};
  document.querySelectorAll("#properties-grid [data-key]").forEach((n) => {
    values[n.dataset.key] = n.dataset.type === "bool" ? (n.checked ? "true" : "false") : n.value;
  });
  await api(`/api/servers/${state.currentId}/properties`, { method: "PUT", body: JSON.stringify({ values }) }).catch(() => null);
  toast(t("webpanel.toast.properties_saved"), "success");
});

// -- uygulama logları ------------------------------------------------------------------
async function pollLogs(reset) {
  if (state.activeTab !== "logs" || state.logPaused) return;
  if (reset) { state.logAfter = 0; state.logEntries = []; }
  const level = $("log-level").value;
  const data = await api(`/api/debug/logs?after=${state.logAfter}&level=${level}&limit=1000`).catch(() => null);
  if (!data) return;
  if (data.entries.length) {
    state.logAfter = data.entries[data.entries.length - 1].seq;
    state.logEntries.push(...data.entries);
    if (state.logEntries.length > 3000) state.logEntries.splice(0, state.logEntries.length - 3000);
  }
  renderLogs(reset || data.entries.length > 0);
}
function renderLogs(changed) {
  if (!changed) return;
  const q = $("log-search").value.trim().toLowerCase();
  const view = $("log-view");
  const atBottom = view.scrollTop + view.clientHeight >= view.scrollHeight - 20;
  const rows = state.logEntries.filter((e) => !q || e.message.toLowerCase().includes(q) || (e.exc_text || "").toLowerCase().includes(q));
  if (!rows.length) { view.replaceChildren(el("div", { class: "line sys", text: t("webpanel.logs.empty") })); return; }
  view.replaceChildren(...rows.map((e) => el("div", { class: `line ${e.level}` }, [
    `${e.time} `, el("span", { class: "lvl", text: e.level }), el("span", { class: "lg", text: `${e.logger.replace(/^mcpack\./, "")}: ` }),
    e.message + (e.exc_text ? "\n" + e.exc_text : ""),
  ])));
  if (atBottom || changed === true) view.scrollTop = view.scrollHeight;
}
setInterval(() => { if (!document.hidden) pollLogs(false); }, 2500);
$("log-level").addEventListener("change", () => pollLogs(true));
$("log-search").addEventListener("input", () => renderLogs(true));
$("btn-log-pause").addEventListener("click", (e) => {
  state.logPaused = !state.logPaused;
  e.currentTarget.textContent = state.logPaused ? t("webpanel.logs.resume") : t("webpanel.logs.pause");
  if (!state.logPaused) pollLogs(false);
});
$("btn-log-download").addEventListener("click", () => download(`mcpack-log-${stamp()}.log`,
  state.logEntries.map((e) => `${e.time} ${e.level} ${e.logger}: ${e.message}${e.exc_text ? "\n" + e.exc_text : ""}`).join("\n") + "\n"));

// -- teşhis -------------------------------------------------------------------------------
async function loadDiagnostics() {
  const [sys, net, exc] = await Promise.all([
    api("/api/debug/system").catch(() => null),
    api("/api/debug/network").catch(() => null),
    api("/api/debug/exceptions").catch(() => null),
  ]);
  if (sys) {
    document.querySelector("#sys-table tbody").replaceChildren(...Object.entries(sys.info).map(([k, v]) =>
      el("tr", {}, [el("td", { text: k }), el("td", { text: v })])));
  }
  if (net) {
    const s = net.stats;
    $("net-stats").textContent = t("webpanel.diag.stats", { total: s.total, failed: s.failed, avg: s.avg_ms ? s.avg_ms.toFixed(0) : "—" });
    document.querySelector("#net-table tbody").replaceChildren(...net.events.slice().reverse().slice(0, 200).map((e) => {
      const bad = e.error || (e.status || 0) >= 400;
      let path = e.url;
      try { const u = new URL(e.url); path = u.pathname + u.search; } catch { /* yoksay */ }
      return el("tr", {}, [
        el("td", { text: new Date(e.created * 1000).toLocaleTimeString() }), el("td", { text: e.method }),
        el("td", { class: bad ? "bad" : "ok", text: e.status != null ? String(e.status) : (e.error || "—") }),
        el("td", { text: e.elapsed_ms != null ? e.elapsed_ms.toFixed(0) : "—" }), el("td", { text: e.host }), el("td", { text: path }),
      ]);
    }));
  }
  if (exc) {
    const list = $("exc-list");
    list.replaceChildren();
    if (!exc.exceptions.length) list.append(el("p", { class: "muted small", text: t("webpanel.diag.none") }));
    for (const e of exc.exceptions.slice(0, 30)) {
      const details = el("details", { class: "exc" }, [
        el("summary", { text: `${e.type}: ${e.message}${e.count > 1 ? `  ×${e.count}` : ""}` }),
        el("div", { class: "muted small", text: e.origin }),
        el("pre", { text: e.traceback }),
      ]);
      list.append(details);
    }
  }
}
$("btn-diag-refresh").addEventListener("click", loadDiagnostics);

// -- mobil menü ---------------------------------------------------------------------------
function closeSidebar() { $("sidebar").classList.remove("open"); $("scrim").classList.add("hidden"); }
$("btn-menu").addEventListener("click", () => { $("sidebar").classList.add("open"); $("scrim").classList.remove("hidden"); });
$("scrim").addEventListener("click", closeSidebar);

boot().catch((err) => toast(String(err), "error"));
