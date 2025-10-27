import os
import platform
from typing import Optional

import jira
import keyring
import keyring.backends.macOS
import typer
from click.shell_completion import CompletionItem
from typing_extensions import Annotated

from .. import __version__, _jira, _time, cfg, name
from .._logging import log
from . import app, config, error, link
from .commands import alias, data
from .commands.config import config as cmd_config

token_found_in_environment = os.getenv('JIRA_API_TOKEN')

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

    config.load()

    ctx.obj = cfg  # make some config options available to subcommands

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
        ctx.invoke(cmd_config, key='JIRA_USER', value=cfg.myself['name'])
    except jira.JIRAError as e:
        error(f'Could not authenticate: {e}')

    cfg.token = token

    if persist_token:
        log.info("Saved token for '%s' to keyring.", cfg.myself['name'])
        keyring.set_password(name, cfg.myself['name'], token)

    cfg.cache = cache
    if not _jira.cache_is_warm() and ctx.invoked_subcommand != 'init' and cache:
        ctx.invoke(data.init, ctx=ctx, cache=cache)
    log.debug('user: %s', cfg.myself['name'])

    if cache and not _jira.cache_is_warm():
        _jira.get_projects(cfg.jira)
        _jira.get_all_issues(cfg.jira)


# Import command modules to register commands
from . import commands  # noqa: F401,E402

if __name__ == '__main__':
    app()
