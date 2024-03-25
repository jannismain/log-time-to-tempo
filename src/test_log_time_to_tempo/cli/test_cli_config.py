import os

import pytest

import log_time_to_tempo.cli.config as config


@pytest.fixture
def fp_test_config(monkeypatch, tmp_path):
    fp_test_config = tmp_path / config.filename
    monkeypatch.setattr('log_time_to_tempo.cli.config.fp_config_default', fp_test_config)
    os.chdir(tmp_path)
    yield fp_test_config


def test_load_config(fp_test_config):
    config.ensure_app_dir_exists()
    assert os.getenv('canary') is None, 'environment variable should not exist'

    fp_test_config.write_text('canary=yellow')
    config.load()

    assert os.getenv('canary') == 'yellow'
