import pandas as pd

df = pd.read_csv("results/experiment_results.csv")

# Table 1: cost by change size
t1 = df.groupby(["scenario", "policy"])["latency"].mean().unstack().round(4)

# Table 2: cost by freshness limit
t2 = df.groupby(["delta", "policy"])["latency"].mean().unstack().round(4)

# Table 3: which strategy FreshOpt chose
f = df[df["policy"] == "FreshOpt"]
t3 = (pd.crosstab(f["delta"], f["strategy"], normalize="index") * 100).round(1)

# Table 4: only the runs where the cache was too old
stale = df[df["cache_age"] > df["delta"]]
t4 = stale.groupby(["scenario", "policy"])["latency"].mean().unstack().round(4)
t4 = t4[["FreshOpt", "Always-Incremental", "Always-Full"]]

t1.to_csv("results/table1_cost_by_scenario.csv")
t2.to_csv("results/table2_cost_by_delta.csv")
t3.to_csv("results/table3_strategy_mix.csv")
t4.to_csv("results/table4_stale_cache_only.csv")

print("Table 4: mean cost (s) when the cache was stale")
print(t4)
print("\nAll 4 tables saved in the results/ folder.")