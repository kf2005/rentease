// Runtime configuration for the web tier.
//
// In production the web server (e.g. Nginx) serves this site AND reverse-proxies
// "/api" to the application tier in the private subnet, so the browser never
// talks to the app tier directly and no CORS is needed. Keep API_BASE = "/api".
//
// For local development without a reverse proxy, point it at the Flask server,
// e.g. "http://localhost:5000/api" (and set CORS_ORIGINS on the backend).
// This file can be regenerated at container start-up from an environment
// variable, so the same image works in every environment.
window.RENTEASE_CONFIG = {
  API_BASE: "http://localhost:5000/api",
};
