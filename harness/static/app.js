/* Procurement Audit Planner — frontend (no build step). */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");
let CONFIG = null;
let stream = null;

// ---- connection (sessionStorage only) --------------------------------------
const store = {
  get(k) { try { return sessionStorage.getItem(k) || ""; } catch { return ""; } },
  set(k, v) { try { v ? sessionStorage.setItem(k, v) : sessionStorage.removeItem(k); } catch { /* private mode */ } },
};
const conn = () => ({ provider: store.get("provider"), model: store.get("model"), key: store.get("key") });
const connected = () => { const c = conn(); return !!(c.provider && c.model && c.key); };

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const r = await fetch(path, { ...opts, headers });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = j.detail || msg; } catch { /* not json */ }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}

function renderConn() {
  const c = conn();
  $("#connDot").className = "dot" + (connected() ? " ok" : "");
  const p = CONFIG?.providers[c.provider];
  $("#connLabel").textContent = connected() ? `${p ? p.label.split(" ")[0] : c.provider} · ${c.model}` : "Connect a model";
}

function openConn(onSaved) {
  const dlg = $("#connDlg");
  const c = conn();
  let provider = c.provider || "anthropic";
  const seg = $("#provSeg");
  seg.innerHTML = Object.entries(CONFIG.providers).map(([id, p]) =>
    `<label><input type="radio" name="prov" value="${id}" ${id === provider ? "checked" : ""}>${esc(p.label.split(" (")[0])}<small>${esc(p.label.match(/\((.*)\)/)?.[1] || "")}</small></label>`).join("");
  const fillModels = () => {
    const p = CONFIG.providers[provider];
    const sel = $("#modelSel");
    sel.innerHTML = p.models.map((m) => `<option value="${m.id}">${esc(m.label)}${m.recommended ? " — recommended" : ""}</option>`).join("") +
      `<option value="__custom">Other model id…</option>`;
    const known = p.models.some((m) => m.id === c.model);
    sel.value = provider === c.provider ? (known ? c.model : (c.model ? "__custom" : p.models[0].id)) : p.models[0].id;
    $("#customModel").value = provider === c.provider && !known ? c.model : "";
    $("#customWrap").hidden = sel.value !== "__custom";
    $("#keyIn").placeholder = p.key_hint;
    $("#keyIn").value = provider === c.provider ? c.key : "";
    showWarn();
  };
  const model = () => ($("#modelSel").value === "__custom" ? $("#customModel").value.trim() : $("#modelSel").value);
  const msg = (t, cls = "hint") => { const m = $("#connMsg"); m.className = cls; m.textContent = t; };
  const showWarn = () => {
    const m = CONFIG.providers[provider].models.find((x) => x.id === $("#modelSel").value);
    msg(m?.warning || "Test key checks the key and model against the provider's model list; it uses no tokens.", m?.warning ? "err" : "hint");
  };
  seg.onchange = (e) => { provider = e.target.value; fillModels(); };
  $("#modelSel").onchange = () => { $("#customWrap").hidden = $("#modelSel").value !== "__custom"; showWarn(); };
  $("#connTest").onclick = async () => {
    const key = $("#keyIn").value.trim();
    if (!key) return msg("Enter an API key.", "err");
    msg("Checking…");
    try {
      const r = await api("/api/keys/test", { method: "POST", headers: { "X-LLM-Key": key }, body: JSON.stringify({ provider, model: model() }) });
      if (!r.ok) return msg(r.error, "err");
      if (r.model_found === false) return msg(`Key works, but "${model()}" is not in this key's model list. Pick another model or check the id.`, "err");
      msg(`Key works; ${model()} is available.`, "okmsg");
    } catch (e) { msg(e.message, "err"); }
  };
  $("#connSave").onclick = () => {
    const key = $("#keyIn").value.trim();
    if (!key || !model()) return msg("Enter a model and an API key.", "err");
    store.set("provider", provider); store.set("model", model()); store.set("key", key);
    renderConn(); dlg.close(); onSaved && onSaved();
  };
  $("#connForget").onclick = () => { store.set("key", ""); $("#keyIn").value = ""; renderConn(); msg("Key removed from this tab."); };
  fillModels();
  dlg.showModal();
}

function withKey(fn) {
  if (connected()) return fn();
  openConn(fn);
}

// ---- formatting --------------------------------------------------------------
const STATUS = {
  created: ["Not started", ""], ready: ["Continuing", ""], stage1: ["Extracting rules", "run"], stage2: ["Analysing", "run"],
  awaiting_review: ["Awaiting risk review", "pen"], stage4: ["Agent team at work", "run"], awaiting_signoff: ["Awaiting sign-off", "pen"],
  complete: ["Complete", "tick"], failed: ["Failed", "pen"], interrupted: ["Interrupted", "amber"],
};
function badge(run) {
  const [label, cls] = STATUS[run.status] || [run.status, ""];
  const dot = run.active ? '<span class="dot run"></span>' : "";
  return `<span class="badge ${cls === "run" ? "" : cls}">${dot}${esc(label)}</span>`;
}
const money = (run) => (run.cost_usd ? `$${run.cost_usd.toFixed(2)}${run.cost_known ? "" : "+"}` : run.cost_known ? "$0.00" : "—");
const when = (t) => (t ? new Date(t * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const clock = (t) => new Date(t * 1000).toLocaleTimeString(undefined, { hour12: false });
const kb = (n) => (n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? Math.round(n / 1e3) + " KB" : n + " B");
const tokens = (n) => (n > 1e6 ? (n / 1e6).toFixed(2) + "M" : n > 1e3 ? Math.round(n / 1e3) + "k" : String(n));

// ---- pipeline definition -----------------------------------------------------
const STAGES = [
  { ref: "A", name: "Extract rules", by: "Skill · extract-rules", io: "contract-rules.pdf → rules.json", what: "Every testable rule with clause, thresholds and a verbatim quote, verified against the PDF.", key: "stage1" },
  { ref: "B", name: "Analyse", by: "Sub-agents · spend-analyst ‖ findings-analyst → risk-assessor", io: "spend xlsx, contracts.csv, committee PDFs → analytics.json, history.json, risk-register.md", what: "Full-population spend tests, audit history, and a cited likelihood × impact register.", key: "stage2" },
  { ref: "C", name: "Risk review", by: "You, the auditor", io: "risk-register.md → auditor-comments.md", what: "Approve, amend or reject each proposed risk.", key: "awaiting_review", human: true },
  { ref: "D", name: "Agent team", by: "Team · planner, challenger, qa-reviewer", io: "approved risks → planning memo, RCM, audit program, challenges, review.md", what: "The plan is built, challenged in two rounds and QA-checked by script.", key: "stage4" },
  { ref: "E", name: "Sign-off", by: "You, the auditor", io: "review.md → signed pack", what: "Sign off the pack, or return it to the team.", key: "awaiting_signoff", human: true },
];
const ORDER = ["stage1", "stage2", "awaiting_review", "stage4", "awaiting_signoff", "complete"];

function stepState(run, i) {
  const key = STAGES[i].key;
  const failedStage = ["failed", "interrupted"].includes(run.status) ? run.next_stage : null;
  let pos = ORDER.indexOf(run.status);
  if (run.status === "ready" || run.status === "created") pos = ORDER.indexOf(run.next_stage);
  if (failedStage) pos = ORDER.indexOf(failedStage);
  const mine = ORDER.indexOf(key);
  if (run.id === "sample" || run.status === "complete") return "done";
  if (failedStage && mine === pos) return "failed";
  if (mine < pos) return "done";
  if (mine === pos) return STAGES[i].human ? "human" : run.active ? "active" : "next";
  return "";
}
const MARKS = { done: "✓", active: "…", human: "✎", failed: "✕", next: "○", "": "" };

// ---- views -------------------------------------------------------------------
function setNav(which) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("on", a.dataset.nav === which));
}

function viewHome() {
  setNav("home");
  app.innerHTML = `
  <section class="lede">
    <div>
      <h1>Plan a procurement audit from the council's public data.</h1>
      <p class="sub">Agents read the Contract Procedure Rules, test every payment over £500 against them, fold in past audit history and propose a rated risk register. You decide what is in scope; a team of agents then builds, challenges and QA-checks the audit pack for your sign-off.</p>
      <div class="actions">
        <a class="btn primary" href="#/run/sample">View the sample run</a>
        <a class="btn" href="#/new">Start a new run</a>
      </div>
    </div>
    <div class="principles">
      <div><b>The model reads and judges; Python computes every number.</b> Figures, scores and samples come from the committed scripts.</div>
      <div><b>Everything is traceable.</b> Quotes are verified against the PDF; every rating cites a rule, a metric or a prior audit.</div>
      <div><b>Indicators, not accusations.</b> Outputs describe patterns to investigate, never wrongdoing.</div>
      <div><b>Missing input means stop and report.</b> Nothing is fabricated.</div>
    </div>
  </section>
  <div class="index-label">Working-paper index · five stages</div>
  <div class="wp">${STAGES.map((s) => `
    <div class="wp-row"><span class="ref">${s.ref}</span>
      <div class="what"><b>${esc(s.name)}</b><p>${esc(s.what)}</p></div>
      <div class="io">${esc(s.io)}</div>
      <div class="who ${s.human ? "human" : ""}">${esc(s.by)}</div></div>`).join("")}
  </div>
  <div class="cards2">
    <div class="panel"><h3>No key? Start with the sample.</h3><p>The sample is the complete Part A run: every stage's output, the challenges, the QA results and the signed review.</p></div>
    <div class="panel"><h3>Bring your own key</h3><p>Runs work with Anthropic, OpenAI or Gemini. The key stays in your browser tab and server memory only. A full run takes roughly 30–90 minutes and makes many model calls.</p></div>
  </div>`;
}

function viewNew() {
  setNav("runs");
  app.innerHTML = `
  <div style="max-width:720px">
    <h2>Start a new run</h2>
    <p class="hint" style="margin:6px 0 24px">A run is a fresh copy of the project: CLAUDE.md, the skills and agents, the scripts and the public data. Stages 1–2 run back to back; the run then waits for your risk review.</p>
    <div class="panel stack">
      <div class="field" style="font-size:12px;font-weight:500;color:var(--ink-2)">Start from</div>
      <div class="seg" style="grid-template-columns:1fr">
        <label><input type="radio" name="seed" value="full" checked>Stage A — the full pipeline<small>Extract the rules from the PDF, then everything after. Most model calls.</small></label>
        <label><input type="radio" name="seed" value="stage2">Stage B — reuse the Part A rules.json<small>Skip rule extraction; run the sub-agents, the register, the review and the team.</small></label>
        <label><input type="radio" name="seed" value="risk">Stage B, risk-assessor only — reuse Part A rules, analytics and history<small>Cheapest live run: the register, your review and the agent team.</small></label>
      </div>
      <label class="field">Label (optional)<input type="text" id="label" maxlength="80" placeholder="e.g. Sonnet trial"></label>
      <div class="row"><button class="btn primary" id="go">Create and start</button><span id="msg" class="hint"></span></div>
      <p class="hint" id="connNote"></p>
    </div>
  </div>`;
  const note = () => { $("#connNote").textContent = connected() ? `Model: ${conn().provider} · ${conn().model}` : "You will be asked to connect a model first."; };
  note();
  $("#go").onclick = () => withKey(async () => {
    note();
    const seed = document.querySelector("input[name=seed]:checked").value;
    $("#go").disabled = true; $("#msg").textContent = "Creating the run folder…";
    try {
      const run = await api("/api/runs", { method: "POST", body: JSON.stringify({ seed, label: $("#label").value }) });
      await startStage(run.id);
      location.hash = `#/run/${run.id}`;
    } catch (e) { $("#msg").className = "err"; $("#msg").textContent = e.message; $("#go").disabled = false; }
  });
}

async function startStage(id) {
  const c = conn();
  return api(`/api/runs/${id}/start`, { method: "POST", headers: { "X-LLM-Key": c.key }, body: JSON.stringify({ provider: c.provider, model: c.model }) });
}

async function viewRuns() {
  setNav("runs");
  app.innerHTML = `<div class="gate-head"><div><h2>Runs</h2><p>Every run started on this server, newest first.</p></div><a class="btn primary" href="#/new">Start a new run</a></div><div class="panel" style="padding:0" id="list"><div class="empty">Loading…</div></div>`;
  const { runs, sample } = await api("/api/runs");
  const rows = [sample, ...runs].map((r) => `
    <tr class="link" data-id="${r.id}"><td><b>${esc(r.label || r.id)}</b><div class="hint mono">${esc(r.id)}</div></td>
    <td>${badge(r)}</td><td>${esc(r.model || "—")}<div class="hint">${esc(r.provider || "")}</div></td>
    <td class="num">${money(r)}</td><td class="hint">${when(r.created)}</td></tr>`).join("");
  $("#list").innerHTML = `<table class="ledger"><thead><tr><th>Run</th><th>Status</th><th>Model</th><th>Cost</th><th>Created</th></tr></thead><tbody>${rows}</tbody></table>`;
  $("#list").onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) location.hash = `#/run/${tr.dataset.id}`; };
}

// ---- run view ----------------------------------------------------------------
const R = { run: null, tab: "log", events: [], file: null, verbose: false };

async function viewRun(id, tab, file) {
  setNav("runs");
  if (!R.run || R.run.id !== id) { R.events = []; R.file = null; }
  R.tab = tab || R.tab || "log";
  if (file) { R.file = file; R.tab = "files"; }
  try { R.run = await api(`/api/runs/${id}`); } catch (e) { app.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  if (!tab) R.tab = R.run.status === "awaiting_review" ? "review" : R.run.status === "awaiting_signoff" ? "signoff" : R.run.id === "sample" ? "files" : "log";
  app.innerHTML = `<div id="head"></div><div id="steps"></div><div class="tabs" id="tabs"></div><div id="pane"></div>`;
  renderHead(); renderTabs(); renderPane();
  openStream(id);
}

function renderHead() {
  const r = R.run;
  const canStart = !r.read_only && !r.active && ["created", "ready", "failed", "interrupted"].includes(r.status);
  const resumeLabel = r.status === "created" ? "Start" : r.status === "ready" ? "Continue" : "Resume stage";
  $("#head").innerHTML = `
    <div class="runhead"><div>
      <h2>${esc(r.label || "Run " + r.id)}</h2>
      <div class="meta"><span>${badge(r)}</span><span>Model <b>${esc(r.model || "—")}</b></span>
      <span>Cost <b class="num">${money(r)}</b></span><span>Tokens <b class="num">${tokens(r.input_tokens)} in · ${tokens(r.output_tokens)} out</b></span>
      <span class="mono">${esc(r.id)}</span></div></div>
      <div class="row">
        ${canStart ? `<button class="btn primary" id="startBtn">${resumeLabel}</button>` : ""}
        ${r.active ? `<button class="btn" id="stopBtn">Stop</button>` : ""}
        <a class="btn" href="/api/runs/${r.id}/download">Download pack (.zip)</a>
      </div></div>
    ${r.note ? `<div class="notice">${esc(r.note)}</div>` : ""}
    ${r.error ? `<div class="notice pen"><b>${r.status === "interrupted" ? "Interrupted" : "Stage failed"}.</b> ${canStart ? "Fix the cause (a different model, or a valid key) and resume: the stage reruns from its start." : ""}<pre>${esc(r.error)}</pre></div>` : ""}`;
  $("#startBtn") && ($("#startBtn").onclick = () => withKey(async () => {
    $("#startBtn").disabled = true;
    try { await startStage(r.id); R.tab = "log"; await refreshRun(); } catch (e) { alert(e.message); $("#startBtn").disabled = false; }
  }));
  $("#stopBtn") && ($("#stopBtn").onclick = async () => { if (confirm("Stop this stage? It can be resumed later from its start.")) await api(`/api/runs/${r.id}/stop`, { method: "POST" }); });
  $("#steps").innerHTML = `<div class="steps">${STAGES.map((s, i) => {
    const st = stepState(r, i);
    return `<div class="step ${st}"><div class="top"><span class="ref">${s.ref}</span><span class="mark">${MARKS[st]}</span></div><b>${esc(s.name)}</b><small>${esc(s.by)}</small></div>`;
  }).join("")}</div>`;
}

async function refreshRun() {
  R.run = await api(`/api/runs/${R.run.id}`);
  renderHead(); renderTabs(); renderPane();
  if (R.run.active && !stream) openStream(R.run.id);
}

function renderTabs() {
  const r = R.run;
  const tabs = [["log", "Activity"], ["files", "Files"], ["review", "Risk review", r.status === "awaiting_review"], ["signoff", "QA & sign-off", r.status === "awaiting_signoff"]];
  $("#tabs").innerHTML = tabs.map(([k, l, flag]) => `<button data-tab="${k}" class="${R.tab === k ? "on" : ""}">${l}${flag ? '<span class="badge pen">your turn</span>' : ""}</button>`).join("");
  $("#tabs").onclick = (e) => { const b = e.target.closest("button[data-tab]"); if (b) { R.tab = b.dataset.tab; renderTabs(); renderPane(); } };
}

function renderPane() {
  ({ log: paneLog, files: paneFiles, review: paneReview, signoff: paneSignoff })[R.tab]();
}

// -- activity
function paneLog() {
  if (R.run.id === "sample") {
    $("#pane").innerHTML = `<div class="empty">The sample run was made in Claude Code, which did not record an event log in this format. Open <b>Files</b> to see every output, or start a run to watch the agents live.</div>`;
    return;
  }
  $("#pane").innerHTML = `<div class="logtools"><label><input type="checkbox" id="verbose" ${R.verbose ? "checked" : ""}> Show tool results</label><span id="evcount" class="num"></span></div><div class="log" id="log"></div>`;
  $("#verbose").onchange = (e) => { R.verbose = e.target.checked; paneLog(); };
  const log = $("#log");
  log.innerHTML = R.events.map(evHtml).join("") || `<div class="empty">No activity yet.</div>`;
  $("#evcount").textContent = `${R.events.length} events`;
  log.scrollTop = log.scrollHeight;
}

function evHtml(e) {
  const t = `<time>${clock(e.ts)}</time><span class="ag">${esc(e.agent)}</span>`;
  switch (e.kind) {
    case "stage": {
      const s = { stage1: "A · Extract rules", stage2: "B · Analyse", stage4: "D · Agent team" }[e.stage] || e.stage;
      const txt = e.state === "started" ? `${s} started (${e.provider} · ${e.model})` : e.state === "done" ? `${s} complete · $${(e.cost_usd || 0).toFixed(2)}` : `${s} ${e.state}: ${e.error || ""}`;
      return `<div class="ev stage ${e.state === "failed" ? "fail" : ""}">${t}<div class="body">${esc(txt)}</div></div>`;
    }
    case "agent_start": return `<div class="ev">${t}<div class="body">Agent started · tools: ${esc((e.tools || []).join(", "))}<details><summary>task</summary><pre>${esc(e.task)}</pre></details></div></div>`;
    case "agent_done": return `<div class="ev msg">${t}<div class="body"><b>Report</b> (${e.turns} turns)<pre>${esc(e.report)}</pre></div></div>`;
    case "message": return e.text ? `<div class="ev msg">${t}<div class="body">${esc(e.text)}</div></div>` : "";
    case "tool_call": return `<div class="ev">${t}<div class="body"><span class="tool">${esc(e.tool)}</span> <span class="mono">${esc(shortArgs(e))}</span></div></div>`;
    case "tool_result": return R.verbose ? `<div class="ev">${t}<div class="body"><pre>${esc(e.result)}</pre></div></div>` : "";
    case "check": return `<div class="ev ${e.passed ? "pass" : "failc"}">${t}<div class="body"><span class="tickm">${e.passed ? "✓" : "✕"}</span> Check <b>${esc(e.check)}</b> ${e.passed ? "passed" : `failed (exit ${e.exit})`}<details><summary>output</summary><pre>${esc(e.output)}</pre></details></div></div>`;
    case "team_message": return `<div class="ev team">${t}<div class="body"><span class="to">→ ${esc(e.to)}${e.relay ? " (relay)" : ""}</span><pre>${esc(e.body)}</pre></div></div>`;
    case "team_start": return `<div class="ev stage">${t}<div class="body">Team spawned: ${esc(e.members.join(", "))}</div></div>`;
    case "team_stop": return `<div class="ev stage">${t}<div class="body">Team stopped: ${esc(e.reason)}</div></div>`;
    case "gate": return `<div class="ev stage">${t}<div class="body">Auditor · ${esc(e.gate)}${e.decisions ? ": " + esc(Object.entries(e.decisions).map(([k, v]) => `${k} ${v}`).join(", ")) : ""}${e.Decision ? "" : ""}</div></div>`;
    case "warning": return `<div class="ev fail">${t}<div class="body">${esc(e.text)}</div></div>`;
    case "run": return `<div class="ev">${t}<div class="body">Run ${esc(e.status)} (start: ${esc(e.seed)})</div></div>`;
    default: return "";
  }
}
function shortArgs(e) {
  try { const a = JSON.parse(e.args); return a.command || a.file_path || a.pattern || (a.to ? `to ${a.to}` : e.args); } catch { return e.args; }
}

function addEvent(e) {
  R.events.push(e);
  if (R.tab === "log" && $("#log")) {
    const log = $("#log");
    const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
    if (R.events.length === 1) log.innerHTML = "";
    log.insertAdjacentHTML("beforeend", evHtml(e));
    $("#evcount").textContent = `${R.events.length} events`;
    if (atEnd) log.scrollTop = log.scrollHeight;
  }
}

async function openStream(id) {
  if (stream) stream.close();
  stream = null;
  if (id === "sample") return;
  if (!R.run.active) {  // nothing running: read the log once instead of holding a stream open
    const { events } = await api(`/api/runs/${id}/log?after=${R.events.length}`);
    events.forEach(addEvent);
    return;
  }
  stream = new EventSource(`/api/runs/${id}/events?after=${R.events.length}`);
  stream.addEventListener("log", (m) => addEvent(JSON.parse(m.data)));
  stream.addEventListener("run", (m) => {
    const prev = R.run;
    R.run = JSON.parse(m.data);
    renderHead();
    if (!R.run.active && stream) { stream.close(); stream = null; }
    if (prev && (prev.status !== R.run.status || prev.active !== R.run.active)) {
      renderTabs();
      if (R.run.status === "awaiting_review" && !R.run.active) { R.tab = "review"; renderTabs(); renderPane(); }
      else if (R.run.status === "awaiting_signoff" && !R.run.active) { R.tab = "signoff"; renderTabs(); renderPane(); }
      else if (R.tab !== "log") renderPane();
    }
  });
}

// -- files
const GROUPS = [
  ["The pack", /^(planning-memo|risk-control-matrix|audit-program|challenges|review)\.md$/],
  ["Risk register", /^(risk-register\.md|auditor-comments\.md|risk-ratings\.json|risk-register\.state\.json)$/],
  ["Inputs to the register", /^(rules|analytics|history)\.json$/],
  ["Samples", /^samples\//],
  ["Plan & figures", /^(audit-plan|pack-figures)\.json$/],
  ["Full analytics lists", /^analytics-full\//],
];
async function paneFiles() {
  $("#pane").innerHTML = `<div class="files"><div class="flist" id="flist"><div class="empty">Loading…</div></div><div class="viewer" id="viewer"><div class="empty">Select a file.</div></div></div>`;
  const { files } = await api(`/api/runs/${R.run.id}/files`);
  if (!files.length) { $("#flist").innerHTML = `<div class="empty">No outputs yet.</div>`; return; }
  const used = new Set();
  let html = "";
  for (const [g, re] of [...GROUPS, ["Other", /.*/]]) {
    const fs = files.filter((f) => !used.has(f.path) && re.test(f.path));
    if (!fs.length) continue;
    fs.forEach((f) => used.add(f.path));
    html += `<div class="grp">${g}</div>` + fs.map((f) => `<button data-p="${esc(f.path)}" class="${R.file === f.path ? "on" : ""}" title="${esc(f.path)}"><span>${esc(f.path.split("/").pop())}</span><small>${kb(f.size)}</small></button>`).join("");
  }
  $("#flist").innerHTML = html;
  $("#flist").onclick = (e) => { const b = e.target.closest("button[data-p]"); if (b) openFile(b.dataset.p); };
  openFile(R.file && used.has(R.file) ? R.file : (files.find((f) => f.path === "planning-memo.md") || files.find((f) => f.path === "risk-register.md") || files[0]).path);
}

async function openFile(path) {
  R.file = path;
  document.querySelectorAll("#flist button").forEach((b) => b.classList.toggle("on", b.dataset.p === path));
  const v = $("#viewer");
  v.innerHTML = `<div class="empty">Loading…</div>`;
  const text = await api(`/api/runs/${R.run.id}/file?path=${encodeURIComponent(path)}`);
  const head = `<div class="vhead"><span>outputs/${esc(path)}</span></div>`;
  if (path.endsWith(".md")) v.innerHTML = head + `<div class="md">${DOMPurify.sanitize(marked.parse(text))}</div>`;
  else if (path.endsWith(".json")) { let t = text; try { t = JSON.stringify(JSON.parse(text), null, 2); } catch { /* truncated */ } v.innerHTML = head + `<pre class="raw">${esc(t)}</pre>`; }
  else if (path.endsWith(".csv")) v.innerHTML = head + csvTable(text);
  else v.innerHTML = head + `<pre class="raw">${esc(text)}</pre>`;
  v.scrollTop = 0;
}

function csvTable(text, max = 500) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length && rows.length <= max; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else if (c !== "\r") cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const [h, ...body] = rows;
  const more = body.length >= max ? `<p class="hint" style="margin-top:8px">First ${max} rows shown; download the pack for the full file.</p>` : "";
  return `<div style="overflow:auto"><table class="csv"><thead><tr>${(h || []).map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${body.slice(0, max).map((r) => `<tr>${r.map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${more}`;
}

// -- gate 1
async function paneReview() {
  const r = R.run;
  const { risks } = await api(`/api/runs/${r.id}/risks`);
  const open = r.status === "awaiting_review" && !r.active && !r.read_only;
  if (!risks.length) { $("#pane").innerHTML = `<div class="empty">The risk register is built at the end of stage B.</div>`; return; }
  const decided = risks.every((x) => x.decision);
  $("#pane").innerHTML = `
    <div class="gate-head"><div><h2>Risk review</h2>
      <p>The risk-assessor proposes; you decide scope. <b>Approve</b> keeps a risk in scope as rated, <b>Amend</b> keeps it once changed (say what to change), <b>Reject</b> takes it out of scope (say why). Read the full justification and evidence in the register before deciding.</p></div>
      <button class="btn" id="openReg">Open risk-register.md</button></div>
    <div class="panel" style="padding:0">
      ${risks.map((x) => `
        <div class="risk" data-id="${x.risk_id}"><span class="rid">${x.risk_id}</span>
          <div><div class="title">${esc(x.title)}</div><div class="rating">${esc(x.rating)}</div>
            ${!open && x.decision ? `<div class="prev">${esc(x.status || "")}</div>` : ""}</div>
          <div>${open ? `
            <div class="choice">${["APPROVE", "AMEND", "REJECT"].map((d) => `<label class="${d.toLowerCase()}"><input type="radio" name="d-${x.risk_id}" value="${d}" ${x.decision === d ? "checked" : ""}>${d}</label>`).join("")}</div>
            <textarea rows="2" placeholder="Comment (needed for Amend and Reject)">${esc(stripSig(x.comment))}</textarea>` :
            `<div><span class="badge ${x.decision === "APPROVE" ? "tick" : x.decision ? "pen" : ""}">${esc(x.decision || "undecided")}</span></div><p class="hint" style="margin-top:6px">${esc(x.comment)}</p>`}
          </div></div>`).join("")}
      ${open ? `<div class="gate-foot"><label class="field" style="width:280px">Auditor name<input type="text" id="auditor" value="${esc(store.get("auditor"))}"></label>
        <div class="row"><span id="gmsg" class="hint">Saving writes outputs/auditor-comments.md; the risk-assessor then builds the revision and the team starts.</span>
        <button class="btn pen" id="submitDec">Record decisions and continue</button></div></div>` : ""}
    </div>
    ${!open && decided && r.status !== "awaiting_review" ? "" : ""}`;
  $("#openReg").onclick = () => { R.tab = "files"; R.file = "risk-register.md"; renderTabs(); renderPane(); };
  if (!open) return;
  $("#submitDec").onclick = () => withKey(async () => {
    const msg = (t, c = "err") => { $("#gmsg").className = c; $("#gmsg").textContent = t; };
    const auditor = $("#auditor").value.trim();
    if (!auditor) return msg("Enter the auditor's name.");
    const decisions = [];
    for (const el of document.querySelectorAll(".risk[data-id]")) {
      const d = el.querySelector("input:checked")?.value;
      const comment = el.querySelector("textarea").value.trim();
      if (!d) return msg(`Decide ${el.dataset.id}.`);
      if (d !== "APPROVE" && !comment) return msg(`${el.dataset.id}: ${d} needs a comment.`);
      decisions.push({ risk_id: el.dataset.id, decision: d, comment });
    }
    store.set("auditor", auditor);
    $("#submitDec").disabled = true; msg("Saving…", "hint");
    try {
      await api(`/api/runs/${r.id}/decisions`, { method: "POST", body: JSON.stringify({ auditor, decisions }) });
      await startStage(r.id);
      R.tab = "log"; await refreshRun();
    } catch (e) { msg(e.message); $("#submitDec").disabled = false; }
  });
}
const stripSig = (c) => (c || "").replace(/^[^,]+, \d{4}-\d{2}-\d{2}[:.]\s*/, "");

// -- gate 2
async function paneSignoff() {
  const r = R.run;
  const files = (await api(`/api/runs/${r.id}/files`)).files.map((f) => f.path);
  if (!files.includes("review.md")) { $("#pane").innerHTML = `<div class="empty">The QA review is written at the end of stage D.</div>`; return; }
  const review = await api(`/api/runs/${r.id}/file?path=review.md`);
  const verdict = r.qa?.verdict || (/\*\*READY FOR SIGN-OFF\*\*|VERDICT: READY FOR SIGN-OFF/.test(review) ? "READY FOR SIGN-OFF" : "BLOCKED");
  const qaText = r.qa?.output || (review.match(/```text\n([\s\S]*?)```/) || [])[1] || "";
  const open = r.status === "awaiting_signoff" && !r.read_only;
  const signed = r.signoff || parseSignoff(review);
  const pack = ["planning-memo.md", "risk-control-matrix.md", "audit-program.md", "challenges.md", "review.md"].filter((f) => files.includes(f));
  $("#pane").innerHTML = `
    <div class="verdict">
      <div class="panel">
        <div class="row" style="justify-content:space-between"><h2>QA verdict</h2><span class="stamp ${verdict === "READY FOR SIGN-OFF" ? "tick" : "pen"}">${esc(verdict)}</span></div>
        <p class="hint" style="margin-top:6px">The harness re-ran <span class="mono">scripts/checks/run_checks.py</span> after the team finished: quotes against the PDF, every figure against the outputs, rule → risk → control → test, and every sampled transaction against the spend data.</p>
        <div class="qaout">${esc(qaText.trim())}</div>
        ${r.qa?.team_done ? `<p class="hint" style="margin-top:12px">Team: ${esc(Object.values(r.qa.team_done).join(" · "))}${r.qa.team_stop ? " — " + esc(r.qa.team_stop) : ""}</p>` : ""}
      </div>
      <div class="panel stack">
        <h3>The pack</h3>
        <div class="packlinks">${pack.map((f) => `<button data-p="${f}">${f}</button>`).join("")}</div>
        <p class="hint">Challenges marked <i>for the auditor</i> are listed at the end of challenges.md.</p>
        ${open ? `
          <label class="field">Auditor name<input type="text" id="sgName" value="${esc(store.get("auditor"))}"></label>
          <label class="field">Decision<select id="sgDec">${verdict === "READY FOR SIGN-OFF" ? "<option>SIGNED OFF</option>" : ""}<option>RETURNED</option></select></label>
          <label class="field">Comments<textarea id="sgCom" rows="3"></textarea></label>
          <div class="row"><button class="btn pen" id="sgGo">Record sign-off</button><span id="sgMsg" class="hint"></span></div>` :
          signed && signed.Auditor ? `<div><span class="stamp ${signed["Decision (SIGNED OFF / RETURNED)"] === "SIGNED OFF" ? "tick" : "pen"}">${esc(signed["Decision (SIGNED OFF / RETURNED)"])}</span>
            <p class="hint" style="margin-top:10px">${esc(signed.Auditor)} · ${esc(signed.Date)}<br>${esc(signed.Comments || "")}</p></div>` : `<p class="hint">Sign-off opens when the team has finished.</p>`}
      </div>
    </div>`;
  document.querySelectorAll(".packlinks button").forEach((b) => (b.onclick = () => { R.tab = "files"; R.file = b.dataset.p; renderTabs(); renderPane(); }));
  if (!open) return;
  $("#sgGo").onclick = async () => {
    const auditor = $("#sgName").value.trim();
    if (!auditor) { $("#sgMsg").className = "err"; $("#sgMsg").textContent = "Enter the auditor's name."; return; }
    store.set("auditor", auditor);
    try {
      await api(`/api/runs/${r.id}/signoff`, { method: "POST", body: JSON.stringify({ auditor, decision: $("#sgDec").value, comments: $("#sgCom").value }) });
      await refreshRun();
    } catch (e) { $("#sgMsg").className = "err"; $("#sgMsg").textContent = e.message; }
  };
}
function parseSignoff(md) {
  const block = md.split("## Auditor sign-off").pop() || "";
  const out = {};
  for (const line of block.split("\n")) {
    const m = line.match(/^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/);
    if (m && m[1] !== "---" && m[2] !== "---") out[m[1]] = m[2];
  }
  return out;
}

// ---- router ------------------------------------------------------------------
function route() {
  if (stream && !location.hash.startsWith("#/run/")) { stream.close(); stream = null; }
  const h = location.hash.replace(/^#/, "") || "/";
  const m = h.match(/^\/run\/([A-Za-z0-9]+)(?:\/(log|files|review|signoff))?$/);
  if (m) return viewRun(m[1], m[2]);
  if (h === "/runs") return viewRuns();
  if (h === "/new") return viewNew();
  return viewHome();
}

(async function init() {
  CONFIG = await api("/api/config");
  renderConn();
  $("#connBtn").onclick = () => openConn();
  window.addEventListener("hashchange", route);
  route();
})();
