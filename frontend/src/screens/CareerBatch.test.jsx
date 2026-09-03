import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { write } = vi.hoisted(() => ({ write: vi.fn() }));

vi.mock("../api.js", () => ({ write }));
vi.mock("../i18n.jsx", () => ({ useI18n: () => ({ t: (key) => key }) }));
vi.mock("../review.jsx", () => ({ SnapshotView: ({ event }) => <div>{event.project?.title || event.experience_context?.label}</div> }));

import CareerBatch from "./CareerBatch.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => { cleanup(); write.mockReset(); });

describe("career batch review", () => {
  it("shows every server proposal before one approval applies them in order", async () => {
    write
      .mockResolvedValueOnce({ proposal: { ref: "proposal-a", event: { experience_context: { label: "Acme" } } }, revision: "r1" })
      .mockResolvedValueOnce({ proposal: { ref: "proposal-b", event: { project: { title: "Migration" } } }, revision: "r2" })
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({});
    const onDone = vi.fn();
    render(<CareerBatch payload={{ contexts: [
      { ref: "context-a", label: "Acme", lifecycle: "draft", revision: "c1", projects: [] },
      { ref: "context-b", label: "Other", lifecycle: "approved", revision: "c2", projects: [
        { ref: "project-b", label: "Migration", lifecycle: "draft", revision: "p1" },
      ] },
    ] }} onDone={onDone} />);

    fireEvent.click(screen.getByRole("button", { name: "action.review_before_confirm" }));

    await waitFor(() => expect(screen.getByText("Acme")).toBeTruthy());
    expect(screen.getByText("Migration")).toBeTruthy();
    expect(write).toHaveBeenNthCalledWith(1, "/api/career/propose", { case_ref: "context-a", revision: "c1" });
    expect(write).toHaveBeenNthCalledWith(2, "/api/career/propose", { case_ref: "project-b", revision: "p1" });

    fireEvent.click(screen.getByRole("button", { name: "action.approve" }));

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
    expect(write).toHaveBeenNthCalledWith(3, "/api/career/approve", {
      case_ref: "context-a", proposal_ref: "proposal-a", revision: "r1",
    });
    expect(write).toHaveBeenNthCalledWith(4, "/api/career/approve", {
      case_ref: "project-b", proposal_ref: "proposal-b", revision: "r2",
    });
  });

  it("does not offer a relationship-conflicted project for batch approval", () => {
    render(<CareerBatch payload={{ contexts: [{
      ref: "context-a", label: "Acme", lifecycle: "approved", revision: "c1", projects: [{
        ref: "project-a", label: "Conflicted", lifecycle: "draft", revision: "p1", relationship_conflict: true,
      }],
    }] }} onDone={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "action.review_before_confirm" })).toBeNull();
    expect(write).not.toHaveBeenCalled();
  });
});
