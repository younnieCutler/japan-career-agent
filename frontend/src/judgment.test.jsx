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

  it("keeps the analysis hidden when persistence fails and permits retry", async () => {
    const onSubmit = vi.fn()
      .mockRejectedValueOnce(new Error("write failed"))
      .mockResolvedValueOnce(undefined);
    render(
      <JudgmentGate labels={labels} onSubmit={onSubmit}>
        <div>agent-analysis-visible</div>
      </JudgmentGate>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Proceed" }));
    fireEvent.click(screen.getByRole("button", { name: "Compare with agent" }));

    await waitFor(() => expect(screen.getByText("Could not save")).toBeTruthy());
    expect(screen.queryByText("agent-analysis-visible")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Compare with agent" }));
    await waitFor(() => expect(screen.getByText("agent-analysis-visible")).toBeTruthy());
    expect(onSubmit).toHaveBeenCalledTimes(2);
  });

  it("guards same-tick duplicate submit while persistence is pending", async () => {
    let resolveSave;
    const onSubmit = vi.fn(() => new Promise((resolve) => { resolveSave = resolve; }));
    render(
      <JudgmentGate labels={labels} onSubmit={onSubmit}>
        <div>agent-analysis-visible</div>
      </JudgmentGate>,
    );
    fireEvent.click(screen.getByRole("radio", { name: "Hold" }));
    const submit = screen.getByRole("button", { name: "Compare with agent" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    resolveSave();
    await waitFor(() => expect(screen.getByText("agent-analysis-visible")).toBeTruthy());
  });

  it("implements radio-group arrow navigation and unique labels for multiple gates", () => {
    const noop = vi.fn().mockResolvedValue(undefined);
    render(
      <>
        <JudgmentGate labels={labels} onSubmit={noop}><span>one</span></JudgmentGate>
        <JudgmentGate labels={labels} onSubmit={noop}><span>two</span></JudgmentGate>
      </>,
    );
    const groups = screen.getAllByRole("radiogroup", { name: "Initial judgment" });
    expect(groups).toHaveLength(2);
    expect(groups[0].getAttribute("aria-labelledby")).not.toBe(groups[1].getAttribute("aria-labelledby"));

    const radios = screen.getAllByRole("radio").slice(0, 4);
    radios[0].focus();
    fireEvent.keyDown(radios[0], { key: "ArrowRight" });
    expect(radios[1].getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(radios[1]);
    fireEvent.keyDown(radios[1], { key: "End" });
    expect(radios[3].getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(radios[3]);
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
