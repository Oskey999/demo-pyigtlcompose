import csv
with open('results.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f'Checking first row docker_stats:')
    if rows:
        stats = rows[0]["docker_stats"]
        print(f'Length: {len(stats)}')
        print(f'Contains timestamp: {"timestamp" in stats}')
        print(f'First 200 chars: {stats[:200]}')
