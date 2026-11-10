// Shared helpers: API client, auth state, header/footer, formatting, toasts.
(function () {
  const cfg = window.RENTEASE_CONFIG || {};
  const API_BASE = (cfg.API_BASE || "/api").replace(/\/$/, "");
  // Origin of the API, used to resolve image paths such as "/api/uploads/..."
  const API_ORIGIN = /^https?:\/\//.test(API_BASE) ? new URL(API_BASE).origin : "";

  const TOKEN_KEY = "rentease_token";
  const USER_KEY = "rentease_user";

  function safeGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function safeSet(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } }
  function safeRemove(key) { try { localStorage.removeItem(key); } catch (e) { /* ignore */ } }

  const auth = {
    get token() { return safeGet(TOKEN_KEY); },
    get user() {
      try { return JSON.parse(safeGet(USER_KEY) || "null"); } catch (e) { return null; }
    },
    save(token, user) { safeSet(TOKEN_KEY, token); safeSet(USER_KEY, JSON.stringify(user)); },
    setUser(user) { safeSet(USER_KEY, JSON.stringify(user)); },
    clear() { safeRemove(TOKEN_KEY); safeRemove(USER_KEY); },
  };

  class ApiError extends Error {
    constructor(status, message, details) { super(message); this.status = status; this.details = details || {}; }
  }

  async function api(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    if (auth.token) headers["Authorization"] = "Bearer " + auth.token;
    let res;
    try {
      res = await fetch(API_BASE + path, { method: options.method || "GET", headers, body });
    } catch (e) {
      throw new ApiError(0, "Cannot reach the server. Check your connection and try again.");
    }
    // Shows which app-tier instance answered: handy for demonstrating the load balancer.
    const servedBy = res.headers.get("X-Served-By");
    const servedEl = document.getElementById("served-by");
    if (servedBy && servedEl) servedEl.textContent = "Served by app instance: " + servedBy;
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      if (res.status === 401 && auth.token) {
        auth.clear();
        if (options.redirectOn401 !== false && !location.pathname.endsWith("login.html")) {
          location.href = "login.html?next=" + encodeURIComponent(location.pathname + location.search);
        }
      }
      throw new ApiError(res.status, (data && data.error) || "Request failed (" + res.status + ")", data && data.details);
    }
    return data;
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function assetUrl(url) {
    if (!url) return "";
    return /^https?:\/\//.test(url) ? url : API_ORIGIN + url;
  }

  function pkr(amount) {
    return "Rs " + Number(amount).toLocaleString("en-PK");
  }

  function shortDate(iso) {
    if (!iso) return "";
    const d = new Date(iso.includes("T") || iso.includes("Z") ? iso : iso.replace(" ", "T") + "Z");
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  const TYPE_ICONS = { house: "🏠", flat: "🏢", portion: "🏘️", room: "🛏️", studio: "🏙️" };
  const GRADIENTS = [
    ["#0f766e", "#14b8a6"], ["#1d4ed8", "#60a5fa"], ["#7c3aed", "#a78bfa"],
    ["#b45309", "#f59e0b"], ["#be123c", "#fb7185"], ["#0369a1", "#38bdf8"],
  ];

  function placeholder(property) {
    const g = GRADIENTS[(property.id || 0) % GRADIENTS.length];
    return '<div class="placeholder" style="background:linear-gradient(135deg,' + g[0] + "," + g[1] + ')">' +
      (TYPE_ICONS[property.property_type] || "🏠") + "</div>";
  }

  function coverHtml(property) {
    return property.cover_url
      ? '<img src="' + esc(assetUrl(property.cover_url)) + '" alt="' + esc(property.title) + '" loading="lazy">'
      : placeholder(property);
  }

  function toast(message, type) {
    let el = document.getElementById("toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = message;
    el.className = "show" + (type === "error" ? " error" : "");
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.className = el.className.replace("show", "").trim(); }, 3200);
  }

  function showFieldErrors(form, err) {
    form.querySelectorAll(".field.has-error").forEach((f) => f.classList.remove("has-error"));
    form.querySelectorAll(".field .error").forEach((e) => e.remove());
    const details = (err && err.details) || {};
    Object.keys(details).forEach((name) => {
      const input = form.querySelector('[name="' + name + '"]');
      const field = input && input.closest(".field");
      if (field) {
        field.classList.add("has-error");
        const msg = document.createElement("div");
        msg.className = "error";
        msg.textContent = details[name];
        field.appendChild(msg);
      }
    });
  }

  function formAlert(form, message, type) {
    let box = form.querySelector(".alert");
    if (!message) { if (box) box.remove(); return; }
    if (!box) { box = document.createElement("div"); form.prepend(box); }
    box.className = "alert " + (type || "error");
    box.textContent = message;
  }

  function requireUser(roles) {
    const user = auth.user;
    if (!user || !auth.token) {
      location.href = "login.html?next=" + encodeURIComponent(location.pathname + location.search);
      return null;
    }
    if (roles && roles.length && !roles.includes(user.role)) {
      location.href = "index.html";
      return null;
    }
    return user;
  }

  function logout() {
    auth.clear();
    location.href = "index.html";
  }

  function renderChrome() {
    const user = auth.user;
    const page = location.pathname.split("/").pop() || "index.html";
    const link = (href, label) =>
      '<a href="' + href + '"' + (page === href ? ' class="active"' : "") + ">" + label + "</a>";
    let nav = link("index.html", "Browse");
    if (user) {
      if (user.role === "owner") nav += link("dashboard.html", "My listings");
      if (user.role === "tenant") nav += link("dashboard.html", "My inquiries");
      if (user.role === "admin") nav += link("admin.html", "Admin");
      nav += '<span class="user-chip">Hi, ' + esc(user.name.split(" ")[0]) + "</span>";
      nav += '<button class="linklike" id="logout-btn" type="button">Log out</button>';
    } else {
      nav += link("login.html", "Log in");
      nav += '<a class="btn small" href="register.html" style="color:#fff">List your property</a>';
    }
    const header = document.createElement("header");
    header.className = "site-header";
    header.innerHTML =
      '<div class="container"><a class="logo" href="index.html"><span class="logo-mark">⌂</span><span>Rent<span class="accent">Ease</span></span></a>' +
      '<nav class="nav">' + nav + "</nav></div>";
    document.body.prepend(header);
    const btn = document.getElementById("logout-btn");
    if (btn) btn.addEventListener("click", logout);

    const footer = document.createElement("footer");
    footer.className = "site-footer";
    footer.innerHTML = '<div class="container"><span>© ' + new Date().getFullYear() +
      ' RentEase — deployed automatically via CI/CD</span><span id="served-by"></span></div>';
    document.body.appendChild(footer);
  }

  function loadingHtml(text) {
    return '<div class="loading"><div class="spinner"></div>' + esc(text || "Loading…") + "</div>";
  }

  function params() { return new URLSearchParams(location.search); }

  window.RentEase = {
    api, auth, esc, pkr, shortDate, assetUrl, coverHtml, placeholder, toast, showFieldErrors, formAlert,
    requireUser, logout, loadingHtml, params, ApiError, TYPE_ICONS,
  };

  document.addEventListener("DOMContentLoaded", renderChrome);
})();
