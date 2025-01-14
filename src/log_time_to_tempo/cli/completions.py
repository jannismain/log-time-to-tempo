from click.shell_completion import CompletionItem

from .. import _jira


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
