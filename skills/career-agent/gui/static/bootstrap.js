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

  const postJson = (path, payload) => fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": window.japanCareerAgentCsrfToken || "",
    },
    body: JSON.stringify(payload),
  }).then((response) => {
    if (!response.ok) throw new Error("Local write unavailable");
    return response.json();
  });

  const listValue = (value) => String(value || "").split(/[\n,]/).map((item) => item.trim()).filter(Boolean);

  const readable = (item) => {
    if (item === null || item === undefined || item === "") return "Unknown";
    if (Array.isArray(item)) return item.length ? item.map(readable).join(", ") : "Reviewed empty";
    if (typeof item === "object") {
      return Object.entries(item).map(([key, child]) => `${key}: ${readable(child)}`).join(" · ");
    }
    return String(item);
  };

  const appendValues = (parent, raw, formatter = readable) => {
    if (raw === null || raw === undefined) {
      parent.append(element("p", "Unknown", "profile-unknown"));
      return;
    }
    if (Array.isArray(raw) && raw.length === 0) {
      parent.append(element("p", "Reviewed empty", "profile-unknown"));
      return;
    }
    const values = Array.isArray(raw) ? raw : [raw];
    const list = element("ul", "", "profile-list");
    values.forEach((item) => list.append(element("li", formatter(item))));
    parent.append(list);
  };

  const profileFieldLabel = (name) => name.replaceAll("_", " ");

  const renderHandoff = (payload) => {
    const handoff = payload.handoff || {};
    const panel = section("HANDOFF", "The next move stays yours.");
    panel.className += " handoff-panel";
    panel.append(element("p", value(handoff.instruction), "lede"));
    if (handoff.command) {
      const command = element("pre", "", "handoff-command");
      command.append(element("code", handoff.command));
      panel.append(command);
    }
    if (handoff.approval_required) {
      panel.append(element("p", "Approval required. The GUI has not written canonical context.", "status-row"));
    }
    return panel;
  };

  const renderSelfAnalysis = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();
    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(
      button("Home", () => fetchView("/api/home", renderHome)),
      button("Timeline", () => fetchView("/api/timeline", renderTimeline)),
      button("Projects / 재직 중", () => fetchView("/api/projects", renderProjects)),
      element("span", "자기분석", "nav-current"),
      button("棚卸し", openTanaoroshi),
      button("Cases", () => fetchView("/api/cases", renderCases)),
    );
    main.append(navigation);
    main.append(element("p", "SELF-ANALYSIS / HYPOTHESES", "section-label"));
    main.append(element("h2", "자기분석을 검토하기"));
    main.append(element("p", "가설과 Unknown을 분리해서 봅니다. GUI는 프로필을 확정하거나 저장하지 않습니다.", "lede"));

    if (payload.state !== "available") {
      const state = section("PROFILE", payload.state === "invalid" ? "Canonical profile unavailable." : "No reviewed profile yet.");
      state.append(element("p", value(payload.reason, "Run the user-led jiko-bunseki flow first."), "profile-unknown"));
      main.append(state, renderHandoff(payload));
      return;
    }

    const profile = payload.profile || {};
    const identity = section("PROFILE", value(profile.candidate_name, "Candidate"));
    identity.append(element("p", `Track: ${value(profile.track)} · Language: ${value(profile.language_preference)}`));
    const fieldStatus = element("div", "", "field-status");
    (payload.field_status || []).forEach((item) => {
      fieldStatus.append(element("p", `${profileFieldLabel(item.field)}: ${item.status}`, "status-row"));
    });
    identity.append(fieldStatus);
    main.append(identity);

    const grid = element("div", "", "dashboard-grid self-analysis-grid");
    const blocks = [
      ["INTEREST HYPOTHESES", "Interest hypotheses", profile.interest_hypotheses, (item) => `${readable(item.activity)}: ${readable(item.response_basis)} (${readable(item.confidence)})`],
      ["BEHAVIOR", "Behavior tendencies", profile.behavior_tendencies, (item) => `${readable(item.name)}: ${readable(item.response_basis)} (${readable(item.confidence)})`],
      ["EPISODES", "Evidence episodes", profile.evidence_episodes, (item) => `${readable(item.experience_type)}: ${readable(item.situation)} · ${readable(item.action)} · ${readable(item.energy_effect)}`],
      ["BARRIERS", "Perceived barriers", profile.perceived_barriers],
      ["SUPPORTS", "Perceived supports", profile.perceived_supports],
      ["VALUES", "Value candidates", profile.value_candidates],
      ["AVOIDS", "Avoid candidates", profile.avoid_candidates],
      ["QUESTIONS", "Verification questions", profile.verification_questions],
    ];
    blocks.forEach(([label, title, raw, formatter]) => {
      const block = section(label, title);
      appendValues(block, raw, formatter);
      grid.append(block);
    });
    const environment = section("ENVIRONMENT", "Environment preferences stay independent.");
    appendValues(environment, profile.environment_preferences);
    grid.append(environment);
    main.append(grid, renderHandoff(payload));
  };

  const renderTanaoroshi = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();
    const session = payload.session || {};
    const draft = payload.draft || {};
    const sessionId = session.session_id;

    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(
      button("Home", () => fetchView("/api/home", renderHome)),
      button("Timeline", () => fetchView("/api/timeline", renderTimeline)),
      button("자기분석", () => fetchView("/api/self-analysis", renderSelfAnalysis)),
      button("Projects / 재직 중", () => fetchView("/api/projects", renderProjects)),
      element("span", "棚卸し", "nav-current"),
      button("Cases", () => fetchView("/api/cases", renderCases)),
    );
    main.append(navigation);
    main.append(element("p", "EXPERIENCE / EVIDENCE", "section-label"));
    main.append(element("h2", "棚卸しを続ける"));
    main.append(element("p", "保存は下書きです。確定するまで Career Vault の証拠は変わりません.", "lede"));

    const form = element("form", "", "inventory-form");
    const controls = {};
    const addControl = (label, name, value, type = "text") => {
      const id = `tanaoroshi-${name.replaceAll(".", "-")}`;
      const wrapper = element("label", "", "form-field");
      wrapper.htmlFor = id;
      wrapper.append(element("span", label));
      const control = type === "textarea" ? element("textarea") : element("input");
      control.id = id;
      control.name = name;
      control.value = value || "";
      if (type !== "textarea") control.type = type;
      controls[name] = control;
      wrapper.append(control);
      form.append(wrapper);
    };
    addControl("무슨 일이었나요?", "summary", draft.summary, "textarea");
    addControl("역할", "role", draft.role);
    addControl("개인 기여", "individual_contribution", draft.individual_contribution, "textarea");
    addControl("행동 (쉼표 또는 줄바꿈)", "direct_actions", (draft.direct_actions || []).join("\n"), "textarea");
    addControl("결과 수치 (쉼표 또는 줄바꿈)", "metrics", (draft.metrics || []).join("\n"), "textarea");
    addControl("근거 (쉼표 또는 줄바꿈)", "evidence", (draft.evidence || []).join("\n"), "textarea");

    const nonWorkLabel = element("label", "", "checkbox-field");
    const nonWork = element("input");
    nonWork.type = "checkbox";
    nonWork.checked = draft.non_work === true;
    nonWork.name = "non_work";
    controls.non_work = nonWork;
    nonWorkLabel.append(nonWork, element("span", "직무 경험이 아님 (학업·동아리·봉사 등)"));
    form.append(nonWorkLabel);

    const confidentialLabel = element("label", "", "checkbox-field");
    const confidential = element("input");
    confidential.type = "checkbox";
    confidential.checked = draft.confidentiality?.contains_confidential === true;
    controls.contains_confidential = confidential;
    confidentialLabel.append(confidential, element("span", "기밀 정보가 포함됨"));
    form.append(confidentialLabel);

    const external = element("select");
    external.name = "external_use";
    ["unknown", "allowed", "blocked"].forEach((state) => {
      const option = element("option", state);
      option.value = state;
      option.selected = state === (draft.confidentiality?.external_use || "unknown");
      external.append(option);
    });
    controls.external_use = external;
    const externalLabel = element("label", "", "form-field");
    externalLabel.append(element("span", "외부 공개 가능 여부"), external);
    form.append(externalLabel);

    const status = element("div", "", "field-status");
    status.setAttribute("aria-live", "polite");
    (payload.field_status || []).forEach((item) => {
      status.append(element("p", `${item.status === "Confirmed" ? "✓" : "?"} ${item.label}`, "status-row"));
    });
    form.append(status);

    const message = element("p", "", "form-message");
    message.id = "tanaoroshi-status";
    message.setAttribute("role", "status");
    form.append(message);

    const collect = () => ({
      summary: controls.summary.value,
      role: controls.role.value,
      individual_contribution: controls.individual_contribution.value,
      direct_actions: listValue(controls.direct_actions.value),
      metrics: listValue(controls.metrics.value),
      evidence: listValue(controls.evidence.value),
      non_work: controls.non_work.checked,
      confidentiality: {
        contains_confidential: controls.contains_confidential.checked,
        external_use: controls.external_use.value,
      },
    });
    // What approval writes has to be on screen before the button that writes it. The proposal is
    // a snapshot of the draft, so editing the draft leaves the snapshot behind: the button is
    // removed the moment the user types, not 800ms later when the autosave lands.
    const review = element("div", "", "proposal-review");
    review.setAttribute("aria-live", "polite");
    let proposalInvalidated = false;
    const clearReview = () => {
      if (!review.firstChild) return;
      review.replaceChildren();
      proposalInvalidated = true;
    };

    let autosaveTimer;
    const scheduleAutosave = () => {
      clearReview();
      window.clearTimeout(autosaveTimer);
      autosaveTimer = window.setTimeout(() => {
        postJson("/api/draft", { session_id: sessionId, draft: collect() })
          .then(() => {
            message.textContent = proposalInvalidated
              ? "초안이 저장되었습니다. 이전 제안은 무효이니 제안을 다시 만드세요."
              : "초안이 저장되었습니다.";
          })
          .catch(() => { message.textContent = "초안 저장에 실패했습니다. 입력은 화면에 남아 있습니다."; });
      }, 800);
    };
    Object.values(controls).forEach((control) => control.addEventListener("input", scheduleAutosave));
    Object.values(controls).forEach((control) => control.addEventListener("change", scheduleAutosave));

    const checkpoint = button("체크포인트 저장", () => {
      postJson("/api/checkpoint", {
        session_id: sessionId,
        stage: "experience_evidence",
        current_item_ref: "new_experience",
        missing_fields: payload.missing_fields || [],
        completed: [],
      })
        .then(() => { message.textContent = "완료된 지점이 저장되었습니다."; })
        .catch(() => { message.textContent = "체크포인트를 저장할 수 없습니다."; });
    });
    checkpoint.className = "secondary-button";
    form.append(checkpoint);

    const proposalLabels = {
      evidence: "근거",
      role: "역할",
      scope: "범위",
      problem: "문제",
      direct_actions: "행동",
      individual_contribution: "개인 기여",
      team_result: "팀 성과",
      metrics: "결과 수치",
      confidentiality: "기밀·외부 공개",
      work_date: "시점",
    };

    const renderProposal = (result) => {
      const proposal = result.proposal || {};
      const event = proposal.event || {};
      review.replaceChildren();
      proposalInvalidated = false;
      review.append(element("p", "PROPOSAL / 승인하면 아래 내용이 확정 사실이 됩니다.", "section-label"));
      review.append(element("p", value(event.summary), "lede"));
      const detail = element("dl", "", "proposal-detail");
      const payload = event.work_event || event.experience || {};
      [["evidence", event.evidence], ...Object.entries(payload)].forEach(([key, item]) => {
        detail.append(element("dt", proposalLabels[key] || profileFieldLabel(key)));
        detail.append(element("dd", readable(item)));
      });
      review.append(detail);
      const approve = button("승인", () => postJson("/api/approve", {
        session_id: sessionId,
        proposal_id: proposal.id,
      }).then(() => {
        review.replaceChildren();
        message.textContent = "승인되었습니다.";
      }).catch(() => {
        message.textContent = "승인할 수 없습니다. 초안이 바뀌었다면 제안을 다시 만드세요.";
      }));
      approve.className = "primary-button";
      review.append(approve);
    };

    const submit = button("제안 만들기", () => {
      postJson("/api/draft", { session_id: sessionId, draft: collect() })
        .then(() => postJson("/api/proposal", { session_id: sessionId }))
        .then((result) => {
          message.textContent = "제안이 만들어졌습니다. 아래에서 확인 후 승인하세요.";
          renderProposal(result);
        })
        .catch(() => { message.textContent = "제안을 만들 수 없습니다. 비어 있는 항목을 확인하세요."; });
    });
    submit.className = "primary-button";
    form.append(submit);
    form.append(review);
    main.append(form);
  };

  // The server binds port 0, so every run is a different origin and localStorage starts empty.
  // Asking the server which sessions are resumable is the only way the browser can find work it
  // left behind. A completed session is not listed, so approving one leads to a fresh start.
  const openTanaoroshi = () => {
    fetchView("/api/sessions", (payload) => {
      const active = (payload.sessions || [])[0];
      if (active && active.session_id) {
        fetchView(
          `/api/tanaoroshi?session_id=${encodeURIComponent(active.session_id)}`,
          renderTanaoroshi,
        );
        return;
      }
      postJson("/api/tanaoroshi", {})
        .then(renderTanaoroshi)
        .catch(() => {
          const status = document.getElementById("session-status");
          if (status) status.textContent = "棚卸し 세션을 시작할 수 없습니다.";
        });
    });
  };

  const renderCases = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();
    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(
      button("Home", () => fetchView("/api/home", renderHome)),
      button("Timeline", () => fetchView("/api/timeline", renderTimeline)),
      button("자기분석", () => fetchView("/api/self-analysis", renderSelfAnalysis)),
      button("棚卸し", openTanaoroshi),
      button("Projects / 재직 중", () => fetchView("/api/projects", renderProjects)),
      element("span", "Cases", "nav-current"),
    );
    main.append(navigation);
    main.append(element("p", "COMPANY / APPLICATION / ARTIFACT", "section-label"));
    main.append(element("h2", "Keep each application in its own case."));
    main.append(element("p", "Company context is shared; application material stays scoped to one application. No canonical evidence is changed here.", "lede"));

    const caseRows = payload.cases || [];
    const artifactRows = payload.artifacts || [];
    const casesById = new Map(caseRows.map((item) => [item.case_id, item]));
    const grid = element("div", "", "dashboard-grid case-grid");
    caseRows.forEach((item) => {
      const card = section(item.kind === "company" ? "COMPANY" : "APPLICATION", value(item.label));
      card.className += " case-card";
      card.append(element("p", `Status: ${value(item.status)}`, "status-row"));
      if (item.parent_ref) {
        card.append(element("p", `Company: ${value(casesById.get(item.parent_ref)?.label)}`, "status-row"));
      }
      const attached = artifactRows.filter((artifact) => artifact.case_ref === item.case_id);
      card.append(element("p", `Artifacts: ${attached.length}`, "status-row"));
      attached.forEach((artifact) => {
        card.append(element("p", `${value(artifact.kind)} · v${value(artifact.version)} · ${value(artifact.status)}`, "status-row"));
      });
      if (item.status === "active") {
        const archive = button("Archive case", () => postJson("/api/cases/archive", { case_id: item.case_id })
          .then(() => fetchView("/api/cases", renderCases))
          .catch(() => { status.textContent = "Case archive failed."; }));
        archive.className = "secondary-button";
        card.append(archive);
      }
      grid.append(card);
    });
    if (!caseRows.length) grid.append(element("p", "No company or application cases yet.", "lede"));
    main.append(grid);

    const handoff = section("RESEARCH HANDOFF", "Run research in the CLI, then register the result.");
    handoff.append(element("p", "The GUI does not browse, call an LLM, or execute a command. Use your existing company-research workflow and bring its reviewed text back to the registration form.", "lede"));
    const command = element("pre", "", "handoff-command");
    command.append(element("code", "career-agent guided --message \"company research\" --vault \"$CAREER_VAULT\""));
    handoff.append(command);
    main.append(handoff);

    const forms = element("div", "", "case-forms");
    const status = element("p", "", "form-message");
    status.setAttribute("role", "status");

    const caseForm = element("form", "", "inventory-form");
    caseForm.append(element("p", "NEW CASE", "section-label"));
    const caseKind = element("select");
    [["company", "Company"], ["application", "Application"]].forEach(([key, label]) => {
      const option = element("option", label);
      option.value = key;
      caseKind.append(option);
    });
    const caseKindLabel = element("label", "", "form-field");
    caseKindLabel.append(element("span", "Case type"), caseKind);
    caseForm.append(caseKindLabel);
    const caseLabel = element("input");
    caseLabel.type = "text";
    caseLabel.required = true;
    const caseLabelField = element("label", "", "form-field");
    caseLabelField.append(element("span", "Company or application name"), caseLabel);
    caseForm.append(caseLabelField);
    const parent = element("select");
    const noParent = element("option", "Select a company for an application");
    noParent.value = "";
    parent.append(noParent);
    caseRows.filter((item) => item.kind === "company" && item.status !== "deleted").forEach((item) => {
      const option = element("option", item.label);
      option.value = item.case_id;
      parent.append(option);
    });
    const parentField = element("label", "", "form-field");
    parentField.append(element("span", "Parent company (application only)"), parent);
    caseForm.append(parentField);
    const jd = element("textarea");
    const jdField = element("label", "", "form-field");
    jdField.append(element("span", "JD text or source note (application only)"), jd);
    caseForm.append(jdField);
    const applicationEvidence = element("textarea");
    const applicationEvidenceField = element("label", "", "form-field");
    applicationEvidenceField.append(element("span", "Evidence refs (one per line, application only)"), applicationEvidence);
    caseForm.append(applicationEvidenceField);
    const caseSubmit = button("Create case", () => {});
    caseSubmit.type = "submit";
    caseSubmit.className = "primary-button";
    caseForm.append(caseSubmit);
    caseForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const body = { kind: caseKind.value, label: caseLabel.value };
      if (caseKind.value === "application") {
        body.parent_ref = parent.value;
        body.jd = jd.value ? { text: jd.value } : {};
        body.evidence_refs = listValue(applicationEvidence.value);
      }
      postJson("/api/cases", body)
        .then(() => { status.textContent = "Case created."; return fetchView("/api/cases", renderCases); })
        .catch(() => { status.textContent = "Case could not be created. Check the parent company."; });
    });

    const artifactForm = element("form", "", "inventory-form");
    artifactForm.append(element("p", "REGISTER ARTIFACT", "section-label"));
    const artifactCase = element("select");
    caseRows.filter((item) => item.status !== "deleted").forEach((item) => {
      const option = element("option", `${item.kind}: ${item.label}`);
      option.value = item.case_id;
      artifactCase.append(option);
    });
    const artifactCaseField = element("label", "", "form-field");
    artifactCaseField.append(element("span", "Attach to case"), artifactCase);
    artifactForm.append(artifactCaseField);
    const artifactKind = element("input");
    artifactKind.type = "text";
    artifactKind.value = "company_research";
    artifactKind.required = true;
    const artifactKindField = element("label", "", "form-field");
    artifactKindField.append(element("span", "Artifact kind"), artifactKind);
    artifactForm.append(artifactKindField);
    const artifactBody = element("textarea");
    artifactBody.required = true;
    const artifactBodyField = element("label", "", "form-field");
    artifactBodyField.append(element("span", "Artifact body"), artifactBody);
    artifactForm.append(artifactBodyField);
    const artifactEvidence = element("textarea");
    const artifactEvidenceField = element("label", "", "form-field");
    artifactEvidenceField.append(element("span", "Evidence refs (one per line)"), artifactEvidence);
    artifactForm.append(artifactEvidenceField);
    const artifactSources = element("textarea");
    const artifactSourcesField = element("label", "", "form-field");
    artifactSourcesField.append(element("span", "Source refs (one per line)"), artifactSources);
    artifactForm.append(artifactSourcesField);
    const artifactSubmit = button("Register artifact", () => {});
    artifactSubmit.type = "submit";
    artifactSubmit.className = "primary-button";
    artifactForm.append(artifactSubmit);
    artifactForm.addEventListener("submit", (event) => {
      event.preventDefault();
      postJson("/api/artifacts", {
        case_ref: artifactCase.value,
        kind: artifactKind.value,
        body: artifactBody.value,
        evidence_refs: listValue(artifactEvidence.value),
        source_refs: listValue(artifactSources.value),
      })
        .then(() => { status.textContent = "Artifact registered as a new digest-named version."; return fetchView("/api/cases", renderCases); })
        .catch(() => { status.textContent = "Artifact could not be registered."; });
    });
    forms.append(caseForm, artifactForm, status);
    main.append(forms);
  };

  const renderProjects = (payload) => {
    const main = document.getElementById("main-content");
    if (!main) return;
    main.replaceChildren();
    const navigation = element("nav", "", "view-nav");
    navigation.setAttribute("aria-label", "Views");
    navigation.append(
      button("Home", () => fetchView("/api/home", renderHome)),
      button("Timeline", () => fetchView("/api/timeline", renderTimeline)),
      button("자기분석", () => fetchView("/api/self-analysis", renderSelfAnalysis)),
      button("棚卸し", openTanaoroshi),
      button("Cases", () => fetchView("/api/cases", renderCases)),
      element("span", "Projects / 재직 중", "nav-current"),
    );
    main.append(navigation);

    const employment = payload.employment || {};
    const employmentPanel = section("EMPLOYMENT", "재직 중 상태는 사용자의 선언입니다.");
    employmentPanel.append(
      element(
        "p",
        "Employment: " + value(employment.employment_status) + " · Search: " + value(employment.job_search),
        "lede",
      ),
      element(
        "p",
        "Career status: " + value(employment.career_status) + " · Target role: " + value(employment.target_role),
      ),
      element("p", "GUI는 재직 여부를 추정하거나 변경하지 않습니다.", "status-row"),
    );
    main.append(employmentPanel);

    const list = element("div", "", "dashboard-grid projects-grid");
    (payload.projects || []).forEach((project) => {
      const card = section("PROJECT", value(project.title));
      card.className += " project-card";
      card.append(element("p", "Status: " + value(project.status), "status-row"));
      if (project.role) card.append(element("p", "Role: " + value(project.role), "status-row"));
      if (project.scope) card.append(element("p", "Scope: " + value(project.scope), "status-row"));
      const period = project.period?.from
        ? project.period.from + " → " + value(project.period.to, "present")
        : "Period Unknown";
      card.append(element("p", period, "timeline-period"));
      if (project.summary) card.append(element("p", value(project.summary), "lede"));
      (project.timeline || []).forEach((entry) => {
        card.append(element("p", value(entry.date) + " · " + value(entry.title), "timeline-entry"));
      });
      list.append(card);
    });
    if (!list.children.length) list.append(element("p", "No confirmed projects yet.", "lede"));
    main.append(list);

    const readOnly = section("READ-ONLY", "Project history stays in the approval path.");
    readOnly.append(element("p", "This screen only reads confirmed project and work-event projections. Additions and employment changes remain user-owned CLI workflows.", "lede"));
    main.append(readOnly);
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
      button("자기분석", () => fetchView("/api/self-analysis", renderSelfAnalysis)),
      button("棚卸し", openTanaoroshi),
      button("Cases", () => fetchView("/api/cases", renderCases)),
      button("Projects / 재직 중", () => fetchView("/api/projects", renderProjects)),
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
    navigation.append(
      button("Home", () => fetchView("/api/home", renderHome)),
      element("span", "Timeline", "nav-current"),
      button("자기분석", () => fetchView("/api/self-analysis", renderSelfAnalysis)),
      button("棚卸し", openTanaoroshi),
      button("Cases", () => fetchView("/api/cases", renderCases)),
      button("Projects / 재직 중", () => fetchView("/api/projects", renderProjects)),
    );
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
