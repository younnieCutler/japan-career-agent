import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { write, navigate } = vi.hoisted(() => ({ write: vi.fn(), navigate: vi.fn() }));

vi.mock("../api.js", () => ({ read: vi.fn(), write }));
vi.mock("../App.jsx", () => ({ navigate, setSelection: vi.fn(), useLocation: () => ({ search: "" }) }));
vi.mock("../i18n.jsx", () => ({ useI18n: () => ({ t: (key) => key, periodText: () => "" }) }));

import { ExperienceRevisionControl } from "./Career.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => { write.mockReset(); navigate.mockReset(); });

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
