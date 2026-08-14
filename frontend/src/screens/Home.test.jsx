import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { read, navigate } = vi.hoisted(() => ({ read: vi.fn(), navigate: vi.fn() }));

vi.mock("../api.js", () => ({ read, write: vi.fn() }));
vi.mock("../App.jsx", () => ({ navigate, setSelection: vi.fn(), useLocation: () => ({ search: "" }) }));
vi.mock("../i18n.jsx", () => ({
  useI18n: () => ({ t: (key) => key, dateTimeText: () => "", enumText: (_group, value) => String(value) }),
}));

import HomeScreen from "./Home.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => { cleanup(); read.mockReset(); navigate.mockReset(); });

const load = (home, sessions = { sessions: [] }) => {
  read.mockImplementation((path) => Promise.resolve(path === "/api/home" ? home : sessions));
};

describe("home attention list", () => {
  it("lists the counts the runtime already made and links each to its list", async () => {
    load({
      conflicts: { count: 0 },
      pending_approval: { count: 4 },
      unknown: { dimensions: [{ name: "a", status: "Unknown" }, { name: "b", status: "Stale" }] },
      readiness: {},
    });
    render(<HomeScreen />);

    await waitFor(() => expect(screen.getByText("home.attention_pending")).toBeTruthy());
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: "action.review" })[1]);
    expect(navigate).toHaveBeenCalledWith("/diagnosis");
  });

  it("says nothing when there is nothing to attend to", async () => {
    load({
      conflicts: { count: 0 },
      pending_approval: { count: 0 },
      unknown: { dimensions: [] },
      readiness: {},
    });
    render(<HomeScreen />);

    await waitFor(() => expect(screen.getByText("home.title")).toBeTruthy());
    expect(screen.queryByText("home.attention_title")).toBeNull();
  });

  it("keeps a conflict in its callout rather than demoting it into the list", async () => {
    load({
      conflicts: { count: 2 },
      pending_approval: { count: 0 },
      unknown: { dimensions: [] },
      readiness: {},
    });
    render(<HomeScreen />);

    // A contradiction is not one more queue item, so it must not appear as a row here.
    await waitFor(() => expect(screen.getByText("career.context_conflict_title")).toBeTruthy());
    expect(screen.queryByText("home.attention_title")).toBeNull();
  });
});
