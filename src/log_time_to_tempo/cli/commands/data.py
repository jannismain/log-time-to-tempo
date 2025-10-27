from datetime import datetime, timedelta

import jira
import rich
import typer
from rich.table import Table
from typing_extensions import Annotated

from ... import _jira, _time, tempo
from .. import app, error
from ..completions import complete_issue, complete_project


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
    """Show used and remaining time budget for given issue.

    If no issue is specified, automatically selects the last booked
    issue from recent worklogs.
    """
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
            rich.print(f'[dim]Showing budget for {alias_for_issue} ({issue})[/dim]')
        else:
            rich.print(f'[dim]Showing budget for {issue}[/dim]')

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
