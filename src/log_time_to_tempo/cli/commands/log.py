import os
from datetime import date, datetime, time, timedelta
from difflib import get_close_matches

import jira
import rich
import typer
from typing_extensions import Annotated

from ... import _jira, _time, tempo
from .. import app, error
from ..completions import complete_issue
from ..utils import get_project_name


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
    """Log multiple time entries at once.

    Entries are specified as a comma-separated list of issue:duration pairs.

    Example: lt logm opt:2h,project:5h30m,admin:30m
    """
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
