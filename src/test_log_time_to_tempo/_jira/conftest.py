import pytest

from log_time_to_tempo._jira import MockClient, MockIssue, MockIssueFields, MockProject


class MockAuthor:
    def __init__(self, display_name: str):
        self.displayName = display_name


class MockWorklog:
    def __init__(self, author_name: str, time_spent_seconds: int):
        self.author = MockAuthor(author_name)
        self.timeSpentSeconds = time_spent_seconds


class MockTimetracking:
    def __init__(self):
        self.originalEstimateSeconds = 28800  # 8 hours
        self.timeSpentSeconds = 14400  # 4 hours
        self.remainingEstimateSeconds = 14400  # 4 hours


class MockIssueFieldsWithTimetracking(MockIssueFields):
    def __init__(self, summary: str):
        super().__init__(summary)
        self.timetracking = MockTimetracking()


class TestClient(MockClient):
    def search_issues(self, jql='project=TEST', **kwargs):
        project = jql.split('=', 1)[1]
        return [
            MockIssue(
                key=f'{project.upper()}-{n}', fields=MockIssueFields(summary=f'Test issue #{n}')
            )
            for n in range(1, 21)
        ]

    def issue(self, issue: str, **kwargs) -> MockIssue:
        return MockIssue(key=issue, fields=MockIssueFieldsWithTimetracking(summary='Test Issue'))

    def worklogs(self, issue, **kwargs):
        """Mock worklogs method for testing budget command."""
        return [
            MockWorklog('Test User', 7200),  # 2 hours
            MockWorklog('Another User', 7200),  # 2 hours
        ]

    def projects(self):
        return [MockProject('TEST', 'Test project'), MockProject('ZEST', 'Zest project')]

    def myself(self):
        return dict(name='test-user', key='test-user-key')


@pytest.fixture()
def test_client():
    return TestClient()
