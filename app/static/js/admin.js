/**
 * static/js/admin.js
 * Handles status-update button clicks on the admin dashboard.
 *
 * Security:
 *  - Reads CSRF token from <meta name="csrf-token"> (no inline scripts).
 *  - Sends X-CSRFToken header on every POST (required by Flask-WTF).
 *  - Uses textContent when writing user data to the DOM (XSS prevention).
 *  - Validates the new status client-side before sending (UX only; server re-validates).
 */

(function () {
  "use strict";

  // ── Read CSRF token from meta tag ─────────────────────────────────────────
  // Security: token injected server-side into a meta tag, JS reads it here.
  // No inline scripts needed, so the strict CSP (script-src 'self') holds.
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  // ── POST a status update via fetch ────────────────────────────────────────
  function updateStatus(complaintId, newStatus, buttonEl) {
    const url = "/api/complaints/" + complaintId + "/status";
    const csrfToken = getCsrfToken();

    buttonEl.disabled = true;
    buttonEl.textContent = "Updating…";

    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,         // Security: CSRF header for fetch POST
        "Accept": "application/json",
      },
      body: JSON.stringify({ status: newStatus }),
    })
      .then(function (res) {
        return res.json().catch(function () {
          return { error: "HTTP " + res.status };
        }).then(function (data) {
          return { ok: res.ok, status: res.status, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data && result.data.success) {
          // live.js will refresh the table via polling; nothing else needed here
        } else {
          const errMsg = (result.data && result.data.error) ? result.data.error : ("Error (" + result.status + ")");
          console.error("Status update error:", errMsg);
          buttonEl.textContent = errMsg;
          buttonEl.disabled = false;
        }
      })
      .catch(function (err) {
        console.error("Fetch failed:", err);
        buttonEl.textContent = "Network error";
        buttonEl.disabled = false;
      });
  }

  // ── Attach click listeners to all action buttons ──────────────────────────
  // Uses event delegation on tbody so it works after live.js re-renders rows.
  function attachListeners() {
    const tbody = document.getElementById("complaints-tbody");
    if (!tbody) return;

    // Remove old listener to avoid duplicates (after complaints-updated event)
    tbody.removeEventListener("click", handleClick);
    tbody.addEventListener("click", handleClick);
  }

  function handleClick(e) {
    const btn = e.target.closest(".btn-action, .btn-resolve");
    if (!btn) return;
    const complaintId = btn.dataset.id;
    const newStatus   = btn.dataset.next;
    if (!complaintId || !newStatus) return;
    e.preventDefault();
    updateStatus(complaintId, newStatus, btn);
  }

  // Re-attach after live.js refreshes the table
  document.addEventListener("complaints-updated", attachListeners);

  // ── Init ─────────────────────────────────────────────────────────────────
  attachListeners();
})();
