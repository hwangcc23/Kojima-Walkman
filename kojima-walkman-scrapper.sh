#!/bin/bash

# Project: Collect Songs in the Walkman of my god: Hideo Kojima
# This script automates the full pipeline: Scrape -> Download -> OCR Analyze

# Check for duration argument, default to 24 if not provided
DURATION=${1:-24}
TARGET_URL="https://x.com/HIDEO_KOJIMA_EN"

# Check if auth_state.json exists
if [ ! -f "auth_state.json" ]; then
    echo "Error: auth_state.json not found!" >&2
    echo "Please follow the setup instructions in x-scrapper.py --help" >&2
    exit 1
fi

# Ensure the virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment (venv) not found. Please run 'python3 -m venv venv' and install requirements." >&2
    exit 1
fi

echo "--- Starting Kojima Walkman Pipeline ---" >&2
echo "Target: $TARGET_URL" >&2
echo "Duration: $DURATION hours" >&2
echo "----------------------------------------" >&2

# Execute the pipeline
# 1. x-scrapper.py: Fetches post metadata
# 2. kojima-walkman-image-downloader.py: Filters 'Good morning' posts and downloads images
# 3. kojima-walkman-music-analyzer.py: Performs OCR to extract music info
./venv/bin/python3 x-scrapper.py "$TARGET_URL" -d "$DURATION" | 
./venv/bin/python3 kojima-walkman-image-downloader.py | 
./venv/bin/python3 kojima-walkman-music-analyzer.py

echo "----------------------------------------" >&2
echo "Pipeline execution finished." >&2
