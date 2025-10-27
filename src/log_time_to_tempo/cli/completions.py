from click.shell_completion import CompletionItem

from .. import _jira, _time


def complete_project(ctx, param: str, incomplete: str) -> list[str]:
    return [
        CompletionItem(value=project_key, help=project_name)
        for project_key, project_name in _jira.get_projects(
            client=_jira.MockClient(), no_update_cache=True
        ).items()
        if project_key.startswith(incomplete) or project_name.lower().startswith(incomplete)
    ]


def complete_issue(ctx, param: str, incomplete: str) -> list[CompletionItem]:
    return [
        CompletionItem(key, help=description)
        for key, description in _jira.get_all_issues(
            client=_jira.MockClient(), no_update_cache=True
        ).items()
    ]


def complete_date_range(ctx, param, incomplete) -> list[CompletionItem]:
    return list(
        CompletionItem(
            v,
            help=f'short: {", ".join(_time.relative_date_range_abbreviations.get(v))}'
            if v in _time.relative_date_range_abbreviations
            else '',
        )
        for v in _time.RelativeDateRange._value2member_map_.keys()
    )
