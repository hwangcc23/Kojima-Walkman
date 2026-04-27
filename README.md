# Kojima Walkman: Song Collection Project

## Who is Hideo Kojima?

Hideo Kojima is a world-renowned, legendary Japanese video game designer, director, producer, and writer. Widely regarded as an auteur of the medium, he is the mastermind behind the groundbreaking **Metal Gear** series, which pioneered the stealth game genre, and the innovative "strand-type" game **Death Stranding**. 

Known for his cinematic storytelling, complex narratives, and deep philosophical themes, Kojima-san continues to push the boundaries of interactive entertainment at his independent studio, **Kojima Productions**. Beyond gaming, he is a dedicated cinephile and music enthusiast, frequently sharing his refined tastes with his global audience.

## Project Purpose

As a devoted follower of Hideo Kojima (who is truly my god in the realm of creativity), I have embarked on this project to document his musical journey. Starting from **April 19, 2026**, this project aims to periodically scrape his tweets from [X.com](https://x.com/HIDEO_KOJIMA_EN) to identify and archive the songs he shares while listening to his Walkman or car audio system.

By using automated scraping and OCR (Optical Character Recognition) technology, we capture the song titles, artists, and albums directly from his shared screenshots, creating a living playlist of the music that inspires a legend.

## Kojima's Walkman Playlist

The following table lists the songs captured from Hideo Kojima's posts, sorted by date. This playlist is updated periodically to reflect his latest recommendations shared on X.com.

| Date | Song Title | Artist | Album | Tweet URL |
| :--- | :--- | :--- | :--- | :--- |
| 2026-04-27 | Spike Island | Pulp | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2048575333251817864) |
| 2026-04-26 | Atmosphere | The Leaving | Ultimate buzz | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2048333550169252221) |
| 2026-04-25 | Cryogen | Muse | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2047888093815193929) |
| 2026-04-24 | Free to Love (feat. Nile Rodgers) | Duran Duran | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2047487052913209453) |
| 2026-04-22 | Looking For Fun | Hard-Fi | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2046647327885246675) |
| 2026-04-20 | First Light | Lana Del Rey | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2046005537888936150) |
| 2026-04-19 | Hypercharged | Electric Callboy & Brawl Stars | TANZNEID | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2045684713545969881) |
| 2026-04-18 | The Man Who Stole Your Soul | Midge Ure | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2045352475398726045) |
| 2026-04-17 | Shadow Moses | Bring Me The Horizon | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2044920652340273208) |
| 2026-04-16 | Ta-lila~儀を見つけて~ | ナナムジカ | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2044558288470298734) |
| 2026-04-15 | Tougher Than the Rest | Nation of Language | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2044196626127040567) |
| 2026-04-14 | Tear You Away | Terminal Serious | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2043838213631160487) |
| 2026-04-13 | Going Shopping | The Strokes | - | [Link](https://x.com/HIDEO_KOJIMA_EN/status/2043479719287624081) |

---

## Technical Overview

This project utilizes a multi-stage pipeline:
1.  **Scraper**: A Playwright-based tool to fetch tweet metadata.
2.  **Downloader**: Filters "Good morning" posts and downloads high-quality screenshots.
3.  **Analyzer**: An EasyOCR-powered engine that extracts music metadata from images.

## Usage

You can execute the entire pipeline using the provided shell script or run each component individually.

### Prerequisites
- Install dependencies: `pip install -r requirements.txt`
- Setup `auth_state.json` (see `python3 x-scrapper.py --help` for details)

### Option 1: One-Click Execution (Recommended)
Use the master script to run all three steps automatically:
```bash
# Scrape and analyze the last 24 hours
./kojima-walkman-scrapper.sh

# Scrape and analyze the last 10 days (240 hours)
./kojima-walkman-scrapper.sh 240
```

### Option 2: Step-by-Step Execution
If you need more control, you can chain the commands manually:
```bash
# 1. Scrape posts to JSON
python3 x-scrapper.py https://x.com/HIDEO_KOJIMA_EN -d 24 > output.json

# 2. Filter and Download images based on keywords
cat output.json | ./venv/bin/python3 kojima-walkman-image-downloader.py > downloads.json

# 3. Analyze images via OCR to extract song info
cat downloads.json | ./venv/bin/python3 kojima-walkman-music-analyzer.py > results.json
```

---

*Author: Chih-Chyuan Hwang (Assisted by Google Gemini)*  
*License: Apache 2.0*
