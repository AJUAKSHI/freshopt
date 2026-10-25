"""
make_paper_figures.py

Builds the two result figures for the IEEE paper from your FINAL results.

Usage (run inside the freshness_optimizer folder):
    python make_paper_figures.py results_final2 paper_figures

It reads these files from the results folder:
    experiment_results.csv      (main experiment, SUM query)
    table5_crossover.csv        (change-size experiment)
    query_types_results.csv     (SUM / SUM + WHERE / GROUP BY)

It writes:
    paper_figures/fig_results.pdf    (Fig. 2 in the paper)
    paper_figures/fig_analysis.pdf   (Fig. 3 in the paper)
    paper_figures/delta_table.csv    (cost per delta, for the text)
and prints a few numbers that the paper text quotes, so you can check them.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = sys.argv[1] if len(sys.argv) > 1 else "results_final2"
OUT = sys.argv[2] if len(sys.argv) > 2 else "paper_figures"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.size": 7.5,
    "font.family": "sans-serif",
    "axes.linewidth": 0.6,
    "axes.titlesize": 7.5,
    "legend.fontsize": 6.5,
    "pdf.fonttype": 42,
})

ORDER = ["FreshOpt", "Always-Cache", "Always-Incremental", "Always-Full"]
SCENARIOS = ["small", "large", "bursty"]
STYLE = {
    "FreshOpt": dict(color="black", hatch="", marker="o", ls="-"),
    "Always-Cache": dict(color="#9a9a9a", hatch="..", marker="s", ls=":"),
    "Always-Incremental": dict(color="#b5b5b5", hatch="///", marker="^", ls="--"),
    "Always-Full": dict(color="white", hatch="\\\\\\", marker="D", ls="-."),
}

# ------------------------------------------------------------------
# Load the main experiment
# ------------------------------------------------------------------
df = pd.read_csv(os.path.join(RES, "experiment_results.csv"))
df["rep"] = df.groupby(["delta", "cache_age", "scenario", "policy"]).cumcount()
df["violation_pct"] = df["violation"].astype(float) * 100

# ------------------------------------------------------------------
# Figure 2: (a) violations  (b) cost per scenario  (c) cost vs delta
# ------------------------------------------------------------------
fig, ax = plt.subplots(1, 3, figsize=(7.16, 2.15))

# (a) freshness violation rate
a = ax[0]
v = df.groupby("policy")["violation_pct"].mean().reindex(ORDER)
for i, p in enumerate(ORDER):
    s = STYLE[p]
    a.bar(i, v[p], color=s["color"], hatch=s["hatch"], edgecolor="black", linewidth=0.6)
    a.text(i, v[p] + 1, "%.1f" % v[p], ha="center", va="bottom", fontsize=6.5)
a.set_xticks(range(4))
a.set_xticklabels(["Fresh-\nOpt", "Always-\nCache", "Always-\nIncr.", "Always-\nFull"])
a.set_ylabel("Freshness violations (%)")
a.set_ylim(0, 50)
a.set_title("(a) Freshness violation rate")

# (b) cost per scenario (log scale), mean +- std over repeats
b = ax[1]
sc = df.groupby(["scenario", "policy", "rep"])["latency"].mean()
m = sc.groupby(["scenario", "policy"]).mean().unstack().reindex(SCENARIOS)
sd = sc.groupby(["scenario", "policy"]).std().unstack().reindex(SCENARIOS)
policies_b = ["FreshOpt", "Always-Incremental", "Always-Full"]
width = 0.26
x = np.arange(len(SCENARIOS))
for k, p in enumerate(policies_b):
    s = STYLE[p]
    b.bar(x + (k - 1) * width, m[p], width, yerr=sd[p], capsize=1.5,
          color=s["color"], hatch=s["hatch"], edgecolor="black", linewidth=0.6,
          error_kw=dict(elinewidth=0.6, capthick=0.6), label=p.replace("Always-Incremental", "Always-Incr."))
b.set_yscale("log")
b.set_ylim(top=m[policies_b].values.max() * 60)
b.set_xticks(x)
b.set_xticklabels(["small\n(2k)", "large\n(70k)", "bursty\n(300k)"])
b.set_ylabel("Mean cost (s), log scale")
b.set_title("(b) Cost by change size")
b.legend(loc="upper left", frameon=False, handlelength=1.4)

# (c) cost vs delta
c = ax[2]
dl = df.groupby(["delta", "policy", "rep"])["latency"].mean()
dm = dl.groupby(["delta", "policy"]).mean().unstack()
ds = dl.groupby(["delta", "policy"]).std().unstack()
for p in policies_b:
    s = STYLE[p]
    c.errorbar(range(len(dm.index)), dm[p], yerr=ds[p], color="black" if p == "FreshOpt" else "#555555",
               marker=s["marker"], ls=s["ls"], ms=3.5, lw=0.9, capsize=1.5, elinewidth=0.6,
               markerfacecolor="white" if p != "FreshOpt" else "black",
               label=p.replace("Always-Incremental", "Always-Incr."))
c.set_xticks(range(len(dm.index)))
c.set_xticklabels([str(int(d)) for d in dm.index])
c.set_xlabel("Freshness limit $\\delta$ (min)")
c.set_ylabel("Mean cost (s)")
c.set_title("(c) Cost vs. freshness limit")
c.set_ylim(0, (dm[policies_b] + ds[policies_b].fillna(0)).values.max() * 1.75)
c.legend(loc="upper center", frameon=False, handlelength=2.2)

fig.tight_layout(pad=0.4, w_pad=0.8)
fig.savefig(os.path.join(OUT, "fig_results.pdf"))
plt.close(fig)

dm.round(4).to_csv(os.path.join(OUT, "delta_table.csv"))

# ------------------------------------------------------------------
# Figure 3: (a) strategy mix  (b) crossover  (c) query types
# ------------------------------------------------------------------
fig, ax = plt.subplots(1, 3, figsize=(7.16, 2.15))

# (a) strategy mix of FreshOpt by delta
a = ax[0]
f = df[df["policy"] == "FreshOpt"]
mix = pd.crosstab(f["delta"], f["strategy"], normalize="index") * 100
for col in ["CACHE", "INCREMENTAL", "FULL"]:
    if col not in mix.columns:
        mix[col] = 0.0
mix = mix[["CACHE", "INCREMENTAL", "FULL"]]
mix_style = {"CACHE": ("white", ""), "INCREMENTAL": ("#b5b5b5", "///"), "FULL": ("black", "")}
bottom = np.zeros(len(mix))
for col in mix.columns:
    colr, hat = mix_style[col]
    a.bar(range(len(mix)), mix[col], bottom=bottom, color=colr, hatch=hat,
          edgecolor="black", linewidth=0.6, width=0.6,
          label={"CACHE": "Cache", "INCREMENTAL": "Incremental", "FULL": "Full"}[col])
    bottom += mix[col].values
a.set_xticks(range(len(mix)))
a.set_xticklabels([str(int(d)) for d in mix.index])
a.set_xlabel("Freshness limit $\\delta$ (min)")
a.set_ylabel("Strategy chosen (%)")
a.set_ylim(0, 100)
a.set_title("(a) FreshOpt strategy mix")
a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False,
         handlelength=1.2, columnspacing=0.8)

# (b) crossover
b = ax[1]
cr = pd.read_csv(os.path.join(RES, "table5_crossover.csv"))
xk = cr["changed_rows"] / 1000.0
b.plot(xk, cr["incremental_measured"], color="black", marker="o", ms=3, lw=0.9, label="Incr. (measured)")
b.plot(xk, cr["full_measured"], color="#555555", marker="D", ms=3, lw=0.9, ls="-.", markerfacecolor="white", label="Full (measured)")
b.plot(xk, cr["incremental_model"], color="black", marker="^", ms=3, lw=0.9, ls="--", markerfacecolor="white", label="Incr. (model)")
b.set_xlabel("Changed rows (thousands)")
b.set_ylabel("Cost (s)")
b.set_title("(b) Incremental vs. full recompute")
b.set_ylim(0, cr[["incremental_measured", "full_measured", "incremental_model"]].values.max() * 1.5)
b.legend(loc="upper left", frameon=False, handlelength=2.2)

# (c) query types
c = ax[2]
q = pd.read_csv(os.path.join(RES, "query_types_results.csv"))
qnames = list(dict.fromkeys(q["query"]))
qm = q.groupby(["query", "policy"])["latency"].mean().unstack().reindex(qnames)
width = 0.26
x = np.arange(len(qnames))
for k, p in enumerate(policies_b):
    s = STYLE[p]
    c.bar(x + (k - 1) * width, qm[p], width, color=s["color"], hatch=s["hatch"],
          edgecolor="black", linewidth=0.6, label=p.replace("Always-Incremental", "Always-Incr."))
c.set_xticks(x)
c.set_xticklabels([n.replace(" + ", "+\n").replace("GROUP BY", "GROUP\nBY") for n in qnames])
c.set_ylabel("Mean cost (s)")
c.set_title("(c) Query types")
c.set_ylim(0, qm[policies_b].values.max() * 1.8)
c.legend(loc="upper left", frameon=False, handlelength=1.4)

fig.tight_layout(pad=0.4, w_pad=0.8)
fig.savefig(os.path.join(OUT, "fig_analysis.pdf"))
plt.close(fig)

# ------------------------------------------------------------------
# Numbers quoted in the paper text (check them against the paper)
# ------------------------------------------------------------------
print("Violation rate (%):")
print(v.round(1).to_string())

rep_cost = df.pivot_table(index="rep", columns="policy", values="latency", aggfunc="mean")
red = (1 - rep_cost["FreshOpt"] / rep_cost["Always-Full"]) * 100
print("\nCost reduction vs Always-Full: %.1f%% +- %.1f" % (red.mean(), red.std()))

stale = df[df["cache_age"] > df["delta"]]
print("\nStale-cache runs only (mean cost, s):")
print(stale.groupby("policy")["latency"].mean().reindex(ORDER).round(4).to_string())
fo = stale[stale["policy"] == "FreshOpt"]["latency"].mean()
af = stale[stale["policy"] == "Always-Full"]["latency"].mean()
print("Stale-only reduction vs Always-Full: %.1f%%" % ((1 - fo / af) * 100))

print("\nCost by delta (mean over repeats):")
print(dm.round(4).to_string())
print("\nFigures saved in", OUT)
