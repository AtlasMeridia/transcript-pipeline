"""YouTube video downloader using yt-dlp."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
            'skip_download': True,
            # Don't select formats - just get basic metadata
            # This avoids YouTube 403 errors from SABR streaming protocol
            'format': None,
            'extract_flat': 'discard_in_playlist',
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

    def download_audio(
        self,
        url: str,
        output_filename: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> tuple[str, Dict]:
        """
        Download audio from YouTube video.

        Args:
            url: YouTube video URL
            output_filename: Optional custom filename (without extension)
            metadata: Optional pre-fetched metadata to avoid redundant API call

        Returns:
            Tuple of (audio_file_path, metadata_dict)

        Raises:
            Exception: If download fails
        """
        # Use provided metadata or fetch it
        if metadata is None:
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
            logger.info(f"Downloading audio from: {metadata['title']}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Return the actual file path
            audio_file = self.output_dir / f"{output_filename}.mp3"

            if not audio_file.exists():
                raise Exception(f"Downloaded file not found: {audio_file}")

            logger.info(f"Audio downloaded successfully: {audio_file}")
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
                logger.info(f"Cleaned up audio file: {audio_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup audio file: {e}")

    def get_captions(
        self, url: str, language: str = 'en', metadata: Optional[Dict] = None
    ) -> Tuple[Optional[str], Dict]:
        """
        Extract auto-generated captions from YouTube video.

        Args:
            url: YouTube video URL
            language: Language code for captions (default: 'en')
            metadata: Optional pre-fetched metadata to avoid redundant API call

        Returns:
            Tuple of (caption_file_path or None, metadata_dict)
            Returns None for caption path if captions unavailable.

        Raises:
            Exception: If unable to extract video info
        """
        # Use provided metadata or fetch it
        if metadata is None:
            logger.info("Fetching video information...")
            metadata = self.get_video_info(url)

        from .utils import sanitize_filename
        output_filename = sanitize_filename(metadata['title'])

        # Create captions subdirectory
        captions_dir = self.output_dir / "captions"
        captions_dir.mkdir(parents=True, exist_ok=True)

        output_template = str(captions_dir / f"{output_filename}.%(ext)s")

        ydl_opts = {
            'quiet': False,  # Show progress for debugging
            'no_warnings': False,
            'skip_download': True,  # Don't download video/audio
            'writeautomaticsub': True,  # Download auto-generated subtitles
            'subtitleslangs': [language],
            'subtitlesformat': 'vtt',  # VTT format has reliable timestamps
            'outtmpl': output_template,
        }

        try:
            logger.info(f"Extracting captions ({language})...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Use process=True to actually download subtitles
                # (download=False with subtitle options still fetches subtitles)
                info = ydl.extract_info(url, download=True)

                # Check if auto captions were available
                auto_captions = info.get('automatic_captions', {})
                requested_subs = info.get('requested_subtitles', {})

                logger.info(f"Available auto-captions languages: {list(auto_captions.keys())[:5]}...")
                logger.info(f"Requested subtitles: {requested_subs}")

                if not requested_subs and language not in auto_captions:
                    logger.info(f"No auto-captions available for language: {language}")
                    return None, metadata

            # Find the downloaded caption file
            caption_file = captions_dir / f"{output_filename}.{language}.vtt"

            if caption_file.exists():
                logger.info(f"Captions downloaded: {caption_file}")
                return str(caption_file), metadata
            else:
                # Try alternate naming pattern
                for f in captions_dir.glob(f"{output_filename}*.vtt"):
                    logger.info(f"Found caption file: {f}")
                    return str(f), metadata

                logger.warning("Caption file not found after download")
                return None, metadata

        except Exception as e:
            logger.warning(f"Failed to get captions: {str(e)}")
            return None, metadata

    def cleanup_captions(self, caption_path: str) -> None:
        """
        Remove downloaded caption file.

        Args:
            caption_path: Path to caption file to delete
        """
        try:
            if os.path.exists(caption_path):
                os.remove(caption_path)
                logger.info(f"Cleaned up caption file: {caption_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup caption file: {e}")


def get_downloader(output_dir: Optional[str] = None) -> VideoDownloader:
    """
    Factory function to create a VideoDownloader.

    Args:
        output_dir: Output directory for audio files.
                   If None, uses OUTPUT_DIR from environment or './output'

    Returns:
        Configured VideoDownloader instance
    """
    if output_dir is None:
        import os
        output_dir = os.getenv('OUTPUT_DIR', './output')
        # Audio goes in a subdirectory
        output_dir = os.path.join(output_dir, 'audio')

    return VideoDownloader(output_dir=output_dir)
