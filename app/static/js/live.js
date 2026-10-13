/**
 * static/js/live.js
 * Polls /api/complaints every 5 seconds and updates the table in place.
 *
 * Security notes:
 *  - Uses textContent (never innerHTML) with user-supplied data to prevent XSS.
 *  - Pauses when the tab is hidden (Page Visibility API).
 *  - Fails silently: shows "reconnecting..." indicator on fetch error.
 *  - Reads the API URL from a <meta> tag, not from hardcoded strings.
 */

(function () {
  "use strict";

  // ── Configuration ────────────────────────────────────────────────────────
  const POLL_INTERVAL_MS = 5000;
  const API_URL = (document.querySelector('meta[name="api-url"]') || {}).content || "/api/complaints";
  const IS_ADMIN = (document.querySelector('meta[name="is-admin"]') || {}).content === "true";

  // ── State ────────────────────────────────────────────────────────────────
  let pollTimer = null;
  let previousStatuses = {}; // complaint_id -> status, for change detection

  // ── DOM references ───────────────────────────────────────────────────────
  const indicator = document.getElementById("live-indicator");
  const liveLabel = document.getElementById("live-label");
  const liveTime  = document.getElementById("live-time");
  const tbody     = document.getElementById("complaints-tbody");
  const emptyState= document.getElementById("empty-state");

  // Admin stat tile references
  const statTotal     = document.getElementById("stat-total");
  const statPending   = document.getElementById("stat-pending");
  const statProgress  = document.getElementById("stat-inprogress");
  const statResolved  = document.getElementById("stat-resolved");

  if (!indicator || !tbody) return; // Not on a complaints page

  // ── Snapshot existing rows so we can detect changes on first poll ────────
  function snapshotCurrentStatuses() {
    const rows = tbody.querySelectorAll("tr[data-id]");
    rows.forEach(function (row) {
      const badge = row.querySelector(".status-badge");
      if (badge) {
        previousStatuses[row.dataset.id] = badge.textContent.trim();
      }
    });
  }

  // ── Build a status badge element safely using textContent ────────────────
  // Security: textContent prevents XSS from malicious status strings
  function buildStatusBadge(status) {
    const span = document.createElement("span");
    const cssClass = "status-" + status.toLowerCase().replace(/\s+/g, "-");
    span.className = "status-badge " + cssClass;
    span.textContent = status; // Security: textContent, not innerHTML
    return span;
  }

  // ── Build a category tag ──────────────────────────────────────────────────
  function buildCategoryTag(category) {
    const span = document.createElement("span");
    span.className = "category-tag";
    span.textContent = category; // Security: textContent
    return span;
  }

  // ── Build API URL with current page filters (if admin) ───────────────────
  function getApiUrl() {
    const url = new URL(API_URL, window.location.origin);
    if (IS_ADMIN) {
      const statusSelect = document.getElementById("status-filter");
      const catSelect = document.getElementById("cat-filter");
      if (statusSelect && statusSelect.value) {
        url.searchParams.set("status", statusSelect.value);
      }
      if (catSelect && catSelect.value) {
        url.searchParams.set("category", catSelect.value);
      }
    }
    return url.toString();
  }

  // ── Build action button safely for admin rows ────────────────────────────
  function buildActionCell(c) {
    const cell = document.createElement("td");
    cell.className = "action-cell";
    cell.dataset.actionFor = c.id;

    if (c.status === "Pending") {
      const btn = document.createElement("button");
      btn.className = "btn btn-sm btn-action";
      btn.dataset.id = c.id;
      btn.dataset.next = "In Progress";
      btn.textContent = "Mark In Progress";
      cell.appendChild(btn);
    } else if (c.status === "In Progress") {
      const btn = document.createElement("button");
      btn.className = "btn btn-sm btn-resolve";
      btn.dataset.id = c.id;
      btn.dataset.next = "Resolved";
      btn.textContent = "Mark Resolved";
      cell.appendChild(btn);
    } else {
      const span = document.createElement("span");
      span.className = "resolved-label";
      span.textContent = "✔ Resolved";
      cell.appendChild(span);
    }
    return cell;
  }

  // ── Build a table row from complaint data ────────────────────────────────
  function buildRow(c) {
    const tr = document.createElement("tr");
    tr.dataset.id = c.id;
    tr.dataset.status = c.status;

    // Helper to add a td with safe textContent
    function td(content, extraClass) {
      const cell = document.createElement("td");
      if (extraClass) cell.className = extraClass;
      if (typeof content === "string" || typeof content === "number") {
        cell.textContent = content; // Security: textContent
      } else {
        cell.appendChild(content); // Already a DOM node
      }
      return cell;
    }

    tr.appendChild(td(c.id));

    if (IS_ADMIN) {
      tr.appendChild(td(c.student_name || "—"));
    }

    tr.appendChild(td(c.title, "complaint-title"));
    tr.appendChild(td(buildCategoryTag(c.category)));
    tr.appendChild(td(buildStatusBadge(c.status)));

    const createdCell = document.createElement("td");
    createdCell.className = "date-cell";
    createdCell.textContent = (c.created_at || "").slice(0, 16);
    tr.appendChild(createdCell);

    if (IS_ADMIN) {
      tr.appendChild(buildActionCell(c));
    } else {
      const updatedCell = document.createElement("td");
      updatedCell.className = "date-cell";
      updatedCell.textContent = (c.updated_at || "").slice(0, 16);
      tr.appendChild(updatedCell);
    }

    return tr;
  }

  // ── Update the table with fresh data ─────────────────────────────────────
  function updateTable(complaints) {
    if (!complaints || complaints.length === 0) {
      tbody.innerHTML = "";
      if (emptyState) emptyState.style.display = "";
      return;
    }
    if (emptyState) emptyState.style.display = "none";

    const existingIds = new Set(
      Array.from(tbody.querySelectorAll("tr[data-id]")).map(function (r) {
        return r.dataset.id;
      })
    );

    complaints.forEach(function (c) {
      const idStr = String(c.id);
      const prevStatus = previousStatuses[idStr];
      const changed = prevStatus !== undefined && prevStatus !== c.status;

      // Update or insert row
      let row = tbody.querySelector("tr[data-id='" + idStr + "']");

      if (!row) {
        // New complaint — prepend
        row = buildRow(c);
        tbody.insertBefore(row, tbody.firstChild);
      } else {
        // Update status badge in place
        const badge = row.querySelector(".status-badge");
        if (badge && badge.textContent.trim() !== c.status) {
          const newBadge = buildStatusBadge(c.status);
          badge.parentNode.replaceChild(newBadge, badge);
          row.dataset.status = c.status;

          // Also update admin action cell button if on admin dashboard
          if (IS_ADMIN) {
            const oldActionCell = row.querySelector(".action-cell");
            if (oldActionCell) {
              const newActionCell = buildActionCell(c);
              oldActionCell.parentNode.replaceChild(newActionCell, oldActionCell);
            }
          }
        }
        // Update updated_at
        const cells = row.querySelectorAll(".date-cell");
        if (cells.length >= 2 && !IS_ADMIN) {
          cells[cells.length - 1].textContent = (c.updated_at || "").slice(0, 16);
        }
      }

      // Highlight changed rows
      if (changed) {
        row.classList.remove("row-changed");
        // Force reflow so animation restarts
        void row.offsetWidth;
        row.classList.add("row-changed");
      }

      previousStatuses[idStr] = c.status;
      existingIds.delete(idStr);
    });

    // Remove rows no longer in the response
    existingIds.forEach(function (id) {
      const stale = tbody.querySelector("tr[data-id='" + id + "']");
      if (stale) stale.remove();
    });
  }

  // ── Update admin stat tiles ────────────────────────────────────────────────
  function updateStats(stats) {
    if (!stats) return;
    function setTile(el, val) {
      if (!el) return;
      const num = el.querySelector(".stat-number");
      if (num) num.textContent = val !== undefined ? val : "0";
    }
    setTile(statTotal,    stats.total);
    setTile(statPending,  stats["Pending"]);
    setTile(statProgress, stats["In Progress"]);
    setTile(statResolved, stats["Resolved"]);
  }

  // ── Set indicator state ────────────────────────────────────────────────────
  function setIndicator(state) {
    if (state === "ok") {
      indicator.classList.remove("reconnecting");
      liveLabel.textContent = "Live";
      const now = new Date();
      liveTime.textContent = "· updated " + now.toLocaleTimeString();
    } else {
      indicator.classList.add("reconnecting");
      liveLabel.textContent = "Reconnecting…";
      liveTime.textContent = "";
    }
  }

  // ── Main poll function ────────────────────────────────────────────────────
  function poll() {
    fetch(getApiUrl(), {
      method: "GET",
      credentials: "same-origin",
      headers: { "Accept": "application/json" },
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        updateTable(data.complaints || []);
        if (IS_ADMIN) {
          updateStats(data.stats);
          // Notify admin.js to re-attach button listeners after DOM update
          document.dispatchEvent(new CustomEvent("complaints-updated"));
        }
        setIndicator("ok");
      })
      .catch(function () {
        // Fail silently — just show reconnecting state
        setIndicator("error");
      });
  }

  // ── Page Visibility API — pause when tab is hidden ────────────────────────
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopPolling();
    } else {
      poll();          // Immediate refresh when tab becomes visible again
      startPolling();
    }
  });

  // ── Init ─────────────────────────────────────────────────────────────────
  snapshotCurrentStatuses();
  poll();
  startPolling();
})();
