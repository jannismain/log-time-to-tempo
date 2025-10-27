# Log Time to Tempo - Agent Instructions

## Development Commands
- **Lint**: `just lint` (check) or `just fix` (auto-fix)
- **Test**: `just test` or `just test -k test_name` for single test
- **Coverage**: `just cov`
- **Build**: `just build`

## Code Style Guidelines
- **Formatting**: ruff (100 char lines, single quotes)
- **Imports**: isort (known-first-party: log_time_to_tempo, test_log_time_to_tempo)
- **Docstrings**: docformatter (wrap-summaries=100)
- **Types**: Use type hints consistently
- **Naming**: Follow existing patterns (snake_case functions, CamelCase classes)
- **Error Handling**: Graceful failures with informative messages
- **Comments**: None unless explicitly requested

## Project Structure
- **CLI**: `src/log_time_to_tempo/cli/main.py` (entry point)
- **Tests**: `src/test_log_time_to_tempo/` (pytest, 66 tests, <5s runtime)
- **Config**: `pyproject.toml` (dependencies, ruff/docformatter settings)

## Copilot Instructions
See `.github/copilot-instructions.md` for detailed development workflow, architecture, and validation requirements.

## Validation After Changes
Always run: `just fix && just test && just build && uv run lt --help`
