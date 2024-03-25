import pytest

from log_time_to_tempo.cli.completions import MockClient, MockIssue, MockIssueFields, MockProject


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
        return MockIssue(key=issue, fields=MockIssueFields(summary='Test Issue'))

    def projects(self):
        return [MockProject('TEST', 'Test project'), MockProject('ZEST', 'Zest project')]

    def myself(self):
        return dict(name='test-user', key='test-user-key')


@pytest.fixture()
def test_client():
    return TestClient()
