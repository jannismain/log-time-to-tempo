import pathlib
import pickle
import shutil
from dataclasses import dataclass

import pytest

import log_time_to_tempo.caching as caching


@dataclass
class MockCache:
    cache_dir: pathlib.Path

    def load_cache(self, fn):
        return pickle.load((self.cache_dir / fn).open('rb'))


@pytest.fixture(scope='function')
def mock(tmp_path, monkeypatch):
    mock = MockCache(cache_dir=tmp_path / 'cache')
    monkeypatch.setattr('log_time_to_tempo.caching.cache_dir', mock.cache_dir)
    yield mock
    shutil.rmtree(mock.cache_dir, ignore_errors=True)
    caching._registry.clear()


def test_cache(mock):
    # in order to accept keyword arguments meant for the cache decorator (no_cache,
    # update_cache, etc.), the function must accept **kwargs!
    @caching.cache()
    def hello(name='world', **kwargs):
        return f'Hello, {name.title()}!'

    assert not mock.cache_dir.is_dir()
    hello(no_cache=True)
    assert not mock.cache_dir.is_dir(), 'no_cache should prevent caching'
    hello()
    assert mock.cache_dir.is_dir(), 'cache dir should have been created'
    assert (mock.cache_dir / 'hello').is_file(), 'the result should be cached to file'
    assert mock.load_cache('hello') == 'Hello, World!'
    hello('alice')
    assert mock.load_cache('hello') == 'Hello, World!', 'the previous result is still cached'
    hello('alice', update_cache=True)
    assert mock.load_cache('hello') == 'Hello, Alice!', 'result should have been cached'


def test_cache_custom_name(mock):
    "The cache decorator should accept a custom filename."

    @caching.cache('foo')
    def hello(name='world', **kwargs):
        return f'Hello, {name.title()}!'

    hello()
    assert mock.load_cache('foo') == 'Hello, World!', 'cache file should be named foo'


@caching.cache('hello-$name')
def hello(name='World', **kwargs):
    return f'Hello, {name.title()}!'


def test_cache_interpolated_name(mock):
    "The cache decorator should accept an interpolated filename."

    hello('alice')
    assert mock.load_cache('hello-alice') == 'Hello, Alice!', 'argument should appear in cache name'
    hello('bob')
    assert mock.load_cache('hello-bob') == 'Hello, Bob!', 'argument should appear in cache name'
    hello()
    assert (
        mock.load_cache('hello-world') == 'Hello, World!'
    ), 'default value should appear in cache name'

    cached_results = caching.get_caches_for(hello)
    assert cached_results, 'cached method should have been registered'
    assert len(cached_results) == 3, 'three cache files should have been registered'


def test_invalidate_single(mock):
    hello('foo')
    hello('bar')
    assert caching.get_caches_for(hello) == set(
        [
            mock.cache_dir / 'hello-foo',
            mock.cache_dir / 'hello-bar',
        ]
    )
    caching.invalidate(hello)
    assert not caching.get_caches_for(hello)


def test_invalidate_all(mock):
    hello('foo')
    hello('bar')
    assert caching.get_caches_for(hello) == set(
        [
            mock.cache_dir / 'hello-foo',
            mock.cache_dir / 'hello-bar',
        ]
    )
    caching.invalidate()
    assert not caching.get_caches_for(hello)
