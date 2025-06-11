# Agent Guidelines for alexify

This repository uses **Conventional Commits** for commit messages. Use the form
`type(scope): short description` when committing. Common types are `feat`,
`fix`, `docs`, `style`, `refactor`, `test` and `chore`.

## Commit Rules
- Keep commits atomic and logically scoped.
- Run `pytest -q` before every commit and ensure it passes.
- If `setup-dev.sh` modifies dependencies, update cached wheels via the script.

## Pull Request Guidelines
- Title should summarize the change.
- In the body include a short description, testing steps and references.

## Maintenance
- Dependencies are defined in `requirements*.txt`. Keep them pinned.
- Update changelog and bump version in `pyproject.toml` following Semantic
  Versioning (`MAJOR.MINOR.PATCH`).
- Pre-commit hooks (if `.pre-commit-config.yaml` exists) must run before
  committing.

