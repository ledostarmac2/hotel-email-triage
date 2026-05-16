const state = {
  taxonomy: { categories: [], risk_flags: [], statuses: [] },
  emails: [],
  selectedId: null,
  filters: {
    category: "",
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
  syncStatus: document.getElementById("syncStatus"),
  refreshButton: document.getElementById("refreshButton"),
  processButton: document.getElementById("processButton"),
  mockButton: document.getElementById("mockButton"),
  toast: document.getElementById("toast"),
  categoryFilter: document.getElementById("categoryFilter"),
  statusFilter: document.getElementById("statusFilter"),
  riskFilter: document.getElementById("riskFilter"),
  searchInput: document.getElementById("searchInput"),
  replyModal: document.getElementById("replyModal"),
  replyModalMeta: document.getElementById("replyModalMeta"),
  replyBox: document.getElementById("replyBox"),
  closeReplyModal: document.getElementById("closeReplyModal"),
  copyReplyButton: document.getElementById("copyReplyButton"),
};

async function boot() {
  const [config, taxonomy] = await Promise.all([
    fetchJson("/api/config"),
    fetchJson("/api/taxonomy"),
  ]);
  state.taxonomy = taxonomy;
  els.mailboxLabel.textContent =
    config.outlook_desktop_export?.mailbox || config.shared_mailbox_email || "NYCWA_Reservations";
  fillSelect(els.categoryFilter, "All categories", taxonomy.categories);
  fillSelect(els.statusFilter, "All statuses", taxonomy.statuses);
  fillSelect(els.riskFilter, "All risks", taxonomy.risk_flags);
  bindEvents();
  await loadEmails();
}

function bindEvents() {
  els.refreshButton.addEventListener("click", () => runAction("Refreshing inbox", refreshInbox));
  els.processButton.addEventListener("click", () => runAction("Running local triage", processPending));
  els.mockButton.addEventListener("click", () => runAction("Loading demo inbox", seedMock));
  els.closeReplyModal.addEventListener("click", closeReplyModal);
  els.replyModal.addEventListener("click", (event) => {
    if (event.target === els.replyModal) closeReplyModal();
  });
  els.copyReplyButton.addEventListener("click", copyReply);

  for (const [key, element] of [
    ["category", els.categoryFilter],
    ["status", els.statusFilter],
    ["risk", els.riskFilter],
  ]) {
    element.addEventListener("change", () => {
      state.filters[key] = element.value;
      loadEmails();
    });
  }

  els.searchInput.addEventListener(
    "input",
    debounce(() => {
      state.filters.q = els.searchInput.value.trim();
      loadEmails();
    }, 180),
  );
}

async function refreshInbox() {
  setSyncStatus("Starting Outlook refresh");
  const result = await fetchJson("/api/outlook-desktop/export-inbox", { method: "POST" });
  if (result.launched_macro) {
    showToast("Outlook refresh started. The queue will update when the macro finishes.");
    await pollInboxImport();
    return;
  }
  showToast(`Inbox refreshed. ${result.exported_count || 0} saved.`);
  await loadEmails();
}

async function pollInboxImport() {
  const originalCount = state.emails.length;
  for (let attempt = 1; attempt <= 15; attempt += 1) {
    await sleep(2000);
    setSyncStatus(`Refreshing ${attempt}/15`);
    await loadEmails({ preserveSelection: true, quiet: true });
    if (state.emails.length !== originalCount || attempt >= 4) {
      setSyncStatus("Ready");
      return;
    }
  }
  setSyncStatus("Ready");
}

async function processPending() {
  const result = await fetchJson("/api/ai/process-pending?limit=100", { method: "POST" });
  showToast(`Local triage complete. ${result.analyzed_count} email${result.analyzed_count === 1 ? "" : "s"} updated.`);
  await loadEmails();
}

async function seedMock() {
  const result = await fetchJson("/api/mock/seed", { method: "POST" });
  showToast(`Demo inbox loaded. ${result.inserted_count} new, ${result.updated_count} updated.`);
  await loadEmails();
}

async function loadEmails(options = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state.filters)) {
    if (value) params.set(key, value);
  }
  params.set("limit", "500");
  const data = await fetchJson(`/api/emails?${params.toString()}`);
  state.emails = data.emails;
  renderMetrics();
  renderEmailList();

  if (state.selectedId && state.emails.some((email) => email.id === state.selectedId)) {
    await selectEmail(state.selectedId, false);
  } else if (!options.preserveSelection && state.emails.length > 0) {
    await selectEmail(state.emails[0].id, false);
  } else if (!state.emails.length) {
    state.selectedId = null;
    renderEmptyDetail();
  }
}

function renderMetrics() {
  const urgent = state.emails.filter((email) => urgency(email) >= 4).length;
  const immediate = state.emails.filter((email) => urgency(email) === 5).length;
  const missing = state.emails.filter((email) => (email.missing_information || []).length > 0).length;
  const manager = state.emails.filter((email) => (email.risk_flags || []).includes("Manager review required")).length;
  const metrics = [
    ["Open inbox", state.emails.length, "active messages"],
    ["Urgency 4-5", urgent, "work first"],
    ["Level 5", immediate, "immediate"],
    ["Missing info", missing, "needs reply"],
    ["Manager review", manager, "escalate"],
  ];
  els.metrics.innerHTML = metrics
    .map(
      ([label, value, caption]) => `
        <article class="metric">
          <span>${escapeHtml(label)}</span>
          <strong>${value}</strong>
          <small>${escapeHtml(caption)}</small>
        </article>
      `,
    )
    .join("");
}

function renderEmailList() {
  els.queueCount.textContent = `${state.emails.length} email${state.emails.length === 1 ? "" : "s"}`;
  if (!state.emails.length) {
    els.emailList.innerHTML = `<div class="empty-state">No emails match the current filters.</div>`;
    return;
  }
  els.emailList.innerHTML = state.emails.map(emailRow).join("");
  els.emailList.querySelectorAll(".email-row").forEach((row) => {
    row.addEventListener("click", () => selectEmail(Number(row.dataset.id), true));
  });
}

function emailRow(email) {
  const active = email.id === state.selectedId ? " active" : "";
  const score = urgency(email);
  const risks = (email.risk_flags || [])
    .slice(0, 2)
    .map((risk) => `<span class="badge risk">${escapeHtml(risk)}</span>`)
    .join("");
  return `
    <button class="email-row${active}" type="button" data-id="${email.id}">
      <span class="urgency-badge urgency-${score}">${score}</span>
      <span class="queue-copy">
        <span class="email-subject">${escapeHtml(email.subject || "(No subject)")}</span>
        <span class="queue-meta">${escapeHtml(email.sender_name || email.sender_email || "Unknown")} · ${formatDate(email.received_datetime)}</span>
        <span class="email-preview">${escapeHtml(email.ai_summary || email.body_preview || "")}</span>
        <span class="pill-stack">
          ${badge(email.category || "Unclassified")}
          ${risks}
        </span>
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
  const risks = (email.risk_flags || []).map((risk) => `<span class="badge risk">${escapeHtml(risk)}</span>`).join("");
  els.detailPanel.innerHTML = `
    <header class="detail-header">
      <div class="detail-title">
        <span class="detail-kicker">Urgency level ${urgency(email)} of 5</span>
        <h2>${escapeHtml(email.subject || "(No subject)")}</h2>
        <p>${escapeHtml(email.sender_name || email.sender_email || "Unknown sender")} · ${formatDate(email.received_datetime)}</p>
        <span class="pill-stack">
          ${badge(email.category || "Unclassified")}
          ${badge(email.status || "New", "status")}
          ${risks}
        </span>
      </div>
      <div class="detail-actions">
        <select id="statusSelect">${state.taxonomy.statuses
          .map((status) => `<option value="${escapeHtml(status)}" ${status === email.status ? "selected" : ""}>${escapeHtml(status)}</option>`)
          .join("")}</select>
        <button class="button primary" id="replyAiButton" type="button">AI Response</button>
      </div>
    </header>
    <div class="detail-body">
      <section class="insight-panel">
        ${section("Email Chain Summary", `<p>${escapeHtml(email.ai_summary || "Run local triage to summarize this email chain.")}</p>`)}
        ${section("Reservations Steps", actionList(email.internal_next_steps))}
        ${section("Missing Information", actionList(email.missing_information, "None noted."))}
      </section>
      <section class="source-panel">
        <div class="field-grid">
          ${field("Owner", email.recommended_department_owner || "Reservations")}
          ${field("Sentiment", email.guest_sentiment || "Neutral")}
          ${field("Importance", email.importance || "normal")}
          ${field("Attachments", email.has_attachments ? "Yes" : "No")}
        </div>
        ${section("Original Email", `<div class="email-body">${escapeHtml(email.body_text || email.body_content || email.body_preview || "")}</div>`)}
      </section>
    </div>
  `;

  document.getElementById("replyAiButton").addEventListener("click", () => generateAiReply(email.id));
  document.getElementById("statusSelect").addEventListener("change", async (event) => {
    await fetchJson(`/api/emails/${email.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: event.target.value }),
    });
    showToast("Local status updated.");
    await loadEmails({ preserveSelection: true });
  });
}

async function generateAiReply(emailId) {
  openReplyModal("Generating response...", "The app is checking this email only.");
  try {
    const data = await fetchJson(`/api/emails/${emailId}/analyze`, { method: "POST" });
    const reply = data.email.suggested_reply_draft || "No suggested response was returned.";
    openReplyModal(reply, `${data.email.analysis_engine || "AI"} · ${data.email.model || "model"}`);
    await loadEmails({ preserveSelection: true });
  } catch (error) {
    openReplyModal(error.message || "Could not generate a recommended response.", "AI response failed");
  }
}

function renderEmptyDetail() {
  els.detailPanel.innerHTML = `<div class="empty-state">Select an email to review.</div>`;
}

function section(title, content) {
  return `<section class="section"><h3>${escapeHtml(title)}</h3>${content}</section>`;
}

function field(label, value) {
  return `<div class="field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "")}</strong></div>`;
}

function actionList(items, emptyLabel = "No steps available.") {
  const values = Array.isArray(items) ? items : [];
  if (!values.length) return `<p class="muted">${escapeHtml(emptyLabel)}</p>`;
  return `<ol>${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>`;
}

function badge(text, extraClass = "") {
  return `<span class="badge ${extraClass}">${escapeHtml(text)}</span>`;
}

function fillSelect(element, label, values) {
  element.innerHTML =
    `<option value="">${escapeHtml(label)}</option>` +
    values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function openReplyModal(value, meta) {
  els.replyModalMeta.textContent = meta || "";
  els.replyBox.value = value || "";
  els.replyModal.hidden = false;
}

function closeReplyModal() {
  els.replyModal.hidden = true;
}

async function copyReply() {
  const value = els.replyBox.value || "";
  try {
    await navigator.clipboard.writeText(value);
  } catch (error) {
    els.replyBox.focus();
    els.replyBox.select();
    document.execCommand("copy");
  }
  showToast("Recommended response copied.");
}

async function runAction(label, action) {
  showToast(`${label}...`);
  try {
    await action();
  } catch (error) {
    setSyncStatus("Ready");
    showToast(error.message || "Action failed.");
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (error) {
    data = { detail: text };
  }
  if (!response.ok) {
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  return data;
}

function setSyncStatus(value) {
  els.syncStatus.textContent = value;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 4200);
}

function urgency(email) {
  return Number(email.urgency_score || email.priority_rank || 2);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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
