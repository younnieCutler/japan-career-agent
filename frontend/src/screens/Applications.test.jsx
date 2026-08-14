import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { read, write } = vi.hoisted(() => ({ read: vi.fn(), write: vi.fn() }));

vi.mock("../api.js", () => ({ read, write }));
vi.mock("../i18n.jsx", () => ({ useI18n: () => ({ t: (key) => key, enumText: (_group, value) => String(value) }) }));

import { AddCompany, AddDocument, AddPosition, AddResearch } from "./Applications.jsx";

if (!globalThis.CSS) globalThis.CSS = {};
if (!globalThis.CSS.supports) globalThis.CSS.supports = () => false;

afterEach(() => { cleanup(); read.mockReset(); write.mockReset(); });

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

describe("application edit", () => {
  it("preserves provenance-only fields and does not offer a parent-company change", async () => {
    write.mockResolvedValueOnce({});
    const onDone = vi.fn();
    const view = render(<AddPosition
      payload={{ companies: [{ ref: "company-1", label: "Acme", status: "active" }], evidence_options: [] }}
      existing={{
        ref: "application-1", parent_ref: "company-1", label: "Backend", updated_at: "2026-08-14T00:00:00Z",
        jd: { text: "Python" }, selected_evidence_refs: [],
      }}
      onDone={onDone}
    />);

    expect(screen.getByText("Acme")).toBeTruthy();
    expect(screen.queryByRole("combobox")).toBeNull();
    fireEvent.click(view.getByRole("button", { name: "action.save" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/applications/positions", {
      case_ref: "application-1", revision: "2026-08-14T00:00:00Z", label: "Backend",
      jd: { text: "Python" }, evidence_refs: [],
    }));
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("does not present immutable research sources in an edit form", () => {
    read.mockResolvedValueOnce({ body: "Existing research" });
    render(<AddResearch position={{ ref: "application-1" }} existing={{ ref: "research-1", revision: "r1" }} onDone={vi.fn()} />);

    expect(screen.queryByText("applications.sources")).toBeNull();
  });

  it("requires an explicit stale-evidence replacement before saving", async () => {
    write.mockResolvedValueOnce({});
    const view = render(<AddPosition
      payload={{
        companies: [{ ref: "company-1", label: "Acme", status: "active" }],
        evidence_options: [{ refs: ["evidence-b"], label: "Corrected delivery", context: "Acme", sharing: "available" }],
      }}
      existing={{
        ref: "application-1", parent_ref: "company-1", label: "Backend", updated_at: "2026-08-14T00:00:00Z",
        jd: {}, selected_evidence_refs: ["evidence-a"],
        stale_evidence: [{ ref: "evidence-a", replacement_ref: "evidence-b" }],
      }}
      onDone={vi.fn()}
    />);

    expect(screen.getByText("applications.stale_evidence")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "applications.use_replacement" }));
    fireEvent.click(view.getByRole("button", { name: "action.save" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/applications/positions", {
      case_ref: "application-1", revision: "2026-08-14T00:00:00Z", label: "Backend",
      jd: {}, evidence_refs: ["evidence-b"],
    }));
  });
});

describe("document edit", () => {
  const existing = {
    ref: "artifact-1", revision: "2026-08-14T00:00:00Z", type: "resume", status: "current",
  };

  it("rewrites the same document instead of filing a second one", async () => {
    read.mockResolvedValueOnce({ body: "First draft" });
    write.mockResolvedValueOnce({});
    const onDone = vi.fn();
    const view = render(<AddDocument
      position={{ ref: "application-1", selected_evidence_count: 2 }}
      existing={existing}
      onDone={onDone}
    />);

    await waitFor(() => expect(screen.getByDisplayValue("First draft")).toBeTruthy());
    fireEvent.click(view.getByRole("button", { name: "action.save" }));

    await waitFor(() => expect(write).toHaveBeenCalledWith("/api/applications/documents", {
      artifact_id: "artifact-1", revision: "2026-08-14T00:00:00Z", body: "First draft",
    }));
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("does not offer to change what a rewrite carries over", async () => {
    read.mockResolvedValueOnce({ body: "First draft" });
    render(<AddDocument
      position={{ ref: "application-1", selected_evidence_count: 2 }}
      existing={existing}
      onDone={vi.fn()}
    />);

    // Kind, sources, and evidence follow the previous version. Offering them would suggest a
    // rewrite can change what an already-generated document rests on.
    await waitFor(() => expect(screen.getByDisplayValue("First draft")).toBeTruthy());
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByText("applications.sources")).toBeNull();
    expect(screen.queryByText("applications.document_evidence_help")).toBeNull();
  });

  it("asks for a document type only when there is no document yet", () => {
    render(<AddDocument position={{ ref: "application-1" }} onDone={vi.fn()} />);

    expect(screen.getByRole("combobox")).toBeTruthy();
    expect(screen.getByText("applications.sources")).toBeTruthy();
    expect(read).not.toHaveBeenCalled();
  });
});
