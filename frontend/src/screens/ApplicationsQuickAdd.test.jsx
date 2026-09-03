import { describe, expect, it } from "vitest";
import { postingFields, recommendEvidence } from "./Applications.jsx";

describe("JD quick add", () => {
  it("fills company and position only from explicit labelled lines", () => {
    expect(postingFields("会社名: Acme\n職種：Platform Engineer\nPython, AWS")).toEqual({
      company: "Acme", position: "Platform Engineer",
    });
    expect(postingFields("Acme is hiring a Platform Engineer for Python work.")).toEqual({
      company: "", position: "",
    });
  });

  it("recommends only shareable evidence with actual posting overlap", () => {
    const options = [
      { refs: ["a"], label: "Python API migration", context: "Acme", sharing: "available" },
      { refs: ["b"], label: "AWS operations", context: "Other", sharing: "available" },
      { refs: ["c"], label: "Python secret project", context: "Other", sharing: "blocked" },
      { refs: ["d"], label: "Unrelated design work", context: "Other", sharing: "available" },
    ];
    expect(recommendEvidence("Python AWS", options)).toEqual(["a", "b"]);
    expect(recommendEvidence("Kubernetes", options)).toEqual([]);
  });
});
