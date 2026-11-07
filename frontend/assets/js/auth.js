(function () {
  const { api, auth, showFieldErrors, formAlert, params } = window.RentEase;

  function destination(user) {
    const next = params().get("next");
    // Only allow same-site relative redirects.
    if (next && next.startsWith("/") && !next.startsWith("//")) return next;
    if (user.role === "admin") return "admin.html";
    if (user.role === "owner") return "dashboard.html";
    return "index.html";
  }

  async function submit(form, path, body) {
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    formAlert(form, null);
    showFieldErrors(form, null);
    try {
      const data = await api(path, { method: "POST", body, redirectOn401: false });
      auth.save(data.token, data.user);
      location.href = destination(data.user);
    } catch (err) {
      showFieldErrors(form, err);
      formAlert(form, err.message);
      btn.disabled = false;
    }
  }

  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    if (auth.user && auth.token) location.href = destination(auth.user);
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submit(loginForm, "/auth/login", {
        email: loginForm.elements.email.value,
        password: loginForm.elements.password.value,
      });
    });
    document.querySelectorAll("[data-demo]").forEach((btn) => {
      btn.addEventListener("click", () => {
        loginForm.elements.email.value = btn.dataset.demo;
        loginForm.elements.password.value = "Password123!";
        loginForm.requestSubmit();
      });
    });
  }

  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const f = registerForm.elements;
      submit(registerForm, "/auth/register", {
        name: f.name.value,
        email: f.email.value,
        phone: f.phone.value,
        password: f.password.value,
        role: registerForm.querySelector("input[name=role]:checked").value,
      });
    });
  }
})();
