from datetime import date, datetime, timedelta
from typing import Optional

import rich
import typer
from rich.table import Table
from typing_extensions import Annotated

from ... import _time, tempo
from .. import app
from .._sparkline import (
    determine_date_range_type,
    generate_axis_labels,
    generate_sparkline_from_daily_data,
)
from ..completions import complete_date_range
from ..utils import get_project_name

# TODO: Combine `stats` and `list` commands into one command with a flag whether to aggregate projects


@app.command('list', rich_help_panel='GET')
def cmd_list(
    ctx: typer.Context,
    date_range: Annotated[
        str,
        typer.Argument(
            callback=lambda x: _time.resolve_relative_date_range(x),
            shell_complete=complete_date_range,
        ),
    ] = 'week',
    from_date: Annotated[date, typer.Option('--from', parser=_time.parse_date)] = None,
    to_date: Annotated[
        date, typer.Option('--to', parser=_time.parse_date, show_default='today')
    ] = datetime.now().date(),
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
    date_range: Annotated[
        str,
        typer.Argument(
            callback=lambda x: _time.resolve_relative_date_range(x),
            shell_complete=complete_date_range,
        ),
    ] = 'month',
    from_date: Annotated[Optional[date], typer.Option('--from', parser=_time.parse_date)] = None,
    to_date: Annotated[
        date, typer.Option('--to', parser=_time.parse_date, show_default='today')
    ] = datetime.now().date(),
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
                'comments': {worklog.comment},
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
