(function () {
  const { api, esc, pkr, coverHtml, loadingHtml } = window.RentEase;
  const form = document.getElementById("search-form");
  const results = document.getElementById("results");
  const pager = document.getElementById("pagination");
  const count = document.getElementById("result-count");
  const sort = document.getElementById("sort");
  const FIELDS = ["q", "city", "type", "min_rent", "max_rent", "bedrooms"];

  function stateFromUrl() {
    const p = new URLSearchParams(location.search);
    FIELDS.forEach((f) => { if (form.elements[f]) form.elements[f].value = p.get(f) || ""; });
    form.elements.furnished.checked = p.get("furnished") === "true";
    sort.value = p.get("sort") || "newest";
    return Number(p.get("page") || 1);
  }

  function buildQuery(page) {
    const p = new URLSearchParams();
    FIELDS.forEach((f) => { const v = form.elements[f].value.trim(); if (v) p.set(f, v); });
    if (form.elements.furnished.checked) p.set("furnished", "true");
    if (sort.value !== "newest") p.set("sort", sort.value);
    if (page > 1) p.set("page", page);
    return p;
  }

  function card(p) {
    return '<a class="card listing" href="property.html?id=' + p.id + '">' +
      '<div class="thumb">' + coverHtml(p) + '<span class="tag">' + esc(p.property_type) + "</span></div>" +
      '<div class="body">' +
      '<div class="price">' + pkr(p.rent) + " <small>/ month</small></div>" +
      "<h3>" + esc(p.title) + "</h3>" +
      '<div class="location">📍 ' + esc(p.area) + ", " + esc(p.city) + "</div>" +
      '<div class="facts"><span>🛏 ' + (p.bedrooms || "Studio") + (p.bedrooms ? " bed" : "") + "</span>" +
      "<span>🛁 " + p.bathrooms + " bath</span>" +
      (p.size_sqft ? "<span>📐 " + p.size_sqft.toLocaleString() + " sq ft</span>" : "") +
      (p.furnished ? "<span>🛋 Furnished</span>" : "") + "</div>" +
      "</div></a>";
  }

  async function load(page, push) {
    const query = buildQuery(page);
    if (push) history.pushState(null, "", query.toString() ? "?" + query : location.pathname);
    results.innerHTML = loadingHtml("Finding homes…");
    pager.innerHTML = "";
    try {
      const data = await api("/properties?" + query.toString());
      count.textContent = data.total === 1 ? "1 property found" : data.total + " properties found";
      if (!data.items.length) {
        results.innerHTML = '<div class="empty card" style="grid-column:1/-1"><div class="big">🔍</div>' +
          "<h3>No properties match your filters</h3><p>Try widening the rent range or choosing another city.</p></div>";
        return;
      }
      results.innerHTML = data.items.map(card).join("");
      renderPager(data.page, data.pages);
    } catch (err) {
      count.textContent = "";
      results.innerHTML = '<div class="alert error" style="grid-column:1/-1">' + esc(err.message) + "</div>";
    }
  }

  function renderPager(page, pages) {
    if (pages <= 1) return;
    let html = '<button class="btn secondary small" data-page="' + (page - 1) + '"' + (page === 1 ? " disabled" : "") + ">‹ Prev</button>";
    for (let i = 1; i <= pages; i++) {
      html += '<button class="btn secondary small' + (i === page ? " current" : "") + '" data-page="' + i + '">' + i + "</button>";
    }
    html += '<button class="btn secondary small" data-page="' + (page + 1) + '"' + (page === pages ? " disabled" : "") + ">Next ›</button>";
    pager.innerHTML = html;
  }

  pager.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-page]");
    if (!btn || btn.disabled) return;
    load(Number(btn.dataset.page), true);
    window.scrollTo({ top: form.offsetTop - 80, behavior: "smooth" });
  });

  form.addEventListener("submit", (e) => { e.preventDefault(); load(1, true); });
  sort.addEventListener("change", () => load(1, true));
  form.elements.city.addEventListener("change", () => load(1, true));
  form.elements.type.addEventListener("change", () => load(1, true));
  form.elements.bedrooms.addEventListener("change", () => load(1, true));
  form.elements.furnished.addEventListener("change", () => load(1, true));
  document.getElementById("reset-btn").addEventListener("click", () => {
    form.reset(); sort.value = "newest"; load(1, true);
  });
  window.addEventListener("popstate", () => load(stateFromUrl(), false));

  async function init() {
    const page = stateFromUrl();
    try {
      const meta = await api("/meta/filters");
      const select = form.elements.city;
      const current = new URLSearchParams(location.search).get("city") || "";
      meta.cities.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c; opt.textContent = c;
        select.appendChild(opt);
      });
      select.value = current;
    } catch (e) { /* filters still work without the city list */ }
    load(page, false);
  }
  init();
})();
