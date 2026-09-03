import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { read, write, navigate, location } = vi.hoisted(() => ({
  read: vi.fn(), write: vi.fn(), navigate: vi.fn(), location: { search: "" },
}));

vi.mock("../api.js", () => ({ read, write }));
vi.mock("../App.jsx", () => ({ navigate, setSelection: vi.fn(), useLocation: () => location }));
vi.mock("../i18n.jsx", () => ({
  useI18n: () => ({ t: (key) => key, periodText: () => "", statusText: (value) => String(value) }),
}));

import CareerScreen, { ExperienceRevisionControl } from "./Career.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => {
  cleanup();
  read.mockReset();
  write.mockReset();
  navigate.mockReset();
  location.search = "";
});

describe("experience edit affordance", () => {
  it("opens a revision session with the evidence revision it read", async () => {
    write.mockResolvedValueOnce({ session: { session_ref: "session-revision" } });
    render(<ExperienceRevisionControl experience={{ ref: "evt-original" }} onError={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "action.edit" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/career/experiences/revise", {
      event_id: "evt-original", revision: "evt-original",
    }));
    expect(navigate).toHaveBeenCalledWith("/work/session-revision");
  });
});

describe("job seeker action budget", () => {
  const emptyCareer = {
    contexts: [], relationship_conflicts: [], unassigned_projects: [], unassigned_work: [],
  };

  it("turns one pasted career history into a draft with one submit decision", async () => {
    location.search = "?capture=1";
    read.mockResolvedValue(emptyCareer);
    write
      .mockResolvedValueOnce({ session: { session_ref: "session-import", revision: 0 }, revision: 0 })
      .mockResolvedValueOnce({ session: { session_ref: "session-import" } });
    render(<CareerScreen />);

    const source = await screen.findByLabelText("applications.document_body");
    fireEvent.change(source, { target: { value: "Acme에서 Python API 이관을 담당했다." } });
    fireEvent.click(screen.getByRole("button", { name: "action.continue" }));

    await waitFor(() => expect(write).toHaveBeenCalledTimes(2));
    expect(write).toHaveBeenNthCalledWith(1, "/api/workflows/start", { workflow: "career_inventory" });
    expect(write).toHaveBeenNthCalledWith(2, "/api/workflows/draft", {
      session_ref: "session-import",
      revision: 0,
      draft: { evidence: ["Acme에서 Python API 이관을 담당했다."] },
    });
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("/work/session-import");
  });

  it("starts an experience without forcing a project to exist first", async () => {
    location.search = "?sel=context-a";
    read.mockResolvedValue({
      contexts: [{
        ref: "context-a", label: "Acme", lifecycle: "approved", projects: [], other_experiences: [], period: {},
      }],
      relationship_conflicts: [], unassigned_projects: [], unassigned_work: [],
    });
    write.mockResolvedValueOnce({ session: { session_ref: "session-experience" } });
    render(<CareerScreen />);

    const addExperience = await screen.findByRole("button", { name: "career.add_experience" });
    fireEvent.click(addExperience);

    await waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    expect(write).toHaveBeenCalledWith("/api/workflows/start", { workflow: "career_inventory" });
    expect(navigate).toHaveBeenCalledWith("/work/session-experience");
  });
});
