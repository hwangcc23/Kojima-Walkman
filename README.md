# Kojima Walkman: Song Collection Project

## Who is Hideo Kojima?

Hideo Kojima is a world-renowned, legendary Japanese video game designer, director, producer, and writer. Widely regarded as an auteur of the medium, he is the mastermind behind the groundbreaking **Metal Gear** series, which pioneered the stealth game genre, and the innovative "strand-type" game **Death Stranding**. 

Known for his cinematic storytelling, complex narratives, and deep philosophical themes, Kojima-san continues to push the boundaries of interactive entertainment at his independent studio, **Kojima Productions**. Beyond gaming, he is a dedicated cinephile and music enthusiast, frequently sharing his refined tastes with his global audience.

## Project Purpose

As a devoted follower of Hideo Kojima (who is truly my god in the realm of creativity), I have embarked on this project to document his musical journey. Starting from **April 19, 2026**, this project aims to periodically scrape his tweets from [X.com](https://x.com/HIDEO_KOJIMA_EN) to identify and archive the songs he shares while listening to his Walkman or car audio system.

By using automated scraping and OCR (Optical Character Recognition) technology, we capture the song titles, artists, and albums directly from his shared screenshots, creating a living playlist of the music that inspires a legend.

## Kojima's Walkman Playlist

The following table lists the songs captured from Hideo Kojima's posts, sorted by date:

| Date | Song Title | Artist | Album |
| :--- | :--- | :--- | :--- |
| 2026-04-19 | Hypercharged | Electric Callboy & Brawl Stars | TANZNEID |
| 2026-04-18 | The Man Who Stole Your Soul | Midge Ure | - |
| 2026-04-16 | Bring Me The Horizon | Shadow Moses | - |
| 2026-04-15 | Ta-lila~儀を見つけて~ | ナナムジカ | - |
| 2026-04-14 | Tougher Than the Rest | Nation of Language | - |
| 2026-04-13 | Tear You Away | Terminal Serious | - |
| 2026-04-13 | Going Shopping | The Strokes | - |

---

## Technical Overview

This project utilizes a multi-stage pipeline:
1.  **Scraper**: A Playwright-based tool to fetch tweet metadata.
2.  **Downloader**: Filters "Good morning" posts and downloads high-quality screenshots.
3.  **Analyzer**: An EasyOCR-powered engine that extracts music metadata from images.

*Author: Chih-Chyuan Hwang (Assisted by Google Gemini)*  
*License: Apache 2.0*
