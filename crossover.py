import pandas as pd
import matplotlib.pyplot as plt

import full_recompute
from incremental import incremental_refresh
from cost_estimator import estimate_costs

SIZES = [2000, 10000, 30000, 50000, 70000, 100000, 150000, 200000, 300000]
REPEATS = 5

base = full_recompute.run_full_recompute("total_sum")
cached_value = base["result"]
full_rows = base["rows_processed"]

rows = []

# warm-up so the first timed run is not slowed by a cold file cache
incremental_refresh(
    "total_sum",
    cached_value,
    changes_path="data/changes_bursty.csv",
    scenario="bursty",
    max_rows=50000,
)

for n in SIZES:
    for _ in range(REPEATS):

        inc = incremental_refresh(
            "total_sum",
            cached_value,
            changes_path="data/changes_bursty.csv",
            scenario="bursty",
            max_rows=n,
        )

        full = full_recompute.run_full_recompute("total_sum")

        # what our rule-based cost model PREDICTS for incremental
        model = estimate_costs(
            cache_exists=True,
            cache_age_seconds=10**9,
            delta_minutes=1,
            changed_rows=inc["changed_rows"],
            full_rows=full_rows,
            incremental_execution_time=0,
            full_execution_time=full["execution_time"],
        )

        rows.append({
            "changed_rows": inc["changed_rows"],
            "incremental_measured": inc["execution_time"],
            "full_measured": full["execution_time"],
            "incremental_model": model["incremental"]["estimated_cost"],
        })

df = pd.DataFrame(rows)
table = df.groupby("changed_rows").median().round(4)

print(table)
table.to_csv("results/table5_crossover.csv")

# Where does incremental stop being cheaper?
worse = table[table["incremental_measured"] >= table["full_measured"]]
if len(worse) > 0:
    print("\nMeasured crossover: incremental stops being cheaper at about",
          worse.index[0], "changed rows")
else:
    print("\nNo measured crossover: incremental stayed cheaper up to",
          table.index.max(), "changed rows")

# Graph 6
plt.figure(figsize=(7, 4.5))
plt.plot(table.index, table["incremental_measured"], marker="o", label="Incremental (measured)")
plt.plot(table.index, table["full_measured"], marker="o", label="Full recompute (measured)")
plt.plot(table.index, table["incremental_model"], marker="o", linestyle="--", label="Incremental (rule-based model)")
plt.xlabel("Changed rows")
plt.ylabel("Cost (seconds)")
plt.title("Incremental vs Full Recompute: Measured vs Model")
plt.legend()
plt.savefig("results/graph6_crossover.png", dpi=200, bbox_inches="tight")
plt.close()

print("Graph saved: results/graph6_crossover.png")