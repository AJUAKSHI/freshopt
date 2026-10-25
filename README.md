# FreshOpt

FreshOpt is a lightweight prototype that chooses how to answer an analytical
query under a user-specified freshness bound (delta, in minutes). It first
removes every strategy that would violate the bound, then picks the cheapest
remaining one among:

- **Cache reuse** (serve the stored result if its age is within delta)
- **Incremental refresh** (apply only the changed rows to the cached result)
- **Full recomputation** (rescan the whole table)

Costs are predicted from a one-time calibration, so only the chosen strategy
is executed.

## Important notes
- Cache ages and the change log are **simulated**. The change log is a set of
  CSV files, not a Delta Lake change data feed.
- Cost is wall-clock time on one laptop and is a compute-cost proxy, not cloud
  billing.
- Supported queries: SUM(amount), SUM(amount) with WHERE region = '...', and
  SUM(amount) GROUP BY region. COUNT and AVG run only through full
  recomputation.

## Requirements
Python 3.13, streamlit, pandas, matplotlib

    python -m pip install streamlit pandas matplotlib

## Project structure
- `main.py` - optimizer pipeline (`run_optimizer`)
- `query_analyzer.py` - parses the SQL query
- `freshness_checker.py` - checks cache age against delta
- `cost_estimator.py` - rule-based cost model
- `decision_manager.py` - freshness filter, then cheapest valid strategy
- `cache.py`, `incremental.py`, `full_recompute.py` - the three strategies
- `result_validator.py`, `query_logger.py` - final check and run log
- `app.py` - Streamlit demo
- `data/` - `sales.csv` (100,000 synthetic rows) and the change-log files
- `results_final2/` - the final results reported in the paper

## Run
Demo app:

    python -m streamlit run app.py

Experiments (run inside this folder):

    python run_experiments.py
    python print_tables.py
    python run_query_types.py
    python crossover.py
    python final_numbers.py
    python make_paper_figures.py results_final2 paper_figures

Absolute times depend on the machine and vary between runs, so compare the
policies within a run.

## Authors
AKSHIH K,
KARTHIK S,
AMITH A,
AADITH J KRISHNA N.