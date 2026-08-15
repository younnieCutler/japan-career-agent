/* The rail has to say which screen you are on.

   A source-string check cannot see this: `aria-current` was spelled correctly in App.jsx for as
   long as the rail marked nothing, because SEED's `SideNavigation.Item` accepts `current` and
   drops unknown attributes. Only a render asserts what the browser and a screen reader receive. */

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./i18n.jsx", () => ({
  useI18n: () => ({ t: (key) => key, language: "ko" }),
}));
vi.mock("./api.js", () => ({ read: vi.fn(() => new Promise(() => {})), write: vi.fn() }));

import App from "./App.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;
// SEED's side navigation observes its own scroll container and a width breakpoint; jsdom ships
// neither API.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: true,
    media: query,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
    dispatchEvent: () => false,
    onchange: null,
  });
}

afterEach(cleanup);

const currentItems = (path) => {
  window.history.pushState({}, "", path);
  render(<App />);
  return screen.getAllByRole("button")
    .filter((node) => node.getAttribute("aria-current") === "page")
    .map((node) => node.textContent);
};

describe("side navigation current view", () => {
  it("marks the open screen, and only that one, in the accessibility tree", () => {
    expect(currentItems("/diagnosis")).toEqual(["nav.diagnosis"]);
  });

  it("keeps the career item current while inside a capture session", () => {
    // `/work/...` is reached from the career screen, so the rail must not go blank there.
    expect(currentItems("/work/session-aaaaaaaaaaaa")).toEqual(["nav.career"]);
  });
});
