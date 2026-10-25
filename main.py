import csv
import json
import os
import re
import time
from datetime import datetime

import cache
import full_recompute

from decision_manager import select_strategy
from query_analyzer import analyze_query
from incremental import incremental_refresh
from cost_estimator import estimate_costs
from result_validator import validate_result
from query_logger import log_experiment
from freshness_checker import check_freshness

INCREMENTAL_SUPPORTED = ("total_sum", "sum_by_region", "group_by_region")
CALIBRATION_FILE = "calibration.json"


# --------------------------------
# Convert SQL query to internal type
# --------------------------------

def convert_query(analysis):
    """
    Convert the analyzed SQL query into the
    internal query type used by our optimizer.
    """

    if (
        analysis["operation"] == "SUM"
        and analysis["target_column"].lower() == "amount"
        and analysis["group_by"] is None
        and analysis["where_clause"] is None
    ):
        return "total_sum"

    if (
        analysis["operation"] == "COUNT"
        and analysis["target_column"] == "*"
        and analysis["group_by"] is None
        and analysis["where_clause"] is None
    ):
        return "count_rows"

    if (
        analysis["operation"] == "AVG"
        and analysis["target_column"].lower() == "amount"
        and analysis["group_by"] is None
        and analysis["where_clause"] is None
    ):
        return "average_amount"

    if (
        analysis["operation"] == "SUM"
        and analysis["target_column"].lower() == "amount"
        and analysis["where_clause"] is not None
        and analysis["group_by"] is None
    ):
        return "sum_by_region"

    if (
        analysis["operation"] == "SUM"
        and analysis["target_column"].lower() == "amount"
        and analysis["group_by"] is not None
    ):
        return "group_by_region"

    raise ValueError("Query type is not supported yet.")


def extract_region(analysis):
    """
    Extract the region value from a WHERE clause.
    Example: region = 'South' -> South
    """

    where_clause = analysis["where_clause"]

    if where_clause is None:
        return None

    match = re.search(
        r"region\s*=\s*['\"]([^'\"]+)['\"]",
        where_clause,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


# --------------------------------
# One-time calibration
# --------------------------------

def load_calibration():
    """
    Measure ONCE how fast this machine scans the data for each query
    type, and how many rows each change log has. Saved in
    calibration.json and reused for every query.

    Delete calibration.json if sales.csv or the change files change.
    """

    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    seconds_per_row = {}
    full_rows = 0

    for query_type in full_recompute.VALID_QUERY_TYPES:
        runs = [
            full_recompute.run_full_recompute(query_type, region="South")
            for _ in range(5)
        ]
        runs.sort(key=lambda r: r["execution_time"])
        median_run = runs[len(runs) // 2]
        full_rows = median_run["rows_processed"]
        seconds_per_row[query_type] = median_run["execution_time"] / full_rows

    # Count the rows of each change file once (change-log metadata)
    changes = {}
    for file_name in os.listdir("data"):
        if file_name.startswith("changes_") and file_name.endswith(".csv"):
            name = file_name[len("changes_"):-len(".csv")]
            with open(os.path.join("data", file_name), encoding="utf-8") as f:
                changes[name] = sum(1 for _ in f) - 1   # minus the header line

    calibration = {
        "full_rows": full_rows,
        "seconds_per_row": seconds_per_row,
        "changes": changes
    }

    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(calibration, f, indent=2)

    return calibration


# --------------------------------
# Main Optimizer Function
# --------------------------------

def run_optimizer(sql_query, delta, scenario="large", measure_all=False):
    """
    measure_all=False : normal mode. Predict costs, decide,
                        then run ONLY the selected strategy.
    measure_all=True  : benchmark mode for experiments. The decision
                        is still made from predictions, but the other
                        strategies are also measured afterwards so that
                        baselines can be compared.
    """

    calibration = load_calibration()

    decision_start = time.perf_counter()

    # STEP 1: Analyze query
    analysis = analyze_query(sql_query)
    query_key = convert_query(analysis)
    region = extract_region(analysis)
    cache_key = query_key if region is None else f"{query_key}_{region}"

    # STEP 2: Check cache and freshness
    cached = cache.get_cached_result(cache_key)

    if cached["exists"]:
        last_refresh = datetime.fromisoformat(cached["refreshed_at"])
        cache_age_minutes, cache_valid = check_freshness(last_refresh, delta)
    else:
        cache_age_minutes = None
        cache_valid = False

    incremental_possible = (
        cached["exists"] and query_key in INCREMENTAL_SUPPORTED
    )

    # STEP 3: Predict costs (nothing is executed here)
    full_rows = calibration["full_rows"]
    predicted_full_time = full_rows * calibration["seconds_per_row"][query_key]
    predicted_changed_rows = calibration["changes"].get(scenario.lower(), 0)

    costs = estimate_costs(
        cache_exists=cached["exists"],
        cache_age_seconds=cached["age_seconds"],
        delta_minutes=delta,
        changed_rows=predicted_changed_rows,
        full_rows=full_rows,
        incremental_execution_time=0,
        full_execution_time=predicted_full_time,
        incremental_available=incremental_possible
    )

    strategies = {

        "CACHE": {
            "valid": cache_valid,
            "cost": costs["cache"]["estimated_cost"]
            if costs["cache"]["estimated_cost"] is not None
            else float("inf")
        },

        "INCREMENTAL": {
            "valid": costs["incremental"]["valid"],
            "cost": costs["incremental"]["estimated_cost"]
            if costs["incremental"]["estimated_cost"] is not None
            else float("inf")
        },

        "FULL": {
            "valid": costs["full_recompute"]["valid"],
            "cost": costs["full_recompute"]["estimated_cost"]
        }
    }

    # STEP 4: Decide
    selected_strategy, reason = select_strategy(strategies)

    decision_time = time.perf_counter() - decision_start

    # STEP 5: Execute ONLY the selected strategy
    incremental_output = None
    full_output = None

    if selected_strategy == "CACHE":

        final_result = cached["result"]
        final_age_minutes = cache_age_minutes
        execution_time = 0

    elif selected_strategy == "INCREMENTAL":

        incremental_output = incremental_refresh(
            query_type=query_key,
            cached_result=cached["result"],
            region=region,
            changes_path=f"data/changes_{scenario.lower()}.csv",
            scenario=scenario
        )

        final_result = incremental_output["result"]
        final_age_minutes = 0
        execution_time = incremental_output["execution_time"]

    else:

        full_output = full_recompute.run_full_recompute(
            query_key,
            region=region
        )

        final_result = full_output["result"]
        final_age_minutes = 0
        execution_time = full_output["execution_time"]

        # Save the fresh result so the next run can use the cache
        cache.save_cached_result(cache_key, final_result)

    # Benchmark mode: also measure the strategies that were not chosen
    if measure_all:

        if incremental_output is None and incremental_possible:
            incremental_output = incremental_refresh(
                query_type=query_key,
                cached_result=cached["result"],
                region=region,
                changes_path=f"data/changes_{scenario.lower()}.csv",
                scenario=scenario
            )

        if full_output is None:
            full_output = full_recompute.run_full_recompute(
                query_key,
                region=region
            )

    # STEP 6: Validate final result
    validation = validate_result(
        final_data_age=final_age_minutes,
        delta=delta,
        selected_strategy=selected_strategy
    )

    # STEP 7: Log experiment
    if selected_strategy == "CACHE":
        selected_cost = costs["cache"]["estimated_cost"]
    elif selected_strategy == "INCREMENTAL":
        selected_cost = costs["incremental"]["estimated_cost"]
    else:
        selected_cost = costs["full_recompute"]["estimated_cost"]

    log_experiment(
        query=sql_query,
        query_type=analysis["query_type"],
        delta=delta,
        data_size=full_rows,
        changed_rows=predicted_changed_rows if incremental_possible else 0,
        selected_strategy=selected_strategy,
        estimated_cost=selected_cost,
        execution_time=execution_time,
        actual_age=final_age_minutes,
        freshness_satisfied=validation["valid"]
    )

    # Return everything the UI needs
    return {
        "query": sql_query,
        "query_key": query_key,
        "analysis": analysis,

        "cache": {
            "exists": cached["exists"],
            "age_minutes": cache_age_minutes,
            "valid": cache_valid,
            "result": cached["result"] if cached["exists"] else None
        },

        "incremental": incremental_output,
        "full_recompute": full_output,
        "costs": costs,

        "selected_strategy": selected_strategy,
        "reason": reason,

        "final_result": final_result,
        "final_age_minutes": final_age_minutes,
        "validation": validation,

        "decision_time": decision_time,
        "execution_time": execution_time
    }


# --------------------------------
# Run directly from terminal
# --------------------------------

if __name__ == "__main__":

    output = run_optimizer(
        sql_query="SELECT SUM(amount) FROM sales;",
        delta=10,
        scenario="large"
    )

    print("Selected Strategy:", output["selected_strategy"])
    print("Result:", output["final_result"])
    print("Decision time (s):", output["decision_time"])
    print("Execution time (s):", output["execution_time"])