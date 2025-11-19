"""YouTube video downloader using yt-dlp."""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

import yt_dlp

logger = logging.getLogger(__name__)


class VideoDownloader:
    """Downloads YouTube videos and extracts metadata."""

    def __init__(self, output_dir: str = "./output"):
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded audio files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url: str) -> Dict:
        """
        Extract video metadata without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary containing video metadata

        Raises:
            Exception: If unable to extract video info
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    'title': info.get('title', 'Unknown'),
                    'author': info.get('uploader', 'Unknown'),
                    'channel': info.get('channel', 'Unknown'),
                    'upload_date': info.get('upload_date', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'description': info.get('description', ''),
                    'url': url,
                    'id': info.get('id', 'unknown'),
                }
        except Exception as e:
            raise Exception(f"Failed to extract video info: {str(e)}")

    def download_audio(self, url: str, output_filename: Optional[str] = None) -> tuple[str, Dict]:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube video URL
            output_filename: Optional custom filename (without extension)

        Returns:
            Tuple of (audio_file_path, metadata_dict)

        Raises:
            Exception: If download fails
        """
        # First get metadata
        logger.info("Fetching video information...")
        metadata = self.get_video_info(url)

        # Determine output filename
        if output_filename is None:
            from .utils import sanitize_filename
            output_filename = sanitize_filename(metadata['title'])

        output_path = self.output_dir / f"{output_filename}.%(ext)s"

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(output_path),
            'quiet': False,
            'no_warnings': False,
        }

        try:
            logger.info("Downloading audio from: %s", metadata["title"])
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Return the actual file path
            audio_file = self.output_dir / f"{output_filename}.mp3"

            if not audio_file.exists():
                raise Exception(f"Downloaded file not found: {audio_file}")

            logger.info("Audio downloaded successfully: %s", audio_file)
            return str(audio_file), metadata

        except Exception as e:
            raise Exception(f"Failed to download audio: {str(e)}")

    def cleanup_audio(self, audio_path: str) -> None:
        """
        Remove downloaded audio file.

        Args:
            audio_path: Path to audio file to delete
        """
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info("Cleaned up audio file: %s", audio_path)
        except Exception as e:
            logger.warning("Failed to cleanup audio file: %s", e)
