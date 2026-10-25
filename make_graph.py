import matplotlib.pyplot as plt

import cache
from main import run_optimizer

query = "SELECT SUM(amount) FROM sales;"

# Make sure a cache exists (incremental needs one)
if not cache.get_cached_result("total_sum")["exists"]:
    run_optimizer(query, 10, "small")

# Run both scenarios and keep the cost numbers
small = run_optimizer(query, 10, "small")["costs"]
large = run_optimizer(query, 10, "large")["costs"]

incremental = [
    small["incremental"]["estimated_cost"],
    large["incremental"]["estimated_cost"],
]
full = [
    small["full_recompute"]["estimated_cost"],
    large["full_recompute"]["estimated_cost"],
]

labels = ["Small changes\n(2,000 rows)", "Large changes\n(70,000 rows)"]
x = [0, 1]
width = 0.35

plt.bar([i - width / 2 for i in x], incremental, width, label="Incremental")
plt.bar([i + width / 2 for i in x], full, width, label="Full recompute")

plt.xticks(x, labels)
plt.ylabel("Compute cost proxy (seconds)")
plt.title("Incremental vs Full Recompute by Change Size")
plt.legend()
plt.savefig("results/comparison.png", dpi=200, bbox_inches="tight")
plt.show()