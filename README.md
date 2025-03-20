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

### Log Time

```sh
# log full workday to default issue
lt log
# log 2h to default issue
lt log 2h
# log 2h to specific issue
lt log 2h TSI-1
# log with custom message
lt log -m "working on foo" 2h TSI-1
# log multiple entries at once
lt logm MyProject:6,OPT:2
```

### Check Logged Time

```sh
# show logged time per issue
lt stats
# show logged time per issue for current month
lt stats month
# ..also show individual worklogs
lt stats -v
```

### Set Aliases

```sh
# set alias name for a commonly used issue
lt alias TSI-7 OPT
lt alias TS-10402 ProjectName
# unset aliases
lt alias --unset ProjectName
# show all aliases
lt alias
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
lt config --system LT_LOG_START 10

# Remove all custom configuration
lt config --unset
```

## Changes

### [latest]
[latest]: https://github.com/jannismain/log-time-to-tempo/commits/main/

<!-- ### [0.0.X] - 202X-XX-XX
[0.0.X]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.X -->

### [0.0.6] - 2025-03-20
[0.0.6]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.6

- when logging to an issue that does not exist, provide suggestions (based on similar aliases and issue summaries)
- add `lt logm` command to log multiple entries at once (e.g. `lt logm MyProject:6,OPT:2`)

### [0.0.5] - 2025-03-03
[0.0.5]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.5

- fix `lt list` command

### [0.0.4] - 2025-01-14
[0.0.4]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.4

- on `lt alias --unset` completion, only existing aliases are suggested
- fix keyring issues
  - keyring provided by `1password-cli` could not be used to persist token → default to system keyring on macOS
  - keyring fails on platforms other than macOS → alternative keyring backends are used.
- fix issue where `lt init` would update cache twice.

### [0.0.3] - 2024-09-12
[0.0.3]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.3

- add `lt stats` command to aggregate spent time per issue
- add `lt alias` command to provide more meaningful aliases for issue descriptions
  - `lt alias --unset` to remove previously set aliases
- renamed relative date ranges
  - `week` → `last_7_days`
  - `month` → `last_30_days`
  - `week_to_date` → `week`
  - `month_to_date` → `month`
- support abbreviations for relative date ranges (e.g. `l7` for `last_7_days`)
- fix issue where app dir would not be created on first run
- fix issue with formatted durations, where days would not be accounted for
- fix issue where token was saved to third-party keyrings (e.g. 1Password)
- parse more relative dates (e.g. "3 weeks ago") (using [`dateparser.parse`][dateparser.parse])

### [0.0.2] - 2024-04-17
[0.0.2]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.2

- add `log --lunch` option to reduce the amount of math you have to do in your head when entering your time
  - lunch will simply be deducted from the total duration and your end time
- rename `log --from-time '' --to-time ''` options to `log --start '' --end ''`
- `log --day` is now case-insensitive (so `Mo` will be recognized as `monday`)
- add `--version` flag

### [0.0.1] - 2024-03-25
[0.0.1]: https://github.com/jannismain/log-time-to-tempo/releases/tag/v0.0.1

- authorize with JIRA instance using personal access token
  - prompt for token and persist using [`keyring`][python-keyring] package
- create and list worklogs via tempo's REST API
- list projects and issues using [`jira`][python-jira] API
- cache projects and issues for faster responses and shell completion

[python-jira]: https://github.com/pycontribs/jira
[python-keyring]: https://pypi.org/project/keyring/
[dateparser.parse]: https://dateparser.readthedocs.io/en/latest/#popular-formats
