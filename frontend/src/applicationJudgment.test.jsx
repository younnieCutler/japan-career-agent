import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api.js", () => ({ read: vi.fn(), write: vi.fn() }));

import { read, write } from "./api.js";
import { ApplicationJudgment } from "./applicationJudgment.jsx";
import { I18nProvider } from "./i18n.jsx";


const messages = {
  "judgment.title": "Application judgment",
  "judgment.intro": "Human first",
  "judgment.question": "Initial judgment",
  "judgment.help": "Answer before Agent analysis",
  "judgment.reason": "Reason",
  "judgment.submit_initial": "Save initial",
  "judgment.choice.proceed": "Proceed",
  "judgment.choice.hold": "Hold",
  "judgment.choice.stop": "Stop",
  "judgment.choice.unknown": "Unknown",
  "judgment.save_failed": "Could not save",
  "judgment.initial_title": "Human initial",
  "judgment.waiting_title": "Waiting for Agent",
  "judgment.waiting_body": "Agent assessment is not recorded yet.",
  "judgment.agent_title": "Agent",
  "judgment.confidence": "Confidence",
  "judgment.reasons": "Reasons",
  "judgment.unknowns": "Unknowns",
  "judgment.evidence_count": "{count} evidence refs",
  "judgment.no_reasons": "No reasons",
  "judgment.no_unknowns": "No unknowns",
  "judgment.aligned": "Aligned",
  "judgment.diverged": "Diverged",
  "judgment.final_title": "Final judgment",
  "judgment.final_intro": "Human decides",
  "judgment.final_reason": "Final reason",
  "judgment.submit_final": "Save final",
  "judgment.outcome_title": "Outcome",
  "judgment.outcome_intro": "Record later",
  "judgment.outcome_reason": "Outcome note",
  "judgment.submit_outcome": "Save outcome",
  "judgment.new_round": "Start new",
  "state.loading": "Loading",
  "error.SAVE_FAILED": "Save failed",
  "error.READ_FAILED": "Read failed",
  "enum.confidence.medium": "Medium",
  "common.other": "Other",
};

const wrapper = (node) => (
  <I18nProvider value={{ language: "en", messages }}>{node}</I18nProvider>
);

const initial = {
  judgment_id: "jdg-1",
  subject: "application",
  target_ref: "case-application-1",
  impact: "l3",
  human_initial: { decision: "hold", reasons: ["scope unclear"], created_at: "2026-09-02T00:00:00Z" },
  agent_assessment: null,
  human_final: null,
  outcome: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => cleanup());

describe("ApplicationJudgment", () => {
  it("persists the human view without sending an impact and only then shows the waiting state", async () => {
    read.mockResolvedValue({ judgments: [] });
    write.mockResolvedValue(initial);
    render(wrapper(<ApplicationJudgment positionRef="case-application-1" />));

    await waitFor(() => expect(screen.getByRole("radio", { name: "Hold" })).toBeTruthy());
    expect(screen.queryByText("Waiting for Agent")).toBeNull();

    fireEvent.click(screen.getByRole("radio", { name: "Hold" }));
    fireEvent.click(screen.getByRole("button", { name: "Save initial" }));

    await waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    expect(write.mock.calls[0][0]).toBe("/api/judgments/initial");
    expect(write.mock.calls[0][1]).toEqual({
      subject: "application",
      target_ref: "case-application-1",
      decision: "hold",
      reasons: [],
    });
    expect(write.mock.calls[0][1]).not.toHaveProperty("impact");
    await waitFor(() => expect(screen.getByText("Waiting for Agent")).toBeTruthy());
  });

  it("shows the human-Agent difference and records a human final decision", async () => {
    read.mockResolvedValue({
      judgments: [{
        ...initial,
        agent_assessment: {
          recommendation: "proceed",
          confidence: "medium",
          reasons: ["evidence fits"],
          unknowns: ["allocation"],
          evidence_ref_count: 2,
        },
      }],
    });
    write.mockResolvedValue({});
    render(wrapper(<ApplicationJudgment positionRef="case-application-1" />));

    await waitFor(() => expect(screen.getByText("Diverged")).toBeTruthy());
    expect(screen.getByText("2 evidence refs")).toBeTruthy();

    const finalGroup = screen.getByText("Final judgment").closest("form");
    expect(finalGroup).toBeTruthy();
    fireEvent.click(screen.getAllByRole("radio", { name: "Proceed" }).at(-1));
    fireEvent.click(screen.getByRole("button", { name: "Save final" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith(
      "/api/judgments/final",
      { judgment_id: "jdg-1", decision: "proceed", reasons: [] },
    ));
  });
});
