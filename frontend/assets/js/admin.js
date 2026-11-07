(function () {
  const { api, esc, pkr, shortDate, coverHtml, toast, requireUser, loadingHtml } = window.RentEase;
  const me = requireUser(["admin"]);
  if (!me) return;

  const panel = document.getElementById("panel");
  const tabs = document.getElementById("tabs");
  let current = "pending";

  async function loadStats() {
    try {
      const s = await api("/admin/stats");
      const stat = (n, k) => '<div class="card stat"><div class="n">' + n + '</div><div class="k">' + k + "</div></div>";
      document.getElementById("stats").innerHTML =
        stat(s.properties.pending, "Listings awaiting review") + stat(s.properties.approved, "Live listings") +
        stat(s.users.owners, "Owners") + stat(s.users.tenants, "Tenants") + stat(s.inquiries.total, "Inquiries sent");
      document.getElementById("pending-count").textContent = s.properties.pending;
    } catch (e) { /* stats are optional */ }
  }

  function propertyRow(p) {
    let actions = "";
    if (p.status !== "approved") actions += '<button class="btn ok small" data-approve="' + p.id + '">Approve</button>';
    if (p.status !== "rejected") actions += '<button class="btn danger small" data-reject="' + p.id + '">Reject</button>';
    actions += '<button class="btn secondary small" data-delete="' + p.id + '">Delete</button>';
    return "<tr><td><div class=\"mini-thumb\">" + coverHtml(p) + "</div></td>" +
      '<td><a href="property.html?id=' + p.id + '" target="_blank" rel="noopener"><strong>' + esc(p.title) + "</strong></a>" +
      '<br><span class="muted">' + esc(p.property_type) + " · " + esc(p.area) + ", " + esc(p.city) + "</span>" +
      (p.rejection_reason ? '<div class="hint" style="color:var(--danger)">Reason: ' + esc(p.rejection_reason) + "</div>" : "") + "</td>" +
      "<td>" + esc(p.owner.name) + '<br><span class="muted">' + esc(p.owner.email || "") + "</span></td>" +
      "<td>" + pkr(p.rent) + "</td><td>" + shortDate(p.updated_at) + "</td>" +
      '<td><div class="row-actions">' + actions + "</div>" +
      '<div class="reject-box" hidden style="margin-top:.5rem"><input placeholder="Reason for rejection" maxlength="255">' +
      '<button class="btn danger small" style="margin-top:.4rem" data-confirm-reject="' + p.id + '">Confirm reject</button></div></td></tr>';
  }

  async function showProperties(status) {
    panel.innerHTML = loadingHtml();
    let items;
    try { items = (await api("/admin/properties?status=" + status)).items; }
    catch (err) { panel.innerHTML = '<div class="alert error">' + esc(err.message) + "</div>"; return; }
    if (!items.length) {
      panel.innerHTML = '<div class="empty card"><div class="big">' + (status === "pending" ? "🎉" : "📭") + "</div><h3>" +
        (status === "pending" ? "All caught up! No listings waiting for review." : "No " + status + " listings.") + "</h3></div>";
      return;
    }
    panel.innerHTML = '<div class="card table-wrap"><table><thead><tr><th></th><th>Listing</th><th>Owner</th><th>Rent</th><th>Updated</th><th>Actions</th></tr></thead><tbody>' +
      items.map(propertyRow).join("") + "</tbody></table></div>";
  }

  async function moderate(id, status, reason) {
    try {
      await api("/admin/properties/" + id, { method: "PATCH", body: { status, reason } });
      toast(status === "approved" ? "Listing approved and now live" : "Listing rejected");
      loadStats();
      show();
    } catch (err) { toast(err.message, "error"); }
  }

  async function showUsers() {
    panel.innerHTML = loadingHtml();
    let users;
    try { users = (await api("/admin/users")).items; }
    catch (err) { panel.innerHTML = '<div class="alert error">' + esc(err.message) + "</div>"; return; }
    panel.innerHTML = '<div class="card table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Listings</th><th>Joined</th><th>Status</th><th></th></tr></thead><tbody>' +
      users.map((u) =>
        "<tr><td><strong>" + esc(u.name) + "</strong>" + (u.phone ? '<br><span class="muted">' + esc(u.phone) + "</span>" : "") + "</td>" +
        "<td>" + esc(u.email) + '</td><td><span class="badge role">' + esc(u.role) + "</span></td>" +
        "<td>" + u.listing_count + "</td><td>" + shortDate(u.created_at) + "</td>" +
        '<td><span class="badge ' + (u.is_active ? "approved" : "rejected") + '">' + (u.is_active ? "active" : "disabled") + "</span></td>" +
        "<td>" + (u.id === me.id ? '<span class="muted">You</span>'
          : '<button class="btn secondary small" data-toggle-user="' + u.id + '" data-active="' + u.is_active + '">' + (u.is_active ? "Disable" : "Enable") + "</button>") +
        "</td></tr>").join("") + "</tbody></table></div>";
  }

  panel.addEventListener("click", async (e) => {
    const t = e.target;
    if (t.dataset.approve) return moderate(t.dataset.approve, "approved");
    if (t.dataset.reject) {
      const box = t.closest("td").querySelector(".reject-box");
      box.hidden = !box.hidden;
      if (!box.hidden) box.querySelector("input").focus();
      return;
    }
    if (t.dataset.confirmReject) {
      const reason = t.closest(".reject-box").querySelector("input").value.trim();
      if (!reason) { toast("Please enter a reason", "error"); return; }
      return moderate(t.dataset.confirmReject, "rejected", reason);
    }
    if (t.dataset.delete) {
      if (t.dataset.sure !== "1") {
        t.dataset.sure = "1"; t.textContent = "Confirm delete";
        setTimeout(() => { t.dataset.sure = ""; t.textContent = "Delete"; }, 4000);
        return;
      }
      try { await api("/properties/" + t.dataset.delete, { method: "DELETE" }); toast("Listing deleted"); loadStats(); show(); }
      catch (err) { toast(err.message, "error"); }
      return;
    }
    if (t.dataset.toggleUser) {
      const active = t.dataset.active === "true";
      try {
        await api("/admin/users/" + t.dataset.toggleUser, { method: "PATCH", body: { is_active: !active } });
        toast(active ? "User disabled" : "User enabled");
        showUsers();
      } catch (err) { toast(err.message, "error"); }
    }
  });

  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (!btn) return;
    current = btn.dataset.tab;
    tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("current", b === btn));
    show();
  });

  function show() { return current === "users" ? showUsers() : showProperties(current); }

  loadStats();
  show();
})();
