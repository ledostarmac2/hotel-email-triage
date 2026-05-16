const state = {
  taxonomy: { categories: [], risk_flags: [], statuses: [], department_owners: [], contact_types: [] },
  emails: [],
  selectedId: null,
  currentView: "inbox",
  user: null,
  filters: {
    category: "",
    status: "",
    risk: "",
    q: "",
  },
};

const els = {
  mailboxLabel: document.getElementById("mailboxLabel"),
  topbarTitle: document.querySelector(".topbar h1"),
  topbarSubtitle: document.querySelector(".topbar p"),
  workspace: document.querySelector(".workspace"),
  metrics: document.getElementById("metrics"),
  emailList: document.getElementById("emailList"),
  detailPanel: document.getElementById("detailPanel"),
  queueCount: document.getElementById("queueCount"),
  syncStatus: document.getElementById("syncStatus"),
  refreshButton: document.getElementById("refreshButton"),
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

const INBOX_WORKSPACE_HTML = els.workspace ? els.workspace.innerHTML : "";

async function boot() {
  // Auth check — redirect to login if not authenticated
  let me;
  try {
    me = await fetchJson("/api/auth/me");
  } catch {
    window.location.href = "/login";
    return;
  }
  state.user = me.user;

  // Show user email in sidebar
  const userEmailEl = document.getElementById("currentUserEmail");
  if (userEmailEl) userEmailEl.textContent = me.user.email;

  // Show Admin nav for admins
  if (me.user.role === "admin") {
    const adminBtn = document.getElementById("adminNavBtn");
    if (adminBtn) adminBtn.hidden = false;
  }

  const [config, taxonomy] = await Promise.all([
    fetchJson("/api/config"),
    fetchJson("/api/taxonomy"),
  ]);
  state.taxonomy = taxonomy;
  els.mailboxLabel.textContent =
    config.outlook_desktop_export?.mailbox || config.shared_mailbox_email || "NYCWA_Reservations";
  cacheWorkspaceElements();
  fillFilterSelects();
  bindEvents();
  bindWorkspaceEvents();
  await loadEmails();
}

function bindEvents() {
  els.refreshButton?.addEventListener("click", () => runAction("Refreshing inbox", refreshInbox));
  els.closeReplyModal.addEventListener("click", closeReplyModal);
  els.replyModal.addEventListener("click", (event) => {
    if (event.target === els.replyModal) closeReplyModal();
  });
  els.copyReplyButton.addEventListener("click", copyReply);

  document.getElementById("logoutBtn")?.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  });

  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.currentView = btn.dataset.view;
      state.selectedId = null;
      if (state.currentView === "admin") {
        renderAdminView();
      } else {
        renderInboxShell();
        renderMetrics();
        renderEmailList();
        renderEmptyDetail();
      }
    });
  });
}

function bindWorkspaceEvents() {
  for (const [key, element] of [
    ["category", els.categoryFilter],
    ["status", els.statusFilter],
    ["risk", els.riskFilter],
  ]) {
    if (!element || element.dataset.bound === "true") continue;
    element.addEventListener("change", () => {
      state.filters[key] = element.value;
      loadEmails();
    });
    element.dataset.bound = "true";
  }

  if (!els.searchInput || els.searchInput.dataset.bound === "true") return;
  els.searchInput.addEventListener(
    "input",
    debounce(() => {
      state.filters.q = els.searchInput.value.trim();
      loadEmails();
    }, 180),
  );
  els.searchInput.dataset.bound = "true";
}

function cacheWorkspaceElements() {
  els.emailList = document.getElementById("emailList");
  els.detailPanel = document.getElementById("detailPanel");
  els.queueCount = document.getElementById("queueCount");
  els.syncStatus = document.getElementById("syncStatus");
  els.categoryFilter = document.getElementById("categoryFilter");
  els.statusFilter = document.getElementById("statusFilter");
  els.riskFilter = document.getElementById("riskFilter");
  els.searchInput = document.getElementById("searchInput");
}

function fillFilterSelects() {
  if (!els.categoryFilter || !els.statusFilter || !els.riskFilter) return;
  fillSelect(els.categoryFilter, "All categories", state.taxonomy.categories);
  fillSelect(els.statusFilter, "All statuses", state.taxonomy.statuses);
  fillSelect(els.riskFilter, "All risks", state.taxonomy.risk_flags);
  els.categoryFilter.value = state.filters.category;
  els.statusFilter.value = state.filters.status;
  els.riskFilter.value = state.filters.risk;
  if (els.searchInput) els.searchInput.value = state.filters.q;
}

function renderInboxShell() {
  if (!els.workspace) return;
  els.workspace.classList.remove("workspace--admin");
  if (!document.getElementById("emailList")) {
    els.workspace.innerHTML = INBOX_WORKSPACE_HTML;
  }
  cacheWorkspaceElements();
  fillFilterSelects();
  bindWorkspaceEvents();
  if (els.topbarTitle) els.topbarTitle.textContent = "Inbox Triage";
  if (els.topbarSubtitle) {
    els.topbarSubtitle.textContent = "Ranked by urgency, ready for the right reservations response.";
  }
  if (els.refreshButton) els.refreshButton.hidden = false;
  if (els.metrics) els.metrics.hidden = false;
}

function renderAdminShell() {
  if (!els.workspace) return;
  els.workspace.classList.add("workspace--admin");
  if (els.topbarTitle) els.topbarTitle.textContent = "Admin";
  if (els.topbarSubtitle) {
    els.topbarSubtitle.textContent = "Review learning, users, confidence, and suggested rules.";
  }
  if (els.refreshButton) els.refreshButton.hidden = true;
  if (els.metrics) els.metrics.hidden = true;
}

async function refreshInbox() {
  setSyncStatus("Starting Outlook refresh");
  const result = await fetchJson("/api/outlook-desktop/export-inbox", { method: "POST" });
  if (result.launched_macro) {
    if (result.launch_method === "vbscript-com") {
      showToast("Inbox refreshed from Outlook.");
      await loadEmails();
      setSyncStatus("Ready");
      return;
    }
    showToast("Outlook refresh started. The queue will update when the macro finishes.");
    await pollInboxImport({ maxAttempts: 30 });
    return;
  }
  showToast(`Inbox refreshed. ${result.fetched_count || result.exported_count || 0} messages loaded.`);
  await loadEmails();
}

async function pollInboxImport(options = {}) {
  const maxAttempts = options.maxAttempts || 15;
  const originalCount = state.emails.length;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    await sleep(2000);
    setSyncStatus(`Refreshing ${attempt}/${maxAttempts}`);
    await loadEmails({ preserveSelection: true, quiet: true });
    if (state.emails.length !== originalCount) {
      setSyncStatus("Ready");
      return;
    }
  }
  setSyncStatus("Ready");
  await loadEmails({ preserveSelection: true, quiet: true });
}


async function loadEmails(options = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(state.filters)) {
    if (value) params.set(key, value);
  }
  params.set("limit", "500");
  const data = await fetchJson(`/api/emails?${params.toString()}`);
  state.emails = data.emails;
  if (state.currentView === "admin") return;
  renderInboxShell();
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
  const escalations = state.emails.filter((email) => (email.risk_flags || []).includes("Leadership review required")).length;
  const metrics = [
    ["Open inbox", state.emails.length, "conversations"],
    ["Urgency 4-5", urgent, "work first"],
    ["Level 5", immediate, "immediate"],
    ["Missing info", missing, "needs reply"],
    ["Escalations", escalations, "review"],
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

function viewEmails() {
  const all = state.emails;
  switch (state.currentView) {
    case "urgent": return all.filter((e) => urgency(e) >= 4);
    case "vip":    return all.filter((e) => (e.importance || "").toLowerCase() === "high" || (e.risk_flags || []).includes("VIP"));
    case "missing": return all.filter((e) => (e.missing_information || []).length > 0);
    default:       return all;
  }
}

function renderEmailList() {
  if (!els.queueCount || !els.emailList) return;
  const visible = viewEmails();
  els.queueCount.textContent = `${visible.length} conversation${visible.length === 1 ? "" : "s"}`;
  if (!visible.length) {
    els.emailList.innerHTML = `<div class="empty-state">No emails match the current filters.</div>`;
    return;
  }
  els.emailList.innerHTML = visible.map(emailRow).join("");
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
  const count = Number(email.conversation_email_count || 1);
  const countLabel = count > 1 ? ` - ${count} emails` : "";
  return `
    <button class="email-row${active}" type="button" data-id="${email.id}">
      <span class="urgency-badge urgency-${score}">${score}</span>
      <span class="queue-copy">
        <span class="email-subject">${escapeHtml(email.subject || "(No subject)")}</span>
        <span class="queue-meta">${escapeHtml(email.sender_name || email.sender_email || "Unknown")} · ${formatDate(email.received_datetime)}</span>
        ${countLabel ? `<span class="queue-meta">${escapeHtml(countLabel.slice(3))}</span>` : ""}
        <span class="email-preview">${escapeHtml(email.ai_summary || email.body_preview || "")}</span>
        <span class="pill-stack">
          ${badge(email.category || "Unclassified")}
          ${badge(email.contact_type || "Direct guest", "status")}
          ${risks}
        </span>
      </span>
    </button>
  `;
}

async function selectEmail(id, rerenderList) {
  if (state.currentView === "admin") return;
  state.selectedId = id;
  if (rerenderList) renderEmailList();
  const data = await fetchJson(`/api/emails/${id}`);
  renderDetail(data.email);
}

function renderDetail(email) {
  if (!els.detailPanel || state.currentView === "admin") return;
  const risks = (email.risk_flags || []).map((risk) => `<span class="badge risk">${escapeHtml(risk)}</span>`).join("");
  els.detailPanel.innerHTML = `
    <header class="detail-header">
      <div class="detail-title">
        <span class="detail-kicker">Urgency level ${urgency(email)} of 5${confidenceBadge(email)}</span>
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
        <button class="button primary" id="replyAiButton" type="button">AI Suggestion</button>
      </div>
    </header>
    <div class="detail-body">
      <section class="insight-panel">
        ${section("Email Chain Summary", `<p>${escapeHtml(email.ai_summary || "Run local triage to summarize this email chain.")}</p>`)}
        ${section("Reservations Steps", actionList(email.internal_next_steps))}
        ${section("Missing Information", actionList(email.missing_information, "None noted."))}
        ${feedbackForm(email)}
      </section>
      <section class="source-panel">
        <div class="field-grid">
          ${field("Owner", email.recommended_department_owner || "Reservations")}
          ${field("Contact", email.contact_type || "Direct guest")}
          ${field("Sentiment", email.guest_sentiment || "Neutral")}
          ${field("Importance", email.importance || "normal")}
          ${field("Attachments", email.has_attachments ? "Yes" : "No")}
        </div>
        ${section("Conversation", conversationMessages(email))}
      </section>
    </div>
  `;

  document.getElementById("replyAiButton").addEventListener("click", () => generateAiReply(email.id));
  document.getElementById("triageFeedbackButton").addEventListener("click", () => submitTriageFeedback(email.id));
  document.getElementById("statusSelect").addEventListener("change", async (event) => {
    await fetchJson(`/api/emails/${email.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: event.target.value }),
    });
    showToast("Local status updated.");
    await loadEmails({ preserveSelection: true });
  });
  resetDetailScroll();
}

async function submitTriageFeedback(emailId) {
  const text = document.getElementById("triageFeedbackText").value.trim();
  const urgencyValue = document.getElementById("feedbackUrgency").value;
  const ownerValue = document.getElementById("feedbackOwner").value;
  if (!text) {
    showToast("Add a correction note first.");
    return;
  }
  const payload = { feedback_text: text };
  if (urgencyValue) payload.corrected_urgency = Number(urgencyValue);
  if (ownerValue) payload.corrected_owner = ownerValue;
  await fetchJson(`/api/emails/${emailId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showToast("Triage feedback applied.");
  await loadEmails({ preserveSelection: true });
}

async function generateAiReply(emailId) {
  const btn = document.getElementById("replyAiButton");
  if (btn) { btn.setAttribute("aria-busy", "true"); btn.textContent = "Drafting…"; }
  openReplyModalLoading();
  try {
    const data = await fetchJson(`/api/emails/${emailId}/analyze`, { method: "POST" });
    const engine = data.email.analysis_engine || "";
    const isAi = engine === "claude" || engine === "openai";
    const meta = `${engine || "AI"} · ${data.email.model || ""}`;
    if (!isAi && data.email.analysis_error) {
      openReplyModal(
        `AI call failed — ${data.email.analysis_error}`,
        "error",
        "AI Unavailable",
      );
    } else {
      const reply = data.email.suggested_reply_draft || "No suggested response was returned.";
      openReplyModal(reply, meta, isAi ? "AI Recommended Response" : "Draft Response");
    }
    await loadEmails({ preserveSelection: true });
  } catch (error) {
    openReplyModal(error.message || "Could not generate a response.", "Error", "Error");
  } finally {
    if (btn) { btn.removeAttribute("aria-busy"); btn.textContent = "AI Suggestion"; }
  }
}

function openReplyModalLoading() {
  const loading = document.getElementById("replyLoading");
  const box = document.getElementById("replyBox");
  const footer = document.querySelector(".modal-actions");
  if (loading) loading.hidden = false;
  if (box) box.hidden = true;
  if (footer) footer.hidden = true;
  els.replyModalMeta.textContent = "Claude Opus 4.7 · reading thread";
  els.replyModal.hidden = false;
}

function renderEmptyDetail() {
  if (!els.detailPanel) return;
  els.detailPanel.innerHTML = `<div class="empty-state">Select an email to review.</div>`;
}

function confidenceBadge(email) {
  const score = Number(email.confidence_score || 0);
  if (!score) return "";
  const level = score >= 75 ? "high" : score >= 50 ? "medium" : "low";
  const reason = email.confidence_reason ? ` · ${email.confidence_reason}` : "";
  return ` <span class="confidence-badge confidence-${level}" title="${score}% confidence${reason}">${score}%</span>`;
}


function feedbackForm(email) {
  const owners = state.taxonomy.department_owners || [];
  const urgencyOptions = [1, 2, 3, 4, 5]
    .map((score) => `<option value="${score}">Urgency ${score}</option>`)
    .join("");
  const ownerOptions = owners
    .map((owner) => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`)
    .join("");
  const applied = email.feedback_applied
    ? `<p class="muted">Learning applied: ${escapeHtml(email.adaptive_explanation || "Feedback")}</p>`
    : "";
  return `
    <section class="feedback-box">
      <h3>Triage Feedback</h3>
      ${applied}
      <textarea id="triageFeedbackText" rows="4" placeholder="Correction notes"></textarea>
      <div class="feedback-controls">
        <select id="feedbackUrgency">
          <option value="">Keep urgency</option>
          ${urgencyOptions}
        </select>
        <select id="feedbackOwner">
          <option value="">Keep owner</option>
          ${ownerOptions}
        </select>
        <button class="button primary" id="triageFeedbackButton" type="button">Apply Feedback</button>
      </div>
    </section>
  `;
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

function conversationMessages(email) {
  const messages = Array.isArray(email.conversation_messages) && email.conversation_messages.length
    ? email.conversation_messages
    : [email];
  return messages
    .map((message, index) => `
      <article class="thread-message">
        <div class="thread-meta">
          <strong>${escapeHtml(message.sender_name || message.sender_email || "Unknown sender")}</strong>
          <span>${escapeHtml(formatDate(message.received_datetime))}${index === 0 ? " - latest" : ""}</span>
        </div>
        <div class="email-body">${escapeHtml(message.body_text || message.body_content || message.body_preview || "")}</div>
      </article>
    `)
    .join("");
}

function resetDetailScroll() {
  els.detailPanel.querySelectorAll(".insight-panel, .source-panel, .detail-body").forEach((panel) => {
    panel.scrollTop = 0;
  });
}

function badge(text, extraClass = "") {
  return `<span class="badge ${extraClass}">${escapeHtml(text)}</span>`;
}

function fillSelect(element, label, values) {
  element.innerHTML =
    `<option value="">${escapeHtml(label)}</option>` +
    values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
}

function openReplyModal(value, meta, title) {
  const loading = document.getElementById("replyLoading");
  const box = document.getElementById("replyBox");
  const footer = document.querySelector(".modal-actions");
  if (loading) loading.hidden = true;
  if (box) box.hidden = false;
  if (footer) footer.hidden = false;
  document.getElementById("replyModalTitle").textContent = title || "AI Recommended Response";
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
    showToast(error.message || "Action failed.", "error");
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
  if (els.syncStatus) els.syncStatus.textContent = value;
}

function showToast(message, type = "info") {
  window.clearTimeout(showToast.timer);
  els.toast.className = `toast ${type === "error" ? "error" : ""}`.trim();
  if (type === "error") {
    els.toast.innerHTML = `
      <span>${escapeHtml(message)}</span>
      <button class="toast-close" type="button" aria-label="Clear message">&times;</button>
    `;
    els.toast.querySelector(".toast-close").addEventListener("click", () => {
      els.toast.hidden = true;
    });
  } else {
    els.toast.textContent = message;
  }
  els.toast.hidden = false;
  if (type !== "error") {
    showToast.timer = window.setTimeout(() => {
      els.toast.hidden = true;
    }, 4200);
  }
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

// ── Admin Dashboard ───────────────────────────────────────────────────────────

async function renderAdminView() {
  if (state.currentView !== "admin") return;
  renderAdminShell();
  const workspace = els.workspace;
  if (!workspace) return;
  workspace.innerHTML = `<div class="admin-loading">Loading admin dashboard…</div>`;

  let data, users;
  try {
    [data, users] = await Promise.all([
      fetchJson("/api/admin/stats"),
      fetchJson("/api/auth/users"),
    ]);
  } catch (err) {
    if (state.currentView !== "admin") return;
    workspace.innerHTML = `<div class="empty-state">Failed to load admin data: ${escapeHtml(err.message)}</div>`;
    return;
  }
  if (state.currentView !== "admin") return;

  const ov = data.overview;
  const engineRows = (ov.engine_breakdown || []).map((r) =>
    `<div class="admin-engine-row"><span>${escapeHtml(r.analysis_engine)}</span><strong>${r.cnt}</strong></div>`
  ).join("");

  const correctionRows = (data.corrections || []).map((r) =>
    `<tr><td>${escapeHtml(r.type)}</td><td>${escapeHtml(r.label)}</td><td><strong>${r.count}</strong></td></tr>`
  ).join("");

  const lowConfRows = (data.low_confidence || []).map((r) =>
    `<tr>
      <td>${escapeHtml(r.subject || "(No subject)")}</td>
      <td>${escapeHtml(r.sender_name || r.sender_email || "")}</td>
      <td>${escapeHtml(r.category || "")}</td>
      <td>${r.confidence_score ?? "—"}%</td>
    </tr>`
  ).join("");

  const ruleRows = (data.rule_candidates || []).map((r) =>
    `<tr>
      <td>${escapeHtml(r.pattern)}</td>
      <td>${escapeHtml(r.suggestion)}</td>
      <td>${r.correction_count}</td>
      <td>${r.confidence}%</td>
    </tr>`
  ).join("");

  const userRows = (users.users || []).map((u) =>
    `<tr>
      <td>${escapeHtml(u.email)}</td>
      <td><span class="badge ${u.role === "admin" ? "" : "status"}">${escapeHtml(u.role)}</span></td>
      <td>${u.last_login ? formatDate(u.last_login) : "Never"}</td>
      <td>${u.invited_by_email ? escapeHtml(u.invited_by_email) : "—"}</td>
      <td>
        ${u.role !== "admin" ? `
          <button class="icon-button" onclick="adminResetPassword(${u.id}, '${escapeHtml(u.email)}')" title="Send reset link">🔑</button>
          <button class="icon-button" onclick="adminDeleteUser(${u.id}, '${escapeHtml(u.email)}')" title="Remove user">✕</button>
        ` : ""}
      </td>
    </tr>`
  ).join("");

  workspace.innerHTML = `
    <div class="admin-shell">
      <div class="admin-overview">
        <article class="metric"><span>Total Emails</span><strong>${ov.total_emails}</strong><small>imported</small></article>
        <article class="metric"><span>Feedback</span><strong>${ov.total_feedback}</strong><small>corrections</small></article>
        <article class="metric"><span>Users</span><strong>${ov.total_users}</strong><small>accounts</small></article>
        <article class="metric"><span>Low Confidence</span><strong>${ov.low_confidence_count}</strong><small>need review</small></article>
      </div>

      <div class="admin-grid">
        <section class="admin-card">
          <h3>Engine Performance</h3>
          <div class="admin-engine">${engineRows || "<p class='muted'>No analysis data yet.</p>"}</div>
        </section>

        <section class="admin-card">
          <h3>Most Corrected Classifications</h3>
          ${correctionRows ? `<table class="admin-table"><thead><tr><th>Type</th><th>Correction</th><th>Count</th></tr></thead><tbody>${correctionRows}</tbody></table>` : "<p class='muted'>No corrections yet.</p>"}
        </section>

        <section class="admin-card admin-card--wide">
          <h3>Low Confidence Analyses</h3>
          ${lowConfRows ? `<table class="admin-table"><thead><tr><th>Subject</th><th>Sender</th><th>Category</th><th>Confidence</th></tr></thead><tbody>${lowConfRows}</tbody></table>` : "<p class='muted'>No low-confidence emails.</p>"}
        </section>

        <section class="admin-card admin-card--wide">
          <h3>Suggested Rules</h3>
          ${ruleRows ? `<table class="admin-table"><thead><tr><th>Pattern</th><th>Suggestion</th><th>Corrections</th><th>Confidence</th></tr></thead><tbody>${ruleRows}</tbody></table>` : "<p class='muted'>No rule candidates yet.</p>"}
        </section>

        <section class="admin-card admin-card--wide">
          <h3>User Management</h3>
          <div class="admin-invite-row">
            <input type="email" id="inviteEmail" placeholder="New user email" />
            <button class="button primary" onclick="adminInviteUser()">Send Invite</button>
          </div>
          <table class="admin-table">
            <thead><tr><th>Email</th><th>Role</th><th>Last Login</th><th>Invited By</th><th>Actions</th></tr></thead>
            <tbody>${userRows}</tbody>
          </table>
        </section>
      </div>
    </div>
  `;
}

async function adminInviteUser() {
  const email = document.getElementById("inviteEmail")?.value.trim();
  if (!email) { showToast("Email is required."); return; }
  try {
    await fetchJson("/api/auth/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    showToast(`Invite sent to ${email} — they'll receive a link to set their password.`);
    document.getElementById("inviteEmail").value = "";
    renderAdminView();
  } catch (err) {
    showToast(err.message || "Invite failed.", "error");
  }
}

async function adminDeleteUser(userId, email) {
  if (!confirm(`Remove user ${email}? This cannot be undone.`)) return;
  try {
    await fetchJson(`/api/auth/users/${userId}`, { method: "DELETE" });
    showToast(`Removed ${email}.`);
    renderAdminView();
  } catch (err) {
    showToast(err.message || "Delete failed.", "error");
  }
}

async function adminResetPassword(userId, email) {
  if (!confirm(`Send a password reset link to ${email}?`)) return;
  try {
    await fetchJson("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    showToast(`Reset link sent to ${email}.`);
  } catch (err) {
    showToast(err.message || "Reset failed.", "error");
  }
}

boot().catch((error) => showToast(error.message || "Dashboard failed to load.", "error"));
