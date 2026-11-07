// Renders inquiry lists for owners (received, with reply box) and tenants (sent).
(function () {
  const { api, esc, shortDate, toast, loadingHtml } = window.RentEase;

  function item(q, role) {
    const prop = '<a href="property.html?id=' + q.property.id + '">' + esc(q.property.title) + "</a>" +
      ' <span class="muted">· ' + esc(q.property.area) + ", " + esc(q.property.city) + "</span>";
    let html = '<div class="card inquiry" data-id="' + q.id + '">' +
      '<div class="head"><div>' + prop + "</div>" +
      '<div><span class="badge ' + esc(q.status) + '">' + esc(q.status) + '</span> <span class="muted">' + shortDate(q.created_at) + "</span></div></div>";

    if (role === "owner") {
      html += '<div class="muted">From <strong style="color:var(--ink)">' + esc(q.tenant.name) + "</strong> · " +
        '<a href="mailto:' + esc(q.tenant.email) + '">' + esc(q.tenant.email) + "</a>" +
        (q.tenant.phone ? ' · <a href="tel:' + esc(q.tenant.phone) + '">' + esc(q.tenant.phone) + "</a>" : "") + "</div>";
    } else {
      html += '<div class="muted">To ' + esc(q.owner.name) + "</div>";
    }
    html += '<div class="msg">' + esc(q.message) + "</div>";
    if (q.reply) {
      html += '<div class="reply"><strong>' + (role === "owner" ? "Your reply" : "Owner's reply") + "</strong> · " +
        '<span class="muted">' + shortDate(q.replied_at) + "</span><br>" + esc(q.reply) + "</div>";
    }
    if (q.status !== "closed") {
      if (role === "owner") {
        html += '<form class="reply-form"><textarea name="reply" placeholder="' + (q.reply ? "Send another reply…" : "Write a reply…") + '" required></textarea>' +
          '<button class="btn small" type="submit">Reply</button>' +
          '<button class="btn secondary small" type="button" data-close-inquiry>Close</button></form>';
      } else {
        html += '<div style="text-align:right"><button class="btn secondary small" type="button" data-close-inquiry>Mark as closed</button></div>';
      }
    }
    return html + "</div>";
  }

  async function renderInquiries(container, role, onChange) {
    container.innerHTML = loadingHtml();
    let items;
    try {
      items = (await api("/my/inquiries")).items;
    } catch (err) {
      container.innerHTML = '<div class="alert error">' + esc(err.message) + "</div>";
      return [];
    }
    if (!items.length) {
      container.innerHTML = '<div class="empty card"><div class="big">💬</div><h3>No inquiries yet</h3><p>' +
        (role === "owner" ? "When tenants contact you about a listing, their messages show up here."
          : 'Find a place you like on the <a href="index.html">listings page</a> and send the owner a message.') + "</p></div>";
      return items;
    }
    container.innerHTML = items.map((q) => item(q, role)).join("");

    container.querySelectorAll(".reply-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = form.closest(".inquiry").dataset.id;
        try {
          await api("/inquiries/" + id, { method: "PATCH", body: { reply: form.elements.reply.value } });
          toast("Reply sent");
          renderInquiries(container, role, onChange);
          if (onChange) onChange();
        } catch (err) { toast(err.message, "error"); }
      });
    });
    container.querySelectorAll("[data-close-inquiry]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.closest(".inquiry").dataset.id;
        try {
          await api("/inquiries/" + id, { method: "PATCH", body: { status: "closed" } });
          toast("Inquiry closed");
          renderInquiries(container, role, onChange);
          if (onChange) onChange();
        } catch (err) { toast(err.message, "error"); }
      });
    });
    return items;
  }

  window.RentEaseInquiries = { renderInquiries };
})();
