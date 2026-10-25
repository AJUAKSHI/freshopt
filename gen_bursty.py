import csv

with open("data/changes_large.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    columns = reader.fieldnames
    rows = list(reader)

TARGET = 300000

with open("data/changes_bursty.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    for i in range(TARGET):
        row = dict(rows[i % len(rows)])
        row["scenario"] = "bursty"
        writer.writerow(row)

print("Created data/changes_bursty.csv with", TARGET, "rows")