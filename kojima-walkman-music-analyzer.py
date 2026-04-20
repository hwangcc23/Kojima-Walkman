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
import re

# Suppress easyocr/torch logs to keep stdout clean for JSON
logging.getLogger('easyocr').setLevel(logging.ERROR)

def analyze_music(reader, image_path):
    try:
        # 1. Perform OCR with full detail to get bounding boxes
        raw_results = reader.readtext(image_path)
        
        if not raw_results:
            return "Unknown Title", None, None

        # 2. Identify Anchor (Progress Bar area)
        # Look for time patterns like "1:23" or "04:50"
        time_pattern = re.compile(r'\d{1,2}:\d{2}')
        time_markers = []
        for (bbox, text, prob) in raw_results:
            if time_pattern.search(text):
                # Calculate center Y of the text box
                y_center = (bbox[0][1] + bbox[2][1]) / 2
                time_markers.append(y_center)
        
        anchor_y = None
        if time_markers:
            # Use the average Y position of all time markers found as the anchor
            anchor_y = sum(time_markers) / len(time_markers)

        # 3. Extract and Clean Text Lines
        candidate_lines = []
        for (bbox, text, prob) in raw_results:
            text = text.strip()
            # Basic noise filtering
            if len(text) < 2 or prob < 0.2:
                continue
            # Skip system/UI keywords and the time markers themselves
            if any(k in text.lower() for k in ["walkman", "sony", "battery", "bluetooth", "good morning"]):
                continue
            if time_pattern.search(text):
                continue
                
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            height = bbox[2][1] - bbox[0][1]
            candidate_lines.append({'text': text, 'y': y_center, 'h': height})

        if not candidate_lines:
            return "Unknown Title", None, None

        # 4. Layout Heuristics based on Anchor
        song_title, artist, album = "Unknown Title", None, None
        
        if anchor_y:
            # Separate lines into those above and below the progress bar
            # Kojima's UI usually has metadata ABOVE the progress bar
            above = sorted([l for l in candidate_lines if l['y'] < anchor_y], key=lambda x: x['y'], reverse=True)
            
            if above:
                # Take up to 3 lines directly above the bar
                # Sorting them from top-to-bottom for assignment
                # If 3 lines: [Top] Title, [Mid] Artist, [Bottom] Album
                # If 2 lines: [Top] Title, [Bottom] Artist
                # If 1 line: Title
                targets = sorted(above[:3], key=lambda x: x['y'])
                
                if len(targets) == 1:
                    song_title = targets[0]['text']
                elif len(targets) == 2:
                    song_title = targets[0]['text']
                    artist = targets[1]['text']
                else:
                    song_title = targets[0]['text']
                    artist = targets[1]['text']
                    album = targets[2]['text']
            else:
                # Fallback if nothing found above, try below (rare UI)
                below = sorted([l for l in candidate_lines if l['y'] > anchor_y], key=lambda x: x['y'])
                if below:
                    targets = below[:3]
                    song_title = targets[0]['text']
                    artist = targets[1]['text'] if len(targets) > 1 else None
                    album = targets[2]['text'] if len(targets) > 2 else None
        else:
            # Fallback: Original logic (top-to-bottom) or size-based
            # Sorting by height is often a good proxy for "Title"
            candidate_lines.sort(key=lambda x: x['h'], reverse=True)
            song_title = candidate_lines[0]['text']
            if len(candidate_lines) > 1:
                # Rest sorted by Y
                others = sorted(candidate_lines[1:], key=lambda x: x['y'])
                artist = others[0]['text']
                album = others[1]['text'] if len(others) > 1 else None
            
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
