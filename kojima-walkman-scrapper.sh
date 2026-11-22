#!/bin/bash

# Project: Collect Songs in the Walkman of my god: Hideo Kojima
# This script automates the full pipeline: Scrape -> Download -> OCR Analyze

# Parse command line arguments
DEBUG_FLAG=""
SKIP_VERIFY=false
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --debug|-D)
            DEBUG_FLAG="--debug"
            ;;
        --no-verify)
            SKIP_VERIFY=true
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

DURATION=${POSITIONAL_ARGS[0]:-24}
ENGINE=${POSITIONAL_ARGS[1]:-ocr}
TARGET_URL="https://x.com/HIDEO_KOJIMA_EN"

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "Error: config.json not found!" >&2
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
echo "Engine: $ENGINE" >&2
if [ -n "$DEBUG_FLAG" ]; then
    echo "Debug Mode: Enabled" >&2
fi
echo "----------------------------------------" >&2

# Execute the pipeline
# 1. x-scrapper.py: Fetches post metadata
# 2. kojima-walkman-image-downloader.py: Filters 'Good morning' posts and downloads images
# 3. kojima-walkman-music-analyzer.py: Performs analysis to extract music info
# 4. song-name-verifier.py: Verifies & corrects music metadata via Gemini / Spotify (default enabled)
# 5. kojima-walkman-update-files.py: Updates JSON database and README
if [ "$SKIP_VERIFY" = true ]; then
    ./venv/bin/python3 x-scrapper.py "$TARGET_URL" -d "$DURATION" ${DEBUG_FLAG:+"$DEBUG_FLAG"} | \
    ./venv/bin/python3 kojima-walkman-image-downloader.py | \
    ./venv/bin/python3 kojima-walkman-music-analyzer.py --engine "$ENGINE" | \
    ./venv/bin/python3 kojima-walkman-update-files.py
else
    ./venv/bin/python3 x-scrapper.py "$TARGET_URL" -d "$DURATION" ${DEBUG_FLAG:+"$DEBUG_FLAG"} | \
    ./venv/bin/python3 kojima-walkman-image-downloader.py | \
    ./venv/bin/python3 kojima-walkman-music-analyzer.py --engine "$ENGINE" | \
    ./venv/bin/python3 song-name-verifier.py ${DEBUG_FLAG:+"$DEBUG_FLAG"} | \
    ./venv/bin/python3 kojima-walkman-update-files.py
fi

echo "----------------------------------------" >&2
echo "Pipeline execution finished." >&2
