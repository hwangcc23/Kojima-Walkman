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
  This script requires 'auth_state.json' to be present in the same directory.
  
  PURPOSE:
  X.com has strong anti-bot protections on its login page. This script bypasses 
  the login process by using a pre-authenticated session (cookies) stored in 
  'auth_state.json'.

  HOW TO SETUP:
  1. Login to X.com in your web browser.
  2. Open Developer Tools (F12) -> Application -> Cookies -> https://x.com.
  3. Find the 'auth_token' cookie and copy its value.
  4. Create a file named 'auth_state.json' in this directory with the following content:

  {
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
  }
        """
    )
    parser.add_argument("url", help="The X.com profile URL (e.g., https://x.com/HIDEO_KOJIMA_EN)")
    parser.add_argument("--duration", "-d", type=int, default=24, help="Time range in hours to scrape (default: 24)")
    parser.add_argument("--debug", "-D", action="store_true", help="Enable debug mode to print detailed logs to stdout")
    return parser.parse_args()

def extract_username(url):
    match = re.search(r"(?:x|twitter)\.com/([^/?#]+)", url)
    if match:
        return match.group(1)
    return "unknown"

async def scrape_x(url, duration_hours, debug=False):
    def log(msg):
        if debug: print(msg, file=sys.stdout)

    if not os.path.exists("auth_state.json"):
        print("Severe Error: 'auth_state.json' not found.", file=sys.stderr)
        return

    username = extract_username(url)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=duration_hours)
    
    results = []
    seen_tweet_ids = set()
    scraped_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            storage_state="auth_state.json"
        )
        page = await context.new_page()

        log(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            if "i/flow/login" in page.url:
                print("Severe Error: Session expired. Please update 'auth_token' in auth_state.json.", file=sys.stderr)
                await browser.close()
                return

            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            except:
                print(f"Severe Error: Timeout waiting for tweets on {url}.", file=sys.stderr)
                await browser.close()
                return

            reached_end = False
            scroll_attempts = 0
            # Increase max scrolls dynamically: ~1 scroll per 5 hours of content, min 50
            max_scroll_attempts = max(50, int(duration_hours / 5) * 10) 

            while not reached_end and scroll_attempts < max_scroll_attempts:
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                
                new_tweets_in_this_scroll = 0
                current_scroll_earliest_time = None

                for tweet in tweets:
                    link_element = await tweet.query_selector('a[href*="/status/"]')
                    if not link_element: continue
                    
                    tweet_path = await link_element.get_attribute("href")
                    tweet_url = f"https://x.com{tweet_path}"
                    tweet_id = tweet_path.split("/")[-1]
                    
                    time_element = await tweet.query_selector('time')
                    if not time_element: continue
                    time_str = await time_element.get_attribute("datetime")
                    tweet_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    
                    # Track the latest time we've seen in this scroll
                    current_scroll_earliest_time = tweet_time

                    if tweet_id in seen_tweet_ids: continue
                    if tweet_time < cutoff_time: continue

                    seen_tweet_ids.add(tweet_id)
                    new_tweets_in_this_scroll += 1

                    # Check for Retweet
                    author_element = await tweet.query_selector('div[data-testid="User-Name"] span:has-text("@")')
                    author_handle = ""
                    if author_element:
                        author_handle = await author_element.inner_text()
                        author_handle = author_handle.strip().lstrip('@').lower()
                    is_retweet = (author_handle != username.lower()) if author_handle else False
                    
                    # Extract Content
                    text_element = await tweet.query_selector('div[data-testid="tweetText"]')
                    text = await text_element.inner_text() if text_element else ""
                    
                    # Extract Media
                    images = [await img.get_attribute("src") for img in await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')]
                    videos = [await v.get_attribute("src") for v in await tweet.query_selector_all('div[data-testid="videoPlayer"] video') if await v.get_attribute("src")]
                    
                    results.append({
                        "account_name": username,
                        "timestamp": time_str,
                        "content": text,
                        "is_retweet": is_retweet,
                        "url": tweet_url,
                        "images": images,
                        "videos": videos
                    })
                    
                    scraped_count += 1
                    log(f"scrapping {scraped_count} {'tweet' if scraped_count == 1 else 'tweets'}")

                if current_scroll_earliest_time and debug:
                    log(f"Scroll {scroll_attempts+1}/{max_scroll_attempts}: reached {current_scroll_earliest_time.strftime('%Y-%m-%d')}")

                # Stop condition: if we've seen tweets older than cutoff (and it's not a pinned tweet)
                if current_scroll_earliest_time and current_scroll_earliest_time < cutoff_time:
                    # Pinned tweets are at the top, so we only stop if we are far enough
                    if scroll_attempts > 2: 
                        reached_end = True

                await page.evaluate("window.scrollBy(0, 2500)")
                await asyncio.sleep(3)
                scroll_attempts += 1

            results.sort(key=lambda x: x['timestamp'], reverse=True)
            print(json.dumps(results, ensure_ascii=False, indent=2))

        except Exception as e:
            print(f"Severe Error: {e}", file=sys.stderr)
        finally:
            await browser.close()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(scrape_x(args.url, args.duration, args.debug))
