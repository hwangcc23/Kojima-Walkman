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
        print("Please ensure you have generated auth_state.json with a valid auth_token.", file=sys.stderr)
        return

    username = extract_username(url)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=duration_hours)
    
    results = []
    seen_tweet_ids = set()
    scraped_count = 0

    async with async_playwright() as p:
        # Launching browser
        browser = await p.chromium.launch(headless=True)
        
        # Load the session state (cookies)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            storage_state="auth_state.json"
        )
        page = await context.new_page()

        log(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Allow some time for the page to render and session to be validated
            await asyncio.sleep(5)
            
            # Check if we were redirected to login (meaning token expired)
            if "i/flow/login" in page.url:
                print("Severe Error: Session expired. Please update 'auth_token' in auth_state.json.", file=sys.stderr)
                await browser.close()
                return

            try:
                # Wait for the main tweet container
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            except:
                print(f"Severe Error: Timeout waiting for tweets on {url}. The account might be private or blocked.", file=sys.stderr)
                await page.screenshot(path="error_page.png")
                await browser.close()
                return

            reached_end = False
            scroll_attempts = 0
            max_scroll_attempts = 30 

            while not reached_end and scroll_attempts < max_scroll_attempts:
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                
                for tweet in tweets:
                    # Extract Post Link
                    link_element = await tweet.query_selector('a[href*="/status/"]')
                    if not link_element: continue
                    
                    tweet_path = await link_element.get_attribute("href")
                    tweet_url = f"https://x.com{tweet_path}"
                    tweet_id = tweet_path.split("/")[-1]
                    
                    if tweet_id in seen_tweet_ids: continue
                    
                    # Extract Timestamp
                    time_element = await tweet.query_selector('time')
                    if not time_element: continue
                        
                    time_str = await time_element.get_attribute("datetime")
                    tweet_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    
                    # Check Time Constraint
                    if tweet_time < cutoff_time:
                        # Skip older tweets but keep scrolling as pinned tweets might be older
                        continue

                    # Check if it's a Retweet (Handle comparison)
                    # The author's handle is usually in a span starting with '@' inside 'User-Name'
                    author_element = await tweet.query_selector('div[data-testid="User-Name"] span:has-text("@")')
                    author_handle = ""
                    if author_element:
                        author_handle = await author_element.inner_text()
                        author_handle = author_handle.strip().lstrip('@').lower()
                    
                    # If the author in the tweet is NOT the person we are scraping, it's a retweet
                    is_retweet = (author_handle != username.lower()) if author_handle else False
                    
                    # Double check: sometimes pinned or specific retweets have socialContext
                    if not is_retweet:
                        retweet_indicator = await tweet.query_selector('div[data-testid="socialContext"]')
                        if retweet_indicator:
                            indicator_text = await retweet_indicator.inner_text()
                            # Standard English "Retweeted" or other language indicators usually share this structure
                            if indicator_text:
                                is_retweet = True

                    # Extract Content
                    text_element = await tweet.query_selector('div[data-testid="tweetText"]')
                    text = await text_element.inner_text() if text_element else ""
                    
                    # Extract Images
                    images = []
                    img_elements = await tweet.query_selector_all('div[data-testid="tweetPhoto"] img')
                    for img in img_elements:
                        src = await img.get_attribute("src")
                        if src: images.append(src)
                    
                    # Extract Videos
                    videos = []
                    video_elements = await tweet.query_selector_all('div[data-testid="videoPlayer"] video')
                    for v in video_elements:
                        v_src = await v.get_attribute("src")
                        if v_src: videos.append(v_src)
                    
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
                    tweet_word = "tweet" if scraped_count == 1 else "tweets"
                    log(f"scrapping {scraped_count} {tweet_word}")

                # Scroll to load more
                await page.evaluate("window.scrollBy(0, 2000)")
                await asyncio.sleep(3)
                scroll_attempts += 1
                
                # Check if we should stop scrolling
                if tweets:
                    last_tweet_time_element = await tweets[-1].query_selector('time')
                    if last_tweet_time_element:
                        last_time_str = await last_tweet_time_element.get_attribute("datetime")
                        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
                        if last_time < cutoff_time:
                            # Reached tweets older than duration
                            reached_end = True

            # Output results
            results.sort(key=lambda x: x['timestamp'], reverse=True)
            print(json.dumps(results, ensure_ascii=False, indent=2))

        except Exception as e:
            print(f"Severe Error: {e}", file=sys.stderr)
        finally:
            await browser.close()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(scrape_x(args.url, args.duration, args.debug))
