"""
full_recompute.py
Member 2 - Freshness Optimizer project

Implements the "Full Recompute" path: read the ENTIRE sales.csv
from disk and compute the query result from scratch, with no
caching and no incremental shortcuts.

SUPPORTED QUERY TYPES (kept intentionally simple)
--------------------------------------------------
    "total_sum"        -> SUM(amount) over all rows
    "sum_by_region"     -> SUM(amount) WHERE region = <region>
    "group_by_region"   -> SUM(amount) GROUP BY region
                            (returns a dict: {region: total, ...})

HOW MEMBER 1 (main.py) USES THIS FILE
--------------------------------------
    import full_recompute

    output = full_recompute.run_full_recompute("total_sum")

    output = full_recompute.run_full_recompute(
        "sum_by_region", region="South"
    )

    output = full_recompute.run_full_recompute("group_by_region")

Each call returns a dict:
    {
        "result": ...,              # the computed value (float or dict)
        "execution_time": 0.0421,   # seconds, measured on THIS machine
        "rows_processed": 100000,
        "refresh_timestamp": "2026-09-12T10:15:00"
    }

The Cost Estimator can use "rows_processed" and "execution_time"
to compare full recompute against cache / incremental refresh.

NOTE ON execution_time
-----------------------
`execution_time` is wall-clock time on this local machine only.
It is meant as a rough compute-cost PROXY (e.g. "recompute is
slower than reading from cache"). It does NOT represent real
cloud dollar cost.
"""

import csv
import time
from datetime import datetime

DEFAULT_CSV_PATH = "data/sales.csv"

VALID_QUERY_TYPES = (
    "total_sum",
    "sum_by_region",
    "group_by_region",
    "count_rows",
    "average_amount"
)


def run_full_recompute(query_type, region=None, csv_path=DEFAULT_CSV_PATH):
    """
    Read the full sales.csv and compute the requested aggregate.

    Parameters
    ----------
    query_type : str
        One of "total_sum", "sum_by_region", "group_by_region".
    region : str, optional
        Required only when query_type == "sum_by_region".
        Example values: "North", "South", "East", "West".
    csv_path : str, optional
        Path to the sales CSV file. Defaults to "data/sales.csv".

    Returns
    -------
    dict with keys:
        result (float or dict)   - the computed aggregate
        execution_time (float)   - seconds taken on this machine
        rows_processed (int)     - number of data rows read
        refresh_timestamp (str)  - ISO timestamp of when this
                                    recompute finished
    """
    if query_type not in VALID_QUERY_TYPES:
        raise ValueError(f"query_type must be one of: {VALID_QUERY_TYPES}")

    if query_type == "sum_by_region" and not region:
        raise ValueError("region must be provided for 'sum_by_region'")

    start_time = time.perf_counter()

    rows_processed = 0
    total_sum = 0.0
    region_totals = {}

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_processed += 1
            amount = float(row["amount"])
            row_region = row["region"]

            if query_type == "total_sum":
                total_sum += amount

            elif query_type == "sum_by_region":
                if row_region == region:
                    total_sum += amount

            elif query_type == "group_by_region":
                region_totals[row_region] = region_totals.get(row_region, 0.0) + amount

            elif query_type == "count_rows":
                pass

            elif query_type == "average_amount":
                 total_sum += amount

    execution_time = time.perf_counter() - start_time

    if query_type == "group_by_region":
        result = {r: round(v, 2) for r, v in region_totals.items()}

    elif query_type == "count_rows":
        result = rows_processed

    elif query_type == "average_amount":
        result = round(total_sum / rows_processed, 2)

    else:
        result = round(total_sum, 2)

    return {
        "result": result,
        "execution_time": execution_time,
        "rows_processed": rows_processed,
        "refresh_timestamp": datetime.now().isoformat(timespec="seconds"),
    }
