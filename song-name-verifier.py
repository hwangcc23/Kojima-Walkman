#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: Verifies and corrects song title, artist, and album against Spotify and Google Search using Gemini LLM.
"""

import os
import sys
import json
import argparse
import subprocess
import time
import re
import httpx

class GeminiAuthError(Exception):
    """Raised when Gemini API encounters a fatal authentication or authorization error (e.g. 400, 401, 403)."""
    pass

def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify and correct song information against Spotify and Google Search using Gemini."
    )
    parser.add_argument(
        "--file", "-f",
        default="kojima-walkman.json",
        help="Path to the database file (default: kojima-walkman.json)"
    )
    parser.add_argument(
        "--readme", "-r",
        default="README.md",
        help="Path to the README.md file (default: README.md)"
    )
    parser.add_argument(
        "--uncommitted", "-u",
        action="store_true",
        help="Verify uncommitted entries in git compared to HEAD (default in standalone mode)"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=None,
        help="Number of recent entries in database to verify"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Verify all entries in the database"
    )
    parser.add_argument(
        "--apply", "-y",
        action="store_true",
        help="Automatically apply verified changes to database and README without prompting"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run verification and display results without modifying any files"
    )
    parser.add_argument(
        "--title",
        help="Single-track lookup: song title"
    )
    parser.add_argument(
        "--artist",
        default="",
        help="Single-track lookup: artist"
    )
    parser.add_argument(
        "--album",
        default="",
        help="Single-track lookup: album"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini model to use (default: gemini-2.5-flash)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    return parser.parse_args()

def load_gemini_api_key():
    """Loads Gemini API key from environment or config.json."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key is not None:
        return api_key.strip() if api_key.strip() else None

    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                val = cfg.get("gemini_api_key")
                if val and str(val).strip():
                    api_key = str(val).strip()
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to read config.json: {e}\n")

    return api_key

def get_best_model(api_key, preferred_model=None):
    """Determines the best available Flash model with fallback."""
    if preferred_model:
        return preferred_model.replace("models/", "")

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                model_names = [m.get("name", "").replace("models/", "") for m in models_data]
                for candidate in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]:
                    if candidate in model_names:
                        return candidate
    except Exception as e:
        sys.stderr.write(f"Warning: Model discovery failed ({e}), defaulting to gemini-2.5-flash.\n")

    return "gemini-2.5-flash"

def verify_song_with_gemini(song_title, artist="", album="", api_key=None, model="gemini-2.5-flash", debug=False):
    """
    Queries Gemini with Google Search tool to verify song against Spotify and Google.
    Returns a dict with verification details.
    """
    prompt = f"""You are a music metadata verification specialist.
Your task is to verify and correct song information extracted from music players or OCR by comparing against Spotify and Google search results.

Input Metadata:
- Song Title: "{song_title}"
- Artist: "{artist}"
- Album: "{album}"

Instructions:
1. Search Spotify and Google to check if this track exists.
2. Determine whether the track can be found on Spotify.
3. Detect and correct any typos, OCR mistakes, truncation, or missing version tags (for example: "James Bond Theme (Moby)" -> "James Bond Theme (Moby's Re-Version)").
4. If album is empty or missing, find the primary official album or single release on Spotify.
5. If artist or title is misspelled, fix it to the official Spotify standard.
6. Return ONLY a valid JSON object in the following format (no text outside the JSON):
{{
  "verified_song_title": "<official track title>",
  "verified_artist": "<official artist name>",
  "verified_album": "<official album name or empty string if single/not found>",
  "spotify_found": true/false,
  "has_corrections": true/false,
  "confidence": "high" / "medium" / "low",
  "correction_notes": "<concise explanation of what was verified or corrected>"
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}]
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if debug:
                sys.stderr.write(f"[Debug] Requesting Gemini ({model}) for '{song_title}', attempt {attempt + 1}...\n")
            with httpx.Client(timeout=35.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code in (400, 401, 403):
                    err_msg = resp.text
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        pass
                    raise GeminiAuthError(f"HTTP {resp.status_code}: {err_msg}")

                if resp.status_code in (429, 503):
                    wait_sec = 2 * (attempt + 1)
                    sys.stderr.write(f"Notice: Gemini API returned {resp.status_code}. Retrying in {wait_sec}s...\n")
                    time.sleep(wait_sec)
                    continue

                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return None

                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if debug:
                    sys.stderr.write(f"[Debug] Raw response: {text_content}\n")

                match = re.search(r'\{.*\}', text_content, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    # Sanitize fields
                    v_title = parsed.get("verified_song_title") or song_title
                    v_artist = parsed.get("verified_artist") or artist
                    v_album = parsed.get("verified_album") or ""
                    if str(v_album).strip() in ("null", "None"):
                        v_album = ""

                    has_diff = (
                        v_title.strip() != song_title.strip() or
                        v_artist.strip() != artist.strip() or
                        (v_album.strip() and v_album.strip() != album.strip())
                    )

                    return {
                        "verified_song_title": v_title.strip(),
                        "verified_artist": v_artist.strip(),
                        "verified_album": v_album.strip(),
                        "spotify_found": bool(parsed.get("spotify_found", False)),
                        "has_corrections": bool(parsed.get("has_corrections", has_diff)),
                        "confidence": parsed.get("confidence", "medium"),
                        "correction_notes": parsed.get("correction_notes", "")
                    }
        except GeminiAuthError:
            raise
        except Exception as e:
            if debug:
                sys.stderr.write(f"[Debug] Attempt {attempt + 1} failed: {e}\n")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                sys.stderr.write(f"Warning: Verification failed for '{song_title}': {e}\n")

    return None

def get_uncommitted_entries(current_entries, json_path):
    """
    Returns entries in current_entries that are not present in git HEAD.
    """
    try:
        res = subprocess.run(
            ["git", "show", f"HEAD:{json_path}"],
            capture_output=True,
            text=True,
            check=True
        )
        head_entries = json.loads(res.stdout)
        head_keys = {
            (e.get("tweet_url") or "", e.get("timestamp") or "")
            for e in head_entries
        }
        uncommitted = [
            e for e in current_entries
            if ((e.get("tweet_url") or "", e.get("timestamp") or "")) not in head_keys
        ]
        return uncommitted
    except Exception as e:
        sys.stderr.write(f"Notice: Could not inspect git HEAD for {json_path} ({e}).\n")
        return []

def update_readme_table(readme_path, all_entries):
    """
    Synchronizes the playlist table in README.md with all_entries.
    """
    if not os.path.exists(readme_path):
        sys.stderr.write(f"Warning: '{readme_path}' not found. Skipping README update.\n")
        return False

    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        header_idx = -1
        for idx, line in enumerate(lines):
            if "| Date | Song Title | Artist | Album | Tweet URL |" in line:
                header_idx = idx
                break

        if header_idx == -1:
            sys.stderr.write(f"Error: Table header not found in '{readme_path}'.\n")
            return False

        divider_idx = -1
        for idx in range(header_idx + 1, len(lines)):
            line = lines[idx]
            if line.strip().startswith("|") and ":" in line:
                divider_idx = idx
                break

        if divider_idx == -1:
            sys.stderr.write(f"Error: Table divider not found in '{readme_path}'.\n")
            return False

        table_rows = []
        for entry in all_entries:
            ts = entry.get("timestamp") or ""
            date_str = ts[:10] if len(ts) >= 10 else "-"
            song = (entry.get("song_title") or "-").replace("|", "\\|")
            artist = (entry.get("artist") or "-").replace("|", "\\|")
            alb = entry.get("album")
            if alb is None or str(alb).strip() in ("null", "None", ""):
                album_str = "-"
            else:
                album_str = str(alb).strip().replace("|", "\\|")

            url = entry.get("tweet_url") or ""
            link_str = f"[Link]({url})" if url else "-"
            table_rows.append(f"| {date_str} | {song} | {artist} | {album_str} | {link_str} |\n")

        new_lines = lines[:divider_idx + 1]
        new_lines.extend(table_rows)

        curr_idx = divider_idx + 1
        while curr_idx < len(lines) and lines[curr_idx].strip().startswith("|"):
            curr_idx += 1

        new_lines.extend(lines[curr_idx:])

        with open(readme_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        sys.stderr.write(f"Successfully synchronized playlist table in '{readme_path}'.\n")
        return True
    except Exception as e:
        sys.stderr.write(f"Error: Failed to update '{readme_path}': {e}\n")
        return False

def pass_through_stream(reason=""):
    """
    Passes JSON list from stdin directly to stdout when verification is skipped or unavailable.
    Ensures downstream pipeline stages (like update-files) receive the unverified items intact.
    """
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.stdout.write("[]\n")
            sys.stdout.flush()
            return
        items = json.loads(input_data)
        if not isinstance(items, list):
            sys.stderr.write("Error: Expected a JSON list from stdin.\n")
            sys.exit(1)
        if reason:
            sys.stderr.write(f"[Verifier] Notice: {reason}. Passing through {len(items)} raw item(s) without verification.\n")
        sys.stdout.write(json.dumps(items, ensure_ascii=False, indent=2))
        sys.stdout.write('\n')
        sys.stdout.flush()
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error: stdin is not valid JSON: {e}\n")
        sys.exit(1)

def process_pipeline_stream(api_key, model, debug=False):
    """
    Handles Unix pipe mode: reads JSON list from stdin, verifies each item,
    and writes updated JSON list to stdout.
    """
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.stdout.write("[]\n")
            sys.stdout.flush()
            return
        items = json.loads(input_data)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error: stdin is not valid JSON: {e}\n")
        sys.exit(1)

    if not isinstance(items, list):
        sys.stderr.write("Error: Expected a JSON list from stdin.\n")
        sys.exit(1)

    if not items:
        sys.stdout.write("[]\n")
        sys.stdout.flush()
        return

    sys.stderr.write(f"--- [Verifier] Verifying {len(items)} song(s) via Gemini Search Grounding ---\n")
    auth_failed = False
    for item in items:
        orig_title = item.get("song_title") or "Unknown Title"
        orig_artist = item.get("artist") or ""
        orig_album = item.get("album") or ""

        if auth_failed:
            sys.stderr.write(f"[Verifier] Skipping verification for '{orig_title}' due to earlier auth failure. Keeping original values.\n")
            continue

        sys.stderr.write(f"[Verifier] Verifying: \"{orig_title}\" by \"{orig_artist}\"...\n")
        res = None
        try:
            res = verify_song_with_gemini(orig_title, orig_artist, orig_album, api_key, model, debug)
        except GeminiAuthError as e:
            sys.stderr.write(f"[Verifier] Gemini API authentication failed: {e}\n")
            sys.stderr.write("[Verifier] Disabling verification for remaining items; retaining original metadata.\n")
            auth_failed = True
        except Exception as e:
            sys.stderr.write(f"[Verifier] Unexpected error during verification: {e}\n")

        if res:
            v_title = res["verified_song_title"]
            v_artist = res["verified_artist"]
            v_album = res["verified_album"]
            found = res["spotify_found"]
            notes = res["correction_notes"]

            status_sym = "✓ Spotify Found" if found else "? Not Confirmed on Spotify"
            sys.stderr.write(f"[Verifier] {status_sym} (Confidence: {res['confidence']})\n")

            if res["has_corrections"] or v_title != orig_title or v_artist != orig_artist or (v_album and v_album != orig_album):
                sys.stderr.write(f"  -> Title:  '{orig_title}' -> '{v_title}'\n")
                if v_artist != orig_artist:
                    sys.stderr.write(f"  -> Artist: '{orig_artist}' -> '{v_artist}'\n")
                if v_album and v_album != orig_album:
                    sys.stderr.write(f"  -> Album:  '{orig_album}' -> '{v_album}'\n")
                if notes:
                    sys.stderr.write(f"  -> Notes:  {notes}\n")

                item["song_title"] = v_title
                item["artist"] = v_artist
                if v_album:
                    item["album"] = v_album
            else:
                sys.stderr.write("  -> Metadata confirmed accurate, no corrections needed.\n")
        else:
            if not auth_failed:
                sys.stderr.write(f"[Verifier] Verification skipped/failed for '{orig_title}'. Keeping original values.\n")

    sys.stderr.write("--- [Verifier] Verification complete ---\n")
    # Output JSON to stdout for pipeline continuity
    sys.stdout.write(json.dumps(items, ensure_ascii=False, indent=2))
    sys.stdout.write('\n')
    sys.stdout.flush()

def main():
    try:
        os.set_blocking(sys.stdout.fileno(), True)
    except AttributeError:
        pass

    args = parse_args()

    # Load Gemini API Key
    api_key = load_gemini_api_key()
    if not api_key:
        if not sys.stdin.isatty():
            # Pipeline Mode: graceful pass-through
            pass_through_stream(reason="Gemini API key not found in config.json or environment")
            return
        else:
            sys.stderr.write("Error: Gemini API key not found. Please set 'gemini_api_key' in config.json or export GEMINI_API_KEY.\n")
            sys.exit(1)

    model = get_best_model(api_key, args.model)
    if args.debug:
        sys.stderr.write(f"[Debug] Selected Gemini model: {model}\n")

    # 1. Single-track Ad-hoc mode
    if args.title:
        sys.stderr.write(f"Verifying track: \"{args.title}\" by \"{args.artist}\" (Album: \"{args.album}\")...\n")
        try:
            res = verify_song_with_gemini(args.title, args.artist, args.album, api_key, model, args.debug)
        except GeminiAuthError as e:
            sys.stderr.write(f"Error: Gemini API authentication failed: {e}\n")
            sys.exit(1)

        if res:
            sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stderr.write("Verification failed.\n")
            sys.exit(1)
        return

    # 2. Pipeline Mode (stdin is piped)
    if not sys.stdin.isatty():
        process_pipeline_stream(api_key, model, args.debug)
        return

    # 3. Standalone File Mode (inspecting database file)
    if not os.path.exists(args.file):
        sys.stderr.write(f"Error: Database file '{args.file}' not found.\n")
        sys.exit(1)

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            all_entries = json.load(f)
            if not isinstance(all_entries, list):
                sys.stderr.write(f"Error: '{args.file}' does not contain a list.\n")
                sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error: Failed to load '{args.file}': {e}\n")
        sys.exit(1)

    if not all_entries:
        sys.stderr.write(f"Database '{args.file}' is empty.\n")
        return

    # Determine target entries
    if args.all:
        target_indices = list(range(len(all_entries)))
        mode_desc = f"all {len(all_entries)} entries"
    elif args.count is not None:
        count = min(args.count, len(all_entries))
        target_indices = list(range(count))
        mode_desc = f"latest {count} entry(s)"
    else:
        # Default: uncommitted new entries in git
        uncommitted = get_uncommitted_entries(all_entries, args.file)
        if not uncommitted:
            sys.stderr.write("No uncommitted new entries found in git for 'kojima-walkman.json'.\n")
            sys.stderr.write("Tip: Specify -c/--count <N> (e.g. -c 1) to verify existing entries, or --all.\n")
            return
        # Find matching indices
        uncommitted_keys = {
            (e.get("tweet_url") or "", e.get("timestamp") or "")
            for e in uncommitted
        }
        target_indices = [
            i for i, e in enumerate(all_entries)
            if ((e.get("tweet_url") or "", e.get("timestamp") or "")) in uncommitted_keys
        ]
        mode_desc = f"{len(target_indices)} uncommitted entry(s)"

    sys.stderr.write(f"=== Verifying {mode_desc} in '{args.file}' using Gemini ({model}) ===\n\n")

    changes_detected = False
    for idx in target_indices:
        entry = all_entries[idx]
        orig_title = entry.get("song_title") or ""
        orig_artist = entry.get("artist") or ""
        orig_album = entry.get("album") or ""
        date_str = (entry.get("timestamp") or "")[:10]

        sys.stderr.write(f"[{idx + 1}/{len(target_indices)}] [{date_str}] \"{orig_title}\" - \"{orig_artist}\" (Album: \"{orig_album}\")\n")
        try:
            res = verify_song_with_gemini(orig_title, orig_artist, orig_album, api_key, model, args.debug)
        except GeminiAuthError as e:
            sys.stderr.write(f"\nError: Gemini API authentication failed: {e}\n")
            sys.stderr.write("Verification aborted.\n")
            sys.exit(1)

        if not res:
            sys.stderr.write("   -> Verification query failed or timed out.\n\n")
            continue

        v_title = res["verified_song_title"]
        v_artist = res["verified_artist"]
        v_album = res["verified_album"]
        found = res["spotify_found"]
        notes = res["correction_notes"]

        status_tag = "✓ Spotify: Found" if found else "✗ Spotify: Not Found"
        sys.stderr.write(f"   Status: {status_tag} | Confidence: {res['confidence']}\n")

        has_diff = (
            v_title != orig_title or
            v_artist != orig_artist or
            (v_album and v_album != orig_album)
        )

        if has_diff:
            changes_detected = True
            sys.stderr.write("   -> PROPOSED CORRECTIONS:\n")
            if v_title != orig_title:
                sys.stderr.write(f"      Song Title : '{orig_title}' -> '{v_title}'\n")
            if v_artist != orig_artist:
                sys.stderr.write(f"      Artist     : '{orig_artist}' -> '{v_artist}'\n")
            if v_album and v_album != orig_album:
                sys.stderr.write(f"      Album      : '{orig_album}' -> '{v_album}'\n")
            if notes:
                sys.stderr.write(f"      Notes      : {notes}\n")

            # Update in memory
            entry["song_title"] = v_title
            entry["artist"] = v_artist
            if v_album:
                entry["album"] = v_album
        else:
            sys.stderr.write("   -> Metadata is verified accurate. No changes needed.\n")
        sys.stderr.write("\n")

    if not changes_detected:
        sys.stderr.write("No corrections required. All verified entries are accurate.\n")
        return

    # Handle applying changes
    if args.dry_run:
        sys.stderr.write("[Dry-run] Modifications detected above, but none were written to disk.\n")
        return

    should_apply = args.apply
    if not should_apply:
        try:
            choice = input(f"Apply these corrections to '{args.file}' and '{args.readme}'? [y/N]: ").strip().lower()
            should_apply = choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            sys.stderr.write("\nAborted by user.\n")
            return

    if should_apply:
        try:
            with open(args.file, "w", encoding="utf-8") as f:
                json.dump(all_entries, f, ensure_ascii=False, indent=2)
                f.write("\n")
            sys.stderr.write(f"Successfully saved updated metadata to '{args.file}'.\n")
            update_readme_table(args.readme, all_entries)
        except Exception as e:
            sys.stderr.write(f"Error saving updates: {e}\n")
            sys.exit(1)
    else:
        sys.stderr.write("Changes discarded.\n")

if __name__ == "__main__":
    main()
