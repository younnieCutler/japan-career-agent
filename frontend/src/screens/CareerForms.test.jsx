import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { write } = vi.hoisted(() => ({ write: vi.fn() }));

vi.mock("../api.js", () => ({ write }));
vi.mock("../App.jsx", () => ({ navigate: vi.fn() }));
vi.mock("../i18n.jsx", () => ({
  useI18n: () => ({
    t: (key) => key,
    enumText: (_group, value) => String(value),
    periodText: (period) => period?.from || "date.unknown",
  }),
}));

import { AddContext, AddProject } from "./CareerForms.jsx";

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class { observe() {} disconnect() {} };
}
if (!globalThis.CSS) globalThis.CSS = { supports: () => false };

afterEach(() => {
  cleanup();
  write.mockReset();
});

describe("career record edits", () => {
  it("sends a context revision and renders the server proposal's before and after", async () => {
    write.mockResolvedValueOnce({
      before: { label: "Old context", role: "Old role" },
      revision: "2026-08-14T00:00:00Z",
      proposal: {
        ref: "proposal-context",
        event: { experience_context: { label: "Server context", kind: "company", role: "Server role" } },
      },
    }).mockResolvedValueOnce({});
    const context = {
      ref: "case-context", context_id: "context-1", revision: "2026-08-14T00:00:00Z",
      relationship: "employer", kind: "company", label: "Old context", role: "Old role",
      summary: "Old summary", period: { from: "2020-01", to: "2020-12", current: false },
    };

    render(<AddContext contexts={[context]} existing={context} onDone={() => {}} />);
    expect(screen.getByLabelText("career.context_name").value).toBe("Old context");
    fireEvent.change(screen.getByLabelText("career.context_name"), { target: { value: "Form context" } });
    fireEvent.click(screen.getByRole("button", { name: "action.review_before_confirm" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/career/contexts", {
      context_id: "context-1", case_ref: "case-context", revision: "2026-08-14T00:00:00Z",
      label: "Form context", relationship: "employer", context_kind: "company", role: "Old role",
      summary: "Old summary", period: { from: "2020-01", to: "2020-12", current: false },
    }));
    expect(screen.getByText("Old context")).toBeTruthy();
    expect(screen.getAllByText("Server context")).not.toHaveLength(0);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "action.approve" }));
    });
    expect(write).toHaveBeenLastCalledWith("/api/career/approve", {
      case_ref: "case-context", proposal_ref: "proposal-context", revision: "2026-08-14T00:00:00Z",
    });
  });

  it("seeds a project edit and sends its identity and revision", async () => {
    write.mockResolvedValueOnce({
      before: { title: "Old project" }, revision: "2026-08-14T00:00:01Z",
      proposal: { ref: "proposal-project", event: { project: { title: "Server project" } } },
    });
    const project = {
      ref: "case-project", project_id: "project-1", revision: "2026-08-14T00:00:01Z",
      label: "Old project", role: "Developer", scope: "Old scope",
      period: { from: "2021-01", to: "2021-12", current: false },
    };

    render(<AddProject context={{ ref: "case-context", projects: [project] }} existing={project} onDone={() => {}} />);
    expect(screen.getByLabelText("career.project_name").value).toBe("Old project");
    fireEvent.change(screen.getByLabelText("career.project_scope"), { target: { value: "New scope" } });
    fireEvent.click(screen.getByRole("button", { name: "action.review_before_confirm" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/career/projects", {
      project_id: "project-1", case_ref: "case-project", revision: "2026-08-14T00:00:01Z",
      label: "Old project", role: "Developer", scope: "New scope",
      period: { from: "2021-01", to: "2021-12", current: false },
    }));
  });
});
