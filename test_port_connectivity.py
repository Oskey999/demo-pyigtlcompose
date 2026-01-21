#!/usr/bin/env python3
"""
Network connectivity test script for Docker containers
Tests connectivity to ports 18944 and 18945 between tmsserver and slicergui
"""

import socket
import sys
import time
from datetime import datetime

class ColorCodes:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(message, level="INFO"):
    """Print formatted log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    level_colors = {
        "INFO": ColorCodes.CYAN,
        "SUCCESS": ColorCodes.GREEN,
        "ERROR": ColorCodes.RED,
        "WARNING": ColorCodes.YELLOW,
        "DEBUG": ColorCodes.BLUE
    }
    
    color = level_colors.get(level, ColorCodes.WHITE)
    reset = ColorCodes.RESET
    
    print(f"{color}[{timestamp}] [{level}]{reset} {message}")

def test_port_connectivity(host, port, timeout=5):
    """
    Test if a port is open on the given host
    Returns: (success: bool, message: str, response_time: float)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    
    start_time = time.time()
    try:
        result = sock.connect_ex((host, port))
        response_time = time.time() - start_time
        
        if result == 0:
            return True, f"Port {port} on {host} is OPEN", response_time
        else:
            return False, f"Port {port} on {host} is CLOSED (Connection refused)", response_time
    except socket.timeout:
        response_time = time.time() - start_time
        return False, f"Port {port} on {host} TIMEOUT after {timeout}s", response_time
    except socket.gaierror:
        response_time = time.time() - start_time
        return False, f"Hostname {host} could not be resolved", response_time
    except Exception as e:
        response_time = time.time() - start_time
        return False, f"Error connecting to {host}:{port} - {str(e)}", response_time
    finally:
        sock.close()

def test_hostname_resolution(hostname):
    """Test if a hostname can be resolved"""
    try:
        ip = socket.gethostbyname(hostname)
        log(f"Hostname '{hostname}' resolved to {ip}", "SUCCESS")
        return True, ip
    except socket.gaierror as e:
        log(f"Failed to resolve hostname '{hostname}': {str(e)}", "ERROR")
        return False, None

def test_connectivity_to_server(server_host, ports, attempts=3):
    """
    Test connectivity to server on specified ports
    server_host: hostname or IP address
    ports: list of ports to test
    attempts: number of retry attempts
    """
    log(f"Starting connectivity tests to {server_host}", "INFO")
    log("=" * 60, "INFO")
    
    # Test hostname resolution
    log(f"Testing hostname resolution for '{server_host}'...", "INFO")
    resolved, ip = test_hostname_resolution(server_host)
    log("=" * 60, "INFO")
    
    all_results = {}
    
    for port in ports:
        log(f"Testing port {port}...", "INFO")
        
        success_count = 0
        total_response_time = 0
        
        for attempt in range(attempts):
            success, message, response_time = test_port_connectivity(server_host, port, timeout=5)
            total_response_time += response_time
            
            if attempt == 0:  # First attempt
                all_results[port] = {"attempts": []}
            
            all_results[port]["attempts"].append({
                "success": success,
                "message": message,
                "response_time": response_time
            })
            
            if success:
                success_count += 1
                log(f"  Attempt {attempt + 1}/{attempts}: {message} ({response_time:.3f}s)", "SUCCESS")
            else:
                log(f"  Attempt {attempt + 1}/{attempts}: {message} ({response_time:.3f}s)", "ERROR")
            
            if attempt < attempts - 1:
                time.sleep(1)  # Wait before retry
        
        avg_response_time = total_response_time / attempts if attempts > 0 else 0
        all_results[port]["success_rate"] = (success_count / attempts) * 100
        all_results[port]["avg_response_time"] = avg_response_time
        
        log("=" * 60, "INFO")
    
    return all_results

def print_summary(results):
    """Print test summary"""
    log("CONNECTIVITY TEST SUMMARY", "BOLD")
    print(f"\n{ColorCodes.BOLD}{'Port':<10}{'Success Rate':<20}{'Avg Response Time':<20}{ColorCodes.RESET}")
    print("-" * 50)
    
    for port, data in sorted(results.items()):
        success_rate = data.get("success_rate", 0)
        avg_time = data.get("avg_response_time", 0)
        
        if success_rate == 100:
            color = ColorCodes.GREEN
            status = "[OK]"
        elif success_rate > 0:
            color = ColorCodes.YELLOW
            status = "[~]"
        else:
            color = ColorCodes.RED
            status = "[X]"
        
        print(f"{color}{status} {port:<8}{success_rate:>6.1f}% {' ' * 10}{avg_time:>6.3f}s{ColorCodes.RESET}")

def main():
    """Main test function"""
    if len(sys.argv) < 2:
        server_host = "tmsserver"  # Default Docker service name
        ports = [18944, 18945]
    else:
        server_host = sys.argv[1]
        if len(sys.argv) > 2:
            ports = [int(p) for p in sys.argv[2:]]
        else:
            ports = [18944, 18945]
    
    log(f"Testing connectivity to {server_host} on ports {ports}", "INFO")
    print()
    
    results = test_connectivity_to_server(server_host, ports, attempts=3)
    
    print()
    print_summary(results)
    print()
    
    # Determine exit code
    all_successful = all(data.get("success_rate", 0) == 100 for data in results.values())
    
    if all_successful:
        log("✓ All connectivity tests PASSED", "SUCCESS")
        return 0
    else:
        log("✗ Some connectivity tests FAILED", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())
