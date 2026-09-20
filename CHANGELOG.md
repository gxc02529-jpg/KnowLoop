# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Dependabot now groups only Python minor and patch updates. Major version
  bumps arrive as individual pull requests so each migration gets its own
  review instead of being buried in an unreviewable batch.
- Dependabot ignores major Python dependency updates. `requirements.txt` is the
  pinned dependency set of the frozen v1.0.11 platform snapshot; a 41-package
  major cascade would silently invalidate the release evidence recorded in
  `V1_RELEASE_MANIFEST.json`, so majors need a deliberate migration.
- Bumped `actions/checkout` to v7 and `actions/setup-python` to v7.

### Added

- MIT license, `.editorconfig`, and Dependabot configuration.
- Contributing guide, changelog, and GitHub issue / pull request templates.

### Changed

- CI now cancels superseded runs before starting a new one, and byte-compiles
  sources before running the tests.

## [0.1.0] - 2026-09-19

### Added

- Initial public reference implementation.

Release and versioning policy: see [VERSIONING.md](VERSIONING.md).

