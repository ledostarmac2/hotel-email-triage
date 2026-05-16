const state = {
  taxonomy: { categories: [], risk_flags: [], statuses: [], department_owners: [], contact_types: [] },
  emails: [],
  selectedId: null,
  currentView: "inbox",
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
  els.closeReplyModal.addEventListener("click", closeReplyModal);
  els.replyModal.addEventListener("click", (event) => {
    if (event.target === els.replyModal) closeReplyModal();
  });
  els.copyReplyButton.addEventListener("click", copyReply);

  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.currentView = btn.dataset.view;
      state.selectedId = null;
      renderEmailList();
      renderEmptyDetail();
    });
  });

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
