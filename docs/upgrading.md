# Compatibility and upgrades

## Release channels

The repository version can be ahead of the stable marketplace channel while a release is being
prepared. The stable channel always points to the latest published immutable `vX.Y.Z` tag; it never
follows `main`.

Source metadata is `2.21.0` while the stable marketplace ref is `v2.1.1`, because the release
workflow has not published a tag for this source yet. Installing from the marketplace therefore
gives you `2.1.1` today, and the gap closes when the next tag is published.

`uvx` and `npx` do not follow this ref — they resolve the latest version published to PyPI and npm —
but that is the version the same release workflow publishes alongside the tag, so in practice all
three channels carry whatever the newest `vX.Y.Z` is and none of them follow `main`. An unpublished
source version is reachable only by cloning.

> Both numbers in the paragraph above are read from the files that own them —
> `pyproject.toml` and `.agents/plugins/marketplace.json` — by
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py). This section
> cannot go stale without failing the build.

## Local fallback

Clone the repository when you need to inspect or run the files directly:

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

## Upgrading from 2.0.x, when this was `japan-recruit-ai-agent`

The project was renamed in 2.1.0. GitHub redirects the old repository URL, so an existing clone or
remote keeps working, but the marketplace entry is matched by name and has to be re-added:

```bash
claude plugin marketplace remove japan-recruit-ai-agent
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

Nothing in your Career Vault changes: the vault path, the event ledger and every document are
untouched by the rename. `JAPAN_RECRUIT_NO_UPDATE_CHECK=1` still disables the update check, so an
existing opt-out stays in force alongside the new `JAPAN_CAREER_NO_UPDATE_CHECK`. Release bundles
published under the old name remain verifiable with
[`scripts/verify_release.py`](../scripts/verify_release.py).