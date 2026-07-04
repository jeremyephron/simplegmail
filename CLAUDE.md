# CLAUDE.md

## Development Process

**TDD is mandatory.** All code changes must follow the red → green → refactor → package cycle:

1. **Red** — Write a failing test first that describes the desired behavior. Run it and confirm it fails for the expected reason before writing any implementation code.
2. **Green** — Write the minimum implementation needed to make the test pass. Run the test suite and confirm it passes.
3. **Refactor** — Clean up the implementation and tests while keeping the whole suite green.
4. **Package** — Build a pip distribution package (`uv build`, which writes the sdist and wheel to `dist/`). And then display the package name and details.

Rules:

- Never write implementation code before a failing test exists for it.
- Never commit with failing tests.
- Bug fixes start with a test that reproduces the bug.

## Tooling

- **uv** is the package manager. The virtualenv lives in `.venv/`; install dependencies with `uv pip install ...`.
- **pytest** is the test runner. Tests live in `tests/`; run them with `.venv/bin/python -m pytest tests/`.
- Distribution packages are built with `uv build`.

## Project Layout

- `simplegmail/` — package source (`gmail.py` is the main client; `message.py`, `attachment.py`, `label.py`, `query.py` are supporting modules)
- `tests/` — test suite
