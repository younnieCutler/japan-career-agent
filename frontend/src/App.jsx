/* Shell and routing.

   Routing stays on the History API against the same server-side route list as before, so a URL is
   still a place you can link to and reload into. Selection inside a split pane rides in `?sel=`
   and is replaced rather than pushed, so Back does not walk every row the user glanced at. */

import React from "react";
import { SideNavigation, SideNavigationProvider, Text } from "@seed-design/react";
import { useI18n } from "./i18n.jsx";
import { Choice } from "./components/Fields.jsx";
import CareerScreen from "./screens/Career.jsx";
import HomeScreen from "./screens/Home.jsx";
import DiagnosisScreen from "./screens/Diagnosis.jsx";
import WorkScreen from "./screens/Work.jsx";
import SelfAnalysisScreen from "./screens/SelfAnalysis.jsx";
import ApplicationsScreen, { DocumentsScreen } from "./screens/Applications.jsx";
import { InProgressScreen, TimelineScreen } from "./screens/Chronology.jsx";
import { ErrorState, LoadingState, NotFound } from "./components/States.jsx";

const ROUTES = [
  ["/", "nav.home"],
  ["/career", "nav.career"],
  ["/diagnosis", "nav.diagnosis"],
  ["/self-analysis", "nav.self_analysis"],
  ["/applications", "nav.applications"],
  ["/documents", "nav.documents"],
];

const isCareerPath = (path) => path === "/career" || path.startsWith("/career/") || path.startsWith("/work/");

export function useLocation() {
  const [location, setLocation] = React.useState(() => ({
    path: window.location.pathname,
    search: window.location.search,
  }));
  React.useEffect(() => {
    const sync = () => setLocation({ path: window.location.pathname, search: window.location.search });
    window.addEventListener("popstate", sync);
    window.addEventListener("app:navigated", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("app:navigated", sync);
    };
  }, []);
  return location;
}

/* A screen with unsaved work registers a guard here. Routing is client-side, so without this a
   click on the sidebar would discard a draft the user is still typing — the browser's own
   `beforeunload` only covers leaving the page, not leaving the screen. */
let leaveGuard = null;
export function setLeaveGuard(guard) { leaveGuard = guard; }

export async function navigate(path, params = {}) {
  if (leaveGuard) {
    const guard = leaveGuard;
    if (!(await guard())) return;
    leaveGuard = null;
  }
  const search = new URLSearchParams({
    lang: new URLSearchParams(window.location.search).get("lang") || "ko",
    ...params,
  });
  window.history.pushState({}, "", `${path}?${search.toString()}`);
  window.dispatchEvent(new Event("app:navigated"));
}

export function setSelection(ref) {
  const url = new URL(window.location.href);
  if (ref) url.searchParams.set("sel", ref);
  else url.searchParams.delete("sel");
  window.history.replaceState({}, "", url.toString());
  window.dispatchEvent(new Event("app:navigated"));
}

/* The catalog is fetched once at boot, so switching language reloads the document rather than
   re-rendering. That is also why it goes through the same leave guard as any other navigation:
   a full load would otherwise discard an unsaved draft without asking. */
function LanguageControl() {
  const { t, language } = useI18n();
  const choices = [["ko", t("language.ko")], ["ja", t("language.ja")], ["en", t("language.en")]];

  const switchTo = async (next) => {
    if (next === language) return;
    if (leaveGuard) {
      const guard = leaveGuard;
      if (!(await guard())) return;
      leaveGuard = null;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("lang", next);
    window.location.assign(url.toString());
  };

  return (
    <Choice value={language} onChange={switchTo} options={choices} label={t("a11y.language")} />
  );
}

function Shell({ path, children }) {
  const { t } = useI18n();
  return (
    <SideNavigationProvider>
      <div className="workspace">
        <SideNavigation.Root style={{ borderRight: "1px solid var(--seed-color-stroke-neutral-muted)" }}>
          <SideNavigation.Header>
            <Text textStyle="t5Bold">{t("app.title")}</Text>
          </SideNavigation.Header>
          <SideNavigation.Content>
            <SideNavigation.Group>
              {ROUTES.map(([target, key]) => {
                const current = target === "/career" ? isCareerPath(path) : path === target;
                return (
                  <SideNavigation.Item
                    key={target}
                    aria-current={current ? "page" : undefined}
                    onClick={() => navigate(target)}
                    style={{ cursor: "pointer" }}
                  >
                    <SideNavigation.ItemLabel>{t(key)}</SideNavigation.ItemLabel>
                  </SideNavigation.Item>
                );
              })}
            </SideNavigation.Group>
          </SideNavigation.Content>
          <SideNavigation.Footer>
            <LanguageControl />
            <Text textStyle="t2Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
              {t("trust.local_detail")}
            </Text>
          </SideNavigation.Footer>
        </SideNavigation.Root>
        <main className="workspace__main" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </SideNavigationProvider>
  );
}

/* One screen at a time, each fetching its own payload. A failed read replaces the screen and says
   whether saved data changed — never a blank page. */
function Screen({ path }) {
  if (path === "/") return <HomeScreen />;
  if (path === "/career") return <CareerScreen />;
  if (path === "/career/in-progress") return <InProgressScreen />;
  if (path === "/career/timeline") return <TimelineScreen />;
  if (path === "/diagnosis") return <DiagnosisScreen />;
  if (path === "/self-analysis") return <SelfAnalysisScreen />;
  if (path === "/applications") return <ApplicationsScreen />;
  if (path === "/documents") return <DocumentsScreen />;
  // The same shape the server routes on, so a hand-typed session id cannot reach the editor.
  if (/^\/work\/session-[a-f0-9]{12,64}$/.test(path)) return <WorkScreen path={path} />;
  return <NotFound path={path} />;
}

export default function App() {
  const { path } = useLocation();
  return (
    <Shell path={path}>
      <React.Suspense fallback={<LoadingState />}>
        <ScreenBoundary key={path}><Screen path={path} /></ScreenBoundary>
      </React.Suspense>
    </Shell>
  );
}

class ScreenBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return <ErrorState error={this.state.error} onRetry={() => this.setState({ error: null })} />;
    }
    return this.props.children;
  }
}
