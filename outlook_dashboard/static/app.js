const state = {
  taxonomy: { categories: [], risk_flags: [], statuses: [], department_owners: [], contact_types: [] },
  emails: [],
  selectedId: null,
  currentView: "inbox",
  user: null,
  config: {},
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
  updateBanner: document.getElementById("updateBanner"),
  updateBannerText: document.getElementById("updateBannerText"),
  updateBannerLink: document.getElementById("updateBannerLink"),
  dismissUpdateBanner: document.getElementById("dismissUpdateBanner"),
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
  checkForUpdate();

  // Show Admin nav for admins
  if (me.user.role === "admin") {
    const adminBtn = document.getElementById("adminNavBtn");
    if (adminBtn) adminBtn.hidden = false;
  }

  const [config, taxonomy] = await Promise.all([
    fetchJson("/api/config"),
    fetchJson("/api/taxonomy"),
  ]);
  state.config = config;
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
  els.dismissUpdateBanner?.addEventListener("click", () => {
    const version = els.updateBanner?.dataset.version || "";
    if (version) localStorage.setItem(`rr_update_dismissed_${version}`, "1");
    if (els.updateBanner) els.updateBanner.hidden = true;
  });

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

async function checkForUpdate() {
  try {
    const data = await fetchJson("/api/update-available");
    if (!data.available || !data.version || !els.updateBanner) return;
    if (localStorage.getItem(`rr_update_dismissed_${data.version}`) === "1") return;
    els.updateBanner.dataset.version = data.version;
    els.updateBannerText.textContent = `ReplyRight v${data.version} is available`;
    els.updateBannerLink.href = data.url || "#";
    els.updateBanner.hidden = false;
  } catch {
    // Update checks should never interrupt inbox work.
  }
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
  if (els.refreshButton) els.refreshButton.disabled = true;
  let elapsed = 0;
  setSyncStatus("Connecting to Outlook…");
  const timer = setInterval(() => {
    elapsed++;
    setSyncStatus(`Importing from Outlook… ${elapsed}s`);
  }, 1000);
  try {
    const result = await fetchJson("/api/outlook-desktop/export-inbox", { method: "POST" });
    clearInterval(timer);
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
    const count = result.fetched_count || result.exported_count || 0;
    showToast(`Inbox refreshed. ${count} messages loaded.`);
    await loadEmails();
    setSyncStatus("Ready");
  } finally {
    clearInterval(timer);
    if (els.refreshButton) els.refreshButton.disabled = false;
  }
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
  const categoryValue = document.getElementById("feedbackCategory").value;
  const contactValue = document.getElementById("feedbackContact").value;
  const sentimentValue = document.getElementById("feedbackSentiment").value;
  const statusValue = document.getElementById("feedbackStatus").value;
  const summaryRating = document.getElementById("feedbackSummaryRating").value;
  const replyRating = document.getElementById("feedbackReplyRating").value;
  if (!text) {
    showToast("Add a correction note first.");
    return;
  }
  const payload = { feedback_text: text };
  if (urgencyValue) payload.corrected_urgency = Number(urgencyValue);
  if (ownerValue) payload.corrected_owner = ownerValue;
  if (categoryValue) payload.corrected_category = categoryValue;
  if (contactValue) payload.corrected_contact_type = contactValue;
  if (sentimentValue) payload.corrected_sentiment = sentimentValue;
  if (statusValue) payload.corrected_status = statusValue;
  if (summaryRating) payload.summary_quality_rating = Number(summaryRating);
  if (replyRating) payload.reply_quality_rating = Number(replyRating);
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
  const categories = state.taxonomy.categories || [];
  const contacts = state.taxonomy.contact_types || [];
  const statuses = state.taxonomy.statuses || [];
  const sentiments = ["Positive", "Neutral", "Concerned", "Upset"];
  const urgencyOptions = [1, 2, 3, 4, 5]
    .map((score) => `<option value="${score}">Urgency ${score}</option>`)
    .join("");
  const ownerOptions = owners
    .map((owner) => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`)
    .join("");
  const categoryOptions = categories
    .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
    .join("");
  const contactOptions = contacts
    .map((contact) => `<option value="${escapeHtml(contact)}">${escapeHtml(contact)}</option>`)
    .join("");
  const statusOptions = statuses
    .map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(status)}</option>`)
    .join("");
  const sentimentOptions = sentiments
    .map((sentiment) => `<option value="${escapeHtml(sentiment)}">${escapeHtml(sentiment)}</option>`)
    .join("");
  const ratingOptions = [1, 2, 3, 4, 5]
    .map((score) => `<option value="${score}">${score}</option>`)
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
        <select id="feedbackCategory">
          <option value="">Keep category</option>
          ${categoryOptions}
        </select>
        <select id="feedbackContact">
          <option value="">Keep contact type</option>
          ${contactOptions}
        </select>
        <select id="feedbackSentiment">
          <option value="">Keep sentiment</option>
          ${sentimentOptions}
        </select>
        <select id="feedbackStatus">
          <option value="">Keep status</option>
          ${statusOptions}
        </select>
        <label class="rating-field">
          <span>Summary quality</span>
          <select id="feedbackSummaryRating">
            <option value="">No rating</option>
            ${ratingOptions}
          </select>
        </label>
        <label class="rating-field">
          <span>Reply quality</span>
          <select id="feedbackReplyRating">
            <option value="">No rating</option>
            ${ratingOptions}
          </select>
        </label>
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

  let data, users, trainingStatus, trainingExamples, dualLabeledStats;
  try {
    [data, users, trainingStatus, trainingExamples, dualLabeledStats] = await Promise.all([
      fetchJson("/api/admin/stats"),
      fetchJson("/api/auth/users"),
      fetchJson("/api/admin/training/status").catch(() => null),
      fetchJson("/api/admin/training/examples?limit=10").catch(() => null),
      fetchJson("/api/admin/training/dual-labeled-stats").catch(() => null),
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
      <td>${escapeHtml(r.status || "")}</td>
      <td>
        <div class="admin-action-row">
          <button class="button small secondary" type="button"
            data-rule-key="${escapeHtml(r.key)}"
            data-rule-status="rejected"
            data-rule-type="${escapeHtml(r.type || "")}"
            data-rule-pattern="${escapeHtml(r.pattern || "")}"
            data-rule-suggestion="${escapeHtml(r.suggestion || "")}">Reject</button>
          <button class="button small ghost" type="button"
            data-rule-key="${escapeHtml(r.key)}"
            data-rule-status="dismissed"
            data-rule-type="${escapeHtml(r.type || "")}"
            data-rule-pattern="${escapeHtml(r.pattern || "")}"
            data-rule-suggestion="${escapeHtml(r.suggestion || "")}">Dismiss</button>
        </div>
      </td>
    </tr>`
  ).join("");

  const ownerDrilldownRows = (data.misclassification_drilldowns?.owner_by_domain || []).map((r) =>
    `<tr>
      <td>${escapeHtml(r.sender_domain || "")}</td>
      <td>${escapeHtml(r.original_owner || "Unlabeled")}</td>
      <td>${escapeHtml(r.corrected_owner || "")}</td>
      <td><strong>${r.count}</strong></td>
    </tr>`
  ).join("");

  const urgencyDrilldownRows = (data.misclassification_drilldowns?.urgency || []).map((r) =>
    `<tr>
      <td>${escapeHtml(r.original_priority || "Unlabeled")}</td>
      <td>${escapeHtml(r.corrected_urgency || "")}</td>
      <td><strong>${r.count}</strong></td>
    </tr>`
  ).join("");

  const aiConfigRows = [
    ["OpenAI refresh", state.config.openai_configured, state.config.openai_model],
    ["Google AI Studio", state.config.google_ai_configured, state.config.google_ai_model],
    ["Claude suggestions", state.config.anthropic_configured, state.config.anthropic_model],
  ].map(([label, configured, model]) => `
    <div class="admin-engine-row">
      <span>${escapeHtml(label)}</span>
      <strong>${configured ? escapeHtml(model || "Configured") : "Off"}</strong>
    </div>
  `).join("");

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

  const auditRows = (data.audit_logs || []).map((r) =>
    `<tr>
      <td>${escapeHtml(formatDate(r.created_at))}</td>
      <td>${escapeHtml(r.actor_email || "system")}</td>
      <td>${escapeHtml(r.action || "")}</td>
      <td>${escapeHtml(r.entity_type || "")}</td>
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
          <h3>AI Configuration</h3>
          <div class="admin-engine">${aiConfigRows}</div>
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
          <h3>Misclassification Drilldowns</h3>
          <div class="admin-split">
            <div>
              ${ownerDrilldownRows ? `<table class="admin-table"><thead><tr><th>Sender Domain</th><th>Original</th><th>Corrected</th><th>Count</th></tr></thead><tbody>${ownerDrilldownRows}</tbody></table>` : "<p class='muted'>No owner corrections yet.</p>"}
            </div>
            <div>
              ${urgencyDrilldownRows ? `<table class="admin-table"><thead><tr><th>Original Priority</th><th>Corrected</th><th>Count</th></tr></thead><tbody>${urgencyDrilldownRows}</tbody></table>` : "<p class='muted'>No urgency corrections yet.</p>"}
            </div>
          </div>
        </section>

        <section class="admin-card admin-card--wide">
          <h3>Suggested Rules</h3>
          ${ruleRows ? `<table class="admin-table"><thead><tr><th>Pattern</th><th>Suggestion</th><th>Corrections</th><th>Confidence</th><th>Status</th><th>Actions</th></tr></thead><tbody>${ruleRows}</tbody></table>` : "<p class='muted'>No rule candidates yet.</p>"}
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

        <section class="admin-card admin-card--wide" id="trainingPipelineCard">
          <h3>Training Data Pipeline</h3>
          <p class="muted" style="margin-bottom:12px;">
            Exports completed emails (PII-redacted) to Supabase as labeled training examples.
            Default run uses existing labels — zero AI cost.
            Enable <em>Refine</em> to re-label heuristic-only emails with Claude.
          </p>
          ${trainingStatus ? `
          <div class="admin-overview" style="margin-bottom:16px;">
            <article class="metric"><span>Uploaded</span><strong>${trainingStatus.uploaded}</strong><small>to Supabase</small></article>
            <article class="metric"><span>Pending</span><strong>${trainingStatus.pending}</strong><small>completed emails</small></article>
            <article class="metric"><span>Skipped</span><strong>${trainingStatus.skipped}</strong><small>too short</small></article>
            <article class="metric"><span>Failed</span><strong>${trainingStatus.failed}</strong><small>upload errors</small></article>
          </div>` : "<p class='muted'>Training status unavailable.</p>"}
          <div class="admin-invite-row" style="flex-wrap:wrap;gap:8px;">
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;">
              Batch size:
              <input type="number" id="trainingBatchSize" value="10" min="1" max="50" style="width:60px;padding:4px 8px;" />
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;">
              <input type="checkbox" id="trainingRefine" />
              Refine with Claude (uses AI credits)
            </label>
            <button class="button primary" id="trainingRunBtn" onclick="adminRunTrainingPipeline()">
              Run Pipeline
            </button>
            <button class="button secondary" id="classifierTrainBtn" onclick="adminTrainClassifier()" title="Train local scikit-learn models from uploaded examples (≥20 required)">
              Train Classifier
            </button>
          </div>
          <div id="trainingRunResult" style="margin-top:12px;"></div>
        </section>

        <section class="admin-card" id="dualLabeledCard">
          <h3>Dual-Labeled This Week</h3>
          ${(() => {
            if (!dualLabeledStats || dualLabeledStats.error) {
              return `<p class="muted">${dualLabeledStats?.error ? escapeHtml(dualLabeledStats.error) : "Unavailable."}</p>`;
            }
            const thisWeek = dualLabeledStats.this_week ?? 0;
            const weeks = dualLabeledStats.weeks ?? [0, 0, 0, 0];
            const maxVal = Math.max(...weeks, 1);
            const barWidth = 18;
            const barGap = 6;
            const chartH = 40;
            const bars = weeks.map((v, i) => {
              const h = Math.max(3, Math.round((v / maxVal) * chartH));
              const x = i * (barWidth + barGap);
              const isCurrent = i === weeks.length - 1;
              return `<rect x="${x}" y="${chartH - h}" width="${barWidth}" height="${h}" rx="3"
                fill="${isCurrent ? "var(--accent)" : "#c7d9f5"}" />`;
            }).join("");
            const svgW = weeks.length * (barWidth + barGap) - barGap;
            return `
              <div class="admin-overview" style="margin-bottom:16px;">
                <article class="metric">
                  <span>Dual-labeled</span>
                  <strong>${thisWeek}</strong>
                  <small>this week</small>
                </article>
                <article class="metric">
                  <span>Total labeled</span>
                  <strong>${weeks.reduce((a, b) => a + b, 0)}</strong>
                  <small>last 4 weeks</small>
                </article>
              </div>
              <svg width="${svgW}" height="${chartH}" style="display:block;overflow:visible;" aria-label="4-week sparkline">
                ${bars}
              </svg>
              <p class="muted" style="margin-top:8px;font-size:11px;">← 4 weeks ago &nbsp;·&nbsp; this week →</p>`;
          })()}
        </section>

        <section class="admin-card admin-card--wide" id="humanReviewCard">
          <h3>Human Review Queue</h3>
          <p class="muted" style="margin-bottom:12px;">Unreviewed training examples from Supabase. Check labels and mark correct ones as reviewed to build a high-quality training set.</p>
          ${(trainingExamples?.examples?.length) ? `
          <table class="admin-table">
            <thead><tr><th>Domain</th><th>Subject tokens</th><th>Urgency</th><th>Owner</th><th>Engine</th><th>Action</th></tr></thead>
            <tbody>${(trainingExamples.examples || []).map((ex) => `
              <tr>
                <td>${escapeHtml(ex.sender_domain || "—")}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(ex.subject_tokens || "")}">${escapeHtml(ex.subject_tokens || "—")}</td>
                <td>${ex.label_urgency ?? "—"}</td>
                <td>${escapeHtml(ex.label_owner || "—")}</td>
                <td>${escapeHtml(ex.labeling_engine || "—")}</td>
                <td><button class="button small secondary" data-review-id="${escapeHtml(ex.id)}" onclick="adminMarkReviewed('${escapeHtml(ex.id)}', this)">Mark Reviewed</button></td>
              </tr>`).join("")}
            </tbody>
          </table>` : `<p class="muted">${trainingExamples?.error ? escapeHtml(trainingExamples.error) : "No unreviewed examples. Run the training pipeline first."}</p>`}
        </section>

        <section class="admin-card admin-card--wide">
          <h3>Audit Log</h3>
          ${auditRows ? `<table class="admin-table"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th></tr></thead><tbody>${auditRows}</tbody></table>` : "<p class='muted'>No audit events yet.</p>"}
        </section>
      </div>
    </div>
  `;
  bindAdminRuleButtons();
}

function bindAdminRuleButtons() {
  document.querySelectorAll("[data-rule-key][data-rule-status]").forEach((button) => {
    if (button.dataset.bound === "true") return;
    button.addEventListener("click", async () => {
      const status = button.dataset.ruleStatus;
      const key = button.dataset.ruleKey;
      if (!key || !status) return;
      if (!confirm(`${status === "dismissed" ? "Dismiss" : "Reject"} this rule candidate?`)) return;
      try {
        await fetchJson("/api/rule-candidates/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            key,
            status,
            type: button.dataset.ruleType || "",
            pattern: button.dataset.rulePattern || "",
            suggestion: button.dataset.ruleSuggestion || "",
          }),
        });
        showToast(`Rule candidate ${status}.`);
        renderAdminView();
      } catch (err) {
        showToast(err.message || "Rule update failed.", "error");
      }
    });
    button.dataset.bound = "true";
  });
}

async function adminRunTrainingPipeline() {
  const btn = document.getElementById("trainingRunBtn");
  const resultEl = document.getElementById("trainingRunResult");
  const batchSize = parseInt(document.getElementById("trainingBatchSize")?.value || "10", 10);
  const refine = document.getElementById("trainingRefine")?.checked || false;
  if (refine && !confirm("Refine mode calls Claude for each heuristic email and uses AI credits. Continue?")) return;
  if (btn) { btn.disabled = true; btn.textContent = "Running…"; }
  if (resultEl) resultEl.innerHTML = "";
  try {
    const result = await fetchJson(
      `/api/admin/training/run?batch_size=${batchSize}&refine=${refine}`,
      { method: "POST" }
    );
    if (resultEl) {
      resultEl.innerHTML = `
        <div class="toast-success" style="padding:10px 14px;border-radius:6px;background:var(--success-bg,#ecfdf5);color:var(--success-text,#065f46);font-size:13px;">
          Processed <strong>${result.processed}</strong> emails —
          <strong>${result.uploaded}</strong> uploaded,
          <strong>${result.skipped}</strong> skipped,
          <strong>${result.failed}</strong> failed.
        </div>`;
    }
    showToast(`Training pipeline: ${result.uploaded} uploaded, ${result.skipped} skipped.`);
    renderAdminView();
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<p class="error-msg">${escapeHtml(err.message || "Pipeline failed.")}</p>`;
    showToast(err.message || "Training pipeline failed.", "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Run Pipeline"; }
  }
}

async function adminTrainClassifier() {
  const btn = document.getElementById("classifierTrainBtn");
  const resultEl = document.getElementById("trainingRunResult");
  if (btn) { btn.disabled = true; btn.textContent = "Training…"; }
  try {
    const result = await fetchJson("/api/admin/classifier/train", { method: "POST" });
    const msg = result.trained
      ? `Classifier trained on <strong>${result.examples}</strong> examples — targets: ${(result.targets || []).join(", ")}.`
      : `Not enough data: ${result.reason || "need more examples"}`;
    if (resultEl) {
      resultEl.innerHTML = `<div style="padding:10px 14px;border-radius:6px;background:${result.trained ? "var(--success-bg,#ecfdf5)" : "var(--muted-bg,#f3f4f6)"};font-size:13px;">${msg}</div>`;
    }
    showToast(result.trained ? `Classifier trained on ${result.examples} examples.` : (result.reason || "Not enough training data."));
  } catch (err) {
    if (resultEl) resultEl.innerHTML = `<p class="error-msg">${escapeHtml(err.message || "Training failed.")}</p>`;
    showToast(err.message || "Classifier training failed.", "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Train Classifier"; }
  }
}

async function adminMarkReviewed(id, btn) {
  if (!id) return;
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  try {
    await fetchJson(`/api/admin/training/examples/${encodeURIComponent(id)}/review`, { method: "PATCH" });
    showToast("Marked as reviewed.");
    const row = btn?.closest("tr");
    if (row) row.remove();
  } catch (err) {
    showToast(err.message || "Mark reviewed failed.", "error");
    if (btn) { btn.disabled = false; btn.textContent = "Mark Reviewed"; }
  }
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
