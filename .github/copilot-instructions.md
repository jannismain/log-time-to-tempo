# Log Time to Tempo - GitHub Copilot Instructions

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the information provided here.

## Project Overview
Log Time to Tempo is a Python CLI application that enables logging work time to JIRA/Tempo from the command line. Built with Python 3.11+, Typer for CLI interface, and uses uv for project management.

## Working Effectively

### Bootstrap and Setup (NEVER CANCEL - takes <5 seconds)
```bash
# Install uv (project manager) and rust-just (task runner)
pip install uv rust-just
```

### Development Commands (NEVER CANCEL - all complete in <10 seconds)
```bash
# Lint the code (1-2 seconds)
just lint

# Fix linting issues (1-2 seconds)
just fix

# Run tests (3-5 seconds, 66 tests)
just test

# Build the package (1-2 seconds)
just build

# Install in development mode and run CLI
uv run lt --help
```

### Validation After Changes
ALWAYS run these validation steps after making code changes:
```bash
# 1. Fix linting & formatting issues (NEVER CANCEL - 2 seconds max)
just fix

# 2. Test (NEVER CANCEL - 5 seconds max)
just test

# 3. Build (NEVER CANCEL - 2 seconds max)
just build

# 4. Test CLI functionality
uv run lt --help
uv run lt config --help
```

## Manual Validation Requirements
After making changes, ALWAYS test these key user scenarios:

### Basic CLI Functionality Test
```bash
# Test main help (should show commands organized in groups)
uv run lt --help

# Test configuration commands (don't require JIRA connection)
uv run lt config --help
uv run lt alias --help
uv run lt config  # shows current config
uv run lt --version  # shows version

# NOTE: The following commands require JIRA connection and will prompt for token:
# uv run lt log --help
# uv run lt stats --help
# uv run lt init --help
# These will hang without JIRA_API_TOKEN environment variable or valid connection
```

### Application Architecture Validation
Run through this checklist when modifying core functionality:
1. **CLI Interface**: Verify `lt --help` shows proper command structure with Configuration/POST/GET groups
2. **Configuration**: Test `lt config` and `lt alias --help` work without JIRA connection
3. **Version**: Test `lt --version` returns version number
4. **Error Handling**: Commands should fail gracefully when JIRA is unreachable
5. **Help System**: Non-JIRA commands should provide `--help` documentation

Note: Commands like `log`, `stats`, `init`, `projects`, `issues`, `budget` require JIRA connection and will prompt for token or fail with connection errors in environments without network access.

## Repository Structure

### Key Directories
```
src/log_time_to_tempo/          # Main application code
├── __init__.py                 # Package config, version info
├── cli/                        # CLI interface code
│   ├── main.py                 # Main CLI entry point
│   ├── config.py              # Configuration management
│   └── alias.py               # Issue alias management
├── _jira.py                   # JIRA API integration
├── tempo.py                   # Tempo API integration
└── caching.py                 # Local data caching

src/test_log_time_to_tempo/     # Test suite
├── cli/                       # CLI tests
└── _jira/                     # JIRA integration tests
```

### Important Files
- `pyproject.toml` - Project configuration, dependencies, build settings
- `src/log_time_to_tempo/cli/main.py` - Primary CLI interface with all commands
- `README.md` - User documentation and usage examples
- `.pre-commit-config.yaml` - Pre-commit hooks for code quality
- `.github/workflows/ci.yml` - CI/CD pipeline

## Common Development Tasks

### Adding New CLI Commands
1. Add command function to `src/log_time_to_tempo/cli/main.py`
2. Use `@app.command()` decorator with appropriate `rich_help_panel`
3. Follow existing patterns for option/argument definitions
4. Add tests in `src/test_log_time_to_tempo/cli/`

### Testing Strategy
- Unit tests cover CLI commands with mocked JIRA/Tempo APIs
- Integration tests use `TestClient` mock for JIRA interactions
- All tests run in <5 seconds - NEVER CANCEL test runs
- Coverage reporting included in test runs

### Code Quality Standards
- Use `ruff` for linting and formatting
- Follow existing code style (single quotes, 100 char line length)
- Maintain test coverage for new functionality
- Use type hints consistently

## Environment and Dependencies

### Python Requirements
- Python 3.11+ required
- Uses `uv` for environment and dependency management
- Dependencies automatically managed via `pyproject.toml`

### CLI Entry Points
The application provides multiple command aliases:
- `lt` (primary command)
- `log-time` (alternative)
- `log-time-to-tempo` (full name)

### Environment Variables
- `JIRA_API_TOKEN` - JIRA personal access token
- `JIRA_INSTANCE` - JIRA server URL (defaults to codecentric instance)
- `LT_*` - Various application configuration options

## Troubleshooting Common Issues

### Build/Test Failures
- Ensure Python 3.11+ is installed
- Run `pip install uv` if uv commands fail
- All commands should complete in <10 seconds - don't cancel prematurely

### JIRA Connection Issues
- App is designed to work offline for configuration/help commands
- JIRA connection only required for `log`, `init`, `stats`, `projects`, `issues`, `budget` commands
- Mock JIRA interactions are used in tests

### Development Environment
- Uses uv virtual environments automatically
- No manual environment setup required
- Dependencies installed automatically on first uv command

## Performance Expectations
- **Setup**: <5 seconds for initial uv install (on first run: ~7 seconds for dependencies)
- **Linting**: <1 second
- **Testing**: 3-4 seconds (66 tests)
- **Building**: <1 second
- **CLI startup**: <1 second for non-JIRA commands

NEVER CANCEL any of these operations - they complete very quickly.

## Command Categories by Network Requirements

### No Network Required (Always Safe to Test):
- `lt --help` - Main help
- `lt config [--help]` - Configuration management
- `lt alias [--help]` - Alias management
- `lt reset --help` - Cache reset help
- `lt --version` - Version information

### Requires JIRA Connection (Will Prompt/Fail Without Network):
- `lt log` - Log time entries
- `lt logm` - Log multiple entries
- `lt init` - Initialize/update caches
- `lt stats` - Time statistics
- `lt list` - List time entries
- `lt issues` - List issues
- `lt budget` - Budget information
- `lt projects` - List projects
