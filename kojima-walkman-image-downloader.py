#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: Downloads images from X-scrapper JSON output based on "Good morning" filter and outputs metadata in JSON.
"""

import json
import sys
import os
import asyncio
import httpx
from urllib.parse import urlparse

MAX_RETRIES = 5
RETRY_DELAY = 2 # seconds

# Ensure stdin/stdout use UTF-8 (required on Windows for Japanese/Unicode content)
if hasattr(sys.stdin, 'reconfigure'):
    sys.stdin.reconfigure(encoding='utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

async def download_image(client, img_url, tweet_url, timestamp, folder):
    try:
        # Extract file extension or default to .jpg
        path = urlparse(img_url).path
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = ".jpg"
        
        # Use the filename from URL or a hash
        filename = os.path.basename(path)
        if not filename:
            filename = f"image_{hash(img_url)}"
        
        # Ensure name is clean (X often appends :large etc to filenames)
        filename = filename.split(':')[0]
        if not filename.endswith(ext):
            filename += ext

        save_path = os.path.join(folder, filename)
        
        # Only download if it doesn't exist
        if not os.path.exists(save_path):
            success = False
            for attempt in range(1, MAX_RETRIES+1):
                try:
                    response = await client.get(img_url)
                    if response.status_code == 200:
                        with open(save_path, "wb") as f:
                            f.write(response.content)
                        success = True
                        break
                    else:
                        sys.stderr.write(f"HTTP {response.status_code} for {img_url} (attempt {attempt}/{MAX_RETRIES})\n")
                except httpx.RequestError as e:
                    sys.stderr.write(f"Network error for {img_url} (attempt {attempt}/{MAX_RETRIES}): {e}\n")

                if not success and attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)

            if not success:
                sys.stderr.write(f"Giving up on {img_url} after {MAX_RETRIES} attempts.\n")
                return None

        # Double check file existence before returning metadata
        if os.path.exists(save_path):
            return {
                "timestamp": timestamp,
                "tweet_url": tweet_url,
                "full_path": os.path.abspath(save_path)
            }
    except Exception as e:
        sys.stderr.write(f"Error downloading {img_url}: {e}\n")
    return None

async def main():
    # Read from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return
        posts = json.loads(input_data)
    except json.JSONDecodeError:
        sys.stderr.write("Error: Input is not valid JSON.\n")
        return

    # Create downloads directory in home folder
    download_dir = os.path.expanduser("~/Downloads")
    os.makedirs(download_dir, exist_ok=True)

    results = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        tasks = []
        for post in posts:
            content = post.get("content", "")
            timestamp = post.get("timestamp", "")
            tweet_url = post.get("url", "")
            
            # Filter for "Good morning" (case-insensitive)
            if "good morning" in content.lower():
                images = post.get("images", [])
                for img_url in images:
                    tasks.append(download_image(client, img_url, tweet_url, timestamp, download_dir))

        if tasks:
            downloaded_metadata = await asyncio.gather(*tasks)
            # Filter out failed downloads
            results = [m for m in downloaded_metadata if m]

    # Output results as JSON to stdout
    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2))
    sys.stdout.write('\n')
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
