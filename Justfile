@_:
    just --list

# fix linter issues and auto-format code
fix:
    uv run ruff check --fix . && uv run ruff format . && uv run docformatter --in-place --config pyproject.toml src/**/*.py

# check for linter issues and verify code formatting
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run docformatter --config pyproject.toml --check src/**/*.py

# run tests
test *args:
    uv run pytest {{ args }}

# run tests and collect coverage data
cov *args:
    uv run pytest --cov-config=pyproject.toml --cov-report=term --cov-report html:build/coverage --cov=log_time_to_tempo --cov-report xml {{ args }}

# build distributable packages
build:
    rm -rf ./dist && uv build

# release a new version
release:
    just test
    echo "Forgot anything? Press CTRL+C to abort..."
    sleep 5
    git tag -m 'bump version to '`hatch version` v`hatch version` --sign
    git push --tags
    rm -rf dist/log_time_to_tempo-*
    just build
    just publish

publish:
    uv publish
    glab release create v`hatch version` \
        --name v`hatch version` \
        --notes '*[see changes](https://gitlab.codecentric.de/jmm/log-time-to-tempo/-/blob/main/README.md#'`hatch version | tr -d .`'-'`date -Idate`')*' \
        dist/*
    gh release create v`hatch version` \
        --title v`hatch version` \
        --notes '*[see changes](https://github.com/jannismain/log-time-to-tempo/blob/main/README.md#'`hatch version | tr -d .`'---'`date -Idate`')*' \
        dist/*
