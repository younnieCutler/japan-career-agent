/* The dropdown has to actually open.

   Every other client contract in this repository is checked by reading `frontend/src` as text,
   which is why this regression shipped: `Choice` composed SEED's Select without `Select.Positioner`
   — the part that owns the floating portal and the positioner ref — so every dropdown in the
   product rendered its current value as fixed text and opened nothing. A source-reading test saw
   `<Choice>` present and passed.

   These render the real component in a DOM and assert on behaviour, so the composition cannot be
   wrong in a way that still looks right in a diff. */

import React from "react";
import { render, screen, act, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Choice } from "./Fields.jsx";

const OPTIONS = [["ko", "한국어"], ["ja", "日本語"], ["en", "English"]];

const settle = () => act(async () => {});

afterEach(cleanup);

describe("Choice", () => {
  it("shows the selected option's own text on the trigger", async () => {
    render(<Choice value="ja" onChange={() => {}} options={OPTIONS} label="language" />);
    await settle();
    expect(screen.getByRole("combobox").textContent).toContain("日本語");
  });

  it("renders every option once opened", async () => {
    render(<Choice value="ko" onChange={() => {}} options={OPTIONS} label="language" />);
    await settle();

    await act(async () => {
      screen.getByRole("combobox").click();
    });

    for (const [, text] of OPTIONS) {
      expect(screen.getByRole("option", { name: text })).toBeTruthy();
    }
  });

  /* The one that catches the regression. Opening worked all along — the state machine is SEED's —
     so an "are the options in the document" assertion passes either way. What broke was where they
     were: rendered inline beside the field rather than through the portal, the split pane's own
     `overflow` clipped them and the control read as inert. jsdom has no layout and cannot see the
     clipping, but it can see the portal, which is the thing that was missing. */
  it("escapes its pane instead of rendering inline where an overflow can clip it", async () => {
    const { container } = render(
      <Choice value="ko" onChange={() => {}} options={OPTIONS} label="language" />,
    );
    await settle();

    await act(async () => {
      screen.getByRole("combobox").click();
    });

    const option = screen.getByRole("option", { name: "English" });
    expect(container.contains(option)).toBe(false);
    expect(option.closest("[class*='seed-select__positioner']")).toBeTruthy();
  });

  it("reports the chosen key as a scalar, not SEED's array", async () => {
    const onChange = vi.fn();
    render(<Choice value="ko" onChange={onChange} options={OPTIONS} label="language" />);
    await settle();

    await act(async () => {
      screen.getByRole("combobox").click();
    });
    await act(async () => {
      screen.getByRole("option", { name: "English" }).click();
    });

    expect(onChange).toHaveBeenCalledWith("en");
  });
});
