import csv
import os
from datetime import datetime

LOG_FILE_PATH = "results/experiments.csv"

def log_experiment(query: str, query_type: str, delta: float, data_size: int, 
                   changed_rows: int, selected_strategy: str, estimated_cost: float, 
                   execution_time: float, actual_age: float, freshness_satisfied: bool):
    """
    Appends experiment metrics to results/experiments.csv.
    Creates the directory and header row automatically if the file does not exist.
    """
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    file_exists = os.path.exists(LOG_FILE_PATH)
    
    headers = [
        "timestamp", "query", "query_type", "delta_limit", "total_data_rows",
        "changed_rows", "selected_strategy", "estimated_cost", 
        "execution_time_sec", "actual_data_age_min", "freshness_satisfied"
    ]
    
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        query,
        query_type,
        delta,
        data_size,
        changed_rows,
        selected_strategy,
        round(estimated_cost, 4),
        round(execution_time, 4),
        round(actual_age, 2),
        freshness_satisfied
    ]
    
    with open(LOG_FILE_PATH, mode="a", newline="") as csv_file:
        writer = csv.writer(csv_file)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)
    
    print(f"[LOGGER] Logged run to {LOG_FILE_PATH} | Strategy: {selected_strategy}")

# --- LOCAL TEST BLOCK ---
if __name__ == "__main__":
    log_experiment(
        query="SELECT SUM(amount) FROM sales;",
        query_type="AGGREGATION",
        delta=5.0,
        data_size=100000,
        changed_rows=2000,
        selected_strategy="INCREMENTAL REFRESH",
        estimated_cost=0.045,
        execution_time=0.12,
        actual_age=2.5,
        freshness_satisfied=True
    )