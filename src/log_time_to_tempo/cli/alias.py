import json
import re
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
        # Regex to match issue keys like TS-12688, TSI-7, MB-345
        issue_key_pattern = re.compile(r'^[A-Z]+-\d+$')
        # Check if all keys match the pattern
        if all(issue_key_pattern.match(key) for key in aliases):
            # Swap keys and values
            # keep backwards compatibility with aliases defined prior to 0.0.9
            aliases = {value: key for key, value in aliases.items()}
            _write_aliases(aliases)
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
    alias: Annotated[str, typer.Argument()] = None,
    issue: Annotated[str, typer.Argument(shell_complete=complete_issue_aliased)] = None,
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
        for alias, issue in sorted(aliases.items(), key=lambda item: item[1]):
            grid.add_row(alias, issue)
        rich.print(grid)
        return
    if not alias:
        alias = typer.prompt('Alias: ')
    if alias in aliases:
        if not typer.confirm(f"Alias '{alias}' already exists ({aliases[alias]}). Overwrite?"):
            return
    aliases[alias] = issue
    _write_aliases(aliases)
    typer.echo(f'Alias for {issue} created: {alias}')


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
            alias = menu_items[idx][KEY]
        else:
            return
    else:
        if issue_or_alias in aliases.keys():
            alias = issue_or_alias
        elif issue_or_alias in aliases.values():
            alias = next(k for k, v in aliases.items() if v == issue_or_alias)
        else:
            typer.secho(f'Unknown issue or alias: {issue_or_alias}', color='yellow')
            exit(1)
    if force or typer.confirm(f"Delete alias '{alias}' for {aliases[alias]}?"):
        aliases.pop(alias)
        _write_aliases(aliases)
