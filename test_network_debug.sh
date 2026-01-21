#!/bin/bash
# Comprehensive network debugging script for Docker containers
# Tests connectivity and network configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

# Main function
main() {
    local TARGET_HOST="${1:-tmsserver}"
    local PORT_18944="${2:-18944}"
    local PORT_18945="${3:-18945}"
    
    log_header "Docker Network Debugging Tool"
    
    # 1. Check network interfaces
    log_header "1. Network Interfaces Configuration"
    ifconfig 2>/dev/null || ip addr show
    
    # 2. Check network routes
    log_header "2. Network Routes"
    route -n 2>/dev/null || ip route show
    
    # 3. Check DNS resolution
    log_header "3. DNS Resolution Test"
    log_info "Attempting to resolve hostname: $TARGET_HOST"
    if nslookup "$TARGET_HOST" 2>/dev/null; then
        log_success "DNS resolution successful for $TARGET_HOST"
    else
        log_warning "nslookup not available, trying getent..."
        if getent hosts "$TARGET_HOST" 2>/dev/null; then
            log_success "Hostname resolved via getent: $TARGET_HOST"
        else
            log_error "Failed to resolve hostname: $TARGET_HOST"
        fi
    fi
    
    # 4. Ping test
    log_header "4. Ping Test"
    if ping -c 3 "$TARGET_HOST" 2>/dev/null; then
        log_success "Ping to $TARGET_HOST successful"
    else
        log_warning "Ping to $TARGET_HOST failed or timed out"
    fi
    
    # 5. Port 18944 connectivity
    log_header "5. Testing Port $PORT_18944 (OpenIGTLink Server)"
    log_info "Attempting to connect to $TARGET_HOST:$PORT_18944"
    
    if timeout 5 nc -zv "$TARGET_HOST" "$PORT_18944" 2>&1; then
        log_success "Port $PORT_18944 is OPEN on $TARGET_HOST"
    else
        log_error "Port $PORT_18944 is CLOSED or unreachable on $TARGET_HOST"
        
        # Try with alternate netcat syntax
        log_info "Trying alternate netcat method..."
        if echo | nc -w 3 "$TARGET_HOST" "$PORT_18944" 2>/dev/null; then
            log_success "Port $PORT_18944 is reachable (alternate method)"
        else
            log_error "Could not connect to port $PORT_18944"
        fi
    fi
    
    # 6. Port 18945 connectivity
    log_header "6. Testing Port $PORT_18945 (Text Server)"
    log_info "Attempting to connect to $TARGET_HOST:$PORT_18945"
    
    if timeout 5 nc -zv "$TARGET_HOST" "$PORT_18945" 2>&1; then
        log_success "Port $PORT_18945 is OPEN on $TARGET_HOST"
    else
        log_error "Port $PORT_18945 is CLOSED or unreachable on $TARGET_HOST"
        
        # Try with alternate netcat syntax
        log_info "Trying alternate netcat method..."
        if echo | nc -w 3 "$TARGET_HOST" "$PORT_18945" 2>/dev/null; then
            log_success "Port $PORT_18945 is reachable (alternate method)"
        else
            log_error "Could not connect to port $PORT_18945"
        fi
    fi
    
    # 7. Network tools summary
    log_header "7. Network Debugging Tools Installed"
    
    local tools=("netcat" "ping" "telnet" "curl" "nc" "route" "ifconfig" "ip" "nslookup" "dig")
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            log_success "$tool: installed"
        else
            log_warning "$tool: not found"
        fi
    done
    
    # 8. Netstat to show listening ports
    log_header "8. Listening Ports on This Container"
    if command -v netstat &> /dev/null; then
        netstat -tlnp 2>/dev/null | grep LISTEN || true
    else
        ss -tlnp 2>/dev/null | grep LISTEN || true
    fi
    
    # 9. Check if this is the server container
    log_header "9. Server Status (if applicable)"
    if netstat -tlnp 2>/dev/null | grep -E ':18944|:18945'; then
        log_success "This container is running the OpenIGTLink servers on ports 18944 and/or 18945"
    else
        log_info "OpenIGTLink servers not running on this container"
    fi
    
    # 10. Summary
    log_header "Debugging Summary"
    echo -e "${CYAN}Target Server: ${NC}$TARGET_HOST"
    echo -e "${CYAN}Ports Being Tested: ${NC}$PORT_18944, $PORT_18945"
    echo -e "${CYAN}Timestamp: ${NC}$(date)"
    
    echo ""
    log_info "Debugging complete. Review the output above to diagnose connectivity issues."
    echo ""
}

# Display usage
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 [TARGET_HOST] [PORT_18944] [PORT_18945]"
    echo ""
    echo "Arguments:"
    echo "  TARGET_HOST    - Hostname or IP to test (default: tmsserver)"
    echo "  PORT_18944     - Port for OpenIGTLink server (default: 18944)"
    echo "  PORT_18945     - Port for text server (default: 18945)"
    echo ""
    echo "Examples:"
    echo "  $0                              # Test 'tmsserver' on ports 18944, 18945"
    echo "  $0 tmsserver 18944 18945        # Explicit parameters"
    echo "  $0 192.168.1.100 18944 18945    # Test by IP address"
    exit 0
fi

# Run main function
main "$@"
