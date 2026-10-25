"""
cache.py
Member 2 - Freshness Optimizer project

A very simple cache / materialized-result store.

WHAT IT DOES
------------
Stores the result of a query together with the time it was
refreshed, so the rest of the pipeline (Freshness Checker,
Decision Manager) can check:
    - whether a cached result exists for a query
    - what that result is
    - how old it is (to compare against the user's delta)

There is no database. The cache is a plain Python dictionary that
is also mirrored to a small JSON file (cache_store.json) so it
survives between separate runs of the program.

HOW MEMBER 1 (main.py) USES THIS FILE
--------------------------------------
    import cache

    # After computing a result the first time (e.g. via full_recompute
    # or incremental refresh), save it:
    cache.save_cached_result("total_sum", 1234567.89)

    # Later, when a new query comes in, check the cache:
    info = cache.get_cached_result("total_sum")

    if info["exists"]:
        print(info["result"])          # the cached value
        print(info["refreshed_at"])    # ISO timestamp string
        print(info["age_seconds"])     # how old the cache is, in seconds
    else:
        print("No cached result yet -- need to compute it.")

The Freshness Checker can compare `age_seconds` against the user's
delta (freshness limit, in seconds) to decide if the cache is fresh
enough to answer the query directly.

query_key
---------
A short string identifying the query, e.g. "total_sum",
"sum_by_region_South", "group_by_region". The Query Analyzer is
expected to turn the user's SQL into a key like this before calling
these functions.
"""

import json
import os
from datetime import datetime

CACHE_FILE = "cache_store.json"

_cache = {}


def _load_cache_from_disk():
    """Load the cache dictionary from CACHE_FILE, if it exists."""
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _cache = {}
    else:
        _cache = {}


def _save_cache_to_disk():
    """Write the current cache dictionary out to CACHE_FILE."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, indent=2, default=str)


# Load whatever was cached from a previous run as soon as this
# module is imported, so the cache persists across runs.
_load_cache_from_disk()


def save_cached_result(query_key, result):
    """
    Save (or overwrite) the cached result for a given query.

    Parameters
    ----------
    query_key : str
        Identifier for the query, e.g. "total_sum",
        "sum_by_region_South", "group_by_region".
    result : any JSON-serializable value
        The value to cache (a number, a list, a dict, etc).

    Returns
    -------
    None
    """
    _cache[query_key] = {
        "result": result,
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_cache_to_disk()


def get_cached_result(query_key):
    """
    Retrieve the cached result for a given query key.

    Parameters
    ----------
    query_key : str
        Same identifier used in save_cached_result().

    Returns
    -------
    dict with keys:
        exists (bool)                 - True if a cached entry was found
        result (any or None)          - the cached value, or None
        refreshed_at (str or None)    - ISO timestamp of last refresh,
                                         or None if not found
        age_seconds (float or None)   - how many seconds old the cache
                                         is right now, or None if not found
    """
    entry = _cache.get(query_key)

    if entry is None:
        return {
            "exists": False,
            "result": None,
            "refreshed_at": None,
            "age_seconds": None,
        }

    refreshed_at = datetime.fromisoformat(entry["refreshed_at"])
    age_seconds = (datetime.now() - refreshed_at).total_seconds()

    return {
        "exists": True,
        "result": entry["result"],
        "refreshed_at": entry["refreshed_at"],
        "age_seconds": age_seconds,
    }


def clear_cache(query_key=None):
    """
    Remove one cached entry (if query_key is given) or clear the
    entire cache (if query_key is None). Useful for testing/demos.
    """
    global _cache
    if query_key is None:
        _cache = {}
    else:
        _cache.pop(query_key, None)
    _save_cache_to_disk()
