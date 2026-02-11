"""
Podcast / YouTube transcript scraper.

Works for: Financially Incorrect Podcast, Lynn Ngugi Talks.

Strategy:
1. List videos from YouTube channel via yt-dlp
2. Extract transcripts via youtube-transcript-api
3. Fall back to auto-generated captions
4. Save transcripts as text files for processing

Dependencies:
    pip install youtube-transcript-api yt-dlp
"""

import json
import subprocess
import re
from pathlib import Path
from typing import List, Optional

from src.scrapers.base import BaseScraper, DiscoveredDocument, ScrapedDocument
from src.utils.file_utils import write_text, safe_filename
from src.utils.logging_config import get_logger

logger = get_logger("scraper.podcast")


class PodcastScraper(BaseScraper):
    """
    Scraper for YouTube channels — extracts video transcripts.

    Uses yt-dlp for video discovery and youtube-transcript-api
    for transcript extraction.
    """

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []

        for seed_url in self.config.seed_urls:
            if "youtube.com" in seed_url:
                docs = self._discover_youtube_videos(seed_url)
                all_docs.extend(docs)

        max_videos = self.settings.youtube_max_videos
        self.logger.info(
            f"{self.config.name}: discovered {len(all_docs)} videos "
            f"(cap: {max_videos})",
            extra={"source_id": self.config.source_id},
        )
        return all_docs[:max_videos]

    def _discover_youtube_videos(self, channel_url: str) -> List[DiscoveredDocument]:
        """Get video list from a YouTube channel using yt-dlp."""
        docs = []

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--flat-playlist",
                    "--dump-json",
                    "--no-warnings",
                    f"{channel_url}/videos",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                self.logger.warning(
                    f"yt-dlp failed for {channel_url}: {result.stderr[:200]}",
                    extra={"source_id": self.config.source_id},
                )
                return docs

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    video = json.loads(line)
                    video_id = video.get("id", "")
                    title = video.get("title", "Untitled")
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

                    docs.append(DiscoveredDocument(
                        url=video_url,
                        title=title,
                        source_page=channel_url,
                        doc_type="html",  # Will be overridden to transcript
                        category="podcast_episode",
                    ))
                except json.JSONDecodeError:
                    continue

        except FileNotFoundError:
            self.logger.warning(
                "yt-dlp not found. Install: pip install yt-dlp",
                extra={"source_id": self.config.source_id},
            )
        except subprocess.TimeoutExpired:
            self.logger.warning("yt-dlp timed out")

        return docs

    def run(self) -> List[ScrapedDocument]:
        """
        Override run() to handle transcript extraction.

        Instead of downloading files, we extract transcripts directly.
        """
        self.logger.info(
            f"Starting podcast scraper for {self.config.name}",
            extra={"source_id": self.config.source_id},
        )

        discovered = self.discover_documents()
        scraped = []
        raw_dir = self.settings.source_raw_dir(self.config.source_id)

        for i, doc in enumerate(discovered):
            video_id = self._extract_video_id(doc.url)
            if not video_id:
                continue

            transcript = self._get_transcript(video_id)
            if not transcript or len(transcript) < 100:
                self.logger.debug(f"No transcript for {doc.title}")
                continue

            # Save transcript as text file
            filename = safe_filename(f"{self.config.source_id}_{i:04d}_{video_id}")
            text_path = raw_dir / f"{filename}.txt"
            write_text(transcript, text_path)

            scraped.append(ScrapedDocument(
                doc_id=f"{self.config.source_id}_{i:04d}",
                source_id=self.config.source_id,
                source_name=self.config.name,
                title=doc.title,
                url=doc.url,
                source_page=doc.source_page,
                doc_type="html",  # Text content, processed like HTML
                category="podcast_episode",
                raw_file=str(text_path),
                word_count=len(transcript.split()),
                char_count=len(transcript),
                scraped_at=str(Path(text_path).stat().st_mtime)
                if text_path.exists() else "",
            ))

        self.logger.info(
            f"{self.config.name}: scraped {len(scraped)} transcripts",
            extra={"source_id": self.config.source_id},
        )

        self._save_scrape_manifest(scraped)
        return scraped

    def _get_transcript(self, video_id: str) -> Optional[str]:
        """Extract transcript from YouTube video."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join(entry["text"] for entry in transcript_list)
        except ImportError:
            self.logger.warning(
                "youtube-transcript-api not installed. "
                "Run: pip install youtube-transcript-api"
            )
            return None
        except Exception as e:
            self.logger.debug(f"Transcript unavailable for {video_id}: {e}")
            return None

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", url)
        return match.group(1) if match else None
