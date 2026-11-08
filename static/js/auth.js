(() => {
  "use strict";

  const loginForm = document.querySelector("#login-form");
  const registerForm = document.querySelector("#register-form");
  const feedback = document.querySelector("#auth-feedback");
  const loginTab = document.querySelector("#show-login");
  const registerTab = document.querySelector("#show-register");

  function showForm(mode) {
    const registering = mode === "register";
    loginForm.hidden = registering;
    registerForm.hidden = !registering;
    loginTab.classList.toggle("active", !registering);
    registerTab.classList.toggle("active", registering);
    loginTab.setAttribute("aria-selected", String(!registering));
    registerTab.setAttribute("aria-selected", String(registering));
    document.querySelector("#auth-title").textContent = registering ? "Crea tu cuenta" : "Bienvenida de nuevo";
    document.querySelector("#auth-description").textContent = registering ? "Regístrate para guardar tus casos y análisis." : "Ingresa para continuar con tus casos.";
    feedback.textContent = "";
    feedback.classList.remove("error");
  }

  async function submitAuth(event, endpoint) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector(".auth-submit");
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Procesando...";
    feedback.textContent = "";
    feedback.classList.remove("error");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "No se pudo completar el acceso.");
      window.location.assign("/");
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
      button.disabled = false;
      button.textContent = label;
    }
  }

  loginTab.addEventListener("click", () => showForm("login"));
  registerTab.addEventListener("click", () => showForm("register"));
  loginForm.addEventListener("submit", event => submitAuth(event, "/api/auth/login"));
  registerForm.addEventListener("submit", event => submitAuth(event, "/api/auth/register"));
})();
