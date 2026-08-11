(() => {
  const element = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  };

  const value = (item, fallback = "Unknown") => (
    item === null || item === undefined || item === "" ? fallback : String(item)
  );

  const button = (label, action) => {
    const node = element("button", label, "nav-button");
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  };

  const section = (label, title) => {
    const node = element("section", "", "dashboard-section");
    node.append(element("p", label, "section-label"), element("h2", title));
    return node;
  };

  const renderHome = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();

    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(
      button("Home", () => renderHome(payload)),
      button("Timeline", () => fetchView("/api/timeline", renderTimeline)),
    );
    main.append(navigation);

    const caseSection = section("CASE", "Your record, as it stands.");
    const caseData = payload.case || {};
    caseSection.append(
      element("p", `${value(caseData.target_role, "Target role not set")} · ${value(caseData.career_status)}`, "lede"),
      element("p", `Employment: ${value(caseData.employment_status)} · Search: ${value(caseData.job_search)}`),
    );
    main.append(caseSection);

    const grid = element("div", "", "dashboard-grid");
    const readiness = section("READINESS", "Independent signals.");
    (payload.readiness?.dimensions ? Object.entries(payload.readiness.dimensions) : []).forEach(([name, state]) => {
      readiness.append(element("p", `${name}: ${value(state)}`, "status-row"));
    });
    grid.append(readiness);

    const pending = section("PENDING", "Waiting for your decision.");
    pending.append(element("p", `${value(payload.pending_approval?.count, "0")} proposal(s) await approval.`));
    grid.append(pending);

    const unknown = section("UNKNOWN / CONFLICT", "Gaps stay visible.");
    const unknownCount = payload.unknown?.dimensions?.length || 0;
    const conflictCount = payload.conflicts?.count || 0;
    unknown.append(element("p", `${unknownCount} dimension(s) need evidence. ${conflictCount} conflict(s) need review.`));
    grid.append(unknown);

    const next = section("NEXT WORK", "Choose the next honest step.");
    (payload.next_work?.actions || []).slice(0, 6).forEach((action) => {
      next.append(element("p", value(action.label), "status-row"));
    });
    grid.append(next);
    main.append(grid);
  };

  const renderTimeline = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();
    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(button("Home", () => fetchView("/api/home", renderHome)), element("span", "Timeline", "nav-current"));
    main.append(navigation);
    main.append(element("h2", "Timeline"));
    const list = element("div", "", "timeline-list");
    (payload.sections || []).forEach((item) => {
      const article = element("article", "", "timeline-item");
      const period = item.period?.from ? `${item.period.from} → ${value(item.period.to, "present")}` : "Period Unknown";
      article.append(element("p", value(item.kind).toUpperCase(), "section-label"));
      article.append(element("h3", value(item.label)));
      article.append(element("p", period, "timeline-period"));
      (item.entries || []).forEach((entry) => {
        article.append(element("p", `${value(entry.date)} · ${value(entry.title)}`, "timeline-entry"));
      });
      list.append(article);
    });
    if (!list.children.length) list.append(element("p", "No confirmed timeline entries yet.", "lede"));
    main.append(list);
  };

  const fetchView = (path, render) => {
    fetch(path, { credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) throw new Error("Read model unavailable");
        return response.json();
      })
      .then(render)
      .catch(() => {
        const status = document.getElementById("session-status");
        if (status) status.textContent = "The local read model could not be loaded.";
      });
  };

  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get("t");
  if (!token) return;

  fetch("/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  })
    .then((response) => {
      if (!response.ok) throw new Error("Session bootstrap failed");
      return response.json();
    })
    .then((session) => {
      window.japanCareerAgentCsrfToken = session.csrf_token;
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      const status = document.getElementById("session-status");
      if (status) status.textContent = "Secure local session ready.";
      fetchView("/api/home", renderHome);
    })
    .catch(() => {
      const status = document.getElementById("session-status");
      if (status) status.textContent = "The local session could not be opened. Close this tab and try again.";
    });
})();
