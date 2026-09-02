import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JudgmentDifference, JudgmentGate } from "./judgment.jsx";

const labels = {
  question: "Initial judgment",
  help: "Answer before agent analysis is shown.",
  reason: "Reason",
  continue: "Compare with agent",
  errorTitle: "Could not save",
  error: "Try again.",
  human: "Human",
  agent: "Agent",
  divergedTitle: "Different judgments",
  alignedTitle: "Same judgment",
  choices: {
    proceed: "Proceed",
    hold: "Hold",
    stop: "Stop",
    unknown: "Unknown",
  },
};

afterEach(() => cleanup());

describe("JudgmentGate", () => {
  it("does not reveal agent analysis before the initial human judgment is persisted", async () => {
    let resolveSave;
    const onSubmit = vi.fn(() => new Promise((resolve) => { resolveSave = resolve; }));
    render(
      <JudgmentGate labels={labels} onSubmit={onSubmit}>
        <div>agent-analysis-visible</div>
      </JudgmentGate>,
    );

    expect(screen.queryByText("agent-analysis-visible")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Hold" }));
    fireEvent.click(screen.getByRole("button", { name: "Compare with agent" }));

    expect(onSubmit).toHaveBeenCalledWith({ decision: "hold", reasons: [] });
    expect(screen.queryByText("agent-analysis-visible")).toBeNull();

    resolveSave();
    await waitFor(() => expect(screen.getByText("agent-analysis-visible")).toBeTruthy());
  });

  it("keeps the analysis hidden when persistence fails", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("write failed"));
    render(
      <JudgmentGate labels={labels} onSubmit={onSubmit}>
        <div>agent-analysis-visible</div>
      </JudgmentGate>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Proceed" }));
    fireEvent.click(screen.getByRole("button", { name: "Compare with agent" }));

    await waitFor(() => expect(screen.getByText("Could not save")).toBeTruthy());
    expect(screen.queryByText("agent-analysis-visible")).toBeNull();
  });

  it("shows whether the human and agent assessments diverge", () => {
    const { rerender } = render(
      <JudgmentDifference humanDecision="hold" agentDecision="proceed" labels={labels} />,
    );
    expect(screen.getByText("Different judgments")).toBeTruthy();
    rerender(<JudgmentDifference humanDecision="hold" agentDecision="hold" labels={labels} />);
    expect(screen.getByText("Same judgment")).toBeTruthy();
  });
});
