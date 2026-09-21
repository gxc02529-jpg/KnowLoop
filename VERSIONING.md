# Versioning

This repository follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and records
user-visible changes in [CHANGELOG.md](CHANGELOG.md), in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## Current baseline

| Item | Value |
| --- | --- |
| Latest release | `v1.0.0` |
| Long-lived branch | `main` |
| Supported Python | 3.12 |

## Branching

`main` is the only long-lived branch and always holds the latest verified state. Work that is not
ready to ship stays on a short-lived topic branch (`feat/...`, `fix/...`, `chore/...`, `docs/...`)
and merges back once the regression suite is green. There is no parallel release branch: a version
is a tag on `main`, not a separate line of development.

## Tags

A release is tagged `vMAJOR.MINOR.PATCH` on the commit that was verified. A published tag is never
moved; if a release needs a fix, it gets a new patch tag.

| Part | Bumped when |
| --- | --- |
| `MAJOR` | the public HTTP API, the scenario package format or the storage schema changes incompatibly |
| `MINOR` | a backwards-compatible capability, scenario or configuration key is added |
| `PATCH` | a backwards-compatible fix lands |

## Release checklist

1. Confirm the offline regression suite passes. It needs no model weights and no external database:

   ```powershell
   python -m pytest -q tests/test_logistics_scenario.py tests/test_memory_history.py `
     tests/test_answer_confidence.py tests/test_api_protection.py
   ```

2. Move the `[Unreleased]` entries in `CHANGELOG.md` into a dated version section and commit that.
3. Tag the commit `vX.Y.Z` and push the tag.
4. Publish a GitHub Release from the same notes.

Steps that need model weights, MySQL, Milvus or Redis are outside the offline gate and are not a
prerequisite for tagging a backwards-compatible fix.

## Dependency changes

`requirements.txt` is the pinned dependency set. Automated updates are not accepted there: CI
installs a curated subset for the isolated tests, so a bump would report green without ever being
exercised. Dependency upgrades are done as an explicit migration, with the regression suite re-run,
and land in their own commit.
