import cache
import full_recompute

from decision_manager import select_strategy
from query_analyzer import analyze_query
from incremental import incremental_refresh
from cost_estimator import estimate_costs
from result_validator import validate_result
from query_logger import log_experiment

from datetime import datetime
from freshness_checker import check_freshness

 # Query types that incremental refresh can handle
INCREMENTAL_SUPPORTED = ("total_sum", "sum_by_region", "group_by_region")
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
    Example:
        region = 'South'
        -> South
    """

    where_clause = analysis["where_clause"]

    if where_clause is None:
        return None

    import re

    match = re.search(
        r"region\s*=\s*['\"]([^'\"]+)['\"]",
        where_clause,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


# --------------------------------
# Main Optimizer Function
# --------------------------------

def run_optimizer(sql_query, delta, scenario="large"):

    # --------------------------------
    # STEP 1: Analyze Query
    # --------------------------------

    analysis = analyze_query(sql_query)

    query_key = convert_query(analysis)

    region = extract_region(analysis)

    print("Query:", query_key)
    print("Freshness Limit:", delta, "minutes")


    # --------------------------------
    # STEP 2: Check Existing Cache
    # --------------------------------

    cached = cache.get_cached_result(query_key)

    if cached["exists"] and query_key in ("total_sum", "sum_by_region", "group_by_region"):

        incremental_output = incremental_refresh(
            query_type=query_key,
            cached_result=cached["result"],
            region=region,
            changes_path="data/changes.csv",
            scenario=scenario
        )

        print("\nIncremental Refresh")
        print("-------------------")
        print("Result:", incremental_output["result"])
        print("Changed Rows:", incremental_output["changed_rows"])
        print("Execution Time:", incremental_output["execution_time"])
        print("Refresh Time:", incremental_output["refresh_timestamp"])

    else:
        incremental_output = None


    # --------------------------------
    # Check Cache Freshness
    # --------------------------------

    if cached["exists"]:

        last_refresh = datetime.fromisoformat(cached["refreshed_at"])

        cache_age_minutes, cache_valid = check_freshness(last_refresh, delta)

    else:

        cache_age_minutes = None
        cache_valid = False


    print("\nCache Information")
    print("-----------------")
    print("Cache Exists:", cached["exists"])
    print("Cache Age:", cache_age_minutes, "minutes")
    print("Cache Valid:", cache_valid)


    # --------------------------------
    # STEP 3: Full Recompute
    # --------------------------------

    full_output = full_recompute.run_full_recompute(
        query_key,
        region=region
    )

    full_cost = full_output["execution_time"]


    # --------------------------------
    # STEP 4: Cost Estimation
    # --------------------------------

    if incremental_output is not None:

        changed_rows = incremental_output["changed_rows"]
        incremental_time = incremental_output["execution_time"]
        incremental_available = True

    else:

        changed_rows = 0
        incremental_time = 0
        incremental_available = False


    costs = estimate_costs(
        cache_exists=cached["exists"],
        cache_age_seconds=cached["age_seconds"],
        delta_minutes=delta,
        changed_rows=changed_rows,
        full_rows=full_output["rows_processed"],
        incremental_execution_time=incremental_time,
        full_execution_time=full_output["execution_time"],
        incremental_available=incremental_available
    )


    # --------------------------------
    # Create Strategy List
    # --------------------------------

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


    print("\nCost Estimation")
    print("----------------")
    print("Cache:", costs["cache"])
    print("Incremental:", costs["incremental"])
    print("Full Recompute:", costs["full_recompute"])


    # --------------------------------
    # STEP 5: Decision Manager
    # --------------------------------

    selected_strategy, reason = select_strategy(strategies)


    print("\nDecision")
    print("--------")
    print("Selected Strategy:", selected_strategy)
    print("Reason:", reason)


    # --------------------------------
    # STEP 6: Execute Selected Strategy
    # --------------------------------

    if selected_strategy == "CACHE":

        final_result = cached["result"]

        final_age_minutes = cache_age_minutes


    elif selected_strategy == "INCREMENTAL":

        final_result = incremental_output["result"]

        # Incremental refresh creates a fresh result
        final_age_minutes = 0


    elif selected_strategy == "FULL":

        final_result = full_output["result"]

        # Full recompute creates a fresh result
        final_age_minutes = 0


    else:

        final_result = None
        final_age_minutes = None


    print("\nFinal Result")
    print("------------")
    print("Result:", final_result)
    print("Strategy Used:", selected_strategy)

    # Save the fresh result so the next run can use the cache
    if selected_strategy == "FULL":
        cache.save_cached_result(query_key, final_result)
    
    # --------------------------------
    # STEP 7: Validate Final Result
    # --------------------------------

    validation = validate_result(
        final_data_age=final_age_minutes,
        delta=delta,
        selected_strategy=selected_strategy
    )


    print("\nResult Validation")
    print("-----------------")
    print("Valid:", validation["valid"])
    print("Final Data Age:", validation["final_age"], "minutes")
    print("Freshness Limit:", validation["delta"], "minutes")
    print("Strategy:", validation["selected_strategy"])


    # --------------------------------
    # STEP 8: Log Experiment
    # --------------------------------

    if incremental_output is not None:

        changed_rows = incremental_output["changed_rows"]

    else:

        changed_rows = 0


    if selected_strategy == "CACHE":

        selected_cost = costs["cache"]["estimated_cost"]
        execution_time = 0

    elif selected_strategy == "INCREMENTAL":

        selected_cost = costs["incremental"]["estimated_cost"]
        execution_time = incremental_output["execution_time"]

    else:

        selected_cost = costs["full_recompute"]["estimated_cost"]
        execution_time = full_output["execution_time"]


    log_experiment(
        query=sql_query,
        query_type=analysis["query_type"],
        delta=delta,
        data_size=full_output["rows_processed"],
        changed_rows=changed_rows,
        selected_strategy=selected_strategy,
        estimated_cost=selected_cost,
        execution_time=execution_time,
        actual_age=final_age_minutes,
        freshness_satisfied=validation["valid"]
    )


    print("\nExperiment logged successfully.")


    # --------------------------------
    # Return Results for UI
    # --------------------------------

    return {
        "query": sql_query,
        "query_key": query_key,
        "analysis": analysis,

        "cache": {
            "exists": cached["exists"],
            "age_minutes": cache_age_minutes,
            "valid": cache_valid,
            "result": cached["result"]
            if cached["exists"]
            else None
        },

        "incremental": incremental_output,

        "full_recompute": full_output,

        "costs": costs,

        "selected_strategy": selected_strategy,

        "reason": reason,

        "final_result": final_result,

        "final_age_minutes": final_age_minutes,

        "validation": validation
    }


# --------------------------------
# Run directly from terminal
# --------------------------------

if __name__ == "__main__":

    sql_query = "SELECT SUM(amount) FROM sales;"

    delta = 10

    run_optimizer(
        sql_query=sql_query,
        delta=delta,
        scenario="large"
    )