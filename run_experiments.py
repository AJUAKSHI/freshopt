import os
import io
import shutil
import contextlib
from datetime import datetime, timedelta

import pandas as pd
import matplotlib.pyplot as plt

import cache
import full_recompute
from main import run_optimizer

# ---------------- Settings ----------------
QUERY = "SELECT SUM(amount) FROM sales;"
QUERY_KEY = "total_sum"
DELTAS = [1, 5, 10, 30]                 # freshness limits (minutes)
CACHE_AGES = [0.5, 2, 4, 8, 15, 25]     # simulated cache ages (minutes)
SCENARIOS = ["small", "large", "bursty"]   # 2,000 / 70,000 / 300,000 changed rows
REPEATS = 10
CACHE_COST = 0.0001

LOG_FILE = "results/experiments.csv"
STORE_FILE = "cache_store.json"
ORDER = ["FreshOpt", "Always-Cache", "Always-Incremental", "Always-Full"]


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


def set_cache(value, age_minutes):
    """Save a cached result, then make it look age_minutes old."""
    cache.save_cached_result(QUERY_KEY, value)
    past = datetime.now() - timedelta(minutes=age_minutes)
    cache._cache[QUERY_KEY]["refreshed_at"] = past.isoformat(timespec="seconds")


os.makedirs("results", exist_ok=True)
if os.path.exists("calibration.json"):
    os.remove("calibration.json")
log_existed = backup(LOG_FILE)
store_existed = backup(STORE_FILE)

rows = []

try:
    baseline = full_recompute.run_full_recompute(QUERY_KEY)["result"]

    for delta in DELTAS:
        for cache_age in CACHE_AGES:
            for scenario in SCENARIOS:
                for rep in range(REPEATS):

                    set_cache(baseline, cache_age)

                    # run the optimizer silently
                    with contextlib.redirect_stdout(io.StringIO()):
                        out = run_optimizer(QUERY, delta, scenario, measure_all=True)

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
                            age, cost, rows_read = cache_age, CACHE_COST, 0
                        elif strategy == "INCREMENTAL":
                            age, cost, rows_read = 0, inc["execution_time"], inc["changed_rows"]
                        else:
                            age, cost, rows_read = 0, full["execution_time"], full["rows_processed"]

                        key = {"CACHE": "cache", "INCREMENTAL": "incremental", "FULL": "full_recompute"}[strategy]
                        predicted = out["costs"][key]["estimated_cost"]
                        if predicted is None:
                            predicted = CACHE_COST

                        rows.append({
                            "delta": delta,
                            "cache_age": cache_age,
                            "scenario": scenario,
                            "policy": policy,
                            "strategy": strategy,
                            "age": age,
                            "violation": age > delta,
                            "latency": cost,
                            "refresh_cost": 0 if strategy == "CACHE" else cost,
                            "rows_read": rows_read,
                            "predicted": predicted,
                            "decision_time": out["decision_time"],
                        })

    print("Experiment finished:", len(rows), "measurements")

finally:
    # put the user's original files back
    restore(LOG_FILE, log_existed)
    restore(STORE_FILE, store_existed)


# ---------------- Results table ----------------
df = pd.DataFrame(rows)
df.to_csv("results/experiment_results.csv", index=False)


def save(name):
    plt.savefig("results/" + name, dpi=200, bbox_inches="tight")
    plt.close()


# Graph 1: freshness violation rate
g1 = df.groupby("policy")["violation"].mean().reindex(ORDER) * 100
plt.figure(figsize=(7, 4))
plt.bar(g1.index, g1.values)
plt.ylabel("Freshness violation rate (%)")
plt.title("Freshness Violation Rate by Policy")
plt.xticks(rotation=15)
save("graph1_violation_rate.png")

# Graph 2: cost by change size
g2 = df.groupby(["scenario", "policy"])["latency"].mean().unstack()[ORDER]
g2.plot(kind="bar", figsize=(8, 4.5), rot=0)
plt.ylabel("Mean query cost / latency (s)")
plt.xlabel("Change scenario (small = 2,000, large = 70,000, bursty = 300,000 rows)")
plt.title("Cost by Policy and Change Size")
plt.legend(title="policy", loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=4)
save("graph2_cost_by_scenario.png")

# Graph 3: cost as delta tightens
g3 = df.groupby(["delta", "policy"])["latency"].mean().unstack()
g3 = g3[["FreshOpt", "Always-Incremental", "Always-Full"]]
g3.plot(marker="o", figsize=(7, 4))
plt.xlabel("Freshness limit δ (minutes)")
plt.ylabel("Mean cost (s)")
plt.title("Cost as the Freshness Limit Tightens")
plt.xticks(DELTAS)
save("graph3_cost_vs_delta.png")

# Graph 4: which strategy FreshOpt chose
f = df[df["policy"] == "FreshOpt"]
mix = pd.crosstab(f["delta"], f["strategy"], normalize="index") * 100
mix.plot(kind="bar", stacked=True, figsize=(7, 4), rot=0)
plt.xlabel("Freshness limit δ (minutes)")
plt.ylabel("Strategy chosen (%)")
plt.title("FreshOpt Strategy Mix")
plt.legend(title="strategy", loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=3)
save("graph4_strategy_mix.png")

# Graph 5: age, latency, I/O, refresh cost
fig, ax = plt.subplots(2, 2, figsize=(11, 7))
df.groupby("policy")["age"].mean().reindex(ORDER).plot(kind="bar", ax=ax[0][0], rot=15, title="Mean answer age (min)")
df.groupby("policy")["latency"].mean().reindex(ORDER).plot(kind="bar", ax=ax[0][1], rot=15, title="Mean query latency (s)")
df.groupby("policy")["rows_read"].mean().reindex(ORDER).plot(kind="bar", ax=ax[1][0], rot=15, title="Mean rows read (I/O proxy)")
df.groupby("policy")["refresh_cost"].mean().reindex(ORDER).plot(kind="bar", ax=ax[1][1], rot=15, title="Mean refresh cost (s)")
for a in ax.flatten():
    a.set_xlabel("")
fig.tight_layout()
save("graph5_age_latency_io_refresh.png")


# ---------------- Summary ----------------
print("\nFreshness violation rate (%):")
print(g1.round(1).to_string())

fresh_cost = df[df["policy"] == "FreshOpt"]["latency"].mean()
full_cost = df[df["policy"] == "Always-Full"]["latency"].mean()
print("\nCost reduction vs Always-Full: %.1f%%" % ((full_cost - fresh_cost) / full_cost * 100))

print("\nAll graphs saved in the results/ folder.")

for name, policy in (("Incremental", "Always-Incremental"), ("Full", "Always-Full")):
    part = df[df["policy"] == policy]
    error = ((part["predicted"] - part["latency"]).abs() / part["latency"]).mean() * 100
    print("Cost-model prediction error (%s): %.1f%%" % (name, error))

print("Mean decision time: %.6f s" % df[df["policy"] == "FreshOpt"]["decision_time"].mean())