import pathlib
from enum import StrEnum, auto

import typer
from dotenv import dotenv_values, find_dotenv, load_dotenv

from .. import name
from . import app_dir

filename = f'.{name}'
fp_config_default = app_dir / filename


class ConfigOptionChoice(typer.completion.click.Choice):
    """Custom Choice type that hides enum options from usage line.

    This provides a more clear error message.
    """

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


def load_full_config(config_files: list[str | pathlib.Path] = None):
    if config_files is None:
        config_files = [fp_config_default, find_local_config()]
    full_config = {}
    for fp in config_files:
        if fp.exists():
            full_config.update(dotenv_values(fp))
    return full_config
