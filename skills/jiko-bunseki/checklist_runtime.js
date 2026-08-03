(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.JikoChecklist = api;
})(globalThis, function () {
  function collectScale(selection, field, unanswered, explicitUnknown) {
    if (selection === undefined) {
      unanswered.push(field);
      return null;
    }
    if (selection === "unknown") {
      explicitUnknown.push(field);
      return null;
    }
    return Number(selection);
  }

  function resolveScaleSelection(value, touched, explicitUnknown) {
    if (explicitUnknown) return "unknown";
    return touched ? value : undefined;
  }

  function collectMulti(input, field, unanswered, explicitUnknown) {
    const values = Array.isArray(input && input.values) ? input.values : [];
    if (!values.length && input && input.explicit_unknown) {
      explicitUnknown.push(field);
      return [];
    }
    if (!values.length) unanswered.push(field);
    return values;
  }

  function collectText(value, field, unanswered) {
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) unanswered.push(field);
    return text || null;
  }

  function collectEpisode(input, prefix, unanswered, explicitUnknown) {
    const field = `episodes.${prefix}`;
    if (input && input.unknown) {
      explicitUnknown.push(field);
      return null;
    }
    const values = {
      id: prefix,
      experience_type: input && input.experience_type ? input.experience_type : null,
      situation: input && typeof input.situation === "string" ? input.situation.trim() || null : null,
      action: input && typeof input.action === "string" ? input.action.trim() || null : null,
      energy_reason: input && typeof input.energy_reason === "string" ? input.energy_reason.trim() || null : null
    };
    const touched = Object.entries(values).some(([key, value]) => key !== "id" && value !== null);
    if (!touched) {
      unanswered.push(field);
      return null;
    }
    Object.entries(values).forEach(([key, value]) => {
      if (key !== "id" && value === null) unanswered.push(`${field}.${key}`);
    });
    return values;
  }

  function collectScales(selections, fieldPrefix, unanswered, explicitUnknown) {
    return Object.fromEntries(Object.entries(selections || {}).map(([id, selection]) => [
      id,
      collectScale(selection, `${fieldPrefix}.${id}`, unanswered, explicitUnknown)
    ]));
  }

  function buildSubmission(input) {
    const unanswered = [];
    const explicitUnknown = [];
    const behaviorTendencies = collectScales(
      input.behavior_tendencies, "behavior_tendencies", unanswered, explicitUnknown
    );
    const environmentPreferences = collectScales(
      input.environment_preferences, "environment_preferences", unanswered, explicitUnknown
    );
    const episodes = (input.episodes || [])
      .map((episode) => collectEpisode(episode, episode.id, unanswered, explicitUnknown))
      .filter(Boolean);
    return {
      jiko_bunseki_submission: true,
      submission_version: 2,
      name: typeof input.name === "string" ? input.name.trim() : "",
      language: input.language,
      track: input.track,
      interest_activities: collectMulti(input.interest_activities, "interest_activities", unanswered, explicitUnknown),
      behavior_tendencies: behaviorTendencies,
      episodes,
      career_self_efficacy: {
        learning_confidence: collectScale(
          input.learning_confidence,
          "career_self_efficacy.learning_confidence",
          unanswered,
          explicitUnknown
        ),
        outcome_expectation: collectText(
          input.outcome_expectation,
          "career_self_efficacy.outcome_expectation",
          unanswered
        ),
        goal: collectText(input.goal, "career_self_efficacy.goal", unanswered)
      },
      perceived_barriers: collectMulti(input.perceived_barriers, "perceived_barriers", unanswered, explicitUnknown),
      perceived_supports: collectMulti(input.perceived_supports, "perceived_supports", unanswered, explicitUnknown),
      environment_preferences: environmentPreferences,
      value_candidates: collectMulti(input.value_candidates, "value_candidates", unanswered, explicitUnknown),
      avoid_candidates: collectMulti(input.avoid_candidates, "avoid_candidates", unanswered, explicitUnknown),
      unanswered_fields: unanswered,
      explicit_unknown_fields: explicitUnknown
    };
  }

  return { buildSubmission, resolveScaleSelection };
});
