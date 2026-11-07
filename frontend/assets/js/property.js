(function () {
  const { api, auth, esc, pkr, shortDate, assetUrl, placeholder, toast, showFieldErrors, formAlert, loadingHtml, params } = window.RentEase;
  const content = document.getElementById("content");
  const id = Number(params().get("id"));

  function spec(k, v) {
    return '<div class="spec"><div class="k">' + esc(k) + '</div><div class="v">' + esc(v) + "</div></div>";
  }

  function gallery(p) {
    if (!p.images.length) {
      return '<div class="gallery-main">' + placeholder(p) + "</div>";
    }
    const thumbs = p.images.length > 1
      ? '<div class="gallery-thumbs">' + p.images.map((img, i) =>
          '<button type="button" data-src="' + esc(assetUrl(img.url)) + '"' + (i === 0 ? ' class="current"' : "") +
          ' aria-label="Photo ' + (i + 1) + '"><img src="' + esc(assetUrl(img.url)) + '" alt=""></button>').join("") + "</div>"
      : "";
    return '<div class="gallery-main"><img id="main-img" src="' + esc(assetUrl(p.images[0].url)) + '" alt="' + esc(p.title) + '"></div>' + thumbs;
  }

  function contactPanel(p) {
    const user = auth.user;
    let html = '<div class="card pad sticky">' +
      '<div class="price" style="font-size:1.6rem">' + pkr(p.rent) + " <small>/ month</small></div>" +
      '<p class="muted" style="margin:.25rem 0 1rem">Listed by <strong style="color:var(--ink)">' + esc(p.owner.name) + "</strong></p>";

    if (p.can_manage) {
      html += '<div class="alert info">This is your listing. Status: <span class="badge ' + esc(p.status) + '">' + esc(p.status) + "</span></div>" +
        (p.rejection_reason ? '<div class="alert error">Rejected: ' + esc(p.rejection_reason) + "</div>" : "") +
        '<a class="btn block secondary" href="' + (user && user.role === "admin" ? "admin.html" : "dashboard.html") + '">Manage listing</a>';
    } else if (!user) {
      html += '<p>Log in as a tenant to see the owner\'s phone number and send an inquiry.</p>' +
        '<a class="btn block" href="login.html?next=' + encodeURIComponent(location.pathname + location.search) + '">Log in to contact owner</a>' +
        '<p class="hint" style="text-align:center;margin-top:.75rem">No account? <a href="register.html">Sign up free</a></p>';
    } else {
      if (p.owner.phone) html += '<p>📞 <a href="tel:' + esc(p.owner.phone) + '"><strong>' + esc(p.owner.phone) + "</strong></a></p>";
      if (user.role === "tenant") {
        html += '<form id="inquiry-form" novalidate>' +
          '<h3 style="font-size:1.05rem">Send an inquiry</h3>' +
          '<div class="field"><label for="message">Message</label>' +
          '<textarea id="message" name="message" required placeholder="Hi, is this still available? When can I visit?"></textarea></div>' +
          '<div class="field"><label for="contact_phone">Your phone (optional)</label>' +
          '<input id="contact_phone" name="contact_phone" type="tel" value="' + esc(user.phone || "") + '"></div>' +
          '<button class="btn block" type="submit">Send inquiry</button></form>';
      } else {
        html += '<p class="hint">Only tenant accounts can send inquiries.</p>';
      }
    }
    return html + "</div>";
  }

  function render(p) {
    document.title = p.title + " — RentEase";
    content.innerHTML =
      '<div class="detail"><div>' + gallery(p) +
      '<div style="margin-top:1.25rem"><span class="badge role">' + esc(p.property_type) + "</span>" +
      (p.furnished ? ' <span class="badge approved">Furnished</span>' : "") +
      '<h1 style="margin-top:.6rem;font-size:1.8rem">' + esc(p.title) + "</h1>" +
      '<div class="location">📍 ' + esc(p.area) + ", " + esc(p.city) + (p.address ? " · " + esc(p.address) : "") + "</div></div>" +
      '<div class="spec-list">' +
      spec("Bedrooms", p.bedrooms || "Studio") + spec("Bathrooms", p.bathrooms) +
      spec("Size", p.size_sqft ? p.size_sqft.toLocaleString() + " sq ft" : "—") +
      spec("Furnishing", p.furnished ? "Furnished" : "Unfurnished") + spec("Listed", shortDate(p.created_at)) +
      "</div>" +
      '<div class="card pad"><h2 style="font-size:1.15rem">About this property</h2><p class="description">' + esc(p.description) + "</p></div>" +
      "</div><aside>" + contactPanel(p) + "</aside></div>";

    content.querySelectorAll(".gallery-thumbs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.getElementById("main-img").src = btn.dataset.src;
        content.querySelectorAll(".gallery-thumbs button").forEach((b) => b.classList.remove("current"));
        btn.classList.add("current");
      });
    });

    const form = document.getElementById("inquiry-form");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = form.querySelector("button[type=submit]");
        btn.disabled = true;
        formAlert(form, null);
        try {
          await api("/properties/" + p.id + "/inquiries", {
            method: "POST",
            body: { message: form.elements.message.value, contact_phone: form.elements.contact_phone.value },
          });
          form.innerHTML = '<div class="alert info">✅ Inquiry sent! The owner\'s reply will appear in ' +
            '<a href="dashboard.html">My inquiries</a>.</div>';
          toast("Inquiry sent to " + p.owner.name);
        } catch (err) {
          showFieldErrors(form, err);
          formAlert(form, err.message);
          btn.disabled = false;
        }
      });
    }
  }

  async function init() {
    if (!id) { content.innerHTML = '<div class="alert error">No listing selected.</div>'; return; }
    content.innerHTML = loadingHtml();
    try {
      render(await api("/properties/" + id, { redirectOn401: false }));
    } catch (err) {
      content.innerHTML = '<div class="empty card"><div class="big">🏚️</div><h3>' + esc(err.message) +
        '</h3><p><a href="index.html">Browse other properties</a></p></div>';
    }
  }
  init();
})();
