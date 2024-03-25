from more_itertools import is_sorted

import log_time_to_tempo._jira as _jira


def test_get_issues(test_client):
    issues = _jira.get_issues(test_client, project='TEST', no_cache=True)
    assert is_sorted(
        issues, key=lambda i: int(i.split('-')[1])
    ), 'issues should be sorted by their number'


def test_get_all_issues(monkeypatch, test_client):
    issues = _jira.get_all_issues(test_client, no_cache=True)
    assert is_sorted(
        issues.keys(), key=lambda i: (i.split('-')[0], int(i.split('-')[1]))
    ), 'issues should be sorted by their number'


def test_cache_is_warm(monkeypatch, tmp_path, test_client):
    monkeypatch.setattr('log_time_to_tempo.caching.cache_dir', tmp_path / 'cache')
    assert not _jira.cache_is_warm()
    _jira.get_all_issues(test_client)
    assert _jira.cache_is_warm()
