#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project: Collect Songs in the Walkman of my god: Hideo Kojima
Author: Chih-Chyuan Hwang (hwangcc@csie.nctu.edu.tw) (Assisted by Google Gemini)
License: Apache 2.0
Description: A tool to scrape posts from X.com profiles.
"""
import asyncio
import json
import sys
import argparse
import re
import os
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

JST = timezone(timedelta(hours=9))

# Ensure stdout uses UTF-8 encoding (required on Windows for Japanese/Unicode output)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
# Ensure stdout is in blocking mode to prevent truncation on large data
try:
    import os
    os.set_blocking(sys.stdout.fileno(), True)
except:
    pass

def parse_args():
    parser = argparse.ArgumentParser(
        description="X.com (Twitter) Scraper - Scrapes posts and media links from a specified account within the last N hours.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  1. Scrape Hideo Kojima's posts from the last 24 hours (default):
     python3 x-scrapper.py https://x.com/HIDEO_KOJIMA_EN

  2. Scrape posts from the last 48 hours and save to a JSON file:
     python3 x-scrapper.py https://x.com/HIDEO_KOJIMA_EN -d 48 > result.json

  3. Enable debug mode to see detailed scraping progress:
     python3 x-scrapper.py https://x.com/HIDEO_KOJIMA_EN --debug

Notes:
  This script requires 'config.json' to be present in the same directory.

  PURPOSE:
  X.com has strong anti-bot protections on its login page. This script bypasses
  the login process by using a pre-authenticated session (cookies) stored in
  'config.json' under the key 'x_auth_state'.

  HOW TO SETUP:
  1. Login to X.com in your web browser.
  2. Open Developer Tools (F12) -> Application -> Cookies -> https://x.com.
  3. Find the 'auth_token' cookie and copy its value.
  4. Create a file named 'config.json' in this directory with the following content:

  {
    "x_auth_state": {
      "cookies": [
        {
          "name": "auth_token",
          "value": "PASTE_YOUR_AUTH_TOKEN_HERE",
          "domain": ".x.com",
          "path": "/",
          "secure": true,
          "httpOnly": true,
          "sameSite": "Lax"
        }
      ],
      "origins": []
    },
    "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE"
  }
"""
    )
    parser.add_argument("url", help="The X.com profile URL")
    parser.add_argument("--duration", "-d", type=int, default=24, help="Hours to scrape")
    parser.add_argument("--debug", "-D", action="store_true", help="Enable progress logs to stderr")
    return parser.parse_args()

def extract_username(url):
    match = re.search(r"(?:x|twitter)\.com/([^/?#]+)", url)
    return match.group(1) if match else "unknown"

def sanitize_cookies(cookies):
    sanitized = []
    for c in cookies:
        if not isinstance(c, dict):
            continue

        name = c.get("name")
        value = c.get("value")
        domain = c.get("domain", ".x.com")
        path = c.get("path", "/")
        if not name or value is None:
            continue

        cookie = {
            "name": str(name),
            "value": str(value),
            "domain": str(domain),
            "path": str(path),
        }

        # Normalize sameSite for Playwright requirement ('Strict' | 'Lax' | 'None')
        ss = c.get("sameSite")
        if isinstance(ss, str):
            ss_lower = ss.lower()
            if ss_lower == "strict":
                cookie["sameSite"] = "Strict"
            elif ss_lower in ("lax", "unspecified"):
                cookie["sameSite"] = "Lax"
            elif ss_lower in ("none", "no_restriction"):
                cookie["sameSite"] = "None"
            else:
                cookie["sameSite"] = "Lax"
        else:
            cookie["sameSite"] = "Lax"

        # Normalize expiration field
        expires = c.get("expires") if "expires" in c else c.get("expirationDate")
        if isinstance(expires, (int, float)):
            cookie["expires"] = float(expires)

        if "httpOnly" in c and isinstance(c["httpOnly"], bool):
            cookie["httpOnly"] = c["httpOnly"]
        if "secure" in c and isinstance(c["secure"], bool):
            cookie["secure"] = c["secure"]

        if "partitionKey" in c and isinstance(c["partitionKey"], str):
            cookie["partitionKey"] = c["partitionKey"]

        sanitized.append(cookie)

    return sanitized

async def scrape_x(url, duration_hours, debug=False):
    def log(msg):
        if debug:
            sys.stderr.write(f"LOG: {msg}\n")
            sys.stderr.flush()

    if not os.path.exists("config.json"):
        sys.stderr.write("Error: config.json not found.\n")
        sys.stdout.write("[]\n")
        sys.stdout.flush()
        return

    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config_data = json.load(f)
            auth_state = config_data.get("x_auth_state")
            if not auth_state or not auth_state.get("cookies"):
                sys.stderr.write("Error: 'x_auth_state' or 'cookies' not found in config.json.\n")
                sys.stdout.write("[]\n")
                sys.stdout.flush()
                return

            # Auto-sanitize cookies for Playwright compatibility
            auth_state["cookies"] = sanitize_cookies(auth_state["cookies"])
    except Exception as e:
        sys.stderr.write(f"Error loading config.json: {e}\n")
        sys.stdout.write("[]\n")
        sys.stdout.flush()
        return

    username = extract_username(url)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=duration_hours)
    
    results = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            storage_state=auth_state,
            viewport={"width": 1440, "height": 1200}
        )
        page = await context.new_page()

        auth_error_detected = [False]

        async def handle_response(response):
            if "graphql" in response.url and response.status == 403:
                try:
                    text = await response.text()
                    if "Could not authenticate you" in text or '"code":32' in text:
                        auth_error_detected[0] = True
                except:
                    pass

        page.on("response", handle_response)

        log(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Active polling and scrolling loop to wait for tweets
            log("Waiting for tweets to render...")
            tweets_found = False
            start_wait = asyncio.get_event_loop().time()
            max_wait_seconds = 120

            while asyncio.get_event_loop().time() - start_wait < max_wait_seconds:
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                if len(tweets) > 0:
                    tweets_found = True
                    log(f"Tweets detected ({len(tweets)}) after {asyncio.get_event_loop().time() - start_wait:.1f}s.")
                    break

                # Dismiss potential popups/overlays
                await page.keyboard.press("Escape")
                # Scroll down to trigger lazy loading / virtualized list
                await page.evaluate("window.scrollBy(0, 600)")
                await asyncio.sleep(2)

            if not tweets_found:
                await page.screenshot(path="debug_timeout.png")
                if auth_error_detected[0]:
                    sys.stderr.write("ERROR: X.com authentication failed (auth_token expired or invalid).\n")
                    sys.stderr.write("Please update 'auth_token' in config.json with a fresh cookie from your logged-in browser session.\n")
                else:
                    log("Timeout waiting for tweets. Screenshot saved to debug_timeout.png")
                raise TimeoutError("Timeout exceeded waiting for article[data-testid=\"tweet\"] to appear.")

            reached_end = False
            scroll_attempts = 0
            max_scrolls = max(400, int(duration_hours * 2))
            empty_streak = 0

            while not reached_end and scroll_attempts < max_scrolls:
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                found_new = False

                for tweet in tweets:
                    link = await tweet.query_selector('a[href*="/status/"]')
                    if not link: continue
                    path = await link.get_attribute("href")
                    tid = path.split("/")[-1]
                    
                    time_el = await tweet.query_selector('time')
                    if not time_el: continue
                    tstr = await time_el.get_attribute("datetime")
                    ttime = datetime.fromisoformat(tstr.replace("Z", "+00:00"))
                    
                    if tid in seen_ids: continue

                    # Basic Pinned Check (supports EN, ZH, JA)
                    is_pinned = False
                    sc = await tweet.query_selector('div[data-testid="socialContext"]')
                    if sc:
                        sc_text = await sc.inner_text()
                        if any(k in sc_text for k in ("Pinned", "已釘選", "固定されたツイート")):
                            is_pinned = True
                    
                    if ttime < cutoff_time:
                        if scroll_attempts < 20: continue # Likely suggested/pinned
                        else: continue

                    seen_ids.add(tid)
                    found_new = True

                    author_el = await tweet.query_selector('div[data-testid="User-Name"] span:has-text("@")')
                    author = (await author_el.inner_text()).strip().lstrip('@').lower() if author_el else ""
                    
                    text_el = await tweet.query_selector('div[data-testid="tweetText"]')
                    text = await text_el.inner_text() if text_el else ""
                    imgs = [await img.get_attribute("src") for img in await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')]
                    vids = [await v.get_attribute("src") for v in await tweet.query_selector_all('div[data-testid="videoPlayer"] video') if await v.get_attribute("src")]
                    
                    results.append({
                        "account_name": username,
                        "timestamp": ttime.astimezone(JST).isoformat(),
                        "content": text,
                        "is_retweet": (author != username.lower()),
                        "url": f"https://x.com{path}",
                        "images": imgs,
                        "videos": vids
                    })
                    if len(results) % 20 == 0:
                        log(f"Scraped {len(results)} tweets... (current date: {ttime.strftime('%Y-%m-%d')})")

                if not found_new and scroll_attempts > 20:
                    empty_streak += 1
                    if empty_streak >= 15:
                        log("Timeframe boundary reached. Stopping.")
                        reached_end = True
                else:
                    empty_streak = 0

                await page.evaluate("window.scrollBy(0, 3500)")
                await asyncio.sleep(2)
                scroll_attempts += 1

            # FINAL OUTPUT
            results.sort(key=lambda x: x['timestamp'], reverse=True)
            log(f"Success! Total {len(results)} tweets found.")
            
            # Using synchronous print to ensure the OS pipe receives everything before exit
            final_json = json.dumps(results, ensure_ascii=False, indent=2)
            sys.stdout.write(final_json)
            sys.stdout.write('\n')
            sys.stdout.flush()

        except Exception as e:
            sys.stderr.write(f"CRITICAL ERROR: {e}\n")
            sys.stdout.write("[]\n")
            sys.stdout.flush()
        finally:
            await browser.close()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(scrape_x(args.url, args.duration, args.debug))
