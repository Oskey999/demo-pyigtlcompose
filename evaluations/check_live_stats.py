import csv
import json

with open('results.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    
print(f'Total rows: {len(rows)}')
print(f'\nFirst row docker_stats sample:')
if rows:
    stats_json = rows[0].get('docker_stats', '')
    if stats_json and len(stats_json) > 100:
        data = json.loads(stats_json)
        print(f'Timestamp: {data.get("timestamp")}')
        containers = data.get('container_stats', {})
        print(f'Containers found: {len(containers)}')
        for name, stats in list(containers.items())[:3]:
            print(f'  - {name}: CPU={stats.get("cpu_percent")}, Memory={stats.get("memory_usage")}')
    else:
        print(f'docker_stats is empty or too short (length: {len(stats_json)})')
