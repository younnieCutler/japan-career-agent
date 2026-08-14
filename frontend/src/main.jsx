import React from "react";
import { createRoot } from "react-dom/client";
import "@seed-design/css/base.css";
import "./workspace.css";
import { openLocalSession } from "./api.js";
import { I18nProvider, loadMessages } from "./i18n.jsx";
import App from "./App.jsx";

/* SEED gates its dark palette on explicit attributes rather than on `prefers-color-scheme` alone,
   so the mode has to be wired before anything renders or half the palette inverts and the other
   half does not. `system` keeps following the OS. */
function followColourScheme() {
  const root = document.documentElement;
  root.dataset.seedColorMode = "system";
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const apply = () => { root.dataset.seedUserColorScheme = query.matches ? "dark" : "light"; };
  apply();
  query.addEventListener("change", apply);
}

async function start() {
  followColourScheme();
  try {
    await openLocalSession();
    const catalog = await loadMessages();
    createRoot(document.getElementById("app-root")).render(
      <React.StrictMode>
        <I18nProvider value={catalog}><App /></I18nProvider>
      </React.StrictMode>,
    );
  } catch {
    // The shell carries a localized boot error already; the client cannot translate one yet
    // because the failure may be the catalog fetch itself.
    const status = document.getElementById("session-status");
    const fallback = document.getElementById("boot-error-copy");
    if (status && fallback) status.textContent = fallback.textContent;
  }
}

start();
