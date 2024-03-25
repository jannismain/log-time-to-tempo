from datetime import date, timedelta
from typing import Callable

import keyring
import pytest
from click.testing import Result
from keyring.errors import PasswordDeleteError

from log_time_to_tempo.cli import name
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


@pytest.mark.parametrize('cmd', 'config issues list projects log'.split())
def test_help(log_time, cmd):
    result: Result = log_time([cmd, '--help'], env={'JIRA_API_TOKEN': '12345'})
    assert result.stdout
    assert not result.stderr


def test_init(log_time):
    result: Result = log_time(['init'], input='12345\n')
    print(result.stdout)
    print(result.stderr)
    assert result.exit_code == 0
    assert 'token:' in result.stdout, 'should prompt for token on initial run'
    assert 'project cache' in result.stdout, 'should mention project cache'
    assert 'issue cache' in result.stdout, 'should mention issue cache'
    assert not result.stderr, 'should not log any warnings or errors'


def test_log_when_uninitialized(log_time):
    result: Result = log_time(['log'], input='12345\n')

    assert result.exit_code == 0, 'should exit cleanly'
    # should prompt for token on initial run
    assert 'token:' in result.stdout

    # should update caches on initial run
    assert 'project cache' in result.stdout
    assert 'issue cache' in result.stdout

    # should summarize what is being logged
    assert result.stdout.splitlines()[-2].startswith('Log')
    # should ask for confirmation
    assert result.stdout.splitlines()[-1].startswith('Continue')


@pytest.mark.parametrize(
    'day,expected',
    [
        (date.today(), 'today'),
        (date.today() - timedelta(days=1), 'yesterday'),
        ('12.3.21', '12.3.2021'),
        ('12.3.2021', '12.3.2021'),
    ],
)
def test_log_custom_day(log_time: Callable[[list[str]], Result], day, expected):
    if isinstance(day, date):
        day = day.strftime('%d.%m')
    response = log_time(
        ['log', '--day', day],
        env={'JIRA_API_TOKEN': '12345', 'LT_CACHE': 'False'},
    )
    confirmation_prompt = response.stdout.splitlines()[0]
    print(confirmation_prompt)
    assert expected in confirmation_prompt


def test_no_persist_token(log_time, mock_keyring):
    result: Result = log_time(['--no-persist-token'], env=dict(JIRA_API_TOKEN='12345'))
    assert result.exit_code == 0
    assert name not in mock_keyring

    token = 'canary-token'
    result: Result = log_time(['--persist-token', 'init'], env=dict(JIRA_API_TOKEN=token))
    assert result.exit_code == 0
    assert 'test-user' in mock_keyring[name]
    assert token in mock_keyring[name]['test-user']
