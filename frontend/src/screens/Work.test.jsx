import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { write } = vi.hoisted(() => ({ write: vi.fn() }));

vi.mock("../api.js", () => ({ read: vi.fn(), write }));
vi.mock("../App.jsx", () => ({ navigate: vi.fn(), setLeaveGuard: vi.fn() }));
vi.mock("../i18n.jsx", () => ({
  useI18n: () => ({ t: (key) => key, enumText: (_group, value) => String(value), periodText: () => "" }),
}));
vi.mock("../evidence.jsx", () => ({ StatusChip: () => null }));
vi.mock("../components/States.jsx", () => ({ ErrorState: () => null, LoadingState: () => null, useAsync: () => ({}) }));
vi.mock("../review.jsx", () => ({
  ApprovalDialog: ({ before }) => <div data-testid="approval-before">{before?.summary}</div>,
  FIELD_LABELS: new Set(), HIDDEN_REVIEW_FIELDS: new Set(), Value: () => null,
}));

import { CaptureForm } from "./Work.jsx";

if (!globalThis.ResizeObserver) globalThis.ResizeObserver = class { observe() {} disconnect() {} };
if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => write.mockReset());

describe("experience revision review", () => {
  it("passes the server review-before snapshot to approval", async () => {
    write.mockResolvedValueOnce({
      revision: 1,
      review_before: { summary: "Original evidence" },
      proposal: { ref: "proposal-revision", event: { work_event: {}, claim_summary: "Replacement" } },
    });
    render(<CaptureForm payload={{
      revision: 0,
      draft: { summary: "Replacement", outcome_state: "unknown", confidentiality: {} },
      session: { session_ref: "session-1", status: "draft", subject: {} },
    }} onReload={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "action.review_before_confirm" }));

    await waitFor(() => expect(screen.getByTestId("approval-before").textContent).toBe("Original evidence"));
  });
});
