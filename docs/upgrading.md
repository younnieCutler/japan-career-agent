# Compatibility and upgrades

## Release channels

The repository version can be ahead of the stable marketplace channel while a release is being
prepared. The stable channel always points to the latest published immutable `vX.Y.Z` tag; it never
follows `main`.

Source metadata is `3.0.1` while the stable marketplace ref is `v2.1.1`, because the release
workflow has not published a tag for this source yet. Installing from the marketplace therefore
gives you `2.1.1` today, and the gap closes when the next tag is published.

An unpublished source version is reachable only by cloning.

> Both numbers in the paragraph above are read from the files that own them —
> `pyproject.toml` and `.agents/plugins/marketplace.json` — by
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py). This section
> cannot go stale without failing the build.

## Local fallback

Clone the repository when you need to inspect or run the files directly:

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

Workspace data lives in `./data/` (`evidence.yml`, `pipeline.yml`, `applications.yml`, `rules.yml`)
and generated reports live in `./career-docs/`. Set `JAPAN_CAREER_NO_UPDATE_CHECK=1` to disable the
24-hour manifest version check.
