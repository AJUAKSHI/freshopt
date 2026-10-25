import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("results/experiment_results.csv")

ORDER = ["FreshOpt", "Always-Cache", "Always-Incremental", "Always-Full"]
SCENARIOS = ["small", "large", "bursty"]

# repeat number (0, 1, 2, ...) of every measurement
df["rep"] = df.groupby(["delta", "cache_age", "scenario", "policy"]).cumcount()
df["violation_pct"] = df["violation"].astype(float) * 100

# ---------- Table 7: exact numbers for Graph 5 and the violation rate ----------
metrics = ["violation_pct", "age", "latency", "rows_read", "refresh_cost"]
per_rep = df.groupby(["policy", "rep"])[metrics].mean()
mean = per_rep.groupby("policy").mean().reindex(ORDER)
std = per_rep.groupby("policy").std().reindex(ORDER)

table7 = mean.round(4).astype(str) + " ± " + std.round(4).astype(str)
table7.to_csv("results/table7_policy_metrics.csv")
print("Table 7: mean ± std over the repeats")
print(table7.to_string())

# ---------- Cost reduction with its spread ----------
rep_cost = df.pivot_table(index="rep", columns="policy", values="latency", aggfunc="mean")
reduction = (1 - rep_cost["FreshOpt"] / rep_cost["Always-Full"]) * 100
print("\nCost reduction vs Always-Full: %.1f%% ± %.1f" % (reduction.mean(), reduction.std()))

# ---------- Table 8 and Graph 2 with error bars ----------
sc = df.groupby(["scenario", "policy", "rep"])["latency"].mean()
m = sc.groupby(["scenario", "policy"]).mean().unstack()[ORDER].reindex(SCENARIOS)
s = sc.groupby(["scenario", "policy"]).std().unstack()[ORDER].reindex(SCENARIOS)

table8 = m.round(4).astype(str) + " ± " + s.round(4).astype(str)
table8.to_csv("results/table8_scenario_cost.csv")
print("\nTable 8: mean cost (s) per scenario, mean ± std")
print(table8.to_string())

m.plot(kind="bar", yerr=s, capsize=3, figsize=(8, 4.5), rot=0)
plt.ylabel("Mean query cost / latency (s)")
plt.xlabel("Change scenario (small = 2,000, large = 70,000, bursty = 300,000 rows)")
plt.title("Cost by Policy and Change Size (error bars = std over repeats)")
plt.legend(title="policy", loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=4)
plt.savefig("results/graph2_with_error_bars.png", dpi=200, bbox_inches="tight")
plt.close()

print("\nSaved: table7, table8 and graph2_with_error_bars.png in results/")