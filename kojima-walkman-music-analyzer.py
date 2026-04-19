#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: Analyzes downloaded images using OCR to extract song title, artist, and album.
"""

import json
import sys
import os
import easyocr
import logging

# Suppress easyocr/torch logs to keep stdout clean for JSON
logging.getLogger('easyocr').setLevel(logging.ERROR)

def analyze_music(reader, image_path):
    try:
        # Perform OCR
        results = reader.readtext(image_path, detail=0)
        
        if not results:
            return "Unknown Title", None, None

        # Filter out very short strings or noise (e.g., icons, clock)
        clean_lines = [line.strip() for line in results if len(line.strip()) > 1]
        
        # Heuristic for Sony Walkman / Car Display / Music Player UI:
        # 1st line: Title
        # 2nd line: Artist
        # 3rd line: Album
        song_title = clean_lines[0] if len(clean_lines) > 0 else "Unknown Title"
        artist = clean_lines[1] if len(clean_lines) > 1 else None
        album = clean_lines[2] if len(clean_lines) > 2 else None
            
        return song_title, artist, album
    except Exception as e:
        sys.stderr.write(f"Error processing {image_path}: {e}\n")
        return "Error", None, None

def main():
    # Read JSON from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return
        image_list = json.loads(input_data)
    except json.JSONDecodeError:
        sys.stderr.write("Error: Input is not valid JSON.\n")
        return

    # Initialize EasyOCR Reader
    sys.stderr.write("Initializing OCR engine (this may take a moment)...\n")
    try:
        reader = easyocr.Reader(['en', 'ja'], gpu=False)
    except Exception as e:
        sys.stderr.write(f"Failed to initialize OCR: {e}\n")
        return

    final_results = []
    
    for item in image_list:
        path = item.get("full_path")
        timestamp = item.get("timestamp")
        tweet_url = item.get("tweet_url")
        
        if path and os.path.exists(path):
            sys.stderr.write(f"Analyzing: {os.path.basename(path)}...\n")
            title, artist, album = analyze_music(reader, path)
            
            result_entry = {
                "timestamp": timestamp,
                "tweet_url": tweet_url,
                "image_path": path,
                "song_title": title
            }
            if artist:
                result_entry["artist"] = artist
            if album:
                result_entry["album"] = album
            
            final_results.append(result_entry)

    # Output final summary to stdout
    if final_results:
        sys.stdout.write(json.dumps(final_results, ensure_ascii=False, indent=2))
        sys.stdout.write('\n')
        sys.stdout.flush()
    else:
        sys.stdout.write("[]\n")

if __name__ == "__main__":
    main()
