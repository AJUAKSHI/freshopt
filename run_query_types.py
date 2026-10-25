import contextlib
import io
import os
import shutil
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd

import cache
import full_recompute
from main import run_optimizer

# name: (sql, query_key, cache_key, region)
QUERIES = {
    "SUM": ("SELECT SUM(amount) FROM sales;", "total_sum", "total_sum", None),
    "SUM + WHERE": ("SELECT SUM(amount) FROM sales WHERE region = 'South';",
                    "sum_by_region", "sum_by_region_South", "South"),
    "GROUP BY": ("SELECT region, SUM(amount) FROM sales GROUP BY region;",
                 "group_by_region", "group_by_region", None),
}

DELTAS = [1, 5, 10, 30]
CACHE_AGES = [0.5, 2, 4, 8, 15, 25]
SCENARIOS = ["small", "large", "bursty"]
REPEATS = 5
CACHE_COST = 0.0001

LOG_FILE = "results/experiments.csv"
STORE_FILE = "cache_store.json"


def backup(path):
    existed = os.path.exists(path)
    if existed:
        shutil.copy(path, path + ".bak")
    return existed


def restore(path, existed):
    if existed:
        shutil.copy(path + ".bak", path)
        os.remove(path + ".bak")
    elif os.path.exists(path):
        os.remove(path)


os.makedirs("results", exist_ok=True)
if os.path.exists("calibration.json"):
    os.remove("calibration.json")

log_existed = backup(LOG_FILE)
store_existed = backup(STORE_FILE)

rows = []

try:
    for name, (sql, query_key, cache_key, region) in QUERIES.items():

        baseline = full_recompute.run_full_recompute(query_key, region=region)["result"]

        for delta in DELTAS:
            for cache_age in CACHE_AGES:
                for scenario in SCENARIOS:
                    for rep in range(REPEATS):

                        cache.save_cached_result(cache_key, baseline)
                        past = datetime.now() - timedelta(minutes=cache_age)
                        cache._cache[cache_key]["refreshed_at"] = past.isoformat(timespec="seconds")

                        with contextlib.redirect_stdout(io.StringIO()):
                            out = run_optimizer(sql, delta, scenario, measure_all=True)

                        inc = out["incremental"]
                        full = out["full_recompute"]

                        policies = {
                            "FreshOpt": out["selected_strategy"],
                            "Always-Cache": "CACHE",
                            "Always-Incremental": "INCREMENTAL",
                            "Always-Full": "FULL",
                        }

                        for policy, strategy in policies.items():
                            if strategy == "CACHE":
                                age, cost = cache_age, CACHE_COST
                            elif strategy == "INCREMENTAL":
                                age, cost = 0, inc["execution_time"]
                            else:
                                age, cost = 0, full["execution_time"]

                            key = {"CACHE": "cache", "INCREMENTAL": "incremental",
                                   "FULL": "full_recompute"}[strategy]
                            predicted = out["costs"][key]["estimated_cost"]
                            if predicted is None:
                                predicted = CACHE_COST

                            rows.append({
                                "query": name,
                                "delta": delta,
                                "cache_age": cache_age,
                                "scenario": scenario,
                                "policy": policy,
                                "strategy": strategy,
                                "violation": age > delta,
                                "latency": cost,
                                "predicted": predicted,
                            })

        print("Finished query type:", name)

finally:
    restore(LOG_FILE, log_existed)
    restore(STORE_FILE, store_existed)

df = pd.DataFrame(rows)
df.to_csv("results/query_types_results.csv", index=False)


def error(part):
    return ((part["predicted"] - part["latency"]).abs() / part["latency"]).mean() * 100


summary = []
for name in QUERIES:
    part = df[df["query"] == name]
    fresh = part[part["policy"] == "FreshOpt"]
    full = part[part["policy"] == "Always-Full"]
    inc = part[part["policy"] == "Always-Incremental"]
    cch = part[part["policy"] == "Always-Cache"]

    summary.append({
        "query": name,
        "FreshOpt violations %": round(fresh["violation"].mean() * 100, 1),
        "Always-Cache violations %": round(cch["violation"].mean() * 100, 1),
        "FreshOpt cost s": round(fresh["latency"].mean(), 4),
        "Always-Full cost s": round(full["latency"].mean(), 4),
        "Reduction vs full %": round((1 - fresh["latency"].mean() / full["latency"].mean()) * 100, 1),
        "Pred. error incr %": round(error(inc), 1),
        "Pred. error full %": round(error(full), 1),
    })

table = pd.DataFrame(summary)
print()
print(table.to_string(index=False))
table.to_csv("results/table6_query_types.csv", index=False)

g = df.groupby(["query", "policy"])["latency"].mean().unstack()
g = g.loc[list(QUERIES), ["FreshOpt", "Always-Incremental", "Always-Full"]]
g.plot(kind="bar", figsize=(8, 4.5), rot=0)
plt.ylabel("Mean cost (s)")
plt.xlabel("Query type")
plt.title("Cost by Query Type")
plt.legend(title="policy", loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
plt.savefig("results/graph7_query_types.png", dpi=200, bbox_inches="tight")
plt.close()

print("\nSaved: table6_query_types.csv and graph7_query_types.png in results/")