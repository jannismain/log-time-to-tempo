import os
import shutil
from datetime import date, datetime, time, timedelta

import jira
import keyring
import rich
import typer
from keyring.errors import PasswordDeleteError
from rich.table import Table
from typing_extensions import Annotated

from .. import _jira, _time, caching, cfg, name, tempo
from .._logging import log
from . import app, config, error, link
from .completions import complete_issue, complete_project

token_found_in_environment = os.getenv('JIRA_API_TOKEN')
config.load()


def cb_duration(ctx: typer.Context, value: str) -> timedelta:
    if value:
        return _time.parse_duration(value)


@app.callback(
    invoke_without_command=True,
    context_settings=dict(auto_envvar_prefix=name.upper(), show_default=False),
)
def main(
    ctx: typer.Context,
    token: Annotated[str, typer.Option(envvar='JIRA_API_TOKEN', show_default='prompt')] = None,
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

    # return early for subcommands that don't interact with jira
    if ctx.invoked_subcommand not in 'log issues list projects init *'.split():
        return

    if token is None:
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
    from_time: Annotated[time, typer.Option(parser=_time.parse_time, show_default='9')] = None,
    to_time: Annotated[time, typer.Option(parser=_time.parse_time)] = None,
    message: Annotated[str, typer.Option('--message', '-m')] = None,
    yes: Annotated[bool, typer.Option('--yes', '-y', help='log time without confirmation')] = False,
):
    "Log time entry."
    if ctx.resilient_parsing:  # script is running for completion purposes
        return
    cfg = ctx.obj
    cfg.issue = cfg.jira.issue(issue, fields='summary,comment')

    worklogs = tempo.get_worklogs(ctx.obj.myself['key'], day, day)
    seconds_logged = sum(worklog.timeSpentSeconds for worklog in worklogs)
    duration_logged = timedelta(seconds=seconds_logged)
    if worklogs and from_time is None:
        last_worklog = worklogs[-1]
        from_time = (last_worklog.started + timedelta(seconds=last_worklog.timeSpentSeconds)).time()
    elif from_time is None:
        from_time = _time.parse_time(os.getenv('LT_LOG_FROM_TIME', '9'))

    started = datetime.combine(day, from_time)
    if to_time is not None:
        duration = datetime.combine(day, to_time) - started
    else:
        to_time = (started + duration).time()

    rich.print(
        'Log',
        _time.format_duration(duration),
        f'({from_time.strftime('%H:%M')} - {to_time.strftime('%H:%M')})',
        f'as [italic]{cfg.issue.fields.summary} ({cfg.issue.key})[/italic]',
        f'for {_time.format_date_relative(day)}',
    )

    if duration_logged + duration > timedelta(hours=10):
        error(
            f'You already have {_time.format_duration(duration_logged)} logged on that day. Cannot log more than 10h per day.'
        )

    if yes or typer.confirm('Continue?'):
        tempo.create_worklog(
            worker_id=cfg.myself['key'],
            task_id=cfg.issue.id,
            started=started.isoformat(timespec='milliseconds'),
            time_spent_seconds=duration.total_seconds(),
            message=message,
        )


@app.command('list', rich_help_panel='GET')
def cmd_list(
    ctx: typer.Context,
    date_range: Annotated[_time.RelativeDateRange, typer.Argument()] = 'week',
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
            f'{worklog.started.strftime("%d.%m %H:%M")}: {worklog.timeSpent} - {worklog.issue.summary} ({worklog.issue.key}) - {worklog.comment}'
        )


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


if __name__ == '__main__':
    app()
