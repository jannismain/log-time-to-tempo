import inspect
import pickle
from functools import wraps
from pathlib import Path
from string import Template

from ._time import modified_within
from .cli import app_dir

cache_dir = app_dir / 'cache'

_registry = {}


def cache(filename='', days=7):
    def caching_decorator(func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            if func not in _registry:
                _registry[func] = set()
            filename2 = func.__name__ if not filename else filename
            if kwargs.get('no_cache', False):
                return func(*args, **kwargs)
            spec = inspect.getfullargspec(func)
            default_args = (
                {k: v for k, v in zip(reversed(spec.args), spec.defaults)}
                if spec.defaults is not None
                else {}
            )
            given_args = {k: v for k, v in zip(reversed(spec.args), args)}
            filename3 = (
                Template(filename2).safe_substitute(
                    _get_args_dict(func, args, {**default_args, **given_args, **kwargs})
                )
                if '$' in filename2
                else filename2
            )
            if not cache_dir.is_dir():
                cache_dir.mkdir(parents=True, exist_ok=True)
            fp = cache_dir / filename3
            if fp not in _registry[func]:
                _registry[func].add(fp)
            if fp.exists() and not kwargs.get('update_cache') and modified_within(fp, days=days):
                return pickle.load(fp.open('rb'))
            rv = func(*args, **kwargs)
            if not kwargs.get('no_update_cache'):
                pickle.dump(rv, fp.open('wb'))
            return rv

        return wrapped_function

    return caching_decorator


def invalidate(fn=None):
    if fn is None:
        for fp in cache_dir.glob('*'):
            fp.unlink(missing_ok=True)
        _registry.clear()
        return
    for fp in get_caches_for(fn):
        fp.unlink(missing_ok=True)
    del _registry[inspect.unwrap(fn)]


def get_caches_for(fn) -> set[Path]:
    fn = inspect.unwrap(fn)
    return _registry.get(fn, {})


def _get_args_dict(fn, args, kwargs):
    args_names = fn.__code__.co_varnames[: fn.__code__.co_argcount]
    return {**dict(zip(args_names, args)), **kwargs}
