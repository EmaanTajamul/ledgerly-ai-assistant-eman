/* =====================================================================
   script.js — everything the page DOES.
   Flow: you click/type -> this file calls the backend with fetch()
         -> FastAPI (app.py) runs -> JSON comes back -> we draw it.
   Sections: 1 Settings | 2 Helpers | 3 Pages | 4 Chat | 5 Tool forms | 6 Approvals
   ===================================================================== */
"use strict";

/* ---------- 1. SETTINGS ---------- */
// "" means "same server that served this page" (FastAPI on port 8000).
const API_BASE = "";
const PAGES = { overview: "Overview", assistant: "AI Assistant", products: "Products",
                inventory: "Inventory", orders: "Orders", approvals: "Approvals", audit: "Audit Logs" };

// Little symbols shown next to each sidebar item.
const ICONS = { overview: "▦", assistant: "✳", products: "◇", inventory: "▤", orders: "☰", approvals: "◉", audit: "≡" };

/* ---------- 2. HELPERS ---------- */
const $ = selector => document.querySelector(selector);   // short for getElementById-style lookups

// SAFETY: turns < > & " ' into harmless text so data can never inject HTML.
function esc(text) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(text ?? "").replace(/[&<>"']/g, ch => map[ch]);
}

// Small message that appears bottom-right for 3 seconds.
function showToast(message) {
  const box = $("#toast");
  box.textContent = message;
  box.classList.add("on");
  setTimeout(() => box.classList.remove("on"), 3000);
}

// The ONE function that talks to the backend. Every request goes through here.
// It turns every kind of failure into an Error with a readable message.
async function callApi(path, options = {}) {
  let response;
  try {
    response = await fetch(API_BASE + path, { headers: { "Content-Type": "application/json" }, ...options });
  } catch {
    const e = new Error("Cannot reach the backend. Is the server running?");
    e.offline = true; throw e;                       // server off / network down
  }
  let data = null;
  try { data = await response.json(); } catch { /* body was not JSON */ }
  if (!response.ok) {                                // 4xx / 5xx
    const e = new Error(data && typeof data.detail === "string" ? data.detail : "The server returned an error.");
    e.status = response.status; throw e;
  }
  if (data === null) throw new Error("The server sent an invalid response.");
  return data;
}

function setConnection(ok) {                         // little pill in the top bar
  $("#conn").textContent = ok ? "Backend reachable" : "Backend unreachable";
  $("#conn").className = "pill " + (ok ? "ok" : "bad");
}

/* ---------- 3. PAGES (sidebar navigation) ---------- */
// Build the sidebar links from the PAGES list above.
$("#nav").innerHTML = Object.entries(PAGES)
  .map(([key, label]) => `<a href="#${key}" data-key="${key}"><span class="ic">${ICONS[key]}</span>${label}</a>`).join("");

// Show the page named in the URL (#assistant, #approvals ...) and hide the rest.
function showPage() {
  const key = PAGES[location.hash.slice(1)] ? location.hash.slice(1) : "overview";
  document.querySelectorAll("[data-view]").forEach(sec => sec.hidden = sec.dataset.view !== key);
  document.querySelectorAll("#nav a").forEach(a => {
    if (a.dataset.key === key) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  $("#title").textContent = PAGES[key];
  $("#crumb").textContent = PAGES[key];
  $("#side").classList.remove("open");               // close mobile menu
  if (key === "overview") loadOverview();
  if (key === "approvals") loadApprovals();
  if (key === "assistant") loadInbox();
}
window.addEventListener("hashchange", showPage);
$("#menu").onclick = () => $("#side").classList.toggle("open");

/* ---------- 4. CHAT ---------- */
const log = $("#log"), input = $("#q"), sendButton = $("#send");
let isBusy = false;                                  // true while waiting -> blocks double sends

// Dates for the suggested questions (the AI does not know today's date, so we give it dates).
const isoDate = d => d.toISOString().slice(0, 10);   // 2026-06-30
const daysAgo = (d, n) => new Date(d.getTime() - n * 86400000);
$("#d2").value = isoDate(new Date());
$("#d1").value = isoDate(daysAgo(new Date(), 29));

// Each suggestion: [button label, function that builds the question, optional "just fill the box"]
const SUGGESTIONS = [
  ["Show me the top-selling products.", p => `Show the top 10 products by revenue from ${p.start} to ${p.end}.`],
  ["Which products have low stock?",    () => "Which product variants are low on stock or out of stock? Use the stockout risk tool."],
  ["Summarize recent sales.",           p => `Summarize sales from ${p.start} to ${p.end}.`],
  ["Compare sales across periods.",     p => `Compare sales between ${p.prevStart} to ${p.prevEnd} (first period) and ${p.start} to ${p.end} (second period).`],
  ["Summarize refund activity.",        p => `Summarize refunds from ${p.start} to ${p.end}.`],
  ["Calculate a reorder quantity.",     () => "Calculate the reorder quantity for variant ID ", true],
];
$("#sugg").innerHTML = SUGGESTIONS.map((s, i) => `<button class="btn" data-i="${i}">${esc(s[0])}</button>`).join("");
$("#sugg").onclick = event => {
  const button = event.target.closest("button");
  if (!button) return;
  const s = SUGGESTIONS[button.dataset.i];
  const start = new Date($("#d1").value), end = new Date($("#d2").value);
  const length = Math.round((end - start) / 86400000) + 1;   // days in the chosen period
  const text = s[1]({ start: isoDate(start), end: isoDate(end),
                      prevStart: isoDate(daysAgo(start, length)), prevEnd: isoDate(daysAgo(start, 1)) });
  if (s[2]) { input.value = text; input.focus(); } else askAssistant(text);
};

// Add one chat bubble. kind = "user" | "bot" | "err". Returns the element.
function addMessage(kind, html) {
  const empty = log.querySelector(".empty");
  if (empty) empty.remove();
  const bubble = document.createElement("div");
  bubble.className = "msg " + kind;
  bubble.innerHTML = html;
  log.append(bubble);
  log.scrollTop = log.scrollHeight;                  // auto-scroll to newest
  return bubble;
}

// Turns the AI's markdown-style text into SAFE html (tables, headings, lists, bold).
function formatAnswer(text) {
  const lines = esc(text).split("\n");            // escape FIRST so nothing can inject HTML
  let html = "", openList = "", inTable = false, firstRow = true;
  const inline = t => t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  function closeBlocks() {
    if (openList) { html += "</" + openList + ">"; openList = ""; }
    if (inTable) { html += "</table>"; inTable = false; }
  }
  for (const line of lines) {
    let m;
    if (/^\s*-{3,}\s*$/.test(line)) { closeBlocks(); html += "<hr>"; }
    else if ((m = line.match(/^\s*#{1,6}\s+(.*)/))) { closeBlocks(); html += "<h4>" + inline(m[1]) + "</h4>"; }
    else if (/^\s*\|.*\|\s*$/.test(line)) {
      if (/^[\s|:-]+$/.test(line)) continue;      // skip the |:---| separator row
      if (!inTable) { closeBlocks(); html += "<table>"; inTable = true; firstRow = true; }
      const tag = firstRow ? "th" : "td"; firstRow = false;
      html += "<tr>" + line.trim().slice(1, -1).split("|").map(c => "<" + tag + ">" + inline(c.trim()) + "</" + tag + ">").join("") + "</tr>";
    }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (openList !== "ul") { closeBlocks(); html += "<ul>"; openList = "ul"; } html += "<li>" + inline(m[1]) + "</li>"; }
    else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (openList !== "ol") { closeBlocks(); html += "<ol>"; openList = "ol"; } html += "<li>" + inline(m[1]) + "</li>"; }
    else { closeBlocks(); if (line.trim()) html += "<p>" + inline(line) + "</p>"; }
  }
  closeBlocks();
  return html;
}

function friendlyError(e) {
  if (e.offline) return e.message;
  if (e.status === 422) return "The question was not valid. Make sure it is not empty.";
  if (e.status >= 500) return "The assistant could not finish. Possible causes: Gemini quota, a wrong API key, or a tool error. Check the PowerShell window running the server.";
  return e.message;
}

// MAIN CHAT FUNCTION: send a question to POST /chat and show the answer.
async function askAssistant(question) {
  question = (question || "").trim();
  if (!question || isBusy) return;                   // ignore empty or duplicate sends
  isBusy = true; sendButton.disabled = true;
  location.hash = "assistant";
  addMessage("user", esc(question));
  input.value = "";
  const reply = addMessage("bot", '<span class="dots"><span></span><span></span><span></span></span> Working…');
  const t0 = performance.now();                      // start the stopwatch for the trace panel
  try {
    const data = await callApi("/chat", { method: "POST", body: JSON.stringify({ question }) });
    if (typeof data.answer !== "string") throw new Error("The assistant returned an unexpected response.");
    reply.innerHTML = formatAnswer(data.answer) || "No answer was returned.";
    recordTrace(question, true, 200, t0, data.answer.length);
  } catch (e) {
    reply.className = "msg err";
    recordTrace(question, false, e.status || "network", t0, 0, friendlyError(e));
    reply.innerHTML = `<p><b>Request failed.</b> ${esc(friendlyError(e))}</p><button class="btn">Retry</button>`;
    input.value = question;                          // keep the user's text
    reply.querySelector("button").onclick = () => { reply.remove(); askAssistant(question); };
  } finally {
    isBusy = false; sendButton.disabled = false;
  }
}
sendButton.onclick = () => askAssistant(input.value);
input.addEventListener("keydown", event => {        // Enter sends, Shift+Enter = new line
  if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); askAssistant(input.value); }
});
log.innerHTML = `<div class="empty"><h2>What would you like to know?</h2><p>Ask about products, stock, orders, sales or refunds.<br>Proposals are never applied from chat.</p></div>`;

/* ---------- 5. TOOL FORMS (Products / Inventory / Orders) ---------- */
// The backend has NO product/order endpoints. These forms only write a question
// for you and send it to /chat. type "Proposal" = fill the box, do not auto-send.
// Fields are [name, label, input type, required?]
const TOOL_FORMS = {
  products: [
    { title: "Search products", type: "Read", fields: [["query", "Name keyword", "text", false], ["category", "Category (exact)", "text", false]],
      question: v => `Search products${v.query ? ` matching "${v.query}"` : ""}${v.category ? ` in category "${v.category}"` : ""}, limit 10.` },
    { title: "Product details", type: "Read", fields: [["id", "Product ID", "number", true]], question: v => `Get details for product ID ${v.id}.` },
    { title: "Product performance", type: "Read", fields: [["start", "Start", "date", true], ["end", "End", "date", true]],
      question: v => `Show product performance from ${v.start} to ${v.end}.` },
    { title: "Propose a discount", type: "Proposal", fields: [["id", "Product ID", "number", true], ["pct", "Discount %", "number", true], ["why", "Reason", "text", true]],
      question: v => `Propose a ${v.pct}% discount for product ID ${v.id}. Reason: ${v.why}` },
  ],
  inventory: [
    { title: "Stockout risk", type: "Read", fields: [["n", "How many variants", "number", false]], question: v => `List up to ${v.n || 20} variants at risk of stockout.` },
    { title: "Variant inventory", type: "Read", fields: [["id", "Variant ID", "number", true]], question: v => `Get inventory for variant ID ${v.id}.` },
    { title: "Reorder recommendation", type: "Recommendation", fields: [["id", "Variant ID", "number", true]], question: v => `Calculate the reorder quantity for variant ID ${v.id}.` },
    { title: "Propose inventory alert", type: "Proposal", fields: [["id", "Variant ID", "number", true]],
      question: v => `Propose an inventory alert for variant ID ${v.id}. (This saves a pending approval request if stock is low.)` },
  ],
  orders: [
    { title: "Look up an order", type: "Read", fields: [["id", "Order ID", "number", true]], question: v => `Get order ID ${v.id} with its items.` },
    { title: "Customer summary", type: "Read", fields: [["id", "Customer ID", "number", true]], question: v => `Give a summary of customer ID ${v.id}.` },
    { title: "Refund summary", type: "Read", fields: [["start", "Start", "date", true], ["end", "End", "date", true]], question: v => `Summarize refunds from ${v.start} to ${v.end}.` },
  ],
};

// Draw one card (form) per tool.
for (const page in TOOL_FORMS) {
  $("#l-" + page).innerHTML = TOOL_FORMS[page].map((tool, i) => `
    <form class="card" data-page="${page}" data-i="${i}">
      <h3>${esc(tool.title)} <span class="tag ${tool.type === "Proposal" ? "proposal" : ""}">${tool.type}</span></h3>
      ${tool.fields.map(([name, label, type, required]) =>
        `<label class="fld">${esc(label)}<input name="${name}" type="${type}" ${required ? "required" : ""}></label>`).join("")}
      <button class="btn ${tool.type === "Proposal" ? "" : "primary"}">${tool.type === "Proposal" ? "Draft in assistant" : "Ask assistant"}</button>
    </form>`).join("");
}

document.addEventListener("submit", event => {
  const form = event.target.closest("form[data-page]");
  if (!form) return;
  event.preventDefault();                            // stop the browser reloading the page
  const tool = TOOL_FORMS[form.dataset.page][form.dataset.i];
  const question = tool.question(Object.fromEntries(new FormData(form)));
  if (tool.type === "Proposal") {                    // proposals: user must press Send themselves
    location.hash = "assistant"; input.value = question; input.focus();
    showToast("Drafted. Review it, then press Send.");
  } else {
    askAssistant(question);
  }
});

/* ---------- 6. APPROVALS ---------- */
const STATUSES = ["pending", "approved", "rejected"];     // the only 3 values the backend accepts
let currentStatus = "pending";
const approvalCache = { pending: [], approved: [], rejected: [] };

// GET /approvals?status=...  -> { count, approvals: [...] }
async function fetchApprovals(status) {
  const data = await callApi("/approvals?status=" + status);
  if (!Array.isArray(data.approvals)) throw new Error("Unexpected response from /approvals.");
  approvalCache[status] = data.approvals;
  setConnection(true);
  return data.approvals;
}

function approvalsTable(list) {
  return `<table class="t"><thead><tr><th>ID</th><th>Action</th><th>Requested by</th><th>Requested</th><th>Status</th></tr></thead><tbody>
    ${list.map(r => `<tr class="row" tabindex="0" data-id="${esc(r.request_id)}">
      <td>#${esc(r.request_id)}</td><td>${esc(r.action)}</td><td>${esc(r.requester)}</td>
      <td>${esc(r.requested_at)}</td><td><span class="badge ${esc(r.status)}">${esc(r.status)}</span></td></tr>`).join("")}
  </tbody></table>`;
}
function makeRowsClickable(container) {
  container.querySelectorAll("tr.row").forEach(row => {
    row.onclick = () => showDetail(row.dataset.id);
    row.onkeydown = e => { if (e.key === "Enter") showDetail(row.dataset.id); };
  });
}

// Approvals page: tabs + list for the selected status.
$("#tabs").innerHTML = STATUSES.map(s => `<button role="tab" data-s="${s}">${s} <span id="n-${s}"></span></button>`).join("");
$("#tabs").onclick = e => { const b = e.target.closest("button"); if (b) { currentStatus = b.dataset.s; loadApprovals(); } };

async function loadApprovals() {
  document.querySelectorAll("#tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.s === currentStatus));
  const box = $("#aplist");
  box.innerHTML = '<p class="muted">Loading…</p>';
  try {
    const list = await fetchApprovals(currentStatus);
    STATUSES.forEach(s => { $("#n-" + s).textContent = "(" + approvalCache[s].length + ")"; });
    box.innerHTML = list.length ? approvalsTable(list) : `<p class="muted">No ${currentStatus} requests.</p>`;
    makeRowsClickable(box);
  } catch (e) {
    setConnection(!e.offline);
    box.innerHTML = `<p><b>Could not load approvals.</b> ${esc(e.message)}</p><button class="btn" id="retry">Retry</button>`;
    $("#retry").onclick = loadApprovals;
  }
}

// Overview page: the 3 counts and the latest pending requests (real data only).
async function loadOverview() {
  const results = await Promise.allSettled(STATUSES.map(fetchApprovals));
  setConnection(results.some(r => r.status === "fulfilled"));
  $("#counts").innerHTML = STATUSES.map((s, i) => results[i].status === "fulfilled"
    ? `<div class="card stat"><b>${approvalCache[s].length}</b>${s} approval requests</div>`
    : `<div class="card stat unavail"><b>—</b>${s}: unavailable</div>`).join("");
  const box = $("#ovPending");
  if (results[0].status === "fulfilled") {
    box.innerHTML = approvalCache.pending.length ? approvalsTable(approvalCache.pending.slice(0, 5)) : '<p class="muted">Nothing awaiting review.</p>';
    makeRowsClickable(box);
  } else {
    box.innerHTML = `<p class="muted">${esc(results[0].reason.message)}</p>`;
  }
}

// Detail pop-up for one request, with Approve / Reject if it is still pending.
const dialog = $("#dlg");
function showDetail(id) {
  const req = Object.values(approvalCache).flat().find(r => String(r.request_id) === String(id));
  if (!req) return;
  const payload = req.payload && typeof req.payload === "object" ? req.payload : { raw: req.payload };
  const pending = req.status === "pending";
  dialog.innerHTML = `
    <h3>Request #${esc(req.request_id)} <span class="badge ${esc(req.status)}">${esc(req.status)}</span></h3>
    <dl class="dl">
      <dt>Action</dt><dd>${esc(req.action)}</dd><dt>Requested by</dt><dd>${esc(req.requester)}</dd>
      <dt>Requested</dt><dd>${esc(req.requested_at)}</dd><dt>Reviewer</dt><dd>${esc(req.reviewer) || "—"}</dd>
      <dt>Reviewed</dt><dd>${esc(req.reviewed_at) || "—"}</dd>
      ${Object.entries(payload).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(typeof v === "object" ? JSON.stringify(v) : v)}</dd>`).join("")}
    </dl>
    <details><summary>Raw payload</summary><pre>${esc(JSON.stringify(req.payload, null, 2))}</pre></details>
    ${pending ? `<p class="muted">A decision records review status only. The proposed action is NOT executed.</p>
      <label class="fld">Reviewer name (required)<input id="reviewer"></label>` : ""}
    <p id="dlgError" role="alert" style="color:var(--bad)"></p>
    <div class="acts"><button class="btn" id="closeDlg">Close</button>
      ${pending ? '<button class="btn bad" data-d="rejected">Reject</button><button class="btn primary" data-d="approved">Approve</button>' : ""}</div>`;
  $("#closeDlg").onclick = () => dialog.close();
  if ($("#reviewer")) $("#reviewer").value = $("#whoami").value;   // prefill from the sidebar
  dialog.querySelectorAll("[data-d]").forEach(b => b.onclick = () => reviewRequest(req, b.dataset.d));
  dialog.showModal();
}

// Show a review error inside the pop-up if it is open, otherwise as a toast.
function reviewMessage(msg) { if (dialog.open) $("#dlgError").textContent = msg; else showToast(msg); }

// POST /approvals/{id}/review  with  { decision, reviewer }
async function reviewRequest(req, decision) {
  const reviewer = (($("#reviewer") || $("#whoami")).value || "").trim();
  if (!reviewer) { reviewMessage("Enter your name (sidebar: Reviewing as) before reviewing."); return; }
  const ok = confirm(`${decision === "approved" ? "Approve" : "Reject"} request #${req.request_id} as "${reviewer}"?\n\nThis records a decision only. No action will be executed.`);
  if (!ok) return;
  dialog.querySelectorAll("button").forEach(b => b.disabled = true);   // prevent double clicks
  try {
    const result = await callApi(`/approvals/${req.request_id}/review`, { method: "POST", body: JSON.stringify({ decision, reviewer }) });
    dialog.close();
    showToast(result.message || "Review saved.");
  } catch (e) {
    reviewMessage(e.message);                 // e.g. "Request is already approved" (409)
    dialog.querySelectorAll("button").forEach(b => b.disabled = false);
    if (e.status === 409 || e.status === 404) dialog.close();
  }
  if (location.hash === "#approvals") loadApprovals(); else loadOverview();
  loadInbox();
}

/* ---------- 7. EXTRAS: trace, recent questions, inbox, reviewer, theme ---------- */
const recentQuestions = [];

// Request trace: everything here is measured in the browser. /chat does not return tool names.
function recordTrace(question, ok, code, t0, chars, error) {
  const ms = Math.round(performance.now() - t0);
  $("#trace").innerHTML = `<dl class="dl">
    <dt>Status</dt><dd><span class="badge ${ok ? "approved" : "rejected"}">${ok ? "answered" : "failed"}</span></dd>
    <dt>HTTP</dt><dd>${esc(code)}</dd><dt>Time</dt><dd>${ms} ms</dd>
    <dt>Answer size</dt><dd>${chars} characters</dd><dt>Sent at</dt><dd>${new Date().toLocaleTimeString()}</dd>
    ${error ? `<dt>Error</dt><dd>${esc(error)}</dd>` : ""}</dl>
    <p class="muted">Measured in your browser. Tool names and arguments are not returned by /chat.</p>`;
  recentQuestions.unshift(question);
  if (recentQuestions.length > 6) recentQuestions.pop();
  $("#recent").innerHTML = recentQuestions.map((t, i) => `<button class="btn rq" data-i="${i}">${esc(t.length > 70 ? t.slice(0, 70) + "…" : t)}</button>`).join("");
}
$("#recent").onclick = e => { const b = e.target.closest("button"); if (b) askAssistant(recentQuestions[b.dataset.i]); };

// Pending-review inbox on the assistant page (real data from GET /approvals?status=pending).
async function loadInbox() {
  const box = $("#inbox");
  try {
    const list = await fetchApprovals("pending");
    $("#inboxN").textContent = list.length;
    box.innerHTML = list.length ? list.slice(0, 3).map(r => `<div class="inb"><b>${esc(r.action)}</b>
      <small>#${esc(r.request_id)} · ${esc(r.requester)}</small>
      <div class="acts2"><button class="btn primary" data-id="${esc(r.request_id)}" data-d="approved">Approve</button>
      <button class="btn" data-id="${esc(r.request_id)}" data-d="rejected">Reject</button>
      <button class="btn" data-id="${esc(r.request_id)}" data-d="view">Details</button></div></div>`).join("")
      : '<p class="muted">Nothing awaiting review.</p>';
  } catch (e) { box.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("#inbox").onclick = e => {
  const b = e.target.closest("button"); if (!b) return;
  const req = approvalCache.pending.find(r => String(r.request_id) === b.dataset.id);
  if (!req) return;
  if (b.dataset.d === "view") showDetail(req.request_id); else reviewRequest(req, b.dataset.d);
};

// Reviewer name and theme are remembered in the browser (harmless preferences, not secrets).
try {
  if (localStorage.getItem("reviewer")) $("#whoami").value = localStorage.getItem("reviewer");
  if (localStorage.getItem("theme") === "light") document.documentElement.dataset.theme = "light";
} catch { /* storage blocked: ignore */ }
$("#whoami").addEventListener("change", () => { try { localStorage.setItem("reviewer", $("#whoami").value.trim()); } catch {} });
$("#theme").onclick = () => {
  const light = document.documentElement.dataset.theme !== "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
  try { localStorage.setItem("theme", light ? "light" : "dark"); } catch {}
};

/* ---------- START ---------- */
showPage();
fetchApprovals("pending").catch(e => setConnection(!e.offline));   // sets the status pill on first load
