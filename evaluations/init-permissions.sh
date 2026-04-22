#!/bin/bash
# Initialize evaluations directory with proper permissions
# This script should be run at container startup

EVAL_DIR="/app/evaluations"
CSV_FILE="$EVAL_DIR/results.csv"

echo "Initializing permissions for $EVAL_DIR"

# Create directory if it doesn't exist
if [ ! -d "$EVAL_DIR" ]; then
    echo "Creating directory: $EVAL_DIR"
    mkdir -p "$EVAL_DIR"
fi

# Set directory permissions to allow all access
echo "Setting directory permissions to 777..."
chmod 777 "$EVAL_DIR" 2>/dev/null || echo "Warning: Could not set directory permissions"

# If CSV file exists, make it writable
if [ -f "$CSV_FILE" ]; then
    echo "Making CSV file writable..."
    chmod 666 "$CSV_FILE" 2>/dev/null || echo "Warning: Could not set file permissions"
fi

echo "Permissions initialized"
