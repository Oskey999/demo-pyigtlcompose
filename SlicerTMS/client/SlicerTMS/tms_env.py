"""
TMS Environment Configuration Loader

This module provides reliable access to TMS environment variables 
even when running in desktop environments (like XFCE) where 
environment variables may not be properly inherited.

Usage:
    from tms_env import get_tms_config
    
    config = get_tms_config()
    host = config['TMS_SERVER_HOST']
    port1 = config['TMS_SERVER_PORT_1']
    port2 = config['TMS_SERVER_PORT_2']
"""

import os
import subprocess
from typing import Dict, Optional


def read_env_file(filepath: str) -> Dict[str, str]:
    """Read environment variables from a file."""
    env_vars = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}")
    return env_vars


def source_bash_script(script_path: str) -> Dict[str, str]:
    """Source a bash script and extract environment variables."""
    env_vars = {}
    try:
        # Run a bash command that sources the script and prints all env vars
        cmd = f'source {script_path} && env'
        result = subprocess.run(
            ['bash', '-c', cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.startswith('TMS_'):
                        env_vars[key] = value
    except Exception as e:
        print(f"Warning: Could not source {script_path}: {e}")
    
    return env_vars


def get_tms_config(defaults: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Get TMS configuration from multiple sources in order of preference:
    1. Environment variables (os.environ)
    2. Config file (/config/tms_env.conf)
    3. Bash script (/config/tms_env.sh)
    4. System environment file (/etc/environment)
    5. Provided defaults
    6. Hard-coded fallback defaults
    
    Returns:
        Dictionary with TMS_SERVER_HOST, TMS_SERVER_PORT_1, TMS_SERVER_PORT_2
    """
    
    # Hard-coded fallback defaults
    fallback_defaults = {
        'TMS_SERVER_HOST': 'localhost',
        'TMS_SERVER_PORT_1': '18944',
        'TMS_SERVER_PORT_2': '18945'
    }
    
    # Use provided defaults or fallback
    if defaults:
        fallback_defaults.update(defaults)
    
    config = fallback_defaults.copy()
    
    # Source 5: System environment file
    system_env = read_env_file('/etc/environment')
    config.update({k: v for k, v in system_env.items() if k.startswith('TMS_')})
    
    # Source 4: Bash script (if exists)
    bash_env = source_bash_script('/config/tms_env.sh')
    config.update(bash_env)
    
    # Source 3: Config file (primary method)
    file_env = read_env_file('/config/tms_env.conf')
    config.update(file_env)
    
    # Source 2: Docker environment variables passed at runtime
    for key in ['TMS_SERVER_HOST', 'TMS_SERVER_PORT_1', 'TMS_SERVER_PORT_2']:
        env_value = os.environ.get(key)
        if env_value:
            config[key] = env_value
    
    return config


def get_tms_value(key: str, default: Optional[str] = None) -> str:
    """
    Get a single TMS configuration value.
    
    Args:
        key: Configuration key (e.g., 'TMS_SERVER_HOST')
        default: Default value if not found
        
    Returns:
        Configuration value as string
    """
    config = get_tms_config()
    return config.get(key, default)


def print_debug_info():
    """Print debug information about environment variable sources."""
    print("=" * 60)
    print("TMS Environment Variable Debug Info")
    print("=" * 60)
    
    print("\n1. Direct os.environ:")
    for key in ['TMS_SERVER_HOST', 'TMS_SERVER_PORT_1', 'TMS_SERVER_PORT_2']:
        value = os.environ.get(key)
        print(f"   {key}: {value if value else 'NOT SET'}")
    
    print("\n2. From /config/tms_env.conf:")
    conf_vars = read_env_file('/config/tms_env.conf')
    for key, value in conf_vars.items():
        print(f"   {key}: {value}")
    if not conf_vars:
        print("   (file not found or empty)")
    
    print("\n3. From /config/tms_env.sh:")
    bash_vars = source_bash_script('/config/tms_env.sh')
    for key, value in bash_vars.items():
        print(f"   {key}: {value}")
    if not bash_vars:
        print("   (file not found or could not source)")
    
    print("\n4. From /etc/environment:")
    sys_vars = read_env_file('/etc/environment')
    tms_sys_vars = {k: v for k, v in sys_vars.items() if k.startswith('TMS_')}
    for key, value in tms_sys_vars.items():
        print(f"   {key}: {value}")
    if not tms_sys_vars:
        print("   (no TMS variables found)")
    
    print("\n5. Final resolved configuration:")
    config = get_tms_config()
    for key in ['TMS_SERVER_HOST', 'TMS_SERVER_PORT_1', 'TMS_SERVER_PORT_2']:
        print(f"   {key}: {config[key]}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # When run directly, print debug info
    print_debug_info()
    
    # Example usage
    print("\nExample usage:")
    config = get_tms_config()
    print(f"TMS Server: {config['TMS_SERVER_HOST']}:{config['TMS_SERVER_PORT_1']}")
