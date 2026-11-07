(function () {
  const { api, esc, pkr, shortDate, assetUrl, coverHtml, toast, showFieldErrors, formAlert, requireUser, loadingHtml } = window.RentEase;
  const { renderInquiries } = window.RentEaseInquiries;

  const user = requireUser(["owner", "tenant"]);
  if (!user) return;

  const tabs = document.getElementById("tabs");
  const panel = document.getElementById("panel");
  const modal = document.getElementById("listing-modal");
  const form = document.getElementById("listing-form");
  const imagesSection = document.getElementById("images-section");
  const imageManager = document.getElementById("image-manager");
  const imageInput = document.getElementById("image-input");
  let editing = null; // property currently in the modal

  // ---------------- tenant ----------------
  if (user.role === "tenant") {
    document.getElementById("dash-title").textContent = "My inquiries";
    document.getElementById("dash-sub").textContent = "Messages you've sent to property owners and their replies.";
    tabs.remove();
    renderInquiries(panel, "tenant");
    return;
  }

  // ---------------- owner ----------------
  document.getElementById("dash-title").textContent = "My listings";
  document.getElementById("dash-sub").textContent = "Add properties, upload photos and reply to tenants.";
  const newBtn = document.getElementById("new-listing-btn");
  newBtn.hidden = false;
  newBtn.addEventListener("click", () => openModal(null));

  let current = location.hash === "#inquiries" ? "inquiries" : "listings";
  let counts = { listings: 0, inquiries: 0 };

  function renderTabs() {
    tabs.innerHTML =
      '<button type="button" data-tab="listings"' + (current === "listings" ? ' class="current"' : "") + '>Listings<span class="count">' + counts.listings + "</span></button>" +
      '<button type="button" data-tab="inquiries"' + (current === "inquiries" ? ' class="current"' : "") + '>Inquiries received<span class="count">' + counts.inquiries + "</span></button>";
  }
  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (!btn) return;
    current = btn.dataset.tab;
    history.replaceState(null, "", current === "inquiries" ? "#inquiries" : location.pathname);
    show();
  });

  async function refreshCounts() {
    try {
      const [props, inq] = await Promise.all([api("/my/properties"), api("/my/inquiries")]);
      counts = { listings: props.items.length, inquiries: inq.items.filter((q) => q.status === "new").length };
      renderTabs();
      return props.items;
    } catch (e) { return null; }
  }

  async function show() {
    renderTabs();
    if (current === "inquiries") {
      await renderInquiries(panel, "owner", refreshCounts);
      return;
    }
    panel.innerHTML = loadingHtml();
    let items;
    try {
      items = (await api("/my/properties")).items;
    } catch (err) {
      panel.innerHTML = '<div class="alert error">' + esc(err.message) + "</div>";
      return;
    }
    counts.listings = items.length;
    renderTabs();
    if (!items.length) {
      panel.innerHTML = '<div class="empty card"><div class="big">🏠</div><h3>You haven\'t listed anything yet</h3>' +
        '<p>Add your first property. It goes live as soon as an admin approves it.</p>' +
        '<button class="btn" type="button" id="empty-add">+ Add your first listing</button></div>';
      document.getElementById("empty-add").addEventListener("click", () => openModal(null));
      return;
    }
    panel.innerHTML = '<div class="card table-wrap"><table><thead><tr><th></th><th>Listing</th><th>Rent</th><th>Status</th><th>Inquiries</th><th>Updated</th><th></th></tr></thead><tbody>' +
      items.map((p) =>
        "<tr><td><div class=\"mini-thumb\">" + coverHtml(p) + "</div></td>" +
        '<td><a href="property.html?id=' + p.id + '"><strong>' + esc(p.title) + "</strong></a><br><span class=\"muted\">" + esc(p.area) + ", " + esc(p.city) + "</span>" +
        (p.status === "rejected" && p.rejection_reason ? '<div class="hint" style="color:var(--danger)">Reason: ' + esc(p.rejection_reason) + "</div>" : "") + "</td>" +
        "<td>" + pkr(p.rent) + "</td>" +
        '<td><span class="badge ' + esc(p.status) + '">' + esc(p.status) + "</span></td>" +
        "<td>" + p.inquiry_count + "</td>" +
        "<td>" + shortDate(p.updated_at) + "</td>" +
        '<td><div class="row-actions"><button class="btn secondary small" data-edit="' + p.id + '">Edit</button>' +
        '<button class="btn danger small" data-delete="' + p.id + '">Delete</button></div></td></tr>'
      ).join("") + "</tbody></table></div>";

    panel.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", async () => {
      try { openModal(await api("/properties/" + b.dataset.edit)); } catch (err) { toast(err.message, "error"); }
    }));
    panel.querySelectorAll("[data-delete]").forEach((b) => b.addEventListener("click", async () => {
      const row = b.closest("tr");
      if (b.dataset.confirm !== "1") {
        b.dataset.confirm = "1"; b.textContent = "Confirm delete";
        setTimeout(() => { b.dataset.confirm = ""; b.textContent = "Delete"; }, 4000);
        return;
      }
      try {
        await api("/properties/" + b.dataset.delete, { method: "DELETE" });
        row.remove();
        toast("Listing deleted");
        show();
      } catch (err) { toast(err.message, "error"); }
    }));
  }

  // ---------------- modal ----------------
  const FIELDS = ["title", "property_type", "rent", "city", "area", "bedrooms", "bathrooms", "size_sqft", "address", "description"];

  function openModal(property) {
    editing = property;
    form.reset();
    showFieldErrors(form, null);
    formAlert(form, null);
    document.getElementById("modal-title").textContent = property ? "Edit listing" : "Add listing";
    document.getElementById("save-btn").textContent = property ? "Save changes" : "Save and add photos";
    if (property) {
      FIELDS.forEach((f) => { form.elements[f].value = property[f] == null ? "" : property[f]; });
      form.elements.furnished.checked = !!property.furnished;
      renderImages(property.images || []);
      imagesSection.hidden = false;
    } else {
      imagesSection.hidden = true;
    }
    modal.classList.add("open");
    form.elements.title.focus();
  }

  function closeModal() {
    modal.classList.remove("open");
    editing = null;
    show();
  }

  modal.addEventListener("click", (e) => { if (e.target === modal || e.target.closest("[data-close]")) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && modal.classList.contains("open")) closeModal(); });

  function renderImages(images) {
    imageManager.innerHTML = images.length
      ? images.map((img, i) => '<div class="img"><img src="' + esc(assetUrl(img.url)) + '" alt="Photo ' + (i + 1) + '">' +
          '<button type="button" data-remove-image="' + img.id + '">Remove</button></div>').join("")
      : '<span class="hint">No photos yet. Listings with photos get far more inquiries.</span>';
  }

  imageManager.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-remove-image]");
    if (!btn || !editing) return;
    try {
      await api("/images/" + btn.dataset.removeImage, { method: "DELETE" });
      editing.images = editing.images.filter((i) => String(i.id) !== btn.dataset.removeImage);
      renderImages(editing.images);
    } catch (err) { toast(err.message, "error"); }
  });

  imageInput.addEventListener("change", async () => {
    if (!editing || !imageInput.files.length) return;
    const data = new FormData();
    Array.from(imageInput.files).forEach((f) => data.append("images", f));
    imageInput.disabled = true;
    try {
      const res = await api("/properties/" + editing.id + "/images", { method: "POST", body: data });
      editing.images = res.images;
      renderImages(res.images);
      toast("Photos uploaded");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      imageInput.value = "";
      imageInput.disabled = false;
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("save-btn");
    btn.disabled = true;
    const body = {};
    FIELDS.forEach((f) => { body[f] = form.elements[f].value; });
    body.furnished = form.elements.furnished.checked;
    try {
      if (editing) {
        const justCreated = editing.__justCreated;
        await api("/properties/" + editing.id, { method: "PUT", body });
        toast(justCreated ? "Listing submitted for admin review." : "Changes saved. Your listing is back in review.");
        closeModal();
      } else {
        const created = await api("/properties", { method: "POST", body });
        showFieldErrors(form, null);
        toast("Listing created. Now add some photos.");
        editing = created;
        document.getElementById("modal-title").textContent = "Add photos";
        document.getElementById("save-btn").textContent = "Done";
        renderImages([]);
        imagesSection.hidden = false;
        formAlert(form, "Listing saved and sent for review. Add photos below, then click Done.", "info");
        modal.querySelector(".modal").scrollTop = 0;
        // Next submit just closes the modal after optional edits.
        editing.__justCreated = true;
      }
    } catch (err) {
      showFieldErrors(form, err);
      formAlert(form, err.message);
    } finally {
      btn.disabled = false;
    }
  });

  refreshCounts().then(show);
})();
