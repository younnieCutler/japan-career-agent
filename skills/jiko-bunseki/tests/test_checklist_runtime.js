const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { buildSubmission, resolveScaleSelection } = require("../checklist_runtime.js");

assert.equal(resolveScaleSelection("3", false, false), undefined);
assert.equal(resolveScaleSelection("3", true, false), "3");
assert.equal(resolveScaleSelection("3", true, true), "unknown");
assert.equal(resolveScaleSelection("5", true, false), "5");

function confidenceSubmission(selection) {
  return buildSubmission({
    behavior_tendencies: {},
    environment_preferences: {},
    learning_confidence: selection,
    episodes: []
  });
}

const numericConfidence = confidenceSubmission(resolveScaleSelection("5", true, false));
assert.equal(numericConfidence.career_self_efficacy.learning_confidence, 5);
assert.equal(
  numericConfidence.unanswered_fields.includes("career_self_efficacy.learning_confidence"),
  false
);

const untouchedConfidence = confidenceSubmission(resolveScaleSelection("3", false, false));
assert.equal(untouchedConfidence.career_self_efficacy.learning_confidence, null);
assert.ok(untouchedConfidence.unanswered_fields.includes("career_self_efficacy.learning_confidence"));

const unknownConfidence = confidenceSubmission(resolveScaleSelection("3", false, true));
assert.equal(unknownConfidence.career_self_efficacy.learning_confidence, null);
assert.ok(unknownConfidence.explicit_unknown_fields.includes("career_self_efficacy.learning_confidence"));

const result = buildSubmission({
  name: "  Test User  ",
  language: "ko",
  track: "chuto",
  behavior_tendencies: { initiative: "5", analysis: undefined },
  environment_preferences: { autonomy: "unknown", relatedness: undefined },
  learning_confidence: "unknown",
  outcome_expectation: "  기대  ",
  goal: "",
  episodes: [
    { id: "episode-a", situation: "상황", action: "행동", experience_type: "project", energy_reason: "" },
    { id: "episode-b", unknown: true }
  ],
  interest_activities: { values: ["build"], explicit_unknown: false },
  perceived_barriers: { values: [], explicit_unknown: true },
  perceived_supports: { values: [], explicit_unknown: false },
  value_candidates: { values: [], explicit_unknown: false },
  avoid_candidates: { values: [], explicit_unknown: false }
});

const simultaneous = buildSubmission({
  behavior_tendencies: { initiative: "5", analysis: "5" },
  environment_preferences: {},
  episodes: []
});
assert.equal(simultaneous.behavior_tendencies.initiative, 5);
assert.equal(simultaneous.behavior_tendencies.analysis, 5);

assert.equal(result.name, "Test User");
assert.equal(result.behavior_tendencies.initiative, 5);
assert.equal(result.behavior_tendencies.analysis, null);
assert.ok(result.unanswered_fields.includes("behavior_tendencies.analysis"));
assert.ok(result.explicit_unknown_fields.includes("environment_preferences.autonomy"));
assert.ok(result.explicit_unknown_fields.includes("career_self_efficacy.learning_confidence"));
assert.equal(result.career_self_efficacy.outcome_expectation, "기대");
assert.ok(result.unanswered_fields.includes("career_self_efficacy.goal"));
assert.deepEqual(result.interest_activities, ["build"]);
assert.deepEqual(result.perceived_barriers, []);
assert.ok(result.explicit_unknown_fields.includes("perceived_barriers"));
assert.deepEqual(result.perceived_supports, []);
assert.ok(result.unanswered_fields.includes("perceived_supports"));
assert.deepEqual(result.value_candidates, []);
assert.ok(result.unanswered_fields.includes("value_candidates"));
assert.equal(result.episodes.length, 1);
assert.ok(result.unanswered_fields.includes("episodes.episode-a.energy_reason"));
assert.ok(result.explicit_unknown_fields.includes("episodes.episode-b"));
assert.equal(result.submission_version, 2);

const html = fs.readFileSync(path.join(__dirname, "..", "checklist.html"), "utf8");
for (const forbidden of ["fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon"]) {
  assert.equal(html.toLowerCase().includes(forbidden.toLowerCase()), false, forbidden);
}
assert.equal(html.includes("./checklist_runtime.js"), true);
console.log("OK: executable Jiko checklist export contract passed");
