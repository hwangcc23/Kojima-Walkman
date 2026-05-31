#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: Analyzes downloaded images using EasyOCR or Gemini LLM to extract song title, artist, and album.
"""

import json
import sys
import os
import argparse
import base64
import mimetypes
import logging
import re
import httpx

def analyze_music(reader, image_path):
    try:
        # 1. Perform OCR with full detail to get bounding boxes
        raw_results = reader.readtext(image_path)
        
        if not raw_results:
            return "Unknown Title", None, None

        # 2. Identify Anchor (Progress Bar area)
        # Look for time patterns like "1:23" or "04:50" (handle OCR misreads of ':')
        time_pattern = re.compile(r'\d{1,2}[:l|;.,\s]\d{1,2}')
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

def get_best_model(api_key):
    """
    Queries the Gemini API for available models and returns the best Flash model.
    """
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models_data]

                # Check models in order of preference
                for candidate in ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]:
                    if candidate in model_names:
                        return candidate

                # Fallback to any model containing flash
                for name in model_names:
                    if "flash" in name.lower():
                        return name

                # Fallback to the first available model if any
                if model_names:
                    return model_names[0]
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to query available models ({e}). Defaulting to models/gemini-2.5-flash.\n")
    return "models/gemini-2.5-flash"

def analyze_music_gemini(image_path, api_key, model_name):
    """
    Analyzes downloaded images using Google Gemini API to extract music metadata (song_title, artist, album).
    """
    try:
        # 1. Read and base64 encode the image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # 2. Determine mime type
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"

        # 3. Construct Gemini API request payload
        model_id = model_name.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Analyze this screenshot from a music player (like a Walkman or car screen) "
                                "to extract the song information.\n"
                                "Please extract: \n"
                                "1. song_title: The name of the song currently playing.\n"
                                "2. artist: The artist of the song (set to null if not found).\n"
                                "3. album: The album of the song (set to null if not found).\n\n"
                                "Do not include UI text, time, battery indicators, or device brands like SONY/WALKMAN. "
                                "Ensure the fields are returned exactly matching the requested JSON structure."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "song_title": {"type": "STRING"},
                        "artist": {"type": "STRING"},
                        "album": {"type": "STRING"}
                    },
                    "required": ["song_title"]
                }
            }
        }

        # 4. Make HTTP POST request to Gemini API
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

            response_json = response.json()
            # Extract content from response
            candidates = response_json.get("candidates", [])
            if not candidates:
                sys.stderr.write(f"No candidates returned from Gemini for {os.path.basename(image_path)}\n")
                return "Unknown Title", None, None

            text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text_content:
                sys.stderr.write(f"Empty text content in Gemini response for {os.path.basename(image_path)}\n")
                return "Unknown Title", None, None

            # Parse response JSON
            data = json.loads(text_content.strip())

            song_title = data.get("song_title") or "Unknown Title"
            artist = data.get("artist") or None
            album = data.get("album") or None

            return song_title, artist, album

    except Exception as e:
        sys.stderr.write(f"Error processing {image_path} with Gemini ({model_name}): {e}\n")
        return "Error", None, None

def main():
    # Setup Argument Parser
    parser = argparse.ArgumentParser(description="Analyzes downloaded images using OCR or Gemini LLM to extract music metadata.")
    parser.add_argument(
        "--engine", "-e",
        choices=["ocr", "gemini"],
        default="ocr",
        help="Analysis engine to use (default: ocr)"
    )
    args = parser.parse_args()

    # Read JSON from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return
        image_list = json.loads(input_data)
    except json.JSONDecodeError:
        sys.stderr.write("Error: Input is not valid JSON.\n")
        sys.exit(1)

    reader = None
    api_key = None
    model_name = None

    if args.engine == "gemini":
        # Load API key from config.json first
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    api_key = cfg.get("gemini_api_key")
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to load config.json: {e}\n")

        # Fallback to environment variable
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            sys.stderr.write("Error: Gemini API key not found. Please set 'gemini_api_key' in config.json or export GEMINI_API_KEY.\n")
            sys.exit(1)

        # Query for the best available model
        model_name = get_best_model(api_key)
        sys.stderr.write(f"Selected Gemini model: {model_name}\n")
    else:
        # Initialize EasyOCR Reader
        sys.stderr.write("Initializing OCR engine (this may take a moment)...\n")
        try:
            import easyocr
            logging.getLogger('easyocr').setLevel(logging.ERROR)
            reader = easyocr.Reader(['en', 'ja'], gpu=False)
        except Exception as e:
            sys.stderr.write(f"Failed to initialize OCR: {e}\n")
            sys.exit(1)

    final_results = []

    for item in image_list:
        path = item.get("full_path")
        timestamp = item.get("timestamp")
        tweet_url = item.get("tweet_url")

        if path and os.path.exists(path):
            sys.stderr.write(f"Analyzing: {os.path.basename(path)}...\n")
            if args.engine == "gemini":
                title, artist, album = analyze_music_gemini(path, api_key, model_name)
            else:
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


