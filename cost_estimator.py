"""Transparent, rule-based cost estimates for the three optimizer paths.

Costs are seconds on the local machine, not cloud billing figures.  The small
incremental overhead models bookkeeping; it makes a very large change set
appropriately compete with a full read of the source file.
"""


def estimate_costs(
    *,
    cache_exists,
    cache_age_seconds,
    delta_minutes,
    changed_rows,
    full_rows,
    incremental_execution_time,
    full_execution_time,
    incremental_available=True,
):
    """Return validity, reason, and local-time cost estimates per strategy."""
    delta_seconds = float(delta_minutes) * 60
    cache_valid = bool(cache_exists and cache_age_seconds <= delta_seconds)
    cache_reason = (
        "Cache is within the freshness limit"
        if cache_valid
        else ("No cached result exists" if not cache_exists else "Cache age exceeds the freshness limit")
    )

    # At a large change volume, merge/bookkeeping can outweigh a sequential
    # full scan. max() keeps measured local time meaningful on quick machines.
    full_cost = max(float(full_execution_time), 0.0001)
    fraction_changed = float(changed_rows) / max(int(full_rows), 1)
    incremental_cost = max(
        float(incremental_execution_time),
        0.001 + full_cost * fraction_changed * 1.2,
    )

    return {
        "cache": {
            "valid": cache_valid,
            "estimated_cost": 0.0001 if cache_valid else None,
            "reason": cache_reason,
        },
        "incremental": {
            "valid": bool(incremental_available),
            "estimated_cost": incremental_cost if incremental_available else None,
            "reason": "Changed rows can be applied to the cached aggregate"
            if incremental_available
            else "No cache baseline is available for incremental refresh",
        },
        "full_recompute": {
            "valid": True,
            "estimated_cost": full_cost,
            "reason": "A full recompute always creates a fresh result",
        },
    }


def choose_cheapest_valid_strategy(costs):
    """Return ``cache``, ``incremental``, or ``full_recompute``."""
    valid = [(name, info["estimated_cost"]) for name, info in costs.items() if info["valid"]]
    if not valid:
        raise ValueError("No execution strategy is valid")
    return min(valid, key=lambda item: item[1])[0]
