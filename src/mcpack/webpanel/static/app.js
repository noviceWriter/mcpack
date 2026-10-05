"use strict";

const GB_PRESETS = [1, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32];

let currentServerId = null;
let currentServer = null;
let consoleSocket = null;
let selectedPlayer = null;
let commandHistory = [];
let commandHistoryIndex = 0;

// -- yardımcılar --------------------------------------------------------------

async function api(path, options = {}) {
  const resp = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (resp.status === 401) {
    showLogin();
    throw new Error("Giriş gerekli");
  }
  let data = null;
  try { data = await resp.json(); } catch (e) { /* boş gövde olabilir */ }
  if (!resp.ok) {
    const detail = (data && data.detail) || `HTTP ${resp.status}`;
    toast(detail, true);
    throw new Error(detail);
  }
  return data;
}

function toast(text, isError) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 3500);
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.appendChild(c);
  return node;
}

// -- giriş ----------------------------------------------------------------

function showLogin() {
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app").classList.add("hidden");
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
}

async function checkAuthAndStart() {
  const status = await (await fetch("/api/auth/status", { credentials: "same-origin" })).json();
  document.getElementById("network-badge").textContent = status.auth_required
    ? "🌐 Ağa Açık"
    : "🔒 Sadece Bu Bilgisayar";
  if (status.auth_required && !status.authenticated) {
    showLogin();
    return;
  }
  showApp();
  await loadServers();
}

document.getElementById("login-button").addEventListener("click", doLogin);
document.getElementById("login-password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") doLogin();
});

async function doLogin() {
  const password = document.getElementById("login-password").value;
  const resp = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!resp.ok) {
    document.getElementById("login-error").textContent = "Şifre yanlış.";
    return;
  }
  document.getElementById("login-error").textContent = "";
  showApp();
  await loadServers();
}

// -- sunucu listesi ---------------------------------------------------------

async function loadServers() {
  const servers = await api("/api/servers");
  const list = document.getElementById("server-list");
  list.innerHTML = "";
  for (const s of servers) {
    const row = el("div", {
      class: "server-row" + (s.id === currentServerId ? " active" : ""),
      onclick: () => selectServer(s.id),
    }, [
      el("div", { class: "name" }, [
        el("span", { class: "dot " + (s.running ? "running" : "stopped") }),
        document.createTextNode(s.name),
      ]),
      el("div", { class: "meta", text: `${s.loader} · MC ${s.minecraft}` }),
    ]);
    list.appendChild(row);
  }
  if (servers.length === 0) {
    list.appendChild(el("div", { class: "meta", text: "Hiç pack yok." }));
  }
}

// -- sunucu seçimi / durum ----------------------------------------------------

async function selectServer(id) {
  currentServerId = id;
  await loadServers();
  document.getElementById("empty-state").classList.add("hidden");
  document.getElementById("server-view").classList.remove("hidden");
  await refreshServer();
  loadProperties();
  switchTab("console");
  connectConsole();
}

async function refreshServer() {
  const s = await api(`/api/servers/${currentServerId}`);
  currentServer = s;
  document.getElementById("server-name").textContent = s.name;
  document.getElementById("server-meta").textContent =
    `${s.loader}${s.loader_version ? " " + s.loader_version : ""} · MC ${s.minecraft}`;

  const pill = document.getElementById("status-pill");
  pill.textContent = s.running ? "Çalışıyor" : "Durduruldu";
  pill.className = "status-pill " + (s.running ? "running" : "stopped");

  document.getElementById("btn-prepare").disabled = s.running;
  document.getElementById("btn-install").classList.toggle("hidden", s.state !== "needs_install");
  document.getElementById("btn-install").disabled = s.running;
  document.getElementById("btn-start").disabled = s.running || s.state !== "ready";
  document.getElementById("btn-stop").disabled = !s.running;
  document.getElementById("command-input").disabled = !s.running;
  document.getElementById("btn-send-command").disabled = !s.running;

  renderSettingsForm(s);
  renderPlayersRunningState(s.running);
  renderModsBar(s);
}

function renderModsBar(s) {
  document.getElementById("mods-bar-title").textContent = `Modlar (sunucuda çalışacak): ${s.mods.length}`;
  const list = document.getElementById("mods-bar-list");
  list.innerHTML = "";
  for (const mod of s.mods) {
    list.appendChild(el("span", { class: "mod-chip", text: mod.name, title: mod.file_name }));
  }
  const excludedEl = document.getElementById("mods-bar-excluded");
  excludedEl.textContent = s.mods_excluded_count > 0
    ? `+ ${s.mods_excluded_count} istemci-only mod sunucu için hariç tutuldu.`
    : "";
}

// -- aksiyon butonları --------------------------------------------------------

document.getElementById("btn-prepare").addEventListener("click", async () => {
  toast("Hazırlanıyor (mod + sunucu dosyası indiriliyor)...");
  await api(`/api/servers/${currentServerId}/prepare`, { method: "POST" });
  toast("Hazırlandı.");
  await refreshServer();
});

document.getElementById("btn-install").addEventListener("click", async () => {
  toast("Kuruluyor (java -jar ... --installServer)... bu biraz sürebilir.");
  await api(`/api/servers/${currentServerId}/install`, { method: "POST" });
  toast("Kurulum tamamlandı.");
  await refreshServer();
});

document.getElementById("btn-start").addEventListener("click", async () => {
  if (currentServer && !currentServer.eula_accepted) {
    const ok = confirm(
      "Yerel bir sunucu çalıştırmak için Mojang'ın Minecraft EULA'sını kabul etmeniz gerekir:\n\n" +
      "https://www.minecraft.net/eula\n\nKabul ediyor musunuz?"
    );
    if (!ok) return;
    await api(`/api/servers/${currentServerId}/settings`, {
      method: "PUT",
      body: JSON.stringify({
        memory_mb: currentServer.memory_mb,
        selected_world: currentServer.selected_world,
        eula_accepted: true,
        use_optimized_flags: currentServer.use_optimized_flags,
      }),
    });
  }
  await api(`/api/servers/${currentServerId}/start`, { method: "POST" });
  toast("Sunucu başlatılıyor...");
  await refreshServer();
  connectConsole();
});

document.getElementById("btn-stop").addEventListener("click", async () => {
  toast("Sunucu durduruluyor (stop komutu gönderildi)...");
  await api(`/api/servers/${currentServerId}/stop`, { method: "POST" });
  await refreshServer();
});

// -- sekmeler ------------------------------------------------------------

for (const btn of document.querySelectorAll(".tab-button")) {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
}

function switchTab(name) {
  for (const btn of document.querySelectorAll(".tab-button")) {
    btn.classList.toggle("active", btn.dataset.tab === name);
  }
  for (const pane of document.querySelectorAll(".tab-pane")) {
    pane.classList.toggle("active", pane.id === "tab-" + name);
  }
}

// -- konsol ------------------------------------------------------------------

function consoleLineClass(text) {
  const m = /]\s*\[[^/\]]+\/(INFO|WARN|ERROR)\]/.exec(text);
  if (!m) return "info";
  return m[1].toLowerCase();
}

function appendConsoleLine(text) {
  const box = document.getElementById("console");
  const line = el("div", { class: "line " + consoleLineClass(text), text });
  box.appendChild(line);
  if (document.getElementById("auto-scroll").checked) {
    box.scrollTop = box.scrollHeight;
  }
}

function connectConsole() {
  if (consoleSocket) { consoleSocket.close(); consoleSocket = null; }
  document.getElementById("console").innerHTML = "";
  const proto = location.protocol === "https:" ? "wss" : "ws";
  consoleSocket = new WebSocket(`${proto}://${location.host}/ws/servers/${currentServerId}/console`);
  consoleSocket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "line") appendConsoleLine(msg.text);
    else if (msg.type === "exited") { appendConsoleLine("[panel] Sunucu süreci kapandı."); refreshServer(); }
    else if (msg.type === "error") appendConsoleLine("[panel] " + msg.text);
  };
}

document.getElementById("btn-clear-console").addEventListener("click", () => {
  document.getElementById("console").innerHTML = "";
});

document.getElementById("btn-send-command").addEventListener("click", sendCommand);
const commandInput = document.getElementById("command-input");
commandInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { sendCommand(); return; }
  if (e.key === "ArrowUp") {
    if (commandHistory.length && commandHistoryIndex > 0) {
      commandHistoryIndex -= 1;
      commandInput.value = commandHistory[commandHistoryIndex];
    }
    e.preventDefault();
  } else if (e.key === "ArrowDown") {
    if (commandHistoryIndex < commandHistory.length - 1) {
      commandHistoryIndex += 1;
      commandInput.value = commandHistory[commandHistoryIndex];
    } else {
      commandHistoryIndex = commandHistory.length;
      commandInput.value = "";
    }
    e.preventDefault();
  }
});

async function sendCommand() {
  const text = commandInput.value.trim();
  if (!text) return;
  if (!commandHistory.length || commandHistory[commandHistory.length - 1] !== text) commandHistory.push(text);
  commandHistoryIndex = commandHistory.length;
  commandInput.value = "";
  await api(`/api/servers/${currentServerId}/command`, { method: "POST", body: JSON.stringify({ text }) });
}

// -- oyuncular -----------------------------------------------------------

function renderPlayersRunningState(running) {
  document.getElementById("btn-refresh-players").disabled = !running;
  if (!running) {
    document.getElementById("players-list-items").innerHTML = "";
    document.getElementById("players-empty").textContent = "Oyuncu paneli için sunucu çalışıyor olmalı.";
    document.getElementById("players-detail-body").classList.add("hidden");
    selectedPlayer = null;
  }
}

document.getElementById("btn-refresh-players").addEventListener("click", refreshPlayers);

async function refreshPlayers() {
  const data = await api(`/api/servers/${currentServerId}/players`);
  const list = document.getElementById("players-list-items");
  list.innerHTML = "";
  for (const name of data.players) {
    const chip = el("div", {
      class: "player-chip" + (name === selectedPlayer ? " active" : ""),
      text: name,
      onclick: () => selectPlayer(name),
    });
    list.appendChild(chip);
  }
  if (data.players.length === 0) {
    list.appendChild(el("div", { class: "meta", text: "Çevrimiçi oyuncu yok." }));
  }
}

function selectPlayer(name) {
  selectedPlayer = name;
  document.getElementById("players-empty").classList.add("hidden");
  document.getElementById("players-detail-body").classList.remove("hidden");
  document.querySelectorAll(".player-chip").forEach((c) => c.classList.toggle("active", c.textContent === name));
  document.querySelector("#inventory-table tbody").innerHTML = "";
  document.querySelector("#ender-table tbody").innerHTML = "";
}

document.getElementById("p-heal").addEventListener("click", () => playerAction("heal"));
document.getElementById("p-kill").addEventListener("click", () => playerAction("kill"));
document.getElementById("p-feed").addEventListener("click", () => playerAction("feed"));
document.getElementById("p-damage").addEventListener("click", () =>
  playerAction("damage", { amount: Number(document.getElementById("p-damage-amount").value) || 4 })
);
document.getElementById("p-hunger").addEventListener("click", () =>
  playerAction("hunger", { duration_s: Number(document.getElementById("p-hunger-seconds").value) || 30 })
);

async function playerAction(action, body) {
  if (!selectedPlayer) return;
  await api(`/api/servers/${currentServerId}/players/${encodeURIComponent(selectedPlayer)}/${action}`, {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
  toast(`${selectedPlayer}: ${action} gönderildi.`);
}

function fillItemTable(tableId, items, withCategory) {
  const body = document.querySelector(`#${tableId} tbody`);
  body.innerHTML = "";
  for (const item of items) {
    body.appendChild(el("tr", {}, [
      el("td", { text: withCategory ? item.category : String(item.slot) }),
      el("td", { text: item.item_id }),
      el("td", { text: String(item.count) }),
    ]));
  }
  if (items.length === 0) {
    body.appendChild(el("tr", {}, [el("td", { text: "—", colspan: "3" })]));
  }
}

document.getElementById("btn-view-inventory").addEventListener("click", async () => {
  if (!selectedPlayer) return;
  const data = await api(`/api/servers/${currentServerId}/players/${encodeURIComponent(selectedPlayer)}/inventory`);
  fillItemTable("inventory-table", data.items, true);
});

document.getElementById("btn-view-ender").addEventListener("click", async () => {
  if (!selectedPlayer) return;
  const data = await api(`/api/servers/${currentServerId}/players/${encodeURIComponent(selectedPlayer)}/ender-chest`);
  fillItemTable("ender-table", data.items, false);
});

// -- ayarlar (bellek GB/MB + dünya + performans) ------------------------------

function renderSettingsForm(s) {
  const presetSelect = document.getElementById("mem-preset");
  const customInput = document.getElementById("mem-custom");
  presetSelect.innerHTML = "";

  const maxSafe = s.max_safe_memory_mb;
  const allowed = GB_PRESETS.filter((gb) => maxSafe == null || gb * 1024 <= maxSafe);
  if (allowed.length === 0) allowed.push(GB_PRESETS[0]);
  for (const gb of allowed) {
    presetSelect.appendChild(el("option", { value: String(gb * 1024), text: `${gb} GB` }));
  }
  presetSelect.appendChild(el("option", { value: "custom", text: "Özel (MB)" }));

  const matching = allowed.find((gb) => gb * 1024 === s.memory_mb);
  if (matching) {
    presetSelect.value = String(matching * 1024);
    customInput.classList.add("hidden");
  } else {
    presetSelect.value = "custom";
    customInput.classList.remove("hidden");
  }
  customInput.value = s.memory_mb;
  customInput.max = maxSafe || 131072;

  document.getElementById("memory-info").textContent =
    s.system_memory_mb == null
      ? "Sistem RAM'i tespit edilemedi — üst sınır konmadı, dikkatli seçin."
      : `Sisteminizde toplam ~${(s.system_memory_mb / 1024).toFixed(1)} GB RAM var. Sunucuya en fazla ` +
        `~${(maxSafe / 1024).toFixed(1)} GB ayrılabiliyor (en az 2 GB size bırakılıyor).`;

  const worldSelect = document.getElementById("world-select");
  worldSelect.innerHTML = "";
  worldSelect.appendChild(el("option", { value: "", text: "(dünya yok)" }));
  for (const w of s.worlds) worldSelect.appendChild(el("option", { value: w, text: w }));
  worldSelect.value = s.selected_world || "";

  document.getElementById("optimized-flags").checked = s.use_optimized_flags;
}

document.getElementById("mem-preset").addEventListener("change", (e) => {
  const customInput = document.getElementById("mem-custom");
  if (e.target.value === "custom") {
    customInput.classList.remove("hidden");
  } else {
    customInput.classList.add("hidden");
    customInput.value = e.target.value;
  }
});

document.getElementById("btn-save-settings").addEventListener("click", async () => {
  const presetValue = document.getElementById("mem-preset").value;
  const memoryMb = presetValue === "custom"
    ? Number(document.getElementById("mem-custom").value)
    : Number(presetValue);
  const body = {
    memory_mb: memoryMb,
    selected_world: document.getElementById("world-select").value || null,
    eula_accepted: currentServer.eula_accepted,
    use_optimized_flags: document.getElementById("optimized-flags").checked,
  };
  await api(`/api/servers/${currentServerId}/settings`, { method: "PUT", body: JSON.stringify(body) });
  toast("Ayarlar kaydedildi.");
  await refreshServer();
});

// -- server.properties ---------------------------------------------------

async function loadProperties() {
  const data = await api(`/api/servers/${currentServerId}/properties`);
  const grid = document.getElementById("properties-grid");
  grid.innerHTML = "";
  grid.dataset.widgets = "";
  const widgets = {};
  for (const prop of data.known) {
    const value = data.values[prop.key] ?? prop.default;
    let input;
    if (prop.type === "bool") {
      input = el("input", { type: "checkbox" });
      input.checked = value === "true";
    } else if (prop.type === "choice") {
      input = el("select", {}, prop.choices.map((c) => el("option", { value: c, text: c })));
      input.value = value;
    } else if (prop.type === "int") {
      input = el("input", { type: "number" });
      input.value = value;
    } else {
      input = el("input", { type: "text" });
      input.value = value;
    }
    widgets[prop.key] = input;
    grid.appendChild(el("label", { text: prop.label }));
    grid.appendChild(input);
  }
  loadProperties._widgets = widgets;
}

document.getElementById("btn-save-properties").addEventListener("click", async () => {
  const widgets = loadProperties._widgets || {};
  const values = {};
  for (const [key, input] of Object.entries(widgets)) {
    values[key] = input.type === "checkbox" ? String(input.checked) : String(input.value);
  }
  await api(`/api/servers/${currentServerId}/properties`, { method: "PUT", body: JSON.stringify({ values }) });
  toast("server.properties kaydedildi.");
});

// -- başlat ----------------------------------------------------------------

checkAuthAndStart();
