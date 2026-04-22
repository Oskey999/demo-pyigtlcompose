#!/usr/bin/env python3
"""
Monitor results.csv and append Docker container statistics to each simulation event row.
Stores last 20 seconds of stats at 0.1s intervals for accurate start/end matching.
"""

import csv
import json
import time
import os
import sys
import threading
from datetime import datetime
from collections import deque
import docker


class DockerStatsBuffer:
    """
    Maintains a rolling buffer of Docker stats for the last 20 seconds.
    Stores samples at 0.1 second intervals (200 total samples).
    """
    
    def __init__(self, max_age_seconds=20, sample_interval=0.1):
        self.max_age_seconds = max_age_seconds
        self.sample_interval = sample_interval
        self.buffer_size = int(max_age_seconds / sample_interval)
        self.buffer = deque(maxlen=self.buffer_size)
        self.lock = threading.Lock()
        self.running = False
        self.collection_thread = None
    
    def start_collection(self):
        """Start background stats collection thread"""
        self.running = True
        self.collection_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.collection_thread.start()
        print(f"Started stats buffer: {self.buffer_size} samples @ {self.sample_interval}s intervals")
    
    def stop_collection(self):
        """Stop background collection"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=1.0)
    
    def _collect_loop(self):
        """Background loop collecting stats every 0.1 seconds"""
        while self.running:
            try:
                stats = self._collect_single_sample()
                with self.lock:
                    self.buffer.append({
                        'timestamp': datetime.now().isoformat(),
                        'stats': stats
                    })
                # Maintain exact 0.1s interval
                time.sleep(self.sample_interval)
            except Exception as e:
                print(f"Stats collection error: {e}")
                time.sleep(self.sample_interval)
    
    def _collect_single_sample(self):
        """Collect single sample of Docker stats"""
        try:
            client = docker.from_env()
            containers = client.containers.list()
            
            if not containers:
                return {'container_count': 0}
            
            flat_stats = {'container_count': len(containers)}
            
            for container in containers:
                try:
                    container_name = container.name
                    stats = container.stats(stream=False)
                    
                    memory_usage = stats.get('memory_stats', {}).get('usage', 0)
                    memory_limit = stats.get('memory_stats', {}).get('limit', 1)
                    memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
                    
                    cpu_delta = stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0) - \
                                stats.get('precpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0)
                    system_delta = stats.get('cpu_stats', {}).get('system_cpu_usage', 0) - \
                                   stats.get('precpu_stats', {}).get('system_cpu_usage', 0)
                    num_cpus = stats.get('cpu_stats', {}).get('online_cpus', 1)
                    cpu_percent = (cpu_delta / system_delta * num_cpus * 100.0) if system_delta > 0 else 0.0
                    
                    pids = stats.get('pids_stats', {}).get('current', 0)
                    
                    prefix = container_name.replace('-', '_').replace(' ', '_')
                    flat_stats[f'{prefix}_cpu_percent'] = round(cpu_percent, 2)
                    flat_stats[f'{prefix}_memory_mb'] = round(memory_usage / (1024**2), 2)
                    flat_stats[f'{prefix}_memory_percent'] = round(memory_percent, 2)
                    flat_stats[f'{prefix}_memory_limit_mb'] = round(memory_limit / (1024**2), 2)
                    flat_stats[f'{prefix}_pids'] = pids
                    flat_stats[f'{prefix}_status'] = container.status
                    
                except Exception as e:
                    continue
            
            return flat_stats
            
        except Exception as e:
            return {'container_count': 0, 'error': str(e)}
    
    def get_stats_for_timestamp(self, target_timestamp):
        """
        Get stats closest to target timestamp from buffer.
        Returns the sample with minimum time difference.
        """
        try:
            target_dt = datetime.fromisoformat(target_timestamp)
        except:
            return None, None
        
        with self.lock:
            if not self.buffer:
                return None, None
            
            # Find closest sample by absolute time difference
            closest_sample = None
            min_diff = float('inf')
            closest_ts = None
            
            for sample in self.buffer:
                sample_dt = datetime.fromisoformat(sample['timestamp'])
                diff = abs((sample_dt - target_dt).total_seconds())
                
                if diff < min_diff:
                    min_diff = diff
                    closest_sample = sample['stats']
                    closest_ts = sample['timestamp']
            
            return closest_sample, closest_ts


class ResultsCSVUpdater:
    """Update the results.csv file with Docker stats"""
    
    def __init__(self, csv_path='./evaluations/results.csv'):
        self.csv_path = csv_path
        self.lock_path = csv_path + '.lock'
        self.watch_active = False
        self.stats_buffer = DockerStatsBuffer(max_age_seconds=20, sample_interval=0.1)
    
    def ensure_csv_initialized(self):
        """Ensure CSV file exists"""
        if not os.path.exists(self.csv_path):
            os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
            open(self.csv_path, 'a').close()
            os.chmod(self.csv_path, 0o666)
    
    def acquire_lock(self, timeout=5):
        """Acquire a lock on the CSV file"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if os.path.exists(self.lock_path):
                    lock_age = time.time() - os.path.getmtime(self.lock_path)
                    if lock_age > 30:
                        try:
                            os.remove(self.lock_path)
                        except:
                            pass
                
                with open(self.lock_path, 'x') as f:
                    f.write(str(os.getpid()))
                return True
            except FileExistsError:
                time.sleep(0.05)
            except:
                time.sleep(0.05)
        return False
    
    def release_lock(self):
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except:
            pass
    
    def read_csv_rows_safe(self, max_retries=3):
        """Read CSV rows"""
        if not os.path.exists(self.csv_path):
            return [], []
        
        for attempt in range(max_retries):
            try:
                time.sleep(0.1)
                with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    rows = list(reader)
                    return rows, fieldnames
            except:
                if attempt < max_retries - 1:
                    time.sleep(0.2)
        return [], []
    
    def update_pending_rows(self):
        """Update rows with historically accurate docker stats"""
        if not self.acquire_lock(timeout=10):
            print("WARNING: Could not acquire lock")
            return
        
        try:
            rows, fieldnames = self.read_csv_rows_safe(max_retries=3)
            if not rows:
                return
            
            # Build complete fieldnames
            all_fieldnames = list(fieldnames) if fieldnames else []
            
            # Ensure base fields exist
            base_fields = ['timestamp', 'start_time', 'end_time', 'start_matrix', 'end_matrix', 
                          'execution_time_sec', 'start_stats_timestamp', 'end_stats_timestamp',
                          'start_stats_actual_timestamp', 'end_stats_actual_timestamp']
            for bf in base_fields:
                if bf not in all_fieldnames:
                    all_fieldnames.append(bf)
            
            # Add stats fields (both start and end versions)
            sample_stats = self.stats_buffer.get_stats_for_timestamp(datetime.now().isoformat())[0] or {}
            for key in sample_stats.keys():
                if key not in all_fieldnames:
                    all_fieldnames.append(key)
                end_key = f'end_{key}'
                if end_key not in all_fieldnames:
                    all_fieldnames.append(end_key)
            
            updated = False
            
            for i, row in enumerate(rows):
                start_time = row.get('start_time', '')
                end_time = row.get('end_time', '')
                start_stats_ts = row.get('start_stats_timestamp', '')
                end_stats_ts = row.get('end_stats_timestamp', '')
                
                # Case 1: Has start, needs start stats
                if start_time and not start_stats_ts:
                    stats, actual_ts = self.stats_buffer.get_stats_for_timestamp(start_time)
                    if stats:
                        for key, value in stats.items():
                            rows[i][key] = value
                        rows[i]['start_stats_timestamp'] = datetime.now().isoformat()
                        rows[i]['start_stats_actual_timestamp'] = actual_ts
                        updated = True
                        print(f"  [{i}] Added START stats (matched to {actual_ts}, diff: {self._time_diff(start_time, actual_ts):.3f}s)")
                    else:
                        print(f"  [{i}] No stats available for start time {start_time[:19]}")
                
                # Case 2: Has end, needs end stats
                elif start_time and end_time and not end_stats_ts:
                    stats, actual_ts = self.stats_buffer.get_stats_for_timestamp(end_time)
                    if stats:
                        for key, value in stats.items():
                            end_key = f'end_{key}'
                            rows[i][end_key] = value
                        rows[i]['end_stats_timestamp'] = datetime.now().isoformat()
                        rows[i]['end_stats_actual_timestamp'] = actual_ts
                        updated = True
                        print(f"  [{i}] Added END stats (matched to {actual_ts}, diff: {self._time_diff(end_time, actual_ts):.3f}s)")
                    else:
                        print(f"  [{i}] No stats available for end time {end_time[:19]}")
            
            if updated:
                self.write_csv_rows_atomic(rows, all_fieldnames)
                
        finally:
            self.release_lock()
    
    def _time_diff(self, ts1, ts2):
        """Calculate time difference in seconds between two ISO timestamps"""
        try:
            dt1 = datetime.fromisoformat(ts1)
            dt2 = datetime.fromisoformat(ts2)
            return abs((dt1 - dt2).total_seconds())
        except:
            return float('inf')
    
    def write_csv_rows_atomic(self, rows, fieldnames, max_retries=3):
        """Write rows to CSV"""
        for attempt in range(max_retries):
            try:
                with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                time.sleep(0.05)
                os.chmod(self.csv_path, 0o666)
                print(f"✅ Wrote {len(rows)} rows")
                return True
            except Exception as e:
                print(f"  Write attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.3)
        return False
    
    def watch_for_changes(self, check_interval=0.5, max_wait_time=10):
        """Watch CSV for changes"""
        self.ensure_csv_initialized()
        
        # Start stats collection in background
        self.stats_buffer.start_collection()
        print("Stats buffer started - collecting every 0.1s")
        
        self.watch_active = True
        last_check_time = time.time()
        last_file_size = 0
        last_mod_time = 0
        
        print(f"Watching {self.csv_path}...")
        print("-" * 60)
        
        try:
            while self.watch_active:
                try:
                    current_time = time.time()
                    time_since_check = current_time - last_check_time
                    
                    if os.path.exists(self.csv_path):
                        try:
                            current_size = os.path.getsize(self.csv_path)
                            current_mod_time = os.path.getmtime(self.csv_path)
                            
                            if (current_size != last_file_size or 
                                current_mod_time != last_mod_time or 
                                time_since_check >= max_wait_time):
                                
                                self.update_pending_rows()
                                last_file_size = current_size
                                last_mod_time = current_mod_time
                                last_check_time = current_time
                        except OSError:
                            pass
                    
                    time.sleep(check_interval)
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")
                    time.sleep(check_interval)
        
        finally:
            self.watch_active = False
            self.stats_buffer.stop_collection()
            self.release_lock()
            print("Watch stopped, stats buffer shutdown")
    
    def stop_watching(self):
        self.watch_active = False


def main():
    csv_path = os.environ.get('RESULTS_CSV_PATH', './evaluations/results.csv')
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    print(f"Results CSV Monitor with Historical Stats")
    print(f"CSV Path: {csv_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 60)
    
    updater = ResultsCSVUpdater(csv_path)
    
    try:
        updater.watch_for_changes(check_interval=0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
        updater.stop_watching()


if __name__ == '__main__':
    main()