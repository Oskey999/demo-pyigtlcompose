#!/bin/bash
# Test script for GUI Recorder fixes
# Validates that both containers are accessible with correct URLs and protocols

set -e

echo "=== GUI Recorder Connection Test ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test rossim (webtop) HTTPS connection
echo -e "${YELLOW}Testing rossim (HTTPS on port 3000)...${NC}"
if docker exec recorder curl -s -k https://rossim:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ rossim HTTPS connection working${NC}"
else
    echo -e "${RED}✗ rossim HTTPS connection failed${NC}"
fi

# Test optimized (KasmVNC) HTTP connection on port 6900
echo ""
echo -e "${YELLOW}Testing optimized (HTTP on port 6900)...${NC}"
if docker exec recorder curl -s http://optimized:6900 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ optimized HTTP connection working${NC}"
else
    echo -e "${RED}✗ optimized HTTP connection failed${NC}"
fi

# Check recorder API
echo ""
echo -e "${YELLOW}Testing Recorder API (http://localhost:8080/status)...${NC}"
if curl -s http://localhost:8080/status > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Recorder API responding${NC}"
    echo ""
    echo "Current recorder status:"
    curl -s http://localhost:8080/status | python -m json.tool 2>/dev/null || echo "  (no active sessions)"
else
    echo -e "${RED}✗ Recorder API not responding${NC}"
fi

echo ""
echo -e "${YELLOW}=== Connection Test Summary ===${NC}"
echo "If all tests passed, you can start split-screen recording with:"
echo "  curl -X POST http://localhost:8080/record_split"
echo ""
echo "And stop it with:"
echo "  curl -X POST http://localhost:8080/stop_split"
echo ""
