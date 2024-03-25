import pathlib
import typing as t

import click
import typer

from .. import name

app_dir = pathlib.Path(click.get_app_dir(name))
app = typer.Typer(no_args_is_help=True, rich_markup_mode='rich', chain=True)


def link(uri, label=None):
    if label is None:
        label = uri
    parameters = ''

    # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST
    escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'

    return escape_mask.format(parameters, uri, label)


def error(message, terminate=True, code=1):
    typer.secho(message, fg=typer.colors.RED)
    if terminate:
        exit(code)


def _patch_typer_argument_shell_completion():
    from typer import __version__

    if (0, 4, 0) <= tuple(int(v) for v in __version__.split('.')) <= (0, 9, 0):
        from typer import main as typer_main
        from typer.models import ParamMeta

        upstream_get_click_param = typer_main.get_click_param

        def patched_get_click_param(
            param: ParamMeta,
        ) -> t.Tuple[t.Union[click.Argument, click.Option], t.Any]:
            """Patch this bug: https://github.com/tiangolo/typer/issues/334."""
            click_param = upstream_get_click_param(param)
            if isinstance(click_param[0], click.Argument) and getattr(
                param.default, 'shell_complete', None
            ):
                click_param[0]._custom_shell_complete = param.default.shell_complete
            return click_param

        typer_main.get_click_param = patched_get_click_param


_patch_typer_argument_shell_completion()
