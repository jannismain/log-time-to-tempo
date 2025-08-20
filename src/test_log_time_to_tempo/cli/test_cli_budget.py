from datetime import date, datetime, timedelta

import pytest
from typer.testing import CliRunner

from log_time_to_tempo.cli import app
from log_time_to_tempo.tempo import Issue, Worklog
from test_log_time_to_tempo._jira.conftest import TestClient


@pytest.fixture
def mock_jira(monkeypatch):
    monkeypatch.setattr('jira.JIRA', TestClient)


@pytest.fixture
def mock_keyring(monkeypatch):
    _keyring = {}

    def _set_password(service_name, username, password):
        if service_name not in _keyring:
            _keyring[service_name] = {}
        _keyring[service_name][username] = password

    def _get_password(service_name, username):
        return _keyring.get(service_name, {}).get(username)

    def _delete_password(service_name, username):
        if service_name in _keyring and username in _keyring[service_name]:
            del _keyring[service_name][username]

    monkeypatch.setattr('keyring.set_password', _set_password)
    monkeypatch.setattr('keyring.get_password', _get_password)
    monkeypatch.setattr('keyring.delete_password', _delete_password)


@pytest.fixture
def mock_tempo_with_worklogs(monkeypatch):
    """Mock tempo with recent worklogs for testing."""

    def get_worklogs(worker_id: str, from_date: date, to_date: date):
        # Create a mock recent worklog
        return [
            Worklog(
                billableSeconds=7200,
                comment='Working on feature',
                issue=Issue(id=123, key='TSI-123', summary='Test Issue 123'),
                started=datetime.now() - timedelta(days=1),
                originTaskId=123,
                timeSpent='2h',
                timeSpentSeconds=7200,
                dateUpdated='2025-08-19T10:00:00',
                dateCreated='2025-08-19T10:00:00',
            )
        ]

    monkeypatch.setattr('log_time_to_tempo.tempo.get_worklogs', get_worklogs)


@pytest.fixture
def mock_tempo_with_worklogs_aliased_issue(monkeypatch):
    """Mock tempo with recent worklogs for an issue that has an alias."""

    def get_worklogs(worker_id: str, from_date: date, to_date: date):
        # Create a mock recent worklog for an issue that will have an alias
        return [
            Worklog(
                billableSeconds=7200,
                comment='Working on feature',
                issue=Issue(id=456, key='TSI-456', summary='Test Issue with Alias'),
                started=datetime.now() - timedelta(days=1),
                originTaskId=456,
                timeSpent='2h',
                timeSpentSeconds=7200,
                dateUpdated='2025-08-19T10:00:00',
                dateCreated='2025-08-19T10:00:00',
            )
        ]

    monkeypatch.setattr('log_time_to_tempo.tempo.get_worklogs', get_worklogs)


@pytest.fixture
def mock_aliases_with_test_alias(monkeypatch):
    """Mock aliases that includes an alias for TSI-456."""

    def mock_read_aliases():
        return {'feature-work': 'TSI-456', 'another-alias': 'TSI-789'}

    monkeypatch.setattr('log_time_to_tempo.cli.alias._read_aliases', mock_read_aliases)


@pytest.fixture
def mock_tempo_no_worklogs(monkeypatch):
    """Mock tempo with no recent worklogs."""

    def get_worklogs(worker_id: str, from_date: date, to_date: date):
        return []

    monkeypatch.setattr('log_time_to_tempo.tempo.get_worklogs', get_worklogs)


def test_budget_with_specific_issue(mock_jira, mock_keyring, mock_tempo_with_worklogs):
    """Test budget command with a specific issue provided."""
    runner = CliRunner()
    result = runner.invoke(app, ['budget', 'TSI-7'], input='test-token\n')

    # Should work normally when issue is provided
    assert result.exit_code == 0


def test_budget_auto_select_last_issue(mock_jira, mock_keyring, mock_tempo_with_worklogs):
    """Test budget command automatically selects last booked issue when none provided."""
    runner = CliRunner()
    result = runner.invoke(app, ['budget'], input='test-token\n')

    # Should automatically select the last booked issue
    assert result.exit_code == 0
    assert 'Using last booked issue: TSI-123' in result.stdout


def test_budget_no_recent_worklogs(mock_jira, mock_keyring, mock_tempo_no_worklogs):
    """Test budget command when no recent worklogs are found."""
    runner = CliRunner()
    result = runner.invoke(app, ['budget'], input='test-token\n')

    # Should exit with error when no recent worklogs found
    assert result.exit_code == 1
    assert 'No recent worklogs found' in result.stdout


def test_budget_auto_select_last_issue_with_alias(
    mock_jira, mock_keyring, mock_tempo_with_worklogs_aliased_issue, mock_aliases_with_test_alias
):
    """Test budget command shows alias when auto-selecting last booked issue that has an alias."""
    runner = CliRunner()
    result = runner.invoke(app, ['budget'], input='test-token\n')

    # Should automatically select the last booked issue and show the alias
    assert result.exit_code == 0
    assert 'Using last booked issue: TSI-456 (alias: feature-work)' in result.stdout
