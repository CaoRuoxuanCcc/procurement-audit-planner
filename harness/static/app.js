/* Procurement Audit Planner — frontend (no build step).
   Every figure shown comes from a run's output files (analytics.json, the
   risk register, the QA output) through the existing API; nothing is
   computed or invented here beyond formatting and counting labelled rows. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");
let CONFIG = null;
let stream = null;
let routeToken = 0;

// ---------------------------------------------------------------- storage & api
const store = {
  get(k) { try { return sessionStorage.getItem(k) || ""; } catch { return ""; } },
  set(k, v) { try { v ? sessionStorage.setItem(k, v) : sessionStorage.removeItem(k); } catch { /* private mode */ } },
};
const conn = () => ({ provider: store.get("provider"), model: store.get("model"), key: store.get("key"), tested: store.get("tested") === "1" });
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
const fileText = (id, path) => api(`/api/runs/${id}/file?path=${encodeURIComponent(path)}`);
async function fileJson(id, path) { try { return JSON.parse(await fileText(id, path)); } catch { return null; } }

// ---------------------------------------------------------------- icons
const I = {
  check: '<svg viewBox="0 0 20 20"><path d="M5 10.5l3.2 3.2L15 7"/></svg>',
  x: '<svg viewBox="0 0 20 20"><path d="M6 6l8 8M14 6l-8 8"/></svg>',
  pen: '<svg viewBox="0 0 20 20"><path d="M4 16l1-4 8-8 3 3-8 8zM11.5 5.5l3 3"/></svg>',
  pause: '<svg viewBox="0 0 20 20"><path d="M8 6v8M12 6v8"/></svg>',
  info: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.3v.2"/></svg>',
  alert: '<svg viewBox="0 0 20 20"><path d="M10 3l8 14H2zM10 8v4M10 14.5v.2"/></svg>',
  doc: '<svg viewBox="0 0 20 20"><path d="M5 2.5h7l3 3v12H5zM8 9h5M8 12h5M8 15h3"/></svg>',
  down: '<svg viewBox="0 0 20 20"><path d="M10 3v10M6 9.5l4 4 4-4M4 16.5h12"/></svg>',
  play: '<svg viewBox="0 0 20 20"><path d="M6.5 4.5v11l9-5.5z"/></svg>',
  stop: '<svg viewBox="0 0 20 20"><rect x="5.5" y="5.5" width="9" height="9" rx="1.5"/></svg>',
  inbox: '<svg viewBox="0 0 24 24"><path d="M3 13l3-8h12l3 8v6H3zM3 13h5l1 3h6l1-3h5"/></svg>',
  shield: '<svg viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 5-3.2 7.6-7 8.5-3.8-.9-7-3.5-7-8.5V6z"/></svg>',
};

// ---------------------------------------------------------------- formatting
const nf = new Intl.NumberFormat("en-GB");
const gbp = (n) => "£" + new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
const gbpShort = (n) => n >= 1e6 ? `£${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}m` : n >= 1e3 ? `£${Math.round(n / 1e3)}k` : gbp(n);
const when = (t) => (t ? new Date(t * 1000).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—");
const clock = (t) => new Date(t * 1000).toLocaleTimeString("en-GB", { hour12: false });
const kb = (n) => (n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? Math.round(n / 1e3) + " KB" : n + " B");
const tokens = (n) => (n > 1e6 ? (n / 1e6).toFixed(2) + "M" : n > 1e3 ? Math.round(n / 1e3) + "k" : String(n || 0));
const money = (r) => (r.cost_usd ? `$${r.cost_usd.toFixed(2)}${r.cost_known ? "" : "+"}` : r.cost_known ? "$0.00" : "—");
const skel = (w = "100%", h = 14) => `<span class="sk" style="width:${w};height:${h}px"></span>`;
const empty = (icon, title, body, action = "") => `<div class="empty">${I[icon] || ""}<b>${esc(title)}</b><p>${body}</p>${action}</div>`;

// ---------------------------------------------------------------- run status
const STATUS = {
  created: ["Ready to start", "", false], ready: ["Continuing", "teal", true], stage1: ["Extracting rules", "teal", true],
  stage2: ["Analysing spend", "teal", true], awaiting_review: ["Awaiting risk review", "critical", false],
  stage4: ["Agent team planning", "teal", true], awaiting_signoff: ["Awaiting sign-off", "critical", false],
  complete: ["Complete", "good", false], failed: ["Failed", "critical", false], interrupted: ["Interrupted", "warn", false],
};
function statusPill(run) {
  const [label, cls] = STATUS[run.status] || [run.status, ""];
  const running = run.active;
  return `<span class="pill ${running ? "teal run" : cls}"><span class="d"></span>${esc(running && !STATUS[run.status][2] ? "Running" : label)}</span>`;
}

const STAGES = [
  { key: "stage1", name: "Rules extraction", by: "Skill · extract-rules", out: "rules.json", filter: "stage1" },
  { key: "stage2", name: "Spend analysis", by: "spend-analyst ‖ findings-analyst → risk-assessor", out: "risk-register.md", filter: "stage2" },
  { key: "awaiting_review", name: "Human risk review", by: "Auditor approves, amends or rejects each risk", human: true, tab: "review" },
  { key: "stage4", name: "Audit planning", by: "Team · planner, challenger, qa-reviewer", out: "planning-memo.md", filter: "stage4" },
  { key: "awaiting_signoff", name: "QA & sign-off", by: "QA scripts, then auditor sign-off", human: true, tab: "signoff" },
];
const ORDER = ["stage1", "stage2", "awaiting_review", "stage4", "awaiting_signoff", "complete"];

function position(run) {
  if (run.id === "sample" || run.status === "complete") return ORDER.length - 1;
  if (["failed", "interrupted", "ready", "created"].includes(run.status)) return ORDER.indexOf(run.next_stage);
  return ORDER.indexOf(run.status);
}
function nodeState(run, i) {
  const pos = position(run);
  const mine = ORDER.indexOf(STAGES[i].key);
  if (mine < pos) return ["done", reused(run, i) ? "Reused from Part A" : "Completed"];
  if (mine > pos) return ["", "Pending"];
  if (run.status === "failed") return ["failed", "Failed"];
  if (run.status === "interrupted") return ["interrupted", "Interrupted"];
  if (STAGES[i].human) return ["awaiting", "Awaiting approval"];
  if (run.active) return ["running", "Running"];
  return ["", run.status === "created" ? "Ready to start" : "Pending"];
}
// A run can start from the Part A outputs: rules.json (stage2), or rules,
// analytics and history (risk), in which case only the risk-assessor runs live.
const reused = (run, i) => i === 0 && (run.seed === "stage2" || run.seed === "risk");
const doneCount = (run) => STAGES.filter((_, i) => nodeState(run, i)[0] === "done").length;

function liveAgents(events) {
  const live = new Set();
  for (const e of events) {
    if (e.kind === "stage") live.clear();
    else if (e.kind === "agent_start") live.add(e.agent);
    else if (e.kind === "agent_done") live.delete(e.agent);
  }
  return [...live].map((a) => (a === "main" ? "extract-rules" : a));
}

function flowHtml(run, { interactive = false, events = [] } = {}) {
  const live = run.active ? liveAgents(events) : [];
  return `<div class="flow" role="list">${STAGES.map((s, i) => {
    const [cls, label] = nodeState(run, i);
    const bub = cls === "done" ? I.check : cls === "failed" ? I.x : cls === "awaiting" ? I.pen : cls === "interrupted" ? I.pause : String(i + 1);
    const clickable = interactive && (cls || s.human);
    const pillCls = { done: "good", running: "teal run", awaiting: "critical", failed: "critical", interrupted: "warn" }[cls] || "";
    return `<button class="node ${cls}" role="listitem" data-node="${i}" ${clickable ? "" : "disabled"} aria-label="${esc(s.name)}: ${esc(label)}">
      <span class="rail"><span class="bub">${bub}</span><span class="line"></span></span>
      <span class="nm">${esc(s.name)}</span>
      <span><span class="pill ${pillCls}"><span class="d"></span>${esc(label)}</span></span>
      <span class="by">${esc(i === 1 && run.seed === "risk" ? "Part A analytics and history reused · risk-assessor live" : s.by)}</span>
      ${cls === "running" && live.length ? `<span class="live">Working: ${esc(live.join(", "))}</span>` : ""}
    </button>`;
  }).join("")}</div>`;
}
const meterHtml = (run) => `<div class="meter">${STAGES.map((_, i) => {
  const c = nodeState(run, i)[0];
  return `<i class="${c === "done" ? "on" : c === "awaiting" || c === "failed" ? "wait" : ""}"></i>`;
}).join("")}</div>`;

// ---------------------------------------------------------------- risk parsing
function parseRating(rating) {
  const m = String(rating || "").match(/L(\d)\s*×\s*I(\d)\s*→\s*(\d+),\s*(.*)$/);
  if (!m) return { l: null, i: null, score: null, band: rating || "", short: rating || "Not rated", sev: "" };
  const band = m[4].trim();
  const sev = /red/i.test(band) ? "critical" : /amber/i.test(band) ? "serious" : /moderate|yellow/i.test(band) ? "warn" : /green|low/i.test(band) ? "good" : "";
  const short = band.replace(/\s*\(.*$/, "").replace(/[†‡]/g, "").trim();
  return { l: +m[1], i: +m[2], score: +m[3], band, short, sev };
}
const isHighBand = (p) => /high|extreme|red|amber/i.test(p.band);
function registerSections(md) {
  const out = {};
  const parts = md.split(/^### /m);
  for (const p of parts.slice(1)) {
    const m = p.match(/^(R-\d{2})\b/);
    if (!m) continue;
    out[m[1]] = "### " + p.split(/\n## /)[0];
  }
  return out;
}

// ---------------------------------------------------------------- tooltip
const tip = $("#tip");
document.addEventListener("mousemove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  if (!t) { tip.hidden = true; return; }
  tip.innerHTML = t.dataset.tip;
  tip.hidden = false;
  const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  tip.style.left = x + "px";
  tip.style.top = (e.clientY + 16) + "px";
});

// ---------------------------------------------------------------- connection
function renderConn() {
  const c = conn();
  const p = CONFIG?.providers[c.provider];
  $("#connDot").className = "conn-dot" + (connected() ? (c.tested ? " ok" : " untested") : "");
  $("#connLabel").textContent = connected() ? c.model : "No model connected";
  $("#connSub").textContent = connected() ? `${p ? p.label : c.provider} · ${c.tested ? "key verified" : "key not tested"}` : "Connect to start a run";
}

function openConn(onSaved) {
  const dlg = $("#connDlg");
  const c = conn();
  let provider = c.provider || "anthropic";
  let tested = false;
  $("#provSeg").innerHTML = `<legend class="lbl">Provider</legend>` + Object.entries(CONFIG.providers).map(([id, p]) => {
    const [name, sub] = [p.label.split(" (")[0], p.label.match(/\((.*)\)/)?.[1] || ""];
    return `<label><input type="radio" name="prov" value="${id}" ${id === provider ? "checked" : ""}>${esc(name)}<small>${esc(sub)}</small></label>`;
  }).join("");
  const msg = (t, cls = "") => { const m = $("#connMsg"); m.className = "inline-msg " + cls; m.textContent = t; };
  const model = () => ($("#modelSel").value === "__custom" ? $("#customModel").value.trim() : $("#modelSel").value);
  const showWarn = () => {
    const m = CONFIG.providers[provider].models.find((x) => x.id === $("#modelSel").value);
    msg(m?.warning || "Test checks the key and model against the provider's model list. It uses no tokens.", m?.warning ? "err" : "");
  };
  const fillModels = () => {
    const p = CONFIG.providers[provider];
    const sel = $("#modelSel");
    sel.innerHTML = p.models.map((m) => `<option value="${m.id}">${esc(m.label)}${m.recommended ? " (recommended)" : ""}</option>`).join("") + `<option value="__custom">Other model id…</option>`;
    const same = provider === c.provider;
    const known = p.models.some((m) => m.id === c.model);
    sel.value = same ? (known ? c.model : c.model ? "__custom" : p.models[0].id) : p.models[0].id;
    $("#customModel").value = same && !known ? c.model : "";
    $("#customWrap").hidden = sel.value !== "__custom";
    $("#keyIn").placeholder = p.key_hint;
    $("#keyIn").value = same ? c.key : "";
    tested = same && c.tested;
    showWarn();
  };
  $("#provSeg").onchange = (e) => { provider = e.target.value; fillModels(); };
  $("#modelSel").onchange = () => { $("#customWrap").hidden = $("#modelSel").value !== "__custom"; tested = false; showWarn(); };
  $("#keyIn").oninput = $("#customModel").oninput = () => { tested = false; };
  $("#connTest").onclick = async () => {
    const key = $("#keyIn").value.trim();
    if (!key) return msg("Enter an API key.", "err");
    $("#connTest").disabled = true; msg("Checking with the provider…");
    try {
      const r = await api("/api/keys/test", { method: "POST", headers: { "X-LLM-Key": key }, body: JSON.stringify({ provider, model: model() }) });
      if (!r.ok) msg(r.error, "err");
      else if (r.model_found === false) msg(`The key works, but "${model()}" is not in its model list. Pick another model or check the id.`, "err");
      else { tested = true; msg(`Key verified. ${model()} is available.`, "ok"); }
    } catch (e) { msg(e.message, "err"); }
    $("#connTest").disabled = false;
  };
  $("#connSave").onclick = () => {
    const key = $("#keyIn").value.trim();
    if (!key || !model()) return msg("Enter a model and an API key.", "err");
    store.set("provider", provider); store.set("model", model()); store.set("key", key); store.set("tested", tested ? "1" : "");
    renderConn(); dlg.close(); onSaved && onSaved();
  };
  $("#connForget").onclick = () => { store.set("key", ""); store.set("tested", ""); $("#keyIn").value = ""; tested = false; renderConn(); msg("Key removed from this tab."); };
  $("#connCancel").onclick = () => dlg.close();
  fillModels();
  dlg.showModal();
}
const withKey = (fn) => (connected() ? fn() : openConn(fn));
const startStage = (id) => {
  const c = conn();
  return api(`/api/runs/${id}/start`, { method: "POST", headers: { "X-LLM-Key": c.key }, body: JSON.stringify({ provider: c.provider, model: c.model }) });
};

// ---------------------------------------------------------------- shared data
async function loadRuns() {
  const data = await api("/api/runs");
  const own = data.runs;
  const n1 = own.filter((r) => r.status === "awaiting_review" && !r.active).length;
  const n2 = own.filter((r) => r.status === "awaiting_signoff" && !r.active).length;
  $("#navReview").hidden = !n1; $("#navReview").textContent = n1;
  $("#navSignoff").hidden = !n2; $("#navSignoff").textContent = n2;
  return data;
}
function setNav(which) {
  $$("[data-nav]").forEach((a) => {
    const on = a.dataset.nav === which;
    a.classList.toggle("on", on);
    on ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current");
  });
}
const runName = (r) => r.label || `Run ${r.id}`;

// ================================================================ OVERVIEW
const TAGS = {
  care_or_education_placement: "Care & education placements", general_procurement: "General procurement",
  grant: "Grants", premises: "Premises", agency_staff: "Agency staff",
};
const INDICATORS = [
  ["threshold_clustering", "Payments just under a tier", "in the band below an App B threshold", (c) => c.flagged_payments],
  ["split_purchases", "Split-purchase groups", "same supplier, combined total crosses a tier", (c) => c.groups],
  ["off_contract", "Suppliers without a matched notice", "above the notice tier, no exact-matched notice", (c) => c.overall?.no_notice_found?.count],
  ["duplicates", "Possible duplicate payments", "clusters with different timestamps", (c) => c.clusters_with_different_timestamp],
  ["expired_notice_spend", "Spend after notice ended", "suppliers paid after every notice ended", (c) => c.flagged],
  ["spend_vs_award", "Spend ahead of award", "annualised spend ≥ 1.25 × award per year", (c) => c.flagged],
  ["high_value_suppliers", "High-value suppliers", "population to request contract evidence for", (c) => c.suppliers],
];

async function viewOverview(token) {
  setNav("overview");
  app.innerHTML = `
    <div class="hero"><div><h1>Procurement audit overview</h1>
      <p>Agents extract the council's procurement rules, test every payment over £500 against them and propose a rated risk register. You approve the scope; an agent team then plans, challenges and QA-checks the audit pack for your sign-off.</p></div>
      <div class="row"><a class="btn" href="#/run/sample">Explore sample run</a><a class="btn primary" href="#/new">${I.play}Start new audit</a></div></div>
    <div class="source" id="src">${skel("260px", 16)}</div>
    <div class="kpis">${[1, 2, 3, 4].map(() => `<div class="card kpi">${skel("50%", 11)}${skel("70%", 28)}${skel("80%", 12)}</div>`).join("")}</div>
    <div class="grid g-main">
      <div class="grid">
        <div class="card" id="wf"><div class="card-h"><div><h3>Agent workflow</h3><p>Loading…</p></div></div><div class="card-b">${skel("100%", 80)}</div></div>
        <div class="card" id="spend"><div class="card-h"><div><h3>Spend tested by category</h3></div></div><div class="card-b">${skel("100%", 140)}</div></div>
      </div>
      <div class="grid">
        <div class="card" id="attn"><div class="card-h"><h3>Needs your attention</h3></div>${skel("100%", 60)}</div>
        <div class="card" id="ind"><div class="card-h"><h3>Spend risk indicators</h3></div>${skel("100%", 120)}</div>
      </div>
    </div>`;
  const { runs, sample } = await loadRuns();
  if (token !== routeToken) return;

  // Attention list: only real, actionable states.
  const attn = runs.filter((r) => !r.active && ["awaiting_review", "awaiting_signoff", "failed", "interrupted"].includes(r.status));
  const running = runs.filter((r) => r.active);
  const items = [...running, ...attn].slice(0, 6);
  $("#attn").innerHTML = `<div class="card-h"><div><h3>Needs your attention</h3><p>Gates waiting on you, and runs in progress</p></div><a class="btn ghost sm" href="#/runs">All runs</a></div>` + (items.length
    ? `<div class="attn">${items.map((r) => {
      const tab = r.status === "awaiting_review" ? "review" : r.status === "awaiting_signoff" ? "signoff" : "log";
      const what = r.active ? "Agents are working" : { awaiting_review: "Approve, amend or reject the proposed risks", awaiting_signoff: "Review QA results and sign off the pack", failed: "A stage failed; resume when ready", interrupted: "Interrupted; resume to continue" }[r.status];
      return `<a href="#/run/${r.id}/${tab}"><span class="t"><b>${esc(runName(r))}</b><small>${esc(what)}</small></span>${statusPill(r)}</a>`;
    }).join("")}</div>`
    : empty("inbox", "Nothing waiting", "Runs that need a decision or are in progress appear here.", `<a class="btn sm" href="#/new">Start new audit</a>`));

  // Pick the data source: newest run with analytics, else the sample.
  const candidates = [];
  const recent = runs.slice(0, 8);
  const lists = await Promise.all(recent.map((r) => api(`/api/runs/${r.id}/files`).then((f) => f.files).catch(() => [])));
  recent.forEach((r, i) => { if (lists[i].some((f) => f.path === "analytics.json")) candidates.push(r); });
  candidates.push(sample);
  if (token !== routeToken) return;
  const saved = store.get("ovsrc");
  const src = candidates.find((r) => r.id === saved) || candidates[0];
  $("#src").innerHTML = `<span>Figures from</span><select id="srcSel" aria-label="Run the figures come from">${candidates.map((r) => `<option value="${r.id}" ${r.id === src.id ? "selected" : ""}>${esc(runName(r))}</option>`).join("")}</select>
    <a href="#/run/${src.id}" class="muted">Open run →</a>`;
  $("#srcSel").onchange = (e) => { store.set("ovsrc", e.target.value); route(); };

  const [analytics, riskData] = await Promise.all([fileJson(src.id, "analytics.json"), api(`/api/runs/${src.id}/risks`).catch(() => ({ risks: [] }))]);
  if (token !== routeToken) return;
  const cl = analytics?.cleaning;
  const risks = riskData.risks.map((r) => ({ ...r, p: parseRating(r.rating) }));
  const high = risks.filter((r) => isHighBand(r.p));
  const na = (why) => `<div class="v na">Not yet calculated</div><div class="s">${esc(why)}</div>`;
  const win = analytics?.window;
  const kpis = [
    ["Total spend tested", cl?.total_tested_gbp != null
      ? `<div class="v" data-tip="${esc(esc(gbp(cl.total_tested_gbp)) + " after exclusions")}">${gbpShort(cl.total_tested_gbp)}</div><div class="s">${win ? `${esc(win.start)} to ${esc(win.end)}` : "after exclusions"}</div>`
      : na("Calculated by the spend-analyst scripts")],
    ["Transactions analysed", cl?.rows_tested != null
      ? `<div class="v">${nf.format(cl.rows_tested)}</div><div class="s">of ${nf.format(cl.rows_read)} rows read; the rest excluded with reasons</div>`
      : na("Calculated by the spend-analyst scripts")],
    ["High-rated risks", risks.length
      ? `<div class="v">${high.length} <span class="muted" style="font-size:15px;font-weight:500">of ${risks.length}</span></div><div class="s">rated Medium-High or above in the register</div>`
      : na("Rated by the risk-assessor at the end of spend analysis")],
    ["Audit progress", `<div class="v">${doneCount(src)} <span class="muted" style="font-size:15px;font-weight:500">of 5 stages</span></div><div class="s">${esc((STATUS[src.status] || [src.status])[0])}</div>${meterHtml(src)}`],
  ];
  $(".kpis").innerHTML = kpis.map(([l, body]) => `<div class="card kpi"><span class="lbl">${l}</span>${body}</div>`).join("");

  $("#wf").innerHTML = `<div class="card-h"><div><h3>Agent workflow</h3><p>${esc(runName(src))}</p></div><a class="btn ghost sm" href="#/run/${src.id}">Open run</a></div>${flowHtml(src)}`;

  // Spend by category: one series, one hue, direct labels, table view.
  const tags = cl?.by_tag ? Object.entries(cl.by_tag).sort((a, b) => b[1].total_gbp - a[1].total_gbp) : [];
  const max = tags.length ? tags[0][1].total_gbp : 1;
  const tableView = store.get("spendTable") === "1";
  $("#spend").innerHTML = `<div class="card-h"><div><h3>Spend tested by category</h3><p>Tag assigned per payment by scripts/clean.py · ${esc(runName(src))}</p></div>
    ${tags.length ? `<button class="btn ghost sm" id="spendToggle">${tableView ? "Show chart" : "Show table"}</button>` : ""}</div>
    <div class="card-b">${!tags.length ? empty("doc", "Not yet calculated", "Spend categories appear once the spend analysis has run.")
      : tableView ? `<table class="data"><thead><tr><th>Category</th><th class="r">Payments</th><th class="r">Total</th></tr></thead><tbody>${tags.map(([k, v]) => `<tr><td>${esc(TAGS[k] || k)}</td><td class="r num">${nf.format(v.count)}</td><td class="r num">${gbp(v.total_gbp)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="bars">${tags.map(([k, v]) => `<div class="bar-row"><span class="name">${esc(TAGS[k] || k)}</span>
          <div class="bar-track" data-tip="${esc(`<b>${esc(TAGS[k] || k)}</b><br>${esc(gbp(v.total_gbp))}<br>${nf.format(v.count)} payments`)}">
            <span class="bar-fill" style="width:${Math.max((v.total_gbp / max) * 72, 0.5)}%"></span>
            <span class="bar-val"><b>${gbpShort(v.total_gbp)}</b> · ${nf.format(v.count)}</span></div></div>`).join("")}</div>`}</div>`;
  $("#spendToggle") && ($("#spendToggle").onclick = () => { store.set("spendTable", tableView ? "" : "1"); route(); });

  const tests = analytics?.tests;
  $("#ind").innerHTML = `<div class="card-h"><div><h3>Spend risk indicators</h3><p>Counts from analytics.json · indicators to investigate, not findings</p></div></div>` + (tests
    ? `<div>${INDICATORS.map(([k, name, sub, get]) => {
      const t = tests[k];
      if (!t) return "";
      const v = t.status === "ran" ? get(t.counts || {}) : null;
      return `<div class="indic-row"><div><b>${esc(name)}</b><p>${esc(sub)}${t.rule_ids?.length ? ` · ${esc(t.rule_ids.slice(0, 3).join(", "))}${t.rule_ids.length > 3 ? "…" : ""}` : ""}</p></div>
        <div class="n">${t.status === "ran" && v != null ? nf.format(v) : `<span class="pill warn">${esc(t.status || "not computed")}</span>`}</div></div>`;
    }).join("")}</div>`
    : empty("shield", "Not yet calculated", "Indicators appear once the spend analysis has run."));
}

// ================================================================ RUNS
async function viewRuns(token) {
  setNav("runs");
  app.innerHTML = `<div class="page-head"><div><h1>Audit runs</h1><p>Each run is a fresh copy of the project: the rules, skills, agents, scripts and public data. Stages A–B run back to back, then wait for your risk review.</p></div>
    <a class="btn primary" href="#/new">${I.play}New audit run</a></div>
    <div class="card" id="list">${skel("100%", 180)}</div>`;
  const { runs, sample } = await loadRuns();
  if (token !== routeToken) return;
  const all = [...runs, sample];
  $("#list").innerHTML = `<table class="data"><thead><tr><th>Run</th><th>Status</th><th>Progress</th><th>Model</th><th class="r">Cost</th><th>Created</th></tr></thead><tbody>
    ${all.map((r) => `<tr class="link" data-id="${r.id}" tabindex="0"><td><b>${esc(runName(r))}</b><div class="small muted mono">${esc(r.id)}</div></td>
      <td>${statusPill(r)}</td><td style="min-width:140px"><div class="kpi" style="padding:0;min-height:0">${meterHtml(r)}</div><div class="small muted">${doneCount(r)} of 5 stages</div></td>
      <td>${esc(r.model || "—")}<div class="small muted">${esc(r.provider || "")}</div></td>
      <td class="r num">${money(r)}</td><td class="small muted">${r.id === "sample" ? "Part A" : when(r.created)}</td></tr>`).join("")}
    </tbody></table>${runs.length ? "" : `<div class="empty" style="border-top:1px solid var(--line)"><p>No live runs yet on this server. The sample above is the complete Part A run.</p></div>`}`;
  const go = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) location.hash = `#/run/${tr.dataset.id}`; };
  $("#list").onclick = go;
  $("#list").onkeydown = (e) => { if (e.key === "Enter") go(e); };
}

function viewNew() {
  setNav("runs");
  app.innerHTML = `
    <div class="crumbs"><a href="#/runs">Audit runs</a> / New</div>
    <div class="page-head"><div><h1>Start a new audit run</h1><p>Choose where the run starts. Earlier stages can reuse the outputs of the Part A run to save time and model cost; everything after runs live with your model.</p></div></div>
    <div class="grid g-main">
      <div class="card"><div class="card-h"><h3>Start point</h3></div><div class="card-b grid">
        <div class="option-list" role="radiogroup" aria-label="Start point">
          <label><input type="radio" name="seed" value="full" checked><b>Full pipeline</b><small>Extract the rules from the PDF, then spend analysis, risk review, planning and QA. Most model calls.</small></label>
          <label><input type="radio" name="seed" value="stage2"><b>Reuse rules · start at spend analysis</b><small>Uses the Part A rules.json; runs the sub-agents, the register, review, team and QA.</small></label>
          <label><input type="radio" name="seed" value="risk"><b>Reuse rules, analytics and history · start at risk rating</b><small>Cheapest live run: the risk-assessor, your review, the agent team and QA.</small></label>
        </div>
        <label class="field">Run label (optional)<input type="text" id="label" maxlength="80" placeholder="e.g. Sonnet trial, October"></label>
      </div></div>
      <div class="card"><div class="card-h"><h3>Model</h3></div><div class="card-b grid">
        <div id="connBox"></div>
        <div class="row"><button class="btn primary" id="go">${I.play}Create and start</button></div>
        <div id="msg" class="inline-msg" role="status"></div>
        <p class="small muted">A full run takes roughly 30–90 minutes and makes many model calls, billed to your key. You can leave this page; the run continues on the server.</p>
      </div></div>
    </div>`;
  const box = () => {
    const c = conn();
    $("#connBox").innerHTML = connected()
      ? `<div class="row" style="justify-content:space-between"><div><b>${esc(c.model)}</b><div class="small muted">${esc(CONFIG.providers[c.provider]?.label || c.provider)} · ${c.tested ? "key verified" : "key not tested"}</div></div><button class="btn sm" id="chg">Change</button></div>`
      : `<div class="banner">${I.info}<div>No model connected yet. You will be asked for a provider and key when you start.</div></div><button class="btn sm" id="chg">Connect a model</button>`;
    $("#chg").onclick = () => openConn(box);
  };
  box();
  $("#go").onclick = () => withKey(async () => {
    box();
    const seed = $("input[name=seed]:checked").value;
    $("#go").disabled = true; $("#msg").className = "inline-msg"; $("#msg").textContent = "Creating the run workspace…";
    try {
      const run = await api("/api/runs", { method: "POST", body: JSON.stringify({ seed, label: $("#label").value }) });
      $("#msg").textContent = "Starting the first stage…";
      try { await startStage(run.id); } catch (e) { location.hash = `#/run/${run.id}`; throw e; }
      location.hash = `#/run/${run.id}/log`;
    } catch (e) { $("#msg").className = "inline-msg err"; $("#msg").textContent = e.message; $("#go").disabled = false; }
  });
}

// ================================================================ REVIEW INDEX
async function viewReviewIndex(token) {
  setNav("review");
  app.innerHTML = `<div class="page-head"><div><h1>Risk review</h1><p>The human approval gate. The risk-assessor proposes a rated register; you decide what is in scope before any audit planning starts.</p></div></div><div id="rv" class="grid">${skel("100%", 120)}</div>`;
  const { runs, sample } = await loadRuns();
  if (token !== routeToken) return;
  const waiting = runs.filter((r) => r.status === "awaiting_review" && !r.active);
  const past = [...runs.filter((r) => ["stage4", "awaiting_signoff", "complete"].includes(r.status) || (r.status !== "awaiting_review" && position(r) > 2)), sample];
  const row = (r, cta) => `<a href="#/run/${r.id}/review"><span class="t"><b>${esc(runName(r))}</b><small>${esc(r.model || "")} · ${r.id === "sample" ? "Part A" : when(r.created)}</small></span>${cta}</a>`;
  $("#rv").innerHTML = `
    <div class="card"><div class="card-h"><div><h3>Waiting for your decision</h3><p>Runs paused at the risk review gate</p></div></div>
      ${waiting.length ? `<div class="attn">${waiting.map((r) => row(r, `<span class="btn primary sm">Review risks</span>`)).join("")}</div>`
        : empty("shield", "No registers awaiting review", "A run pauses here after spend analysis. Start a run, or open a decided register below.", `<a class="btn sm" href="#/new">Start new audit</a>`)}</div>
    <div class="card"><div class="card-h"><div><h3>Decided registers</h3><p>Read-only record of past decisions</p></div></div>
      <div class="attn">${past.map((r) => row(r, statusPill(r))).join("")}</div></div>`;
}

// ================================================================ REPORTS
async function viewReports(token) {
  setNav("reports");
  app.innerHTML = `<div class="page-head"><div><h1>Reports</h1><p>Audit planning packs that have been through the agent team and the QA checks, with their verdict and sign-off.</p></div></div><div class="reports" id="rp">${skel("100%", 220)}</div>`;
  const { runs, sample } = await loadRuns();
  if (token !== routeToken) return;
  const packs = [...runs.filter((r) => ["awaiting_signoff", "complete"].includes(r.status)), sample];
  const cards = await Promise.all(packs.map(async (r) => {
    let verdict = r.qa?.verdict, signed = r.signoff;
    if (!verdict || !signed) {
      const review = await fileText(r.id, "review.md").catch(() => "");
      verdict = verdict || (/VERDICT: READY FOR SIGN-OFF/.test(review) ? "READY FOR SIGN-OFF" : review ? "BLOCKED" : null);
      signed = signed || parseSignoff(review);
    }
    const dec = signed?.["Decision (SIGNED OFF / RETURNED)"];
    return `<div class="card"><div class="card-h"><div><h3>${esc(runName(r))}</h3><p>${esc(r.model || "")} · ${r.id === "sample" ? "Part A run" : when(r.created)}</p></div>${statusPill(r)}</div>
      <div class="card-b grid" style="gap:12px">
        <div class="row">${verdict ? verdictStamp(verdict) : ""}${dec ? `<span class="pill ${dec === "SIGNED OFF" ? "good" : "critical"}">${esc(dec)} · ${esc(signed.Auditor)} · ${esc(signed.Date)}</span>` : `<span class="pill">Not signed off</span>`}</div>
      </div>
      <div style="border-top:1px solid var(--line)">${PACK.slice(0, 3).map(([f, n]) => `<a class="doc" href="#/run/${r.id}/files/${f}"><span class="ic">${I.doc}</span><span><b>${n}</b><small>${f}</small></span></a>`).join("")}</div>
      <div class="card-b row" style="border-top:1px solid var(--line)"><a class="btn sm" href="#/run/${r.id}/signoff">QA &amp; sign-off</a><a class="btn sm" href="/api/runs/${r.id}/download">${I.down}Download pack</a></div></div>`;
  }));
  if (token !== routeToken) return;
  $("#rp").innerHTML = cards.join("");
}
const verdictStamp = (v) => `<span class="stamp ${v === "READY FOR SIGN-OFF" ? "good" : "critical"}">${v === "READY FOR SIGN-OFF" ? I.check : I.x}${esc(v)}</span>`;
const PACK = [
  ["planning-memo.md", "Planning memo", "Scope, approach and the indicators behind each risk"],
  ["risk-control-matrix.md", "Risk-control matrix", "Each approved risk → expected control → test"],
  ["audit-program.md", "Audit program", "Test steps, targeted samples and the request list"],
  ["challenges.md", "Challenge record", "Challenges, planner responses, items for the auditor"],
  ["review.md", "QA review", "Check results, verdict and the sign-off block"],
];
function parseSignoff(md) {
  const block = (md || "").split("## Auditor sign-off")[1] || "";
  const out = {};
  for (const line of block.split("\n")) {
    const m = line.match(/^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/);
    if (m && !/^-+$/.test(m[1]) && m[2] && !/^-+$/.test(m[2])) out[m[1]] = m[2];
  }
  return out.Auditor ? out : null;
}

// ================================================================ RUN VIEW
const R = { run: null, tab: "log", events: [], file: null, verbose: false, filter: "all", registerMd: null };

async function viewRun(id, tab, file, token) {
  setNav("runs");
  if (!R.run || R.run.id !== id) { R.events = []; R.file = null; R.filter = "all"; R.registerMd = null; }
  if (file) R.file = file;
  app.innerHTML = `<div class="crumbs"><a href="#/runs">Audit runs</a> / …</div>${skel("40%", 28)}<div style="height:16px"></div>${skel("100%", 150)}`;
  try { R.run = await api(`/api/runs/${id}`); } catch (e) {
    app.innerHTML = empty("alert", "Run not found", esc(e.message), `<a class="btn sm" href="#/runs">All runs</a>`); return;
  }
  if (token !== routeToken) return;
  loadRuns().catch(() => {});
  R.tab = tab || (R.run.status === "awaiting_review" && !R.run.active ? "review" : R.run.status === "awaiting_signoff" && !R.run.active ? "signoff" : R.run.id === "sample" ? "files" : "log");
  app.innerHTML = `<div id="head"></div><div class="card" id="flowCard"></div><div class="tabs" id="tabs" role="tablist"></div><div id="pane"></div>`;
  await openStream(id);
  renderHead(); renderTabs(); renderPane();
}

function renderHead() {
  const r = R.run;
  const canStart = !r.read_only && !r.active && ["created", "ready", "failed", "interrupted"].includes(r.status);
  const label = { created: "Start run", ready: "Continue", failed: "Resume stage", interrupted: "Resume stage" }[r.status];
  const gate = !r.active && (r.status === "awaiting_review" || r.status === "awaiting_signoff");
  $("#head").innerHTML = `
    <div class="crumbs"><a href="#/runs">Audit runs</a> / ${esc(runName(r))}</div>
    <div class="run-head"><div><h1>${esc(runName(r))}</h1>
      <div class="meta">${statusPill(r)}<span>Model <b>${esc(r.model || "—")}</b></span><span>Cost <b class="num">${money(r)}</b></span>
      <span>Tokens <b class="num">${tokens(r.input_tokens)} in · ${tokens(r.output_tokens)} out</b></span><span class="mono">${esc(r.id)}</span></div></div>
      <div class="row">
        ${canStart ? `<button class="btn primary" id="startBtn">${I.play}${label}</button>` : ""}
        ${r.active ? `<button class="btn" id="stopBtn">${I.stop}Stop stage</button>` : ""}
        <a class="btn" href="/api/runs/${r.id}/download">${I.down}Download pack</a>
      </div></div>
    ${r.note ? `<div class="banner">${I.info}<div>${esc(r.note)}</div></div>` : ""}
    ${r.error ? `<div class="banner critical">${I.alert}<div><b>${r.status === "interrupted" ? "The stage was interrupted." : "The stage failed."}</b> ${canStart ? "Fix the cause (for example a different model or a valid key) and resume; the stage reruns from its start." : ""}<pre>${esc(r.error)}</pre></div></div>` : ""}
    ${gate ? `<div class="banner teal">${I.pen}<div><b>Your decision is needed.</b> ${r.status === "awaiting_review" ? "Review the proposed risks and decide what is in scope. Audit planning starts when you record your decisions." : "The agent team has finished and the QA checks have run. Review the pack and sign it off or return it."}</div>
      <button class="btn primary sm" id="gateBtn">${r.status === "awaiting_review" ? "Review risks" : "Review & sign off"}</button></div>` : ""}`;
  $("#startBtn") && ($("#startBtn").onclick = () => withKey(async () => {
    $("#startBtn").disabled = true;
    try { await startStage(r.id); R.tab = "log"; await refreshRun(); } catch (e) { alert(e.message); $("#startBtn").disabled = false; }
  }));
  $("#stopBtn") && ($("#stopBtn").onclick = async () => {
    if (!confirm("Stop this stage? It can be resumed later; it will rerun from its start.")) return;
    await api(`/api/runs/${r.id}/stop`, { method: "POST" });
  });
  $("#gateBtn") && ($("#gateBtn").onclick = () => setTab(r.status === "awaiting_review" ? "review" : "signoff"));
  $("#flowCard").innerHTML = `<div class="card-h"><div><h3>Workflow</h3><p>Select a stage to see its outputs or decisions</p></div><span class="small muted">${doneCount(r)} of 5 stages complete</span></div>${flowHtml(r, { interactive: true, events: R.events })}`;
  $("#flowCard").onclick = (e) => {
    const b = e.target.closest("button[data-node]:not(:disabled)");
    if (!b) return;
    const s = STAGES[+b.dataset.node];
    if (s.tab) return setTab(s.tab);
    const st = nodeState(r, +b.dataset.node)[0];
    if (st === "done" && s.out) { R.file = s.out; return setTab("files"); }
    R.filter = s.filter; setTab("log");
  };
}

async function refreshRun() {
  R.run = await api(`/api/runs/${R.run.id}`);
  renderHead(); renderTabs(); renderPane();
  if (R.run.active && !stream) openStream(R.run.id);
}
function setTab(t) { R.tab = t; renderTabs(); renderPane(); }

function renderTabs() {
  const r = R.run;
  const tabs = [["log", "Activity"], ["files", "Outputs"], ["review", "Risk review", r.status === "awaiting_review" && !r.active], ["signoff", "QA & sign-off", r.status === "awaiting_signoff" && !r.active]];
  $("#tabs").innerHTML = tabs.map(([k, l, flag]) => `<button role="tab" aria-selected="${R.tab === k}" data-tab="${k}" class="${R.tab === k ? "on" : ""}">${l}${flag ? '<span class="pill critical">Action needed</span>' : ""}</button>`).join("");
  $("#tabs").onclick = (e) => { const b = e.target.closest("button[data-tab]"); if (b) setTab(b.dataset.tab); };
}
function renderPane() { ({ log: paneLog, files: paneFiles, review: paneReview, signoff: paneSignoff })[R.tab](); }

// ---------------------------------------------------------------- activity
function tagStages(events) {
  let cur = "other";
  for (const e of events) {
    if (e.kind === "stage" && e.state === "started") cur = e.stage;
    if (!e._stage) e._stage = e.kind === "gate" ? "gate" : cur;
  }
}
const visible = (e) => R.filter === "all" || e._stage === R.filter;

function paneLog() {
  if (R.run.id === "sample") {
    $("#pane").innerHTML = `<div class="card">${empty("info", "No activity log for the sample", "The sample run was made in Claude Code, which did not record an event log in this format. Open <b>Outputs</b> for every file, or start a run to watch the agents live.", `<button class="btn sm" id="toFiles">Open outputs</button>`)}</div>`;
    $("#toFiles").onclick = () => setTab("files");
    return;
  }
  tagStages(R.events);
  const chips = [["all", "All"], ["stage1", "Rules extraction"], ["stage2", "Spend analysis"], ["stage4", "Audit planning"], ["gate", "Auditor"]];
  $("#pane").innerHTML = `<div class="toolbar"><div class="chips" role="group" aria-label="Filter by stage">${chips.map(([k, l]) => `<button class="chip ${R.filter === k ? "on" : ""}" data-f="${k}" aria-pressed="${R.filter === k}">${l}</button>`).join("")}</div>
    <div class="row"><label><input type="checkbox" id="verbose" ${R.verbose ? "checked" : ""}> Show tool results</label><span id="evcount" class="num"></span></div></div>
    <div class="card log" id="log" aria-live="polite"></div>`;
  $(".chips").onclick = (e) => { const b = e.target.closest("[data-f]"); if (b) { R.filter = b.dataset.f; paneLog(); } };
  $("#verbose").onchange = (e) => { R.verbose = e.target.checked; paneLog(); };
  const log = $("#log");
  const html = R.events.filter(visible).map(evHtml).join("");
  log.innerHTML = html || empty("inbox", R.events.length ? "Nothing in this stage yet" : "No activity yet", R.run.status === "created" ? "Start the run to see the agents work here." : "Events appear here as the agents work.");
  $("#evcount").textContent = `${R.events.length} events`;
  log.scrollTop = log.scrollHeight;
}

function evHtml(e) {
  const t = `<time>${clock(e.ts)}</time><span class="ag" title="${esc(e.agent)}">${esc(e.agent === "main" ? "extract-rules" : e.agent)}</span>`;
  switch (e.kind) {
    case "stage": {
      const s = { stage1: "Rules extraction", stage2: "Spend analysis", stage4: "Audit planning" }[e.stage] || e.stage;
      const txt = e.state === "started" ? `${s} started · ${e.provider} · ${e.model}` : e.state === "done" ? `${s} completed · $${(e.cost_usd || 0).toFixed(2)}` : `${s} ${e.state}: ${e.error || ""}`;
      return `<div class="ev stage ${e.state === "failed" ? "fail" : ""}">${t}<div class="body">${esc(txt)}</div></div>`;
    }
    case "agent_start": return `<div class="ev">${t}<div class="body">Agent started · tools: ${esc((e.tools || []).join(", "))}<details><summary>Task</summary><pre>${esc(e.task)}</pre></details></div></div>`;
    case "agent_done": return `<div class="ev msg">${t}<div class="body"><b>Report</b> <span class="muted">(${e.turns} turns)</span><pre>${esc(e.report)}</pre></div></div>`;
    case "message": return e.text ? `<div class="ev msg">${t}<div class="body">${esc(e.text)}</div></div>` : "";
    case "tool_call": return `<div class="ev">${t}<div class="body"><span class="tool">${esc(e.tool)}</span><span class="mono">${esc(shortArgs(e))}</span></div></div>`;
    case "tool_result": return R.verbose ? `<div class="ev">${t}<div class="body"><pre>${esc(e.result)}</pre></div></div>` : "";
    case "check": return `<div class="ev">${t}<div class="body"><span class="${e.passed ? "ok-ic" : "bad-ic"}">${e.passed ? "✓" : "✕"}</span> Check <b>${esc(e.check)}</b> ${e.passed ? "passed" : `failed (exit ${e.exit})`}<details><summary>Output</summary><pre>${esc(e.output)}</pre></details></div></div>`;
    case "team_message": return `<div class="ev team">${t}<div class="body"><span class="to">→ ${esc(e.to)}${e.relay ? " (relayed by lead)" : ""}</span><pre>${esc(e.body)}</pre></div></div>`;
    case "team_start": return `<div class="ev stage">${t}<div class="body">Agent team spawned: ${esc(e.members.join(", "))}</div></div>`;
    case "team_stop": return `<div class="ev stage">${t}<div class="body">Team stopped: ${esc(e.reason)}</div></div>`;
    case "gate": return `<div class="ev stage">${t}<div class="body">Auditor · ${esc(e.gate)}${e.decisions ? ": " + esc(Object.entries(e.decisions).map(([k, v]) => `${k} ${v}`).join(", ")) : e["Decision (SIGNED OFF / RETURNED)"] ? ": " + esc(e["Decision (SIGNED OFF / RETURNED)"]) : ""}</div></div>`;
    case "warning": return `<div class="ev fail">${t}<div class="body">${esc(e.text)}</div></div>`;
    case "run": return `<div class="ev">${t}<div class="body">Run ${esc(e.status)} (start point: ${esc(e.seed)})</div></div>`;
    default: return "";
  }
}
function shortArgs(e) {
  try { const a = JSON.parse(e.args); return a.command || a.file_path || a.pattern || (a.to ? `to ${a.to}` : e.args); } catch { return e.args; }
}

function addEvent(e) {
  R.events.push(e);
  tagStages(R.events);
  if (R.tab === "log" && $("#log") && visible(e)) {
    const log = $("#log");
    const atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
    if (log.querySelector(".empty")) log.innerHTML = "";
    log.insertAdjacentHTML("beforeend", evHtml(e));
    if (atEnd) log.scrollTop = log.scrollHeight;
  }
  if ($("#evcount")) $("#evcount").textContent = `${R.events.length} events`;
  if (e.kind === "agent_start" || e.kind === "agent_done") renderHead();
}

async function openStream(id) {
  if (stream) stream.close();
  stream = null;
  if (id === "sample") return;
  if (!R.run.active) {  // nothing running: read the log once instead of holding a stream open
    const { events } = await api(`/api/runs/${id}/log?after=${R.events.length}`);
    R.events.push(...events);
    return;
  }
  stream = new EventSource(`/api/runs/${id}/events?after=${R.events.length}`);
  stream.addEventListener("log", (m) => addEvent(JSON.parse(m.data)));
  stream.addEventListener("run", (m) => {
    const prev = R.run;
    R.run = JSON.parse(m.data);
    if (!R.run.active && stream) { stream.close(); stream = null; }
    renderHead();
    if (prev && (prev.status !== R.run.status || prev.active !== R.run.active)) {
      loadRuns().catch(() => {});
      if (R.run.status === "awaiting_review" && !R.run.active) setTab("review");
      else if (R.run.status === "awaiting_signoff" && !R.run.active) setTab("signoff");
      else { renderTabs(); if (R.tab !== "log") renderPane(); }
    }
  });
}

// ---------------------------------------------------------------- outputs
const GROUPS = [
  ["Audit pack", /^(planning-memo|risk-control-matrix|audit-program|challenges|review)\.md$/],
  ["Risk register", /^(risk-register\.md|auditor-comments\.md|risk-ratings\.json|risk-register\.state\.json)$/],
  ["Stage inputs", /^(rules|analytics|history)\.json$/],
  ["Samples", /^samples\//],
  ["Plan & figures", /^(audit-plan|pack-figures)\.json$/],
  ["Full analytics lists", /^analytics-full\//],
];
async function paneFiles() {
  $("#pane").innerHTML = `<div class="files"><div class="card flist" id="flist">${skel("100%", 240)}</div><div class="card viewer" id="viewer"><div class="vb">${skel("60%", 22)}</div></div></div>`;
  const { files } = await api(`/api/runs/${R.run.id}/files`);
  if (!files.length) {
    $("#pane").innerHTML = `<div class="card">${empty("doc", "No outputs yet", "Files appear here as each stage writes them: rules.json after rules extraction, the analytics and register after spend analysis, and the pack after audit planning.")}</div>`;
    return;
  }
  const used = new Set();
  let html = "";
  for (const [g, re] of [...GROUPS, ["Other", /.*/]]) {
    const fs = files.filter((f) => !used.has(f.path) && re.test(f.path));
    if (!fs.length) continue;
    fs.forEach((f) => used.add(f.path));
    html += `<div class="grp lbl">${g}</div>` + fs.map((f) => `<button data-p="${esc(f.path)}" title="${esc(f.path)}"><span>${esc(f.path.split("/").pop())}</span><small>${kb(f.size)}</small></button>`).join("");
  }
  $("#flist").innerHTML = html;
  $("#flist").onclick = (e) => { const b = e.target.closest("button[data-p]"); if (b) openFile(b.dataset.p); };
  const pick = (R.file && used.has(R.file) && R.file) || ["planning-memo.md", "risk-register.md", "rules.json"].find((p) => used.has(p)) || files[0].path;
  openFile(pick);
}

async function openFile(path) {
  R.file = path;
  $$("#flist button").forEach((b) => b.classList.toggle("on", b.dataset.p === path));
  const v = $("#viewer");
  v.innerHTML = `<div class="vh"><span>outputs/${esc(path)}</span></div><div class="vb">${skel("60%", 22)}<div style="height:12px"></div>${skel("100%", 200)}</div>`;
  let text;
  try { text = await fileText(R.run.id, path); } catch (e) { v.innerHTML = empty("alert", "Could not open the file", esc(e.message)); return; }
  const head = `<div class="vh"><span>outputs/${esc(path)}</span><a class="btn ghost sm" href="/api/runs/${R.run.id}/file?path=${encodeURIComponent(path)}" target="_blank" rel="noopener">Raw</a></div>`;
  let body;
  if (path.endsWith(".md")) body = `<div class="md">${DOMPurify.sanitize(marked.parse(text))}</div>`;
  else if (path.endsWith(".json")) { let t = text; try { t = JSON.stringify(JSON.parse(text), null, 2); } catch { /* truncated */ } body = `<pre class="raw">${esc(t)}</pre>`; }
  else if (path.endsWith(".csv")) body = csvTable(text);
  else body = `<pre class="raw">${esc(text)}</pre>`;
  v.innerHTML = head + `<div class="vb">${body}</div>`;
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
  const more = body.length >= max ? `<p class="small muted" style="margin-top:8px">First ${max} rows shown; download the pack for the full file.</p>` : "";
  return `<div style="overflow:auto"><table class="csv"><thead><tr>${(h || []).map((x) => `<th>${esc(x)}</th>`).join("")}</tr></thead><tbody>${body.slice(0, max).map((r) => `<tr>${r.map((x) => `<td>${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${more}`;
}

// ---------------------------------------------------------------- risk review (gate 1)
const dots = (n) => `<span class="dots" aria-hidden="true">${[1, 2, 3, 4, 5].map((k) => `<i class="${k <= n ? "on" : ""}"></i>`).join("")}</span>`;
const stripSig = (c) => (c || "").replace(/^[^,]+, \d{4}-\d{2}-\d{2}[:.]\s*/, "");

async function paneReview() {
  const r = R.run;
  $("#pane").innerHTML = `<div class="card summary">${[1, 2, 3, 4].map(() => `<div>${skel("50%", 11)}<div style="height:8px"></div>${skel("40%", 22)}</div>`).join("")}</div><div class="risks">${skel("100%", 120)}${skel("100%", 120)}</div>`;
  const [{ risks }, md] = await Promise.all([api(`/api/runs/${r.id}/risks`), R.registerMd ?? fileText(r.id, "risk-register.md").catch(() => "")]);
  R.registerMd = md;
  if (R.tab !== "review") return;
  if (!risks.length) {
    $("#pane").innerHTML = `<div class="card">${empty("shield", "No risk register yet", "The risk-assessor builds the register at the end of spend analysis. The run then pauses here for your decisions.")}</div>`;
    return;
  }
  const open = r.status === "awaiting_review" && !r.active && !r.read_only;
  const sections = registerSections(md || "");
  const list = risks.map((x) => ({ ...x, p: parseRating(x.rating) })).sort((a, b) => (b.p.score ?? -1) - (a.p.score ?? -1) || a.risk_id.localeCompare(b.risk_id));
  const high = list.filter((x) => isHighBand(x.p)).length;
  $("#pane").innerHTML = `
    <div class="card summary">
      <div><span class="lbl">Risks proposed</span><div class="v">${list.length}</div></div>
      <div><span class="lbl">Medium-High or above</span><div class="v">${high}</div></div>
      <div><span class="lbl">Decided</span><div class="v" id="decCount"></div><div class="progress"><i id="decBar"></i></div></div>
      <div><span class="lbl">Gate</span><div style="margin-top:8px">${open ? `<span class="pill critical"><span class="d"></span>Open: your decision</span>` : r.status === "awaiting_review" && r.active ? `<span class="pill teal run"><span class="d"></span>Applying decisions</span>` : `<span class="pill good"><span class="d"></span>Decisions applied</span>`}</div></div>
    </div>
    <div class="row" style="justify-content:space-between;margin-bottom:12px"><p class="small muted">Sorted by score. Ratings, scores and bands come from build_register.py using the council's matrix; the agent only judged and cited. ${open ? "Approve keeps a risk in scope as rated; Amend keeps it once changed (say what to change); Reject takes it out of scope (say why)." : ""}</p>
      <button class="btn ghost sm" id="openReg">${I.doc}Full register</button></div>
    <div class="risks">${list.map((x) => {
      const p = x.p;
      const sec = sections[x.risk_id];
      return `<article class="card risk ${p.sev}" data-id="${x.risk_id}"><span class="sev-bar" aria-hidden="true"></span><div class="risk-in"><div>
        <div class="risk-top"><span class="rid">${x.risk_id}</span><span class="pill ${p.sev}" data-tip="${esc(esc(p.band) + (/[†‡]/.test(p.band) ? "<br>† ‡ mark a conflict in the council's scoring method; see the register." : ""))}">${esc(p.short || "Not rated")}</span></div>
        <h3>${esc(x.title)}</h3>
        ${p.score != null ? `<div class="score"><span>Likelihood <b>${p.l}</b>${dots(p.l)}</span><span>Impact <b>${p.i}</b>${dots(p.i)}</span><span>Score <b>${p.score}</b><span class="muted">&nbsp;/ 25</span></span></div>` : `<div class="score"><span class="mono">${esc(x.rating)}</span></div>`}
        ${sec ? `<details class="evidence"><summary>Justification, evidence and proposed focus</summary><div class="md">${DOMPurify.sanitize(marked.parse(sec.replace(/^### .*\n/, "")))}</div></details>` : ""}
      </div><div class="decided">${open ? `
        <div class="seg" role="radiogroup" aria-label="Decision for ${x.risk_id}">${["APPROVE", "AMEND", "REJECT"].map((d) => `<label class="${d.toLowerCase()}"><input type="radio" name="d-${x.risk_id}" value="${d}" ${x.decision === d ? "checked" : ""}>${d}</label>`).join("")}</div>
        <textarea rows="2" aria-label="Comment for ${x.risk_id}" placeholder="Comment (required for Amend and Reject)">${esc(stripSig(x.comment))}</textarea>`
        : `<div><span class="pill ${x.decision === "APPROVE" ? "good" : x.decision === "AMEND" ? "warn" : x.decision ? "critical" : ""}">${esc(x.decision || "Undecided")}</span></div><p class="small muted">${esc(x.comment)}</p>${x.status ? `<p class="small muted">${esc(x.status)}</p>` : ""}`}
      </div></div></article>`;
    }).join("")}</div>
    ${open ? `<div class="card sticky-foot"><label class="field" style="width:280px;max-width:100%">Auditor name<input type="text" id="auditor" value="${esc(store.get("auditor"))}" autocomplete="name"></label>
      <div class="row"><span id="gmsg" class="inline-msg" role="status">Recording writes outputs/auditor-comments.md; the risk-assessor then builds the revision and the agent team starts planning.</span>
      <button class="btn primary" id="submitDec">${I.check}Record decisions & start planning</button></div></div>` : ""}`;
  const counter = () => {
    const n = open ? $$(".risk[data-id]").filter((el) => el.querySelector("input:checked")).length : list.filter((x) => x.decision).length;
    $("#decCount").innerHTML = `${n} <span class="muted" style="font-size:14px;font-weight:500">of ${list.length}</span>`;
    $("#decBar").style.width = `${(n / list.length) * 100}%`;
  };
  counter();
  $("#openReg").onclick = () => { R.file = "risk-register.md"; setTab("files"); };
  if (!open) return;
  $(".risks").onchange = counter;
  $("#submitDec").onclick = () => withKey(async () => {
    const msg = (t, c = "err") => { $("#gmsg").className = "inline-msg " + c; $("#gmsg").textContent = t; };
    const auditor = $("#auditor").value.trim();
    if (!auditor) { $("#auditor").focus(); return msg("Enter the auditor's name."); }
    const decisions = [];
    for (const el of $$(".risk[data-id]")) {
      const d = el.querySelector("input:checked")?.value;
      const comment = el.querySelector("textarea").value.trim();
      if (!d) { el.scrollIntoView({ behavior: "smooth", block: "center" }); return msg(`Decide ${el.dataset.id}.`); }
      if (d !== "APPROVE" && !comment) { el.querySelector("textarea").focus(); return msg(`${el.dataset.id}: ${d} needs a comment.`); }
      decisions.push({ risk_id: el.dataset.id, decision: d, comment });
    }
    store.set("auditor", auditor);
    $("#submitDec").disabled = true; msg("Recording decisions…", "");
    try {
      await api(`/api/runs/${r.id}/decisions`, { method: "POST", body: JSON.stringify({ auditor, decisions }) });
      msg("Starting audit planning…", "");
      await startStage(r.id);
      R.tab = "log"; R.filter = "all"; await refreshRun();
    } catch (e) { msg(e.message); $("#submitDec").disabled = false; }
  });
}

// ---------------------------------------------------------------- QA & sign-off (gate 2)
async function paneSignoff() {
  const r = R.run;
  $("#pane").innerHTML = `<div class="grid g-main"><div class="card card-b">${skel("40%", 22)}<div style="height:16px"></div>${skel("100%", 160)}</div><div class="card card-b">${skel("100%", 200)}</div></div>`;
  const files = (await api(`/api/runs/${r.id}/files`)).files.map((f) => f.path);
  if (R.tab !== "signoff") return;
  if (!files.includes("review.md")) {
    $("#pane").innerHTML = `<div class="card">${empty("shield", "QA has not run yet", "The qa-reviewer writes review.md at the end of audit planning, and the harness re-runs the QA scripts. Sign-off opens then.")}</div>`;
    return;
  }
  const review = await fileText(r.id, "review.md");
  const verdict = r.qa?.verdict || (/VERDICT: READY FOR SIGN-OFF/.test(review) ? "READY FOR SIGN-OFF" : "BLOCKED");
  const qaText = r.qa?.output || (review.match(/```text\n([\s\S]*?)```/) || [])[1] || "";
  const checks = [...qaText.matchAll(/^\|\s*(check_\w+)\s*\|\s*(PASS|FAIL)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|/gm)];
  const open = r.status === "awaiting_signoff" && !r.read_only && !r.active;
  const signed = r.signoff || parseSignoff(review);
  const dec = signed?.["Decision (SIGNED OFF / RETURNED)"];
  const pack = PACK.filter(([f]) => files.includes(f));
  $("#pane").innerHTML = `
    <div class="grid g-main">
      <div class="grid">
        <div class="card"><div class="card-h"><div><h3>QA verdict</h3><p>scripts/checks/run_checks.py, re-run by the harness after the team finished</p></div>${verdictStamp(verdict)}</div>
          ${checks.length ? `<div>${checks.map((m) => `<div class="check"><span class="${m[2] === "PASS" ? "ok-ic" : "bad-ic"}">${m[2] === "PASS" ? "✓" : "✕"}</span><b>${esc(m[1])}</b><span class="note">${esc(m[5].trim())}</span><span class="small muted num">${esc(m[3].trim())} checked · ${esc(m[4].trim())} failed</span></div>`).join("")}</div>` : ""}
          <div class="card-b" style="border-top:1px solid var(--line)"><details><summary>Full check output</summary><pre class="raw" style="margin-top:8px;white-space:pre;overflow-x:auto">${esc(qaText.trim())}</pre></details>
          ${r.qa?.team_done ? `<p class="small muted" style="margin-top:10px">Team: ${esc(Object.values(r.qa.team_done).join(" · "))}${r.qa.team_stop ? " — " + esc(r.qa.team_stop) : ""}</p>` : ""}</div></div>
        <div class="card"><div class="card-h"><div><h3>Audit pack</h3><p>Challenges marked “for the auditor” are listed at the end of the challenge record.</p></div><a class="btn sm" href="/api/runs/${r.id}/download">${I.down}Download .zip</a></div>
          <div>${pack.map(([f, n, d]) => `<button class="doc" data-p="${f}"><span class="ic">${I.doc}</span><span><b>${n}</b><small>${d}</small></span></button>`).join("")}</div></div>
      </div>
      <div class="card"><div class="card-h"><h3>Auditor sign-off</h3></div><div class="card-b grid">
        ${open ? `
          ${verdict !== "READY FOR SIGN-OFF" ? `<div class="banner critical">${I.alert}<div>The QA verdict is BLOCKED, so the pack can only be returned to the team.</div></div>` : ""}
          <p class="small muted">I have reviewed the planning memo, the risk-control matrix, the audit program, the sample files, the challenges and these QA results.</p>
          <label class="field">Auditor name<input type="text" id="sgName" value="${esc(store.get("auditor"))}" autocomplete="name"></label>
          <label class="field">Decision<select id="sgDec">${verdict === "READY FOR SIGN-OFF" ? "<option>SIGNED OFF</option>" : ""}<option>RETURNED</option></select></label>
          <label class="field">Comments<textarea id="sgCom" rows="4"></textarea></label>
          <div class="row"><button class="btn primary" id="sgGo">${I.check}Record sign-off</button></div>
          <div id="sgMsg" class="inline-msg" role="status">Recording writes the sign-off block in outputs/review.md.</div>`
          : dec ? `<div><span class="stamp ${dec === "SIGNED OFF" ? "good" : "critical"}">${dec === "SIGNED OFF" ? I.check : I.x}${esc(dec)}</span></div>
            <dl class="small" style="margin:0;display:grid;grid-template-columns:auto 1fr;gap:6px 16px"><dt class="muted">Auditor</dt><dd style="margin:0">${esc(signed.Auditor)}</dd><dt class="muted">Date</dt><dd style="margin:0">${esc(signed.Date)}</dd><dt class="muted">Comments</dt><dd style="margin:0">${esc(signed.Comments || "")}</dd></dl>`
          : `<p class="muted">Sign-off opens when the agent team has finished.</p>`}
      </div></div>
    </div>`;
  $$(".doc[data-p]").forEach((b) => (b.onclick = () => { R.file = b.dataset.p; setTab("files"); }));
  if (!open) return;
  $("#sgGo").onclick = async () => {
    const auditor = $("#sgName").value.trim();
    const m = $("#sgMsg");
    if (!auditor) { m.className = "inline-msg err"; m.textContent = "Enter the auditor's name."; $("#sgName").focus(); return; }
    store.set("auditor", auditor);
    $("#sgGo").disabled = true;
    try {
      await api(`/api/runs/${r.id}/signoff`, { method: "POST", body: JSON.stringify({ auditor, decision: $("#sgDec").value, comments: $("#sgCom").value }) });
      await refreshRun();
    } catch (e) { m.className = "inline-msg err"; m.textContent = e.message; $("#sgGo").disabled = false; }
  };
}

// ---------------------------------------------------------------- router
function route() {
  const token = ++routeToken;
  if (stream && !location.hash.startsWith("#/run/")) { stream.close(); stream = null; }
  const h = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  const m = h.match(/^\/run\/([A-Za-z0-9]+)(?:\/(log|files|review|signoff)(?:\/(.+))?)?$/);
  window.scrollTo(0, 0);
  const done = (p) => Promise.resolve(p).catch((e) => { if (token === routeToken) app.innerHTML = `<div class="card">${empty("alert", "Something went wrong", esc(e.message), `<button class="btn sm" onclick="route()">Try again</button>`)}</div>`; });
  if (m) return done(viewRun(m[1], m[2], m[3], token));
  if (h === "/runs") return done(viewRuns(token));
  if (h === "/new") return done(viewNew());
  if (h === "/review") return done(viewReviewIndex(token));
  if (h === "/reports") return done(viewReports(token));
  return done(viewOverview(token));
}

(async function init() {
  CONFIG = await api("/api/config");
  renderConn();
  $("#connBtn").onclick = () => openConn();
  window.addEventListener("hashchange", route);
  route();
})();
