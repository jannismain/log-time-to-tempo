from datetime import date
from typing import Callable

import pytest
from click.testing import Result
from keyring.errors import PasswordDeleteError

from test_log_time_to_tempo._jira.conftest import TestClient


@pytest.fixture
def mock_tempo(monkeypatch, tmp_path):
    def no_worklogs(worker_id: str, from_date: date, to_date: date):
        return []

    monkeypatch.setattr('log_time_to_tempo.tempo.get_worklogs', no_worklogs)


@pytest.fixture
def mock_jira(monkeypatch):
    monkeypatch.setattr('jira.JIRA', TestClient)


@pytest.fixture
def mock_keyring(monkeypatch):
    _keyring = {}

    def _set_password(service_name, username, password):
        if service_name not in _keyring:
            _keyring[service_name] = {}
        _keyring[service_name].update({username: password})

    def _get_password(service_name, username):
        try:
            return _keyring[service_name][username]
        except KeyError:
            return None

    def _delete_password(service_name, username):
        try:
            del _keyring[service_name][username]
        except KeyError as e:
            raise PasswordDeleteError() from e

    monkeypatch.setattr('keyring.get_password', _get_password)
    monkeypatch.setattr('keyring.set_password', _set_password)
    monkeypatch.setattr('keyring.delete_password', _delete_password)

    yield _keyring


@pytest.fixture
def mock(mock_tempo, mock_jira, mock_keyring):
    """Use this fixture to mock all server communication."""


@pytest.fixture
def log_time(cli, mock) -> Callable[[list[str]], Result]:
    return cli


def test_stats_with_no_worklogs(log_time):
    """Test that stats command handles empty worklog list gracefully.

    This test ensures that when there are no worklogs for the selected
    period, the stats command doesn't crash with a ValueError but
    instead shows a clean output with zero totals.
    """
    result: Result = log_time(['stats'], env={'JIRA_API_TOKEN': '12345'})

    assert result.exit_code == 0, f'should exit cleanly, got: {result.stderr}'
    assert 'Period:' in result.stdout, 'should show period information'
    assert 'Total' in result.stdout, 'should show total even when empty'

    # Should not contain any error messages
    assert 'Error' not in result.stdout
    assert 'Traceback' not in result.stdout
    assert 'ValueError' not in result.stderr if result.stderr else True


def test_stats_with_sparkline_disabled(log_time):
    """Test stats command with sparkline disabled and no worklogs."""
    result: Result = log_time(['stats', '--no-sparkline'], env={'JIRA_API_TOKEN': '12345'})

    assert result.exit_code == 0, f'should exit cleanly, got: {result.stderr}'
    assert 'Period:' in result.stdout, 'should show period information'
    assert 'Total' in result.stdout, 'should show total even when empty'


def test_stats_help(log_time):
    """Test that stats help works."""
    result: Result = log_time(['stats', '--help'], env={'JIRA_API_TOKEN': '12345'})
    assert result.stdout
    assert not result.stderr
    assert result.exit_code == 0
