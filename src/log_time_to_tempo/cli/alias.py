import json
from typing import Annotated

import rich
import typer
from click.shell_completion import CompletionItem
from rich.table import Table
from simple_term_menu import TerminalMenu
from typer import Context

from .. import _jira
from . import app, app_dir

fp_project_aliases = app_dir / 'aliases'


def _read_aliases() -> dict:
    aliases = {}
    if fp_project_aliases.exists():
        aliases = json.load(fp_project_aliases.open())
    return aliases


def _write_aliases(aliases):
    json.dump(aliases, fp_project_aliases.open('w'), indent=2)


def complete_issue_aliased(ctx: Context, param: str, incomplete: str) -> list[CompletionItem]:
    if ctx.params.get('unset'):
        issues = _read_aliases()
    else:
        issues = _jira.get_all_issues(client=_jira.MockClient(), no_update_cache=True)
    return [CompletionItem(key, help=description) for key, description in issues.items()]


@app.command(rich_help_panel='Configuration')
def alias(
    ctx: typer.Context,
    unset: Annotated[
        bool, typer.Option(help='unset a previously set alias', show_envvar=False)
    ] = False,
    issue: Annotated[str, typer.Argument(shell_complete=complete_issue_aliased)] = None,
    alias: Annotated[str, typer.Argument()] = None,
):
    "Create an alias for an issue."
    if unset:
        ctx.invoke(alias_unset, issue_or_alias=issue if issue else alias)
        return
    aliases = _read_aliases()
    if not issue:
        grid = Table(padding=(0, 1))
        grid.add_column('Alias', justify='right', style='cyan')
        grid.add_column('Issues', justify='left')
        alias_values = sorted(set(aliases.values()))
        for alias in alias_values:
            grid.add_row(alias, '\n'.join(k for k, v in aliases.items() if v == alias))
        rich.print(grid)
        return
    if issue in aliases:
        if not typer.confirm(f'Alias for {issue} already exists ({alias}). Overwrite?'):
            return
    aliases[issue] = alias if alias else typer.prompt('Alias: ')
    _write_aliases(aliases)
    typer.echo(f'Alias for {issue} created: {aliases[issue]}')


@app.command(hidden=True)
def alias_unset(
    issue_or_alias: str = None,
    force: Annotated[bool, typer.Option] = False,
):
    aliases = _read_aliases()
    if issue_or_alias is None:
        KEY, VALUE = 0, 1
        menu_items = [
            (f'[{idx}]{item[KEY]} ({item[VALUE]})', item[KEY])
            for idx, item in enumerate(aliases.items())
        ]

        STR, KEY = 0, 1
        tm = TerminalMenu([item[STR] for item in menu_items])
        idx = tm.show()
        if idx is not None:
            issue = menu_items[idx][KEY]
        else:
            return
    else:
        if issue_or_alias in aliases.keys():
            issue = issue_or_alias
        elif issue_or_alias in aliases.values():
            issue = next(k for k, v in aliases.items() if v == issue_or_alias)
        else:
            typer.secho(f'Unknown issue or alias: {issue_or_alias}', color='yellow')
            exit(1)
    if force or typer.confirm(f"Delete alias '{aliases[issue]}' for {issue}?"):
        aliases.pop(issue)
        _write_aliases(aliases)
