const state = {
  taxonomy: { categories: [], priorities: [], risk_flags: [], statuses: [] },
  emails: [],
  selectedId: null,
  filters: {
    category: "",
    priority: "",
    status: "",
    risk: "",
    q: "",
  },
};

const els = {
  mailboxLabel: document.getElementById("mailboxLabel"),
  metrics: document.getElementById("metrics"),
  emailList: document.getElementById("emailList"),
  detailPanel: document.getElementById("detailPanel"),
  queueCount: document.getElementById("queueCount"),
  syncButton: document.getElementById("syncButton"),
  processButton: document.getElementById("processButton"),
  mockButton: document.getElementById("mockButton"),
  toast: document.getElementById("toast"),
  categoryFilter: document.getElementById("categoryFilter"),
  priorityFilter: document.getElementById("priorityFilter"),
  statusFilter: document.getElementById("statusFilter"),
  riskFilter: document.getElementById("riskFilter"),
  searchInput: document.getElementById("searchInput"),
};

async function boot() {
  const [config, taxonomy] = await Promise.all([
    fetchJson("/api/config"),
    fetchJson("/api/taxonomy"),
  ]);
  state.taxonomy = taxonomy;
  els.mailboxLabel.textContent = config.shared_mailbox_email || "Shared Outlook inbox";
  fillSelect(els.categoryFilter, "All categories", taxonomy.categories);
  fillSelect(els.priorityFilter, "All priorities", taxonomy.priorities);
  fillSelect(els.statusFilter, "All statuses", taxonomy.statuses);
  fillSelect(els.riskFilter, "All risks", taxonomy.risk_flags);
  bindEvents();
  await loadEmails();
}

function bindEvents() {
  els.syncButton.addEventListener("click", () => runAction("Syncing Outlook", syncOutlook));
  els.processButton.addEventListener("click", () => runAction("Processing AI", processPending));
  els.mockButton.addEventListener("click", () => runAction("Loading mock emails", seedMock));
  for (const [key, element] of [
    ["category", els.categoryFilter],
    ["priority", els.priorityFilter],
    ["status", els.statusFilter],
    ["risk", els.riskFilter],
  ]) {
    element.addEventListener("change", () => {
      state.filters[key] = element.value;
      loadEmails();
    });
  }
  els.searchInput.addEventListener("input", debounce(() => {
    state.filters.q = els.searchInput.value.trim();
    loadEmails();
  }, 250));
}

async function syncOutlook() {
  const result = await fetchJson("/api/sync/outlook?mode=shared&top=25&analyze=true", { method: "POST" });
  showToast(`Outlook sync complete. ${result.inserted_count} new, ${result.updated_count} updated.`);
  await loadEmails();
}

async function processPending() {
  const result = await fetchJson("/api/ai/process-pending?limit=50", { method: "POST" });
  showToast(`AI processing complete. ${result.analyzed_count} email${result.analyzed_count === 1 ? "" : "s"} analyzed.`);
  await loadEmails();
}

async function seedMock() {
  const result = await fetchJson("/api/mock/seed", { method: "POST" });
  showToast(`Mock inbox loaded. ${result.inserted_count} new, ${result.updated_count} updated.`);
  await loadEmails();
}

async function loadEmails() {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state.filters)) {
    if (value) params.set(key, value);
  }
  const data = await fetchJson(`/api/emails?${params.toString()}`);
  state.emails = data.emails;
  renderMetrics();
  renderEmailList();
  if (state.selectedId && state.emails.some((email) => email.id === state.selectedId)) {
    await selectEmail(state.selectedId, false);
  } else if (state.emails.length > 0) {
    await selectEmail(state.emails[0].id, false);
  } else {
    state.selectedId = null;
    renderEmptyDetail();
  }
}

function renderMetrics() {
  const metrics = [
    ["Queue", state.emails.length],
    ["New", countBy("status", "New")],
    ["Immediate", countBy("priority_level", "Immediate")],
    ["High", countBy("priority_level", "High")],
    ["VIP Risk", state.emails.filter((email) => (email.risk_flags || []).includes("VIP")).length],
    ["Missing Info", state.emails.filter((email) => (email.missing_information || []).length > 0).length],
  ];
  els.metrics.innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><strong>${value}</strong></div>`)
    .join("");
}

function countBy(key, value) {
  return state.emails.filter((email) => email[key] === value).length;
}

function renderEmailList() {
  els.queueCount.textContent = `${state.emails.length} email${state.emails.length === 1 ? "" : "s"}`;
  if (state.emails.length === 0) {
    els.emailList.innerHTML = `<div class="empty-state">No emails match the current filters.</div>`;
    return;
  }
  els.emailList.innerHTML = state.emails.map((email) => emailRow(email)).join("");
  els.emailList.querySelectorAll(".email-row").forEach((row) => {
    row.addEventListener("click", () => selectEmail(Number(row.dataset.id), true));
  });
}

function emailRow(email) {
  const active = email.id === state.selectedId ? " active" : "";
  const risks = (email.risk_flags || []).slice(0, 2).map((risk) => `<span class="badge risk">${escapeHtml(risk)}</span>`).join("");
  return `
    <button class="email-row${active}" type="button" data-id="${email.id}">
      <span>
        <div class="email-subject">${escapeHtml(email.subject || "(No subject)")}</div>
        <div class="queue-meta">${escapeHtml(email.sender_name || email.sender_email || "Unknown")} · ${formatDate(email.received_datetime)}</div>
        <div class="email-preview">${escapeHtml(email.ai_summary || email.body_preview || "")}</div>
      </span>
      <span class="pill-stack">
        ${badge(email.priority_level || "Pending", `priority-${String(email.priority_level || "normal").toLowerCase()}`)}
        ${badge(email.status || "New", "status")}
        ${risks}
      </span>
    </button>
  `;
}

async function selectEmail(id, rerenderList) {
  state.selectedId = id;
  if (rerenderList) renderEmailList();
  const data = await fetchJson(`/api/emails/${id}`);
  renderDetail(data.email);
}

function renderDetail(email) {
  const riskBadges = (email.risk_flags || []).map((risk) => `<span class="badge risk">${escapeHtml(risk)}</span>`).join("");
  els.detailPanel.innerHTML = `
    <div class="detail-header">
      <div class="detail-title">
        <h2>${escapeHtml(email.subject || "(No subject)")}</h2>
        <span class="muted">${escapeHtml(email.sender_name || email.sender_email || "Unknown sender")} · ${formatDate(email.received_datetime)}</span>
        <span class="pill-stack">
          ${badge(email.category || "Unclassified")}
          ${badge(email.priority_level || "Pending", `priority-${String(email.priority_level || "normal").toLowerCase()}`)}
          ${badge(email.status || "New", "status")}
          ${riskBadges}
        </span>
      </div>
      <div class="detail-actions">
        <select id="statusSelect">${state.taxonomy.statuses.map((status) => `<option value="${escapeHtml(status)}" ${status === email.status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select>
        <button class="button secondary" id="analyzeButton" type="button">Analyze</button>
        <button class="button" id="copyReplyButton" type="button">Copy Reply</button>
      </div>
    </div>
    <div class="detail-body">
      <div class="analysis-column">
        ${section("AI Summary", `<p>${escapeHtml(email.ai_summary || "Not analyzed yet.")}</p>`)}
        ${section("Internal Next Steps", list(email.internal_next_steps))}
        ${section("Missing Information", list(email.missing_information))}
        ${section("Recommended Owner", `<p>${escapeHtml(email.recommended_department_owner || "Reservations")}</p>`)}
        ${section("Suggested Reply Draft", `<textarea class="reply-box" id="replyBox">${escapeHtml(email.suggested_reply_draft || "")}</textarea>`)}
      </div>
      <div class="original-column">
        <div class="field-grid">
          ${field("Sender", `${email.sender_name || ""} ${email.sender_email || ""}`)}
          ${field("From", `${email.from_name || ""} ${email.from_email || ""}`)}
          ${field("Conversation", email.conversation_id || "")}
          ${field("Importance", email.importance || "normal")}
          ${field("Attachments", email.has_attachments ? "Yes" : "No")}
          ${field("Source", `${email.source || "outlook"} / ${email.mailbox_mode || "shared"}`)}
        </div>
        ${section("Body Preview", `<p>${escapeHtml(email.body_preview || "")}</p>`)}
        ${section("Full Email Body", `<div class="email-body">${escapeHtml(email.body_text || email.body_content || "")}</div>`)}
      </div>
    </div>
  `;
  document.getElementById("copyReplyButton").addEventListener("click", copyReply);
  document.getElementById("analyzeButton").addEventListener("click", () => runAction("Analyzing email", async () => {
    await fetchJson(`/api/emails/${email.id}/analyze`, { method: "POST" });
    showToast("Email analysis refreshed.");
    await loadEmails();
  }));
  document.getElementById("statusSelect").addEventListener("change", async (event) => {
    await fetchJson(`/api/emails/${email.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: event.target.value }),
    });
    showToast("Local status updated.");
    await loadEmails();
  });
}

function renderEmptyDetail() {
  els.detailPanel.innerHTML = `<div class="empty-state">Select an email to review.</div>`;
}

function section(title, content) {
  return `<section class="section"><h3>${escapeHtml(title)}</h3>${content}</section>`;
}

function field(label, value) {
  return `<div class="field"><div class="field-label">${escapeHtml(label)}</div><div class="field-value">${escapeHtml(value || "")}</div></div>`;
}

function list(items) {
  const values = Array.isArray(items) ? items : [];
  if (!values.length) return `<p class="muted">None noted.</p>`;
  return `<ul>${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function badge(text, extraClass = "") {
  return `<span class="badge ${extraClass}">${escapeHtml(text)}</span>`;
}

function fillSelect(element, label, values) {
  element.innerHTML = `<option value="">${escapeHtml(label)}</option>` + values
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
    .join("");
}

async function copyReply() {
  const replyBox = document.getElementById("replyBox");
  const value = replyBox?.value || "";
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
    } else {
      fallbackCopy(replyBox);
    }
    showToast("Suggested reply copied.");
  } catch (error) {
    fallbackCopy(replyBox);
    showToast("Suggested reply copied.");
  }
}

function fallbackCopy(element) {
  if (!element) return;
  element.focus();
  element.select();
  document.execCommand("copy");
}

async function runAction(label, action) {
  showToast(`${label}...`);
  try {
    await action();
  } catch (error) {
    showToast(error.message || "Action failed.");
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  return data;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 4200);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}

boot().catch((error) => showToast(error.message || "Dashboard failed to load."));
