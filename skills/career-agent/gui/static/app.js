import { openLocalSession } from "./api.js";
import { errorText, loadMessages, locale, t } from "./i18n.js";
import { renderRoute } from "./screens.js";

const ROUTES = [
  ["/", "nav.home"],
  ["/career", "nav.career"],
  ["/self-analysis", "nav.self_analysis"],
  ["/applications", "nav.applications"],
  ["/documents", "nav.documents"],
];

let leaveGuard = null;
let routeCleanup = null;

function clearRouteGuard() {
  const cleanup = routeCleanup;
  leaveGuard = null;
  routeCleanup = null;
  if (cleanup) cleanup();
}

const make = (tag, className, text) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
};

const routeHref = (path) => `${path}?lang=${locale()}`;

function navigation(currentPath) {
  const nav = make("nav", "global-nav");
  nav.setAttribute("aria-label", t("a11y.primary_nav"));
  for (const [path, key] of ROUTES) {
    const link = make("a", "global-nav__link");
    link.href = routeHref(path);
    link.dataset.route = path;
    link.textContent = t(key);
    const active = path === "/career"
      ? currentPath === path || currentPath.startsWith("/career/") || currentPath.startsWith("/work/")
      : currentPath === path;
    if (active) {
      link.classList.add("nav-current");
      link.setAttribute("aria-current", "page");
    }
    nav.append(link);
  }
  return nav;
}

function languageControl() {
  const wrapper = make("label", "language-control");
  const label = make("span", "sr-only", t("a11y.language"));
  const select = document.createElement("select");
  select.setAttribute("aria-label", t("a11y.language"));
  for (const value of ["ko", "ja", "en"]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = t(`language.${value}`);
    option.selected = value === locale();
    select.append(option);
  }
  select.addEventListener("change", async () => {
    if (leaveGuard && !(await leaveGuard())) {
      select.value = locale();
      return;
    }
    clearRouteGuard();
    const target = new URL(window.location.href);
    target.searchParams.set("lang", select.value);
    target.hash = "";
    window.location.assign(target.toString());
  });
  wrapper.append(label, select);
  return wrapper;
}

function renderShell() {
  const root = document.getElementById("app-root");
  const path = window.location.pathname;
  root.replaceChildren();

  const header = make("header", "topbar");
  const brand = make("a", "wordmark", t("app.title"));
  brand.href = routeHref("/");
  brand.dataset.route = "/";
  const privacy = make("span", "privacy-note", t("app.privacy"));
  header.append(brand, privacy, languageControl());

  const rail = make("aside", "side-rail");
  rail.append(navigation(path));
  const trust = make("p", "trust-note", t("trust.local_detail"));
  rail.append(trust);

  const main = make("main", "content");
  main.id = "main-content";
  main.tabIndex = -1;

  const status = make("div", "system-status");
  status.setAttribute("aria-live", "polite");
  const save = make("span", "system-status__save");
  save.id = "save-state";
  save.hidden = true;
  const announcement = make("span", "system-status__message");
  announcement.id = "route-status";
  status.append(save, announcement);

  const layout = make("div", "app-layout");
  layout.append(rail, main);
  const mobile = make("div", "mobile-nav");
  mobile.append(navigation(path));
  root.append(header, layout, status, mobile);
}

function loadingState() {
  const panel = make("section", "state-panel state-panel--loading");
  panel.setAttribute("aria-busy", "true");
  panel.append(make("p", "eyebrow", t("state.loading_label")), make("h1", "page-title", t("state.loading")));
  return panel;
}

export function setSaveState(key = null) {
  const target = document.getElementById("save-state");
  if (!target) return;
  target.hidden = !key;
  if (key) target.textContent = t(key);
  target.dataset.state = key || "";
}

export function announce(key, values = {}) {
  const target = document.getElementById("route-status");
  if (target) target.textContent = (Array.isArray(key) ? key : [key]).map((item) => t(item, values)).join(" ");
}

export function setLeaveGuard(guard, cleanup = null) {
  if (!guard) {
    clearRouteGuard();
    return;
  }
  if (routeCleanup && routeCleanup !== cleanup) routeCleanup();
  leaveGuard = guard;
  routeCleanup = cleanup;
}

export async function navigate(path, { replace = false } = {}) {
  if (leaveGuard && !(await leaveGuard())) return;
  clearRouteGuard();
  const href = routeHref(path);
  window.history[replace ? "replaceState" : "pushState"]({}, "", href);
  await showCurrentRoute();
}

export async function showCurrentRoute() {
  clearRouteGuard();
  renderShell();
  const main = document.getElementById("main-content");
  main.replaceChildren(loadingState());
  try {
    const screen = await renderRoute(window.location.pathname, {
      announce,
      navigate,
      refresh: showCurrentRoute,
      setLeaveGuard,
      setSaveState,
    });
    main.replaceChildren(screen);
    const heading = main.querySelector("h1");
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  } catch (error) {
    const panel = make("section", "state-panel state-panel--error");
    panel.tabIndex = -1;
    panel.append(make("p", "eyebrow", t("state.error_label")), make("h1", "page-title", errorText(error.code, "READ_FAILED")));
    const retry = make("button", "button button--primary", t("action.retry"));
    retry.type = "button";
    retry.addEventListener("click", showCurrentRoute);
    panel.append(make("p", "muted", t("error.data_unchanged")), retry);
    main.replaceChildren(panel);
    panel.focus();
  }
}

export async function start() {
  try {
    await openLocalSession();
    await loadMessages();
    await showCurrentRoute();
  } catch (error) {
    const status = document.getElementById("session-status");
    const fallback = document.getElementById("boot-error-copy");
    if (status && fallback) {
      status.textContent = fallback.textContent;
      status.closest(".state-panel")?.classList.replace("state-panel--loading", "state-panel--error");
    }
  }
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-route]");
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  navigate(link.dataset.route);
});

window.addEventListener("popstate", async () => {
  if (leaveGuard && !(await leaveGuard())) {
    window.history.forward();
    return;
  }
  clearRouteGuard();
  showCurrentRoute();
});
