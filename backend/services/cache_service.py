from functools import lru_cache
from typing import Any, Callable


def cached_query(maxsize: int = 128):
    return lru_cache(maxsize=maxsize)


def clear_cache(func: Callable[..., Any] | None = None) -> None:
    if func and hasattr(func, "cache_clear"):
        func.cache_clear()
