import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { write } = vi.hoisted(() => ({ write: vi.fn() }));

vi.mock("../api.js", () => ({ read: vi.fn(), write }));
vi.mock("../i18n.jsx", () => ({ useI18n: () => ({ t: (key) => key, enumText: (_group, value) => String(value) }) }));

import { AddCompany } from "./Applications.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => write.mockReset());

describe("company edit", () => {
  it("does not ask to confirm a company against itself", async () => {
    const onDone = vi.fn();
    const confirm = vi.spyOn(window, "confirm");
    write.mockResolvedValueOnce({});
    const company = { ref: "company-1", label: "Acme", revision: "2026-08-14T00:00:00Z" };
    render(<AddCompany companies={[company]} existing={company} onDone={onDone} />);

    fireEvent.click(screen.getByRole("button", { name: "action.save" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/applications/companies", {
      case_ref: "company-1", revision: "2026-08-14T00:00:00Z", label: "Acme",
    }));
    expect(confirm).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalledOnce();
    confirm.mockRestore();
  });
});
