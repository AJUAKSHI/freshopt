"""Incremental-refresh path for the Freshness Optimizer prototype.

This module reads only rows from the simulated ``changes.csv`` file.  It is
not a Delta Lake Change Data Feed implementation; the CSV is a small,
transparent stand-in for one.  The cache must contain the aggregate from
before these changes for the returned value to be a complete result.
"""

import csv
import time
from datetime import datetime

DEFAULT_CHANGES_PATH = "changes.csv"
VALID_QUERY_TYPES = ("total_sum", "sum_by_region", "group_by_region")


def incremental_refresh(
    query_type,
    cached_result,
    region=None,
    changes_path=DEFAULT_CHANGES_PATH,
    scenario="small",
    max_rows=None,
):
    """Apply simulated changes to a cached aggregate.

    ``scenario`` is ``"small"`` (2,000 rows) or ``"large"`` (70,000 rows).
    Changes contain INSERT records.  UPDATE is also supported when a row
    includes an optional ``previous_amount`` column: its net contribution is
    ``amount - previous_amount``.

    Returns ``result``, local ``execution_time`` in seconds, ``changed_rows``
    and a ``refresh_timestamp``.  Execution time is a local cost proxy only.
    """
    if query_type not in VALID_QUERY_TYPES:
        raise ValueError(f"query_type must be one of: {VALID_QUERY_TYPES}")
    if query_type == "sum_by_region" and not region:
        raise ValueError("region must be provided for 'sum_by_region'")
    if cached_result is None:
        raise ValueError("incremental refresh needs an existing cached result")

    start = time.perf_counter()
    changed_rows = 0
    total_change = 0.0
    regional_changes = {}

    with open(changes_path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("scenario", "small").lower() != scenario.lower():
                continue
            changed_rows += 1
            amount = float(row["amount"])
            if row.get("operation", "INSERT").upper() == "UPDATE":
                amount -= float(row.get("previous_amount") or 0)

            if query_type == "total_sum":
                total_change += amount
            elif query_type == "sum_by_region":
                if row["region"] == region:
                    total_change += amount
            else:
                region_name = row["region"]
                regional_changes[region_name] = regional_changes.get(region_name, 0.0) + amount
                
            if max_rows is not None and changed_rows >= max_rows:
                   break

    if query_type == "group_by_region":
        result = {name: round(float(value), 2) for name, value in cached_result.items()}
        for name, change in regional_changes.items():
            result[name] = round(result.get(name, 0.0) + change, 2)
    else:
        result = round(float(cached_result) + total_change, 2)

    return {
        "result": result,
        "execution_time": time.perf_counter() - start,
        "changed_rows": changed_rows,
        "refresh_timestamp": datetime.now().isoformat(timespec="seconds"),
    }
