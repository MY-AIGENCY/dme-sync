# Contributing to DME Knowledge Base Pipeline

Thank you for your interest in contributing! Please follow these guidelines to ensure a smooth and productive collaboration.

## Getting Started
- All development must be performed in a cloud environment (see CLOUD_ONLY_DEVELOPMENT.md).
- Clone the repo and create a new branch for your feature or fix.
- Install dependencies with Poetry: `poetry install`
- Set up your `.env` file with required secrets (never commit secrets to Git).

## Code Style
- Follow PEP8 and use `ruff` for linting: `poetry run ruff .`
- Use type hints and docstrings for all public functions/classes.
- Organize code under `src/` using the existing package structure.

## Testing
- All code must be covered by automated tests using real data (see dev rules).
- Run tests with: `PYTHONPATH=. pytest src/tests/`
- Add new tests for any new features or bug fixes.

## Pull Requests
- Reference the relevant issue or backlog item in your PR.
- Summarize what was changed and why.
- Ensure all tests pass and CI is green before requesting review.
- Update documentation as needed.

## Communication
- Use clear, descriptive commit messages.
- Document any new assumptions or context in the PR description.
- If you encounter blockers, document them in the PR and update the backlog.

## Security
- Never commit secrets or credentials.
- Follow all security and compliance rules in `.DME-SYNC_DEV_RULES.md`.

Thank you for helping make this project robust and production-grade! 