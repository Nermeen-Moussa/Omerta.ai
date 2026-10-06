/* Omerta.ai investigation dashboard (Phase 16).
 * Consumes ONLY the Case Management API - no direct PostgreSQL, Neo4j,
 * LLM, or MCP access. Every view renders API data with explicit empty,
 * loading, and error states. Structural graph signals are labeled as
 * evidence, never as fraud determinations.
 */

const state = {
  page: 0,
  limit: 20,
  total: 0,
  filters: { status: "", severity: "", transaction_id: "" },
  currentCase: null,
  evidenceCache: [],
};

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (err) {
      /* keep status-code fallback */
    }
    throw new Error(`API ${detail}`);
  }
  return response.json();
}

function severityBadge(level) {
  return `<span class="badge ${level}">${level}</span>`;
}

function tierBadge(tier) {
  return `<span class="badge tier-${tier}">${tier}</span>`;
}

function fmtDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                            */
/* ------------------------------------------------------------------ */

async function loadDashboard() {
  const message = $("dashboard-message");
  message.textContent = "Loading cases…";
  message.classList.remove("error");
  const params = new URLSearchParams();
  if (state.filters.status) params.set("status", state.filters.status);
  if (state.filters.severity) params.set("severity", state.filters.severity);
  if (state.filters.transaction_id) params.set("transaction_id", state.filters.transaction_id);
  params.set("limit", state.limit);
  params.set("offset", state.page * state.limit);

  try {
    const data = await api(`/investigations?${params.toString()}`);
    state.total = data.total;
    renderCases(data.items);
    message.textContent = data.total === 0 ? "No cases match the current filters." : "";
  } catch (err) {
    renderCases([]);
    message.textContent = `Failed to load cases: ${err.message}`;
    message.classList.add("error");
  }
}

function renderCases(items) {
  const body = $("cases-body");
  body.innerHTML = "";
  if (items.length === 0) {
    body.innerHTML = '<tr><td colspan="7" class="msg">No cases yet.</td></tr>';
  }
  for (const item of items) {
    const row = document.createElement("tr");
    row.className = "clickable";
    row.innerHTML = `
      <td>${item.case_id}</td>
      <td>${item.transaction_id ?? "—"}</td>
      <td>${item.status}</td>
      <td>${severityBadge(item.severity)}</td>
      <td>${item.evidence_count}</td>
      <td>${item.audit_event_count}</td>
      <td>${fmtDate(item.created_at)}</td>`;
    row.addEventListener("click", () => openInvestigation(item.case_id));
    body.appendChild(row);
  }
  const from = state.total === 0 ? 0 : state.page * state.limit + 1;
  const to = Math.min(state.total, (state.page + 1) * state.limit);
  $("page-info").textContent = `${from}–${to} of ${state.total}`;
  $("btn-prev").disabled = state.page === 0;
  $("btn-next").disabled = to >= state.total;
}

async function loadSummary() {
  try {
    const data = await api("/investigations?limit=100");
    const items = data.items;
    $("stat-total").textContent = data.total;
    $("stat-review").textContent = items.filter((c) => c.status === "REVIEW").length;
    $("stat-high").textContent = items.filter((c) => c.severity === "HIGH").length;
    const dist = {};
    for (const item of items) dist[item.severity] = (dist[item.severity] ?? 0) + 1;
    $("risk-distribution").innerHTML = Object.entries(dist)
      .map(([level, count]) => `<span class="dist-bar badge ${level}">${level}: ${count}</span>`)
      .join("") || '<span class="msg">No severity data yet.</span>';
  } catch (err) {
    $("stat-total").textContent = "—";
  }
}

/* ------------------------------------------------------------------ */
/* Investigation detail                                                 */
/* ------------------------------------------------------------------ */

async function openInvestigation(caseId) {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $("view-investigation").classList.remove("hidden");
  $("inv-title").textContent = `Investigation ${caseId}`;
  const message = $("investigation-message");
  message.textContent = "Loading investigation…";
  message.classList.remove("error");
  state.currentCase = caseId;

  try {
    const detail = await api(`/investigations/${encodeURIComponent(caseId)}`);
    message.textContent = "";
    renderReport(detail);
    renderFindings(detail);
    state.evidenceCache = detail.evidence ?? [];
    renderEvidence(state.evidenceCache);
    await loadGraphSection(caseId);
    await loadAudit(caseId);
  } catch (err) {
    message.textContent = `Failed to load investigation: ${err.message}`;
    message.classList.add("error");
  }
}

function renderReport(detail) {
  const report = detail.report;
  const summary = $("report-summary");
  const meta = $("report-meta");
  const review = $("review-box");
  if (!report) {
    summary.textContent = "No report snapshot stored for this investigation.";
    meta.innerHTML = "";
    review.innerHTML = "";
    return;
  }
  summary.textContent = report.summary;
  meta.innerHTML = `
    <dt>Risk level</dt><dd>${severityBadge(report.risk_level)}</dd>
    <dt>Recommended action</dt><dd><strong>${report.recommended_action}</strong></dd>
    <dt>Confidence</dt><dd>${(report.confidence * 100).toFixed(0)}%</dd>
    <dt>Typologies</dt><dd>${report.typologies.join(", ") || "—"}</dd>
    <dt>LLM provider</dt><dd>${report.provenance?.llm_provider ?? "—"}</dd>
    <dt>Agent version</dt><dd>${report.provenance?.agent_version ?? "—"}</dd>
    <dt>Risk source</dt><dd>${report.provenance?.risk_source ?? "—"}</dd>`;
  review.innerHTML = `<strong>Human review required.</strong>
    Recommended action: ${report.recommended_action}. The analyst decides —
    this platform never freezes accounts, blocks transactions, or submits reports autonomously.`;
}

function renderFindings(detail) {
  const container = $("findings-list");
  container.innerHTML = "";
  const findings = detail.findings ?? [];
  if (findings.length === 0) {
    container.innerHTML = '<div class="msg">No findings stored.</div>';
    return;
  }
  for (const finding of findings) {
    const div = document.createElement("div");
    div.className = "finding";
    const links = (finding.evidence_ids ?? [])
      .map((id) => `<span class="ev-link" data-ev="${id}">${id}</span>`)
      .join("");
    div.innerHTML = `
      <div>${finding.finding}</div>
      <div class="finding-meta">confidence ${(finding.confidence * 100).toFixed(0)}%
      ${finding.category ? `· category ${finding.category}` : ""} · evidence: ${links}</div>`;
    container.appendChild(div);
  }
  container.querySelectorAll(".ev-link").forEach((el) => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-ev");
      document.getElementById("evidence-tier").value = "";
      renderEvidence(state.evidenceCache);
      const target = state.evidenceCache.find((e) => e.evidence_id === id);
      if (target) {
        $("evidence-body").querySelectorAll("tr").forEach((row) => {
          if (row.firstChild && row.firstChild.textContent === id) {
            row.style.outline = "1px solid var(--accent)";
            row.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        });
      }
    });
  });
}

function renderEvidence(rows) {
  const body = $("evidence-body");
  body.innerHTML = "";
  $("evidence-count").textContent = `(${rows.length} items)`;
  if (rows.length === 0) {
    body.innerHTML = '<tr><td colspan="6" class="msg">No evidence matches.</td></tr>';
    return;
  }
  for (const item of rows) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.evidence_id}</td>
      <td>${tierBadge(item.tier)}</td>
      <td>${item.category}</td>
      <td>${item.source}</td>
      <td>${item.producer}</td>
      <td>${item.description}</td>`;
    body.appendChild(row);
  }
}

async function loadGraphSection(caseId) {
  const view = $("graph-view");
  view.innerHTML = '<span class="msg">Loading graph signals…</span>';
  try {
    const data = await api(
      `/investigations/${encodeURIComponent(caseId)}/evidence?tier=STRUCTURAL_SIGNAL`
    );
    const items = data.items ?? [];
    view.innerHTML =
      '<div class="graph-note">Relationships below are structural evidence ' +
      "(shared devices/IPs, transaction paths). A connection alone never proves fraud.</div>";
    if (items.length === 0) {
      view.innerHTML += '<span class="msg">No structural signals collected.</span>';
      return;
    }
    for (const item of items) {
      const payload = item.data ?? {};
      const node = document.createElement("div");
      node.className = "graph-node";
      const section = payload.payload?.section ?? payload.section ?? item.reference;
      node.innerHTML = `<strong>${item.category}</strong><span class="rel">${section}</span>`;
      view.appendChild(node);
    }
  } catch (err) {
    view.innerHTML = `<span class="msg error">Graph signals unavailable: ${err.message}</span>`;
  }
}

async function loadAudit(caseId) {
  const list = $("audit-list");
  list.innerHTML = "<li>Loading…</li>";
  try {
    const events = await api(`/investigations/${encodeURIComponent(caseId)}/audit`);
    list.innerHTML = "";
    if (events.length === 0) {
      list.innerHTML = '<li>No audit events stored.</li>';
      return;
    }
    for (const event of events) {
      const li = document.createElement("li");
      li.innerHTML = `
        <span class="ev-type">${event.event_type}</span>
        <span class="ev-actor">${event.actor_type}</span>
        <span>${event.source}</span>
        <span class="ev-time">${fmtDate(event.created_at)}</span>`;
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li class="msg error">Audit trail unavailable: ${err.message}</li>`;
  }
}

/* ------------------------------------------------------------------ */
/* Wiring                                                               */
/* ------------------------------------------------------------------ */

function backToDashboard() {
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $("view-dashboard").classList.remove("hidden");
  loadSummary();
  loadDashboard();
}

function applyFilters() {
  state.filters = {
    status: $("filter-status").value,
    severity: $("filter-severity").value,
    transaction_id: $("filter-transaction").value.trim(),
  };
  state.page = 0;
  loadDashboard();
}

document.addEventListener("DOMContentLoaded", () => {
  $("btn-refresh").addEventListener("click", applyFilters);
  $("filter-status").addEventListener("change", applyFilters);
  $("filter-severity").addEventListener("change", applyFilters);
  $("filter-transaction").addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyFilters();
  });
  $("btn-prev").addEventListener("click", () => {
    if (state.page > 0) { state.page -= 1; loadDashboard(); }
  });
  $("btn-next").addEventListener("click", () => {
    if ((state.page + 1) * state.limit < state.total) { state.page += 1; loadDashboard(); }
  });
  $("btn-back").addEventListener("click", backToDashboard);
  $("evidence-tier").addEventListener("change", () => {
    const tier = $("evidence-tier").value;
    renderEvidence(tier ? state.evidenceCache.filter((e) => e.tier === tier) : state.evidenceCache);
  });
  loadSummary();
  loadDashboard();
});
