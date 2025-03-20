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
    if ctx.invoked_subcommand not in 'log logm issues list projects init stats *'.split():
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
    start: Annotated[time, typer.Option(parser=_time.parse_time, show_default='9')] = None,
    end: Annotated[time, typer.Option(parser=_time.parse_time)] = None,
    lunch: Annotated[timedelta, typer.Option(parser=_time.parse_duration)] = None,
    message: Annotated[str, typer.Option('--message', '-m')] = None,
    yes: Annotated[bool, typer.Option('--yes', '-y', help='log time without confirmation')] = False,
):
    "Log time entry."
    if ctx.resilient_parsing:  # script is running for completion purposes
        return
    cfg = ctx.obj
    if issue in ctx.obj.aliases.values():
        issue = next(k for k, v in ctx.obj.aliases.items() if v == issue)

    try:
        cfg.issue = cfg.jira.issue(issue, fields='summary,comment')
    except jira.JIRAError as e:
        # If not issue is found, try to figure out what the user meant
        fuzzy_matches = set(get_close_matches(issue, ctx.obj.aliases.values(), n=5, cutoff=0.6))
        similar_issues = {
            value: f'alias for {key}'
            for key, value in ctx.obj.aliases.items()
            if value in fuzzy_matches
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
            suggested_issue = next(k for k in similar_issues)
            # only one similar issue, we can assume the user meant this issue and continue
            if typer.confirm(f"Did you mean '{suggested_issue}'?", default=True):
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
    description = get_project_description(ctx, cfg.issue)

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

    rich.print(
        'Log',
        _time.format_duration(duration),
        f'({start.strftime("%H:%M")} - {end.strftime("%H:%M")})',
        f'as [italic]{cfg.issue.fields.summary} ({description})[/italic]',
        f'for {_time.format_date_relative(day)}',
    )

    if duration_logged + duration > timedelta(hours=10):
        error(
            f'You already have {
                _time.format_duration(duration_logged)
            } logged on that day. Cannot log more than 10h per day.'
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
    for worklog in tempo.get_worklogs(ctx.obj.myself['key'], from_date, to_date):
        typer.echo(
            f'{worklog.started.strftime("%d.%m %H:%M")}  {
                _time.format_duration_aligned(timedelta(seconds=worklog.timeSpentSeconds), 2)
            }  {get_project_description(ctx, worklog.issue)} ({worklog.issue.key}) - {
                worklog.comment
            }'
        )


@app.command('stats', rich_help_panel='GET')
def cmd_stats(
    ctx: typer.Context,
    date_range: Annotated[str, arg_relative_date_range] = 'week',
    from_date: Annotated[Optional[date], typer.Option('--from', parser=_time.parse_date)] = None,
    to_date: Annotated[
        date, typer.Option('--to', parser=_time.parse_date, show_default='today')
    ] = datetime.now().date().strftime('%d.%m'),
    verbose: Annotated[int, typer.Option('-v', count=True)] = 0,
):
    """Show logged time per project.

    For a custom time range, use the --from and --to options:

    $ lt list --from 1.12 --to 24.12
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
        project = get_project_description(ctx, worklog.issue)
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

    for project in sorted(stats, key=lambda k: stats[k]['timeSpentSeconds'], reverse=True):
        total_duration = _time.format_duration_aligned(
            timedelta(seconds=stats[project]['timeSpentSeconds'])
        )
        typer.echo(f'{typer.style(total_duration, bold=True)}  {project}')
        if ctx.obj.verbose > 0 or verbose > 0:
            for date, daily_stats in stats[project]['days'].items():
                timeSpent = _time.format_duration_aligned(
                    timedelta(seconds=daily_stats['timeSpentSeconds'])
                )
                typer.echo(f'          {date}: {timeSpent} - , '.join(daily_stats['comments']))
    typer.secho('-' * 20)
    total_duration = _time.format_duration_aligned(
        timedelta(seconds=sum(project['timeSpentSeconds'] for project in stats.values()))
    )
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


def get_project_description(ctx, issue):
    if alias := ctx.obj.aliases.get(issue.key):
        return alias
    if isinstance(issue, jira.Issue):
        return issue.key
    return issue.summary


if __name__ == '__main__':
    app()
