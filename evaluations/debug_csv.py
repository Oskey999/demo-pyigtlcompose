import csv

with open('results.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f"Total rows: {len(rows)}")
    for i in range(min(3, len(rows))):
        row = rows[i]
        docker_stats = row.get("docker_stats")
        print(f"\nRow {i}:")
        print(f"  docker_stats repr: {repr(docker_stats)}")
        print(f"  Length: {len(docker_stats) if docker_stats else 0}")
        print(f"  Is falsy: {not docker_stats}")
        print(f"  Strip is falsy: {not (docker_stats or '').strip()}")
