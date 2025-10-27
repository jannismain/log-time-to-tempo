import os
import pathlib
import shutil

import dotenv
import keyring
import rich
import typer
from keyring.errors import PasswordDeleteError
from typing_extensions import Annotated

from ... import _jira, caching, name
from ..._logging import log
from .. import app, link
from ..config import (
    ConfigOption,
    ConfigOptionChoice,
    complete_config_option,
    filename,
    find_local_config,
    fp_config_default,
)


@app.command(name='config', rich_help_panel='Configuration')
def config(
    key: Annotated[
        str,
        typer.Argument(
            help='Read or update this configuration option',
            show_default=False,
            shell_complete=complete_config_option,
            click_type=ConfigOptionChoice(
                [option.value for option in ConfigOption], case_sensitive=False
            ),
        ),
    ] = None,
    value: Annotated[
        str,
        typer.Argument(
            help='Update given configuration option with this value', show_default=False
        ),
    ] = None,
    system: Annotated[
        bool,
        typer.Option(
            '--system/--local',
            show_default=False,
            help='interact with specific configuration',
            show_envvar=False,
        ),
    ] = None,
    unset: Annotated[
        bool,
        typer.Option('--unset', show_default=False, help='Remove configuration', show_envvar=False),
    ] = None,
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
    "Interact with configuration."

    # Convert string key to enum if provided
    if key is not None:
        key = ConfigOption(key.upper())

    # Determine which configuration files to interact with
    config_files = []
    fp_closest_local_config = find_local_config()
    if system is True:
        config_files += [fp_config_default]
    elif system is False:
        if fp_closest_local_config:
            config_files += [fp_closest_local_config]
        else:
            config_files += [pathlib.Path(filename)]
    elif system is None:
        if fp_closest_local_config:
            config_files += [fp_closest_local_config]
        config_files += [fp_config_default]

    # We are working with individual configuration options
    if key is not None:
        if value is not None:
            fp = config_files[0]
            dotenv.set_key(fp, key, value)
            return
        if unset:
            for fp in config_files:
                if key in dotenv.dotenv_values(fp):
                    log.info('Unsetting %s from "%s"', key, fp)
                    dotenv.unset_key(fp, key)
                    return
        else:
            for fp in config_files:
                if key in (final_config := dotenv.dotenv_values(fp)):
                    rich.print(final_config[key])
                    return

    # We are working with full configuration files
    if key is None:
        final_config = {}
        for fp in config_files:
            if fp.exists():
                this_config = dotenv.dotenv_values(fp)
                if unset:
                    if not force:
                        rich.print_json(data=this_config)
                    if force or typer.confirm(
                        f'Do you want to delete configuration at "{link(fp)}"?'
                    ):
                        fp.unlink()
                        typer.echo('Config reset.')
                # keep precedence of local over system config
                final_config = {**this_config, **final_config}
        if not unset:
            if final_config:
                rich.print_json(data=final_config)
            else:
                log.warning('No configuration found.')


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

    ctx.invoke(config, unset=True, force=force)
