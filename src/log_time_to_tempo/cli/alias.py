import json
from typing import Annotated

import typer

from . import app, app_dir
from .completions import complete_issue

fp_project_aliases = app_dir / 'aliases'


def _read_aliases() -> dict:
    aliases = {}
    if fp_project_aliases.exists():
        aliases = json.load(fp_project_aliases.open())
    return aliases


def _write_aliases(aliases):
    json.dump(aliases, fp_project_aliases.open('w'), indent=2)


@app.command(rich_help_panel='Configuration')
def alias(
    ctx: typer.Context,
    issue: Annotated[str, typer.Argument(shell_complete=complete_issue)] = None,
    alias: Annotated[str, typer.Argument()] = None,
):
    "Create an alias for an issue."
    aliases = _read_aliases()
    if not issue:
        typer.echo('\n'.join(f'{k}: {v}' for k, v in aliases.items()))
        return
    if issue in aliases:
        if not typer.confirm(f'Alias for {issue} already exists ({alias}). Overwrite?'):
            return
    aliases[issue] = alias if alias else typer.prompt('Alias: ')
    _write_aliases(aliases)
    typer.echo(f'Alias for {issue} created: {aliases[issue]}')
