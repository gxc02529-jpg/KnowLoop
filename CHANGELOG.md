# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- MIT license, `.editorconfig`, and Dependabot configuration.
- Contributing guide, changelog, and GitHub issue / pull request templates.

### Changed

- Dependabot no longer proposes `requirements.txt` changes for this repository.
  CI installs a curated dependency subset rather than `requirements.txt`, so an
  automated dependency bump would always look green while never being actually
  exercised. `requirements.txt` is also the pinned dependency set behind the
  frozen v1.0.11 release evidence, and semantic versioning is unreliable here
  (`torch` 2.7.1 to 2.14.0 and `docling` 2.106.0 to 2.128.0 are both minor
  bumps). Dependency upgrades go through a deliberate migration with the release
  gates re-run, following [VERSIONING.md](VERSIONING.md). `github-actions`
  updates stay automated because CI exercises the upgraded actions directly.
- Bumped `actions/checkout` to v7 and `actions/setup-python` to v7.
- CI now cancels superseded runs before starting a new one, and byte-compiles
  sources before running the tests.

## [0.1.0] - 2026-09-19

### Added

- Initial public reference implementation.

Release and versioning policy: see [VERSIONING.md](VERSIONING.md).
