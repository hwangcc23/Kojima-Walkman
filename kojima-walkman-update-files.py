#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: Automatically updates kojima-walkman.json and README.md with new songs from stdin.
"""

import os
import sys
import json
import argparse
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="Automatically update Walkman JSON and README.md files with new music recommendations.")
    parser.add_argument(
        "--json", "-j",
        default="kojima-walkman.json",
        help="Path to the kojima-walkman.json database file (default: kojima-walkman.json)"
    )
    parser.add_argument(
        "--readme", "-r",
        default="README.md",
        help="Path to the README.md file (default: README.md)"
    )
    return parser.parse_args()

def main():
    # Robust I/O: Ensure stdout is in blocking mode
    try:
        os.set_blocking(sys.stdout.fileno(), True)
    except AttributeError:
        pass  # set_blocking might not exist on all platforms (e.g. Windows, but we are on Linux)

    args = parse_args()

    # 1. Read JSON from stdin
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.stderr.write("No input data received on stdin.\n")
            # Write empty list to stdout for pipeline compatibility
            sys.stdout.write("[]\n")
            sys.stdout.flush()
            return
        new_entries = json.loads(input_data)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error: stdin is not valid JSON: {e}\n")
        sys.exit(1)

    if not isinstance(new_entries, list):
        sys.stderr.write("Error: Input JSON must be a list of objects.\n")
        sys.exit(1)

    if not new_entries:
        sys.stderr.write("No new items to process (input list is empty).\n")
        sys.stdout.write("[]\n")
        sys.stdout.flush()
        return

    # 2. Load existing JSON database
    existing_entries = []
    if os.path.exists(args.json):
        try:
            with open(args.json, "r", encoding="utf-8") as f:
                existing_entries = json.load(f)
                if not isinstance(existing_entries, list):
                    sys.stderr.write(f"Error: Existing file '{args.json}' does not contain a list. Initializing to empty.\n")
                    existing_entries = []
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to load '{args.json}' ({e}). Initializing to empty.\n")
            existing_entries = []
    else:
        sys.stderr.write(f"Database file '{args.json}' not found. It will be created.\n")

    # Build a set of existing tweet URLs and timestamps for deduplication
    existing_urls = {entry.get("tweet_url") for entry in existing_entries if entry.get("tweet_url")}
    existing_timestamps = {entry.get("timestamp") for entry in existing_entries if entry.get("timestamp")}

    # 3. Process new entries and filter out duplicates
    deduped_new_entries = []
    for item in new_entries:
        url = item.get("tweet_url")
        timestamp = item.get("timestamp")
        if not url:
            sys.stderr.write("Warning: Skipping entry because 'tweet_url' is missing.\n")
            continue

        if url in existing_urls:
            sys.stderr.write(f"Skipping duplicate entry (URL already exists): {url}\n")
            continue

        if timestamp and timestamp in existing_timestamps:
            sys.stderr.write(f"Skipping duplicate entry (timestamp already exists): {timestamp}\n")
            continue

        # Clean entry to keep only database fields
        album_val = item.get("album")
        if album_val is None or str(album_val).strip() in ("null", "None", ""):
            album_val = ""
        else:
            album_val = str(album_val).strip()

        clean_entry = {
            "timestamp": timestamp or "",
            "tweet_url": url,
            "song_title": item.get("song_title") or "Unknown Title",
            "artist": item.get("artist") or "",
            "album": album_val
        }
        deduped_new_entries.append(clean_entry)
        existing_urls.add(url)
        if timestamp:
            existing_timestamps.add(timestamp)

    if not deduped_new_entries:
        sys.stderr.write("No new unique songs to add.\n")
        # Output the original input to stdout for pipeline continuity
        sys.stdout.write(json.dumps(new_entries, ensure_ascii=False, indent=2))
        sys.stdout.write('\n')
        sys.stdout.flush()
        return

    # 4. Merge and sort all entries chronologically descending
    merged_entries = existing_entries + deduped_new_entries
    
    # Normalize album values in all merged entries to prevent nulls/None/empty strings being inconsistent
    for entry in merged_entries:
        alb = entry.get("album")
        if alb is None or str(alb).strip() in ("null", "None", ""):
            entry["album"] = ""
        else:
            entry["album"] = str(alb).strip()
    
    # We parse the timestamp or fall back to string comparison
    def get_sort_key(entry):
        ts = entry.get("timestamp") or ""
        try:
            # Try to parse ISO format timestamp
            return datetime.fromisoformat(ts)
        except Exception:
            return ts

    merged_entries.sort(key=get_sort_key, reverse=True)

    # 5. Write back to the JSON database
    try:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(merged_entries, f, ensure_ascii=False, indent=2)
            f.write('\n')
        sys.stderr.write(f"Successfully updated '{args.json}' with {len(deduped_new_entries)} new entries.\n")
    except Exception as e:
        sys.stderr.write(f"Error: Failed to write to '{args.json}': {e}\n")
        sys.exit(1)

    # 6. Update README.md
    if os.path.exists(args.readme):
        try:
            with open(args.readme, "r", encoding="utf-8") as f:
                readme_lines = f.readlines()

            # Find table header and divider indices
            table_header_idx = -1
            for idx, line in enumerate(readme_lines):
                if "| Date | Song Title | Artist | Album | Tweet URL |" in line:
                    table_header_idx = idx
                    break

            if table_header_idx == -1:
                sys.stderr.write(f"Error: Could not find table header in '{args.readme}'. Skipping README update.\n")
            else:
                table_divider_idx = -1
                for idx in range(table_header_idx + 1, len(readme_lines)):
                    line = readme_lines[idx]
                    if line.strip().startswith("|") and ":" in line:
                        table_divider_idx = idx
                        break

                if table_divider_idx == -1:
                    sys.stderr.write(f"Error: Could not find table divider under header in '{args.readme}'. Skipping README update.\n")
                else:
                    # Construct new markdown table rows
                    table_rows = []
                    for entry in merged_entries:
                        # Extract date (YYYY-MM-DD) from timestamp
                        timestamp = entry.get("timestamp") or ""
                        date_str = timestamp[:10] if len(timestamp) >= 10 else "-"
                        
                        song = entry.get("song_title") or "-"
                        artist = entry.get("artist") or "-"
                        
                        album_val = entry.get("album")
                        if album_val is None or str(album_val).strip() in ("null", "None", ""):
                            album = "-"
                        else:
                            album = str(album_val).strip()
                            
                        url = entry.get("tweet_url") or ""

                        # Escape pipe character '|' to not break markdown table structure
                        song = song.replace("|", "\\|")
                        artist = artist.replace("|", "\\|")
                        album = album.replace("|", "\\|")

                        link_str = f"[Link]({url})" if url else "-"
                        table_rows.append(f"| {date_str} | {song} | {artist} | {album} | {link_str} |\n")

                    # Construct the updated README content
                    new_readme_lines = readme_lines[:table_divider_idx + 1]
                    new_readme_lines.extend(table_rows)

                    # Skip old table rows
                    curr_idx = table_divider_idx + 1
                    while curr_idx < len(readme_lines) and readme_lines[curr_idx].strip().startswith("|"):
                        curr_idx += 1

                    # Append the remaining lines of the file
                    new_readme_lines.extend(readme_lines[curr_idx:])

                    with open(args.readme, "w", encoding="utf-8") as f:
                        f.writelines(new_readme_lines)
                    sys.stderr.write(f"Successfully updated playlist table in '{args.readme}'.\n")

        except Exception as e:
            sys.stderr.write(f"Error: Failed to update '{args.readme}': {e}\n")
            sys.exit(1)
    else:
        sys.stderr.write(f"Warning: '{args.readme}' not found. Skipping README update.\n")

    # 7. Output new entries (from stdin) to stdout
    sys.stdout.write(json.dumps(new_entries, ensure_ascii=False, indent=2))
    sys.stdout.write('\n')
    sys.stdout.flush()

if __name__ == "__main__":
    main()
