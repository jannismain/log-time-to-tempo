from dataclasses import dataclass

from click.shell_completion import CompletionItem

from .. import _jira


def complete_project(ctx, param: str, incomplete: str) -> list[str]:
    return [
        CompletionItem(value=project_key, help=project_name)
        for project_key, project_name in _jira.get_projects(
            client=MockClient(), no_update_cache=True
        ).items()
        if project_key.startswith(incomplete) or project_name.lower().startswith(incomplete)
    ]


def complete_issue(ctx, param: str, incomplete: str) -> list[CompletionItem]:
    return [
        CompletionItem(key, help=description)
        for key, description in _jira.get_all_issues(
            client=MockClient(), no_update_cache=True
        ).items()
    ]


# before `init`, caches are not initialized and no client is available during completion
# so we use the MockClient to provide initial completions.


@dataclass
class MockProject:
    key: str
    name: str


@dataclass
class MockIssueFields:
    summary: str


@dataclass
class MockIssue:
    key: str
    fields: MockIssueFields


class MockClient:
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    def projects(self):
        return [MockProject(key='TSI', name='cc Timesheet Internal Tasks')]

    def search_issues(self, jql: str, fields: str = ''):
        return [MockIssue('TSI-7', MockIssueFields('Off-Project Time'))]
