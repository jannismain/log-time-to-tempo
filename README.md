# Log Time to Tempo

[![PyPI - Version](https://img.shields.io/pypi/v/log-time-to-tempo.svg)](https://pypi.org/project/log-time-to-tempo)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/log-time-to-tempo.svg)](https://pypi.org/project/log-time-to-tempo)

-----

Log your time to tempo on a self-hosted Jira instance from the convenience of your command line.

## Requirements

This tool is developed against

- Jira Server v9.4.17
- Tempo Timesheets 17.2.0 plugin

Any deviation from that setup might lead to issues.
Feel free to provide PRs to support other configurations.

## Installation

```console
pip install log-time-to-tempo
```

## Getting Started

To initialize authentication and local caches of projects and issues, run

```
lt init
```

If you want to enable shell completion (which makes picking issues much easier), run

```
lt --install-completion
```

## Usage

```sh
# log full workday to default issue
lt log
# log 2h to default issue
lt log 2h
# log 2h to specific issue
lt log 2h TSI-1
```

## Configuration


The `lt config` command allows to change the default behavior, either system wide (`--system`) or in the local directory and subdirectories.

Here are a couple of usage examples:

```sh
# Set custom jira instance for all projects (i.e. system-wide)
lt config --system JIRA_INSTANCE https://jira.my-server.com

# Set default issue for worklogs created from current directory (and subdirectories)
lt config LT_LOG_ISSUE TSI-7

# Start all your worklogs at 10am (instead of the default 9am)
lt config --system LT_LOG_FROM_TIME 10

# Remove all custom configuration
lt config --unset
```

## Changes

### [latest] - 2024-XX-XX
[latest]: https://gitlab.codecentric.de/jmm/log-time-to-tempo/-/blob/main/README.md

- authorize with JIRA instance using personal access token
  - prompt for token and persist using [`keyring`][python-keyring] package
- create and list worklogs via tempo's REST API
- list projects and issues using [`jira`][python-jira] API
- cache projects and issues for faster responses and shell completion

[python-jira]: https://github.com/pycontribs/jira
[python-keyring]: https://pypi.org/project/keyring/
