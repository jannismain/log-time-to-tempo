import os
import platform
import shutil
from datetime import date, datetime, time, timedelta
from difflib import get_close_matches
from typing import Optional

import jira
import keyring
import keyring.backends.macOS
import rich
import typer
from click.shell_completion import CompletionItem
from keyring.errors import PasswordDeleteError
from rich.table import Table
from typing_extensions import Annotated

from .. import __version__, _jira, _time, caching, cfg, name, tempo
from .._logging import log
from . import alias, app, config, error, link
from ._sparkline import (
    determine_date_range_type,
    generate_axis_labels,
    generate_sparkline_from_daily_data,
)
from .completions import complete_issue, complete_project

token_found_in_environment = os.getenv('JIRA_API_TOKEN')
config.load()

arg_relative_date_range = typer.Argument(
    callback=lambda x: _time.resolve_relative_date_range(x),
    shell_complete=lambda ctx, param, incomplete: list(
        CompletionItem(
            v,
            help=f'short: {", ".join(_time.relative_date_range_abbreviations.get(v))}'
            if v in _time.relative_date_range_abbreviations
            else '',
        )
        for v in _time.RelativeDateRange._value2member_map_.keys()
    ),
)


@app.callback(
    invoke_without_command=True,
    context_settings=dict(auto_envvar_prefix=name.upper(), show_default=False),
)
def main(
    ctx: typer.Context,
    token: Annotated[
        Optional[str], typer.Option(envvar='JIRA_API_TOKEN', show_default='prompt')
    ] = None,
    instance: Annotated[str, typer.Option(envvar='JIRA_INSTANCE')] = 'https://jira.codecentric.de',
    verbose: Annotated[
        int,
        typer.Option(
            '--verbose',
            '-v',
            count=True,
            show_envvar=False,
            show_default=False,
            help='Show logging output',
        ),
    ] = 0,
    persist_token: Annotated[bool, typer.Option(hidden=True)] = True,
    cache: Annotated[bool, typer.Option(hidden=True)] = True,
    version: Annotated[
        bool, typer.Option('--version', callback=lambda v: print(__version__) if v else None)
    ] = False,
):
    """Log time to tempo."""
    if ctx.resilient_parsing:  # script is running for completion purposes, nocov
        return

    # If no subcommand is provided, show help and exit cleanly
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        ctx.exit(0)

    ctx.obj = cfg  # make the config object available to subcommands
    if verbose:
        import coloredlogs

        log_config = dict(
            level='DEBUG' if verbose > 1 else 'INFO',
            logger=log,
        )
        if verbose <= 1:
            log_config['fmt'] = '%(message)s'
            log_config['level_styles'] = dict(info=dict(faint=True))

        coloredlogs.install(**log_config)
    ctx.obj.verbose = verbose
    ctx.obj.aliases = alias._read_aliases()

    # return early for subcommands that don't interact with jira
    if ctx.invoked_subcommand not in 'log logm issues list projects init stats budget *'.split():
        return

    if token is None:
        if platform.system() == 'Darwin':
            keyring.set_keyring(keyring.backends.macOS.Keyring())
        if 'JIRA_USER' in os.environ and (
            token := keyring.get_password(name, os.environ['JIRA_USER'])
        ):
            log.debug('Token read from keyring')
            persist_token = False
        else:
            typer.echo(
                'Create your personal access token here:',
            )
            typer.echo(
                link(
                    f'{instance}/secure/ViewProfile.jspa?selectedTab=com.atlassian.pats.pats-plugin:jira-user-personal-access-tokens'
                )
            )
            token = typer.prompt('JIRA API token', hide_input=True)
            log.debug('Token read from prompt')

    try:
        cfg.jira = jira.JIRA(token_auth=token, server=instance)
    except ConnectionError as e:
        error(f'Could not connect to {instance}: {e}')

    cfg.instance = instance
    try:
        cfg.myself = _jira.myself(cfg.jira)
        ctx.invoke(config.config, key='JIRA_USER', value=cfg.myself['name'])
    except jira.JIRAError as e:
        error(f'Could not authenticate: {e}')

    cfg.token = token

    if persist_token:
        log.info("Saved token for '%s' to keyring.", cfg.myself['name'])
        keyring.set_password(name, cfg.myself['name'], token)

    cfg.cache = cache
    if not _jira.cache_is_warm() and ctx.invoked_subcommand != 'init' and cache:
        ctx.invoke(init, ctx=ctx, cache=cache)
    log.debug('user: %s', cfg.myself['name'])


@app.command('log', rich_help_panel='POST')
def log_time(
    ctx: typer.Context,
    duration: Annotated[
        timedelta, typer.Argument(envvar='LT_LOG_DURATION', parser=_time.parse_duration)
    ] = '8',
    issue: Annotated[
        str, typer.Argument(envvar='LT_LOG_ISSUE', shell_complete=complete_issue)
    ] = 'TSI-7',
    day: Annotated[
        date, typer.Option(parser=_time.parse_date, show_envvar=False, show_default='today')
    ] = datetime.now().date(),
    start: Annotated[
        time,
        typer.Option(
            parser=_time.parse_time, show_default='9', allow_from_autoenv=False
        ),  # envvar is read below, so we can differentiate between custom default from env and provided value
    ] = None,
    end: Annotated[time, typer.Option(parser=_time.parse_time)] = None,
    lunch: Annotated[timedelta, typer.Option(parser=_time.parse_duration)] = None,
    message: Annotated[str, typer.Option('--message', '-m')] = None,
    yes: Annotated[bool, typer.Option('--yes', '-y', help='log time without confirmation')] = False,
):
    "Log time entry."
    if ctx.resilient_parsing:  # script is running for completion purposes
        return
    cfg = ctx.obj

    # resolve issue alias
    alias = ''
    if issue in ctx.obj.aliases:
        alias = issue
        issue = ctx.obj.aliases[alias]
    else:
        if issue in ctx.obj.aliases.values():
            alias = next(key for key, value in ctx.obj.aliases.items() if value == issue)

    try:
        cfg.issue = cfg.jira.issue(issue, fields='summary,comment')
    except jira.JIRAError as e:
        # If not issue is found, try to figure out what the user meant
        fuzzy_matches = set(get_close_matches(issue, ctx.obj.aliases.keys(), n=5, cutoff=0.6))
        similar_issues = {
            issue: f'alias for {alias}'
            for alias, issue in ctx.obj.aliases.items()
            if alias in fuzzy_matches
        }

        # Also check jira issue summaries for matches
        similar_issues.update(
            {
                key: summary
                for key, summary in _jira.get_all_issues(ctx.obj.jira).items()
                if issue.lower() in summary.lower()
                and not any(key in v for v in similar_issues.values())
            }
        )

        if similar_issues and len(similar_issues) == 1:
            suggested_issue, issue_summary = next((k, v) for k, v in similar_issues.items())
            # only one similar issue, we can assume the user meant this issue and continue
            if typer.confirm(f"Did you mean '{suggested_issue}' ({issue_summary})?", default=True):
                ctx.invoke(
                    log_time,
                    duration=duration,
                    issue=suggested_issue,
                    day=day,
                    start=start,
                    end=end,
                    lunch=lunch,
                    message=message,
                    yes=yes,
                    ctx=ctx,
                )
            return
        typer.secho(f'Error: {e.text.lower()} ({issue})', fg='red')
        if similar_issues and len(similar_issues) > 1:
            typer.secho(f'Did you mean: {", ".join(similar_issues)}', fg='red', italic=True)
        return
    project_name = get_project_name(ctx, cfg.issue)

    worklogs = tempo.get_worklogs(ctx.obj.myself['key'], day, day)
    seconds_logged = sum(worklog.timeSpentSeconds for worklog in worklogs)
    duration_logged = timedelta(seconds=seconds_logged)
    if worklogs and start is None:
        last_worklog = worklogs[-1]
        start = (last_worklog.started + timedelta(seconds=last_worklog.timeSpentSeconds)).time()
    elif start is None:
        start = _time.parse_time(os.getenv('LT_LOG_START', '9'))
    started = datetime.combine(day, start)
    if end is not None:
        duration = datetime.combine(day, end) - started
    if end is None:
        end = (started + duration).time()
    if lunch:
        duration -= lunch
        end = (datetime.combine(day, end) - lunch).time()

    # Detect overlap with existing worklogs and warn user
    for worklog in worklogs:
        if (
            worklog.started.time() < end
            and (worklog.started + timedelta(seconds=worklog.timeSpentSeconds)).time() > start
        ):
            typer.secho(
                f'Warning: The time entry overlaps with an existing worklog from {worklog.started.strftime("%H:%M")} to {(worklog.started + timedelta(seconds=worklog.timeSpentSeconds)).strftime("%H:%M")}',
                fg='yellow',
            )

    rich.print(
        'Log',
        _time.format_duration(duration),
        f'({start.strftime("%H:%M")} - {end.strftime("%H:%M")})',
        f'on [italic]{project_name + " (" + (f"{cfg.issue.key}: " if project_name == alias else "")}{cfg.issue.fields.summary})[/italic]',
        f'for {_time.format_date_relative(day)}',
    )

    if duration_logged + duration > timedelta(hours=10):
        error(
            f'You already have {_time.format_duration(duration_logged)} logged on that day.'
            ' Cannot log more than 10h per day.'
        )

    if yes or typer.confirm('Continue?'):
        tempo.create_worklog(
            worker_id=cfg.myself['key'],
            task_id=cfg.issue.id,
            started=started.isoformat(timespec='milliseconds'),
            time_spent_seconds=duration.total_seconds(),
            message=message,
        )


@app.command('logm', rich_help_panel='POST')
def log_multi(
    ctx: typer.Context,
    entries: Annotated[str, typer.Argument()],
    day: Annotated[
        date, typer.Option(parser=_time.parse_date, show_envvar=False, show_default='today')
    ] = datetime.now().date(),
    start: Annotated[time, typer.Option(parser=_time.parse_time, show_default='9')] = None,
    end: Annotated[time, typer.Option(parser=_time.parse_time)] = None,
    message: Annotated[str, typer.Option('--message', '-m')] = None,
    yes: Annotated[bool, typer.Option('--yes', '-y', help='log time without confirmation')] = False,
):
    "Log multiple time entries at once."
    if ctx.resilient_parsing:  # script is running for completion purposes
        return

    for entry in entries.split(','):
        if not entry:
            continue
        try:
            issue, duration = entry.split(':', 1)
            ctx.invoke(
                log_time,
                duration=_time.parse_duration(duration),
                issue=issue,
                day=day,
                start=start,
                end=end,
                message=message,
                yes=yes,
                ctx=ctx,
            )
        except ValueError:
            error(f'Invalid entry: {entry}')


# TODO: Combine `stats` and `list` commands into one command with a flag whether to aggregate projects


@app.command('list', rich_help_panel='GET')
def cmd_list(
    ctx: typer.Context,
    date_range: Annotated[str, arg_relative_date_range] = 'week',
    from_date: Annotated[date, typer.Option('--from', parser=_time.parse_date)] = None,
    to_date: Annotated[
        date, typer.Option('--to', parser=_time.parse_date, show_default='today')
    ] = datetime.now().date().strftime('%d.%m'),
):
    """List time entries.

    For a custom time range, use the --from and --to options:

    $ lt list --from 1.12 --to 24.12
    """
    if from_date is None:
        from_date, to_date = _time.parse_relative_date_range(date_range)

    table = Table(box=None)
    table.add_column('Date', style='cyan')
    table.add_column('Time', style='cyan')
    table.add_column(' ', justify='right')
    table.add_column('Project', style='green')
    table.add_column('Issue', style='blue')
    table.add_column('Comment')

    total_seconds = 0
    previous_worklog_date = None
    for worklog in tempo.get_worklogs(ctx.obj.myself['key'], from_date, to_date):
        table.add_row(
            worklog.started.strftime('%d.%m')
            if worklog.started.date() != previous_worklog_date
            else '',
            worklog.started.strftime('%H:%M'),
            _time.format_duration_aligned(timedelta(seconds=worklog.timeSpentSeconds), 2),
            get_project_name(ctx, worklog.issue),
            worklog.issue.key,
            worklog.comment or '',
        )
        total_seconds += worklog.timeSpentSeconds
        previous_worklog_date = worklog.started.date()
    rich.print(table)
    rich.print(
        f'\n[italic]You have logged [bold]{_time.format_duration(timedelta(seconds=total_seconds))}[/bold] from {from_date} to {to_date}.[/italic]'
    )


@app.command('stats', rich_help_panel='GET')
def cmd_stats(
    ctx: typer.Context,
    date_range: Annotated[str, arg_relative_date_range] = 'month',
    from_date: Annotated[Optional[date], typer.Option('--from', parser=_time.parse_date)] = None,
    to_date: Annotated[
        date, typer.Option('--to', parser=_time.parse_date, show_default='today')
    ] = datetime.now().date().strftime('%d.%m'),
    verbose: Annotated[int, typer.Option('-v', count=True)] = 0,
    show_sparkline: Annotated[
        bool,
        typer.Option(
            '--sparkline/--no-sparkline', is_flag=True, help='toggle sparkline visualization'
        ),
    ] = True,
):
    """Show logged time per project.

    Projects are displayed with total time spent and optionally a
    sparkline visualization showing daily time patterns over the
    selected period.

    For a custom time range, use the --from and --to options:

    $ lt stats --from 1.12 --to 24.12
    """
    if from_date is None:
        typer.secho(f'Period: {date_range.value}', bold=True)
        try:
            from_date, to_date = _time.parse_relative_date_range(date_range)
        except ValueError:
            typer.secho(f'Invalid date range: {date_range}', fg='red')
            exit(1)
    else:
        typer.secho(
            f'Period: {str(from_date) + (f" - {to_date}" if to_date != from_date else "")}',
            bold=True,
        )

    stats = {}
    for worklog in tempo.get_worklogs(ctx.obj.myself['key'], from_date, to_date):
        project = get_project_name(ctx, worklog.issue)
        if project not in stats:
            stats[project] = {
                'timeSpentSeconds': 0,
                'summary': worklog.issue.summary,
                'worklogs': [],
                'days': {},
            }
        stats[project]['timeSpentSeconds'] = (
            stats[project]['timeSpentSeconds'] + worklog.timeSpentSeconds
        )
        stats[project]['worklogs'].append(worklog)
        if (date := worklog.started.strftime('%d.%m')) not in stats[project]['days']:
            stats[project]['days'][date] = {
                'comments': set([worklog.comment]),
                'timeSpentSeconds': worklog.timeSpentSeconds,
            }
        else:
            stats[project]['days'][date]['comments'].add(worklog.comment)
            stats[project]['days'][date]['timeSpentSeconds'] += worklog.timeSpentSeconds

    MAX_COL_WIDTH = 20
    col_width = min(max((len(p) for p in stats), default=0), MAX_COL_WIDTH)
    if col_width < 5:  # ensure that 'Total' on last line fits as well
        col_width = 5

    # Determine date range type and generate axis labels if sparkline is shown
    axis_labels = ''
    if show_sparkline and stats:
        range_type = determine_date_range_type(from_date, to_date)
        axis_labels = generate_axis_labels(from_date, to_date, range_type)

    for project in sorted(stats, key=lambda k: stats[k]['timeSpentSeconds'], reverse=True):
        total_duration = _time.format_duration_aligned(
            timedelta(seconds=stats[project]['timeSpentSeconds'])
        )

        if show_sparkline:
            sparkline = generate_sparkline_from_daily_data(
                stats[project]['days'], from_date, to_date, maximum=8, minimum=0
            )

            # Limit project name width, so that sparkline fits next to it
            if len(project) > col_width:
                project_str = project[: col_width - 2] + '..'
            else:
                project_str = project.ljust(col_width)

            typer.secho(
                f'{total_duration}  {project_str}  {typer.style(sparkline, fg="cyan")}',
                bold=True,
            )
        else:
            typer.secho(f'{total_duration}  {project}', bold=True)

        if ctx.obj.verbose > 0 or verbose > 0:
            for date, daily_stats in stats[project]['days'].items():
                timeSpent = _time.format_duration_aligned(
                    timedelta(seconds=daily_stats['timeSpentSeconds'])
                )
                typer.secho(
                    f'          {date} {timeSpent}  ' + '; '.join(daily_stats['comments']),
                    dim=True,
                )

    typer.echo('-' * 15)
    total_duration = _time.format_duration_aligned(
        timedelta(seconds=sum(project['timeSpentSeconds'] for project in stats.values()))
    )
    if axis_labels and show_sparkline:
        total_str = 'Total'.ljust(col_width)
        typer.echo(
            typer.style(f'{total_duration}  {total_str}', bold=True)
            + typer.style(f'  {axis_labels}', dim=True)
        )
    else:
        typer.secho(f'{total_duration}  Total', bold=True)


@app.command(rich_help_panel='GET')
def issues(
    ctx: typer.Context,
    project: Annotated[
        str, typer.Argument(envvar='JIRA_PROJECT', shell_complete=complete_project)
    ] = '*',
):
    "List issues"
    try:
        if project == '*':
            issues = _jira.get_all_issues(ctx.obj.jira)
        else:
            issues = _jira.get_issues(ctx.obj.jira, project=project)
    except jira.JIRAError as e:
        error(e.text)
    grid = Table(padding=(0, 1))
    grid.add_column('Key', justify='right', style='cyan')
    grid.add_column('Issue', justify='left')
    for key, summary in issues.items():
        grid.add_row(key, summary)
    rich.print(grid)


@app.command(rich_help_panel='GET')
def budget(
    ctx: typer.Context,
    issue: Annotated[
        str,
        typer.Argument(
            envvar='JIRA_ISSUE', shell_complete=complete_issue, show_default='last booked on'
        ),
    ] = '*',
):
    "List issues"
    # If no issue is specified, automatically select the last booked issue
    if issue == '*':
        # Get recent worklogs to find the last booked issue
        # Look back up to 30 days to find the most recent worklog
        from_date = datetime.now().date() - timedelta(days=30)
        to_date = datetime.now().date()
        recent_worklogs = tempo.get_worklogs(ctx.obj.myself['key'], from_date, to_date)

        if not recent_worklogs:
            error('No recent worklogs found. Please specify an issue.')

        # Sort worklogs by start time to get the most recent one
        most_recent_worklog = max(recent_worklogs, key=lambda w: w.started)
        issue = most_recent_worklog.issue.key

        # Check if there's an alias for the selected issue
        alias_for_issue = next(
            (alias for alias, issue_key in ctx.obj.aliases.items() if issue_key == issue), None
        )
        if alias_for_issue:
            rich.print(f'[dim]Using last booked issue: {issue} (alias: {alias_for_issue})[/dim]')
        else:
            rich.print(f'[dim]Using last booked issue: {issue}[/dim]')

    if issue in ctx.obj.aliases:
        issue = ctx.obj.aliases[issue]

    try:
        issue = ctx.obj.jira.issue(issue)
        worklogs = ctx.obj.jira.worklogs(issue=issue)
    except jira.JIRAError as e:
        error(e.text)

    logged_secs_per_person = {
        w.author.displayName: sum(w2.timeSpentSeconds for w2 in worklogs if w2.author == w.author)
        for w in worklogs
    }

    tt = issue.fields.timetracking

    grid = Table(padding=(0, 1))
    grid.add_column('', justify='right', style='cyan')
    grid.add_column('PT', justify='left')
    grid.add_column('Hours', justify='right')
    grid.add_column('%', justify='right')

    grid.add_row(
        'Estimate',
        _time.format_duration_workdays(tt.originalEstimateSeconds, max_day_digits=2),
        f'{tt.originalEstimateSeconds // 60 // 60}h',
        style='bold',
    )
    grid.add_row(
        'Used (total)',
        _time.format_duration_workdays(tt.timeSpentSeconds, max_day_digits=2),
        f'{tt.timeSpentSeconds // 60 // 60}h',
        f'{(tt.timeSpentSeconds / tt.originalEstimateSeconds * 100):.1f}%',
        style='bold',
    )
    for person, logged_secs in logged_secs_per_person.items():
        grid.add_row(
            person,
            _time.format_duration_workdays(logged_secs, max_day_digits=2),
            f'{logged_secs // 60 // 60}h',
            f'{(logged_secs / tt.timeSpentSeconds * 100):.1f}%',
            style='dim',
        )
    grid.add_row(
        'Remaining',
        _time.format_duration_workdays(tt.remainingEstimateSeconds, max_day_digits=2),
        f'{tt.remainingEstimateSeconds // 60 // 60}h',
        f'{(tt.remainingEstimateSeconds / tt.originalEstimateSeconds * 100):.1f}%',
        style='bold',
    )
    if tt.remainingEstimateSeconds > 0:
        for person, logged_secs in logged_secs_per_person.items():
            remaining_for_person = int(
                tt.remainingEstimateSeconds * (logged_secs / tt.timeSpentSeconds)
            )
            grid.add_row(
                person,
                _time.format_duration_workdays(remaining_for_person, max_day_digits=2),
                f'{remaining_for_person // 60 // 60}h',
                style='dim',
            )

    rich.print(grid)


@app.command(rich_help_panel='GET')
def projects(ctx: typer.Context):
    "List projects."
    try:
        projects = _jira.get_projects(ctx.obj.jira, no_cache=not ctx.obj.cache)
    except jira.JIRAError as e:
        error(e.text)

    grid = Table(padding=(0, 1))
    grid.add_column('Key', justify='right', style='cyan')
    grid.add_column('Project', justify='left')
    [grid.add_row(*p) for p in projects.items()]
    rich.print(grid)


@app.command(rich_help_panel='Configuration')
def reset(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option(
            '--force',
            '-f',
            show_default=False,
            help='Delete configuration immediately (without confirmation)',
            show_envvar=False,
        ),
    ] = False,
):
    "Clear local cache and configuration values."
    if force or typer.confirm('Delete cache?'):
        shutil.rmtree(caching.cache_dir, ignore_errors=True)
        typer.echo('Cache reset.')
    if force or typer.confirm('Delete API token from keyring?'):
        try:
            keyring.delete_password(name, os.environ['JIRA_USER'])
            caching.invalidate(_jira.myself)
            typer.echo('Token removed from keyring.')
        except PasswordDeleteError:
            log.info('No token in keyring to delete')
        except KeyError:
            log.info('Cannot delete token without JIRA_USER')

    ctx.invoke(config.config, unset=True, force=force)


@app.command(rich_help_panel='GET')
def init(
    ctx: typer.Context,
    cache: Annotated[
        bool,
        typer.Option(
            is_flag=True, show_default=True, help='Update local caches.', show_envvar=False
        ),
    ] = True,
):
    """Update local caches.

    Run this command, if a new project or issue doesn't show up in the
    list of projects or issues.
    """
    if cache:
        _jira.get_projects(ctx.obj.jira, update_cache=True)
        typer.echo('project cache updated.')
        _jira.get_all_issues(ctx.obj.jira, update_cache=True)
        typer.echo('issue cache updated.')


@app.command(hidden=True)
def debug(ctx: typer.Context):
    typer.echo(ctx.obj)


def get_project_name(ctx, issue):
    if issue.key in ctx.obj.aliases.values():
        project_alias = next(key for key, value in ctx.obj.aliases.items() if value == issue.key)
        return project_alias
    return issue.key


if __name__ == '__main__':
    app()
