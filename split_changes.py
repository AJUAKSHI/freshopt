import csv

with open("data/changes.csv", newline="", encoding="utf-8") as source:
    reader = csv.DictReader(source)
    columns = reader.fieldnames
    files = {}
    writers = {}

    for row in reader:
        name = row.get("scenario", "small").lower()

        if name not in writers:
            files[name] = open(f"data/changes_{name}.csv", "w", newline="", encoding="utf-8")
            writers[name] = csv.DictWriter(files[name], fieldnames=columns)
            writers[name].writeheader()

        writers[name].writerow(row)

for f in files.values():
    f.close()

print("Created:", ", ".join(f"changes_{n}.csv" for n in writers))