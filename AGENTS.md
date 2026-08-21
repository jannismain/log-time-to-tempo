# Log Time to Tempo - Agent Instructions

## Project Overview

Log Time to Tempo is a Python CLI application that enables logging work time to JIRA/Tempo from the command line. It is built with Python 3.11+, Typer for the CLI interface, and uses `uv` for project management.

## Working Effectively

### Bootstrap and Setup

```bash
# Install uv (project manager) and rust-just (task runner)
pip install uv rust-just
```

### Development Commands

```bash
# Lint the code (1-2 seconds)
just lint

# Fix linting issues (1-2 seconds)
just fix

# Run tests (3-5 seconds, 66 tests)
just test

# Run tests for a single case
just test -k test_name

# Run tests with coverage
just cov

# Build the package (1-2 seconds)
just build

# Install in development mode and run CLI
uv run lt --help
```

### Validation After Changes

Always run these validation steps after making code changes:

```bash
# 1. Fix linting & formatting issues
just fix

# 2. Test
just test

# 3. Build
just build

# 4. Test CLI functionality
uv run lt --help
uv run lt config --help
```

### Manual Validation Requirements

After making changes, always test these key user scenarios:

```bash
# Test main help (should show commands organized in groups)
uv run lt --help

# Test configuration commands (don't require JIRA connection)
uv run lt config --help
uv run lt alias --help
uv run lt config
uv run lt --version

# NOTE: The following commands require JIRA connection and will prompt for a token:
# uv run lt log --help
# uv run lt stats --help
# uv run lt init --help
# These will hang without JIRA_API_TOKEN or a valid connection.
```

### Application Architecture Validation

When modifying core functionality, verify the following:

1. The CLI help output shows the proper command structure with Configuration, POST, and GET groups.
2. `lt config` and `lt alias --help` work without a JIRA connection.
3. `lt --version` returns the version number.
4. Commands fail gracefully when JIRA is unreachable.
5. Non-JIRA commands provide useful `--help` documentation.

## Code Style Guidelines
- **Formatting**: ruff (100 char lines, single quotes)
- **Imports**: isort (known-first-party: log_time_to_tempo, test_log_time_to_tempo)
- **Docstrings**: docformatter (wrap-summaries=100)
- **Types**: Use type hints consistently
- **Naming**: Follow existing patterns (snake_case functions, CamelCase classes)
- **Error Handling**: Graceful failures with informative messages
- **Comments**: None unless explicitly requested

## Repository Structure

```text
src/log_time_to_tempo/          # Main application code
├── __init__.py                 # Package config and version info
├── cli/                        # CLI interface code
│   ├── main.py                 # Main CLI entry point
│   ├── config.py               # Configuration management
│   └── alias.py                # Issue alias management
├── _jira.py                    # JIRA API integration
├── tempo.py                    # Tempo API integration
├── caching.py                  # Local data caching
└── cli/_sparkline.py           # Sparkline visualization helpers

src/test_log_time_to_tempo/     # Test suite
├── cli/                        # CLI tests
├── _jira/                      # JIRA integration tests
├── test_cache.py               # Cache tests
├── test_sparkline_axis.py      # Sparkline axis tests
├── test_time.py                # Time helpers tests
└── ...
```

### Important Files

- `pyproject.toml` - Project configuration, dependencies, and build settings
- `src/log_time_to_tempo/cli/main.py` - Primary CLI interface with all commands
- `README.md` - User documentation and usage examples
- `.pre-commit-config.yaml` - Pre-commit hooks for code quality
- `.github/workflows/ci.yml` - CI/CD pipeline

## Common Development Tasks

### Adding New CLI Commands

1. Add the command function to `src/log_time_to_tempo/cli/main.py`.
2. Use the `@app.command()` decorator with the appropriate `rich_help_panel`.
3. Follow the existing patterns for option and argument definitions.
4. Add tests in `src/test_log_time_to_tempo/cli/`.

### Testing Strategy

- Unit tests cover CLI commands with mocked JIRA/Tempo APIs.
- Integration tests use a `TestClient` mock for JIRA interactions.
- All tests run in under 5 seconds.
- Coverage reporting is included in test runs.

### Code Quality Standards

- Use `ruff` for linting and formatting.
- Follow the existing code style (single quotes, 100-character line length).
- Maintain test coverage for new functionality.
- Use type hints consistently.

## Environment and Dependencies

### Python Requirements

- Python 3.11+ required.
- Uses `uv` for environment and dependency management.
- Dependencies are automatically managed via `pyproject.toml`.

### CLI Entry Points

The application provides multiple command aliases:

- `lt` (primary command)
- `log-time` (alternative)
- `log-time-to-tempo` (full name)

### Environment Variables

- `JIRA_API_TOKEN` - JIRA personal access token
- `JIRA_INSTANCE` - JIRA server URL (defaults to the codecentric instance)
- `LT_*` - Application-specific configuration options

## Troubleshooting Common Issues

### Build/Test Failures

- Ensure Python 3.11+ is installed.
- All commands should complete in under 10 seconds; do not cancel them prematurely.

### JIRA Connection Issues

- The app is designed to work offline for configuration and help commands.
- JIRA connectivity is required only for commands such as `log`, `init`, `stats`, `projects`, `issues`, and `budget`.
- Mock JIRA interactions are used in tests.

### Development Environment

- Uses `uv` virtual environments automatically.
- Dependencies are installed automatically on the first `uv` command.

## Performance Expectations

- **Setup**: under 5 seconds for initial `uv` install (on first run: about 7 seconds for dependencies)
- **Linting**: under 1 second
- **Testing**: 3-4 seconds (66 tests)
- **Building**: under 1 second
- **CLI startup**: under 1 second for non-JIRA commands

## Validation Summary

Always run:

```bash
just fix && just test && just build
```
