import pathlib
from enum import StrEnum, auto
from typing import Annotated

import dotenv
import rich
import typer
from dotenv import dotenv_values, find_dotenv, load_dotenv

from .. import name
from .._logging import log
from . import app, app_dir, link

filename = f'.{name}'
fp_config_default = app_dir / filename


class ConfigOptionChoice(typer.completion.click.Choice):
    """Custom Choice type that hides enum options from usage line but provides clear error messages."""

    def __init__(self, choices, case_sensitive=True):
        super().__init__(choices, case_sensitive)

    def get_metavar(self, param):
        """Override to not show choices in usage line."""
        return None

    def convert(self, value, param, ctx):
        """Custom conversion with clear error messages."""
        try:
            return super().convert(value, param, ctx)
        except typer.completion.click.BadParameter:
            # Custom error message without redundancy
            valid_options = ', '.join([f"'{choice}'" for choice in self.choices])
            raise typer.completion.click.BadParameter(
                f"'{value}' is not a valid configuration option.\n"
                f'Valid options are: {valid_options}'
            ) from None


class ConfigOption(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """Return the lower-cased version of the member name."""
        return name.upper()

    JIRA_INSTANCE = auto()
    JIRA_USER = auto()
    # log command
    LT_LOG_ISSUE = auto()
    LT_LOG_START = auto()
    LT_LOG_MESSAGE = auto()
    LT_LOG_DURATION = auto()


def complete_config_option(
    ctx, param: str, incomplete: str
) -> list[typer.completion.click.shell_completion.CompletionItem]:
    """Provide shell completion for config options."""
    return [
        typer.completion.click.shell_completion.CompletionItem(
            option.value, help=f'Configuration option: {option.value}'
        )
        for option in ConfigOption
        if option.value.startswith(incomplete.upper())
    ]


def ensure_app_dir_exists():
    fp_config_default.parent.mkdir(exist_ok=True, parents=True)


def load_local_config():
    if cfg := find_local_config():
        load_dotenv(cfg)


def find_local_config() -> pathlib.Path | None:
    if cfg := find_dotenv(filename, usecwd=True):
        return pathlib.Path(cfg)


def load():
    """Find and load closest local config (if it exists) and system config.

    Local configuration takes precedence over system configuration.
    """
    ensure_app_dir_exists()
    load_local_config()
    load_dotenv(fp_config_default, override=False)


@app.command(rich_help_panel='Configuration')
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
                if key in dotenv_values(fp):
                    log.info('Unsetting %s from "%s"', key, fp)
                    dotenv.unset_key(fp, key)
                    return
        else:
            for fp in config_files:
                if key in (final_config := dotenv_values(fp)):
                    rich.print(final_config[key])
                    return

    # We are working with full configuration files
    if key is None:
        final_config = {}
        for fp in config_files:
            if fp.exists():
                this_config = dotenv_values(fp)
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


def load_full_config(config_files: list[str | pathlib.Path] = None):
    if config_files is None:
        config_files = [fp_config_default, find_local_config()]
    full_config = {}
    for fp in config_files:
        if fp.exists():
            full_config.update(dotenv_values(fp))
    return full_config
