"""Shared utilities for CLI commands."""


def get_project_name(ctx, issue):
    """Get project name, using alias if available."""
    if issue.key in ctx.obj.aliases.values():
        project_alias = next(key for key, value in ctx.obj.aliases.items() if value == issue.key)
        return project_alias
    return issue.key
