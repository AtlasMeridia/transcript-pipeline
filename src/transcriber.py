"""Transcription engine abstraction for Apple Silicon.

Supports two backends:
- CaptionTranscriber: Extract YouTube auto-captions (fastest, no audio processing)
- MLXWhisperTranscriber: Local transcription using MLX-optimized Whisper (Apple Silicon)
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from .utils import format_timestamp
from .config import SEGMENT_GAP_THRESHOLD_SECONDS
from .models import Segment

logger = logging.getLogger(__name__)


# =============================================================================
# Base Transcriber Interface
# =============================================================================

class BaseTranscriber(ABC):
    """Abstract base class for transcription engines."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the name of this transcription engine."""
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs,
    ) -> List[Segment]:
        """
        Transcribe audio file with timestamps.

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            progress_callback: Optional callback(current, total)

        Returns:
            List of Segment objects with start, end, and text attributes
        """
        pass

    def format_transcript(
        self, segments: List[Segment], include_timestamps: bool = True
    ) -> str:
        """Format transcript segments into readable text."""
        lines = []
        for segment in segments:
            if include_timestamps:
                timestamp = format_timestamp(segment.start)
                lines.append(f"{timestamp} {segment.text}")
            else:
                lines.append(segment.text)
        return "\n".join(lines)

    def get_full_text(self, segments: List[Segment]) -> str:
        """Get plain text transcript without timestamps."""
        return " ".join(segment.text for segment in segments)


# =============================================================================
# MLX Whisper Transcriber (Apple Silicon)
# =============================================================================

class MLXWhisperTranscriber(BaseTranscriber):
    """Transcribes audio using MLX-optimized Whisper on Apple Silicon.
    
    Requires: pip install mlx-whisper
    
    This implementation is significantly faster than the standard OpenAI Whisper
    on Apple Silicon Macs, leveraging the Metal GPU acceleration through MLX.
    """

    # Available models from mlx-community on Hugging Face
    # Note: MLX Whisper models use different naming conventions:
    # - Older models: whisper-{size}-mlx (e.g., whisper-small-mlx)
    # - Newer models: whisper-{size}-fp16 (e.g., whisper-small-fp16)
    # - Large models: whisper-large-v3-mlx or whisper-large-v3-turbo
    MODELS = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "distil-large-v3": "mlx-community/distil-whisper-large-v3",
    }

    def __init__(
        self,
        model: str = "large-v3-turbo",
    ):
        """
        Initialize the MLX Whisper transcriber.

        Args:
            model: Model name or HuggingFace repo path. 
                   Shortcuts: tiny, base, small, medium, large, large-v3, 
                   large-v3-turbo (recommended), distil-large-v3
        """
        # Resolve model shortcut to full HF path
        if model in self.MODELS:
            self.model_path = self.MODELS[model]
        else:
            # Assume it's a full HF path
            self.model_path = model
        
        self.model_name = model
        self._mlx_whisper = None

    def _ensure_mlx_whisper(self):
        """Lazy import mlx_whisper to avoid import errors if not installed."""
        if self._mlx_whisper is None:
            try:
                import mlx_whisper
                self._mlx_whisper = mlx_whisper
            except ImportError:
                raise RuntimeError(
                    "mlx-whisper is not installed. "
                    "Install it with: pip install mlx-whisper"
                )
        return self._mlx_whisper

    @property
    def engine_name(self) -> str:
        return f"mlx-whisper ({self.model_name})"

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs,
    ) -> List[Segment]:
        """
        Transcribe audio using MLX Whisper.

        MLX handles long audio natively - no chunking required.
        """
        mlx_whisper = self._ensure_mlx_whisper()

        logger.info(f"Transcribing with {self.engine_name}...")
        
        if progress_callback:
            progress_callback(0, 1)

        # Build options
        options = {"path_or_hf_repo": self.model_path}
        if language:
            options["language"] = language

        # Transcribe
        result = mlx_whisper.transcribe(audio_path, **options)

        # Convert to Segment objects
        segments = []
        for seg in result.get("segments", []):
            segments.append(
                Segment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                )
            )

        # Fallback if no segments but we have text
        if not segments:
            text = result.get("text", "").strip()
            if text:
                segments.append(
                    Segment(start=0.0, end=len(text.split()) * 0.3, text=text)
                )

        if progress_callback:
            progress_callback(1, 1)

        logger.info(f"MLX Whisper transcription complete: {len(segments)} segments")
        return segments


# =============================================================================
# Caption Transcriber (YouTube Auto-Captions)
# =============================================================================

class CaptionsUnavailableError(Exception):
    """Raised when YouTube captions are not available for a video."""
    pass


class CaptionTranscriber(BaseTranscriber):
    """Transcribes using YouTube auto-generated captions.

    This is the fastest option when available - no audio processing required.
    Falls back gracefully when captions aren't available.
    """

    def __init__(
        self,
        output_dir: str = "./output",
        language: str = "en",
    ):
        """
        Initialize the caption transcriber.

        Args:
            output_dir: Directory for temporary caption files
            language: Language code for captions (default: 'en')
        """
        self.output_dir = output_dir
        self.language = language

    @property
    def engine_name(self) -> str:
        return "captions"

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs,
    ) -> List[Segment]:
        """
        Extract captions from YouTube video.

        Note: Requires 'url' in kwargs since this doesn't process audio.
        The audio_path parameter is ignored.

        Raises:
            CaptionsUnavailableError: If captions are not available
            ValueError: If 'url' is not provided
        """
        url = kwargs.get("url")
        if not url:
            raise ValueError("CaptionTranscriber requires 'url' parameter in kwargs")

        lang = language or self.language

        # Import here to avoid circular imports
        from .downloader import VideoDownloader
        from .caption_parser import parse_vtt

        logger.info(f"Fetching YouTube captions for: {url}")

        if progress_callback:
            progress_callback(0, 2)

        # Download captions
        downloader = VideoDownloader(output_dir=self.output_dir)
        caption_path, metadata = downloader.get_captions(url, language=lang)

        if caption_path is None:
            raise CaptionsUnavailableError(
                f"No auto-captions available for language '{lang}'"
            )

        if progress_callback:
            progress_callback(1, 2)

        try:
            # Parse VTT file into segments
            segments = parse_vtt(caption_path)

            if not segments:
                raise CaptionsUnavailableError("Captions file was empty or unparseable")

            logger.info(f"Caption extraction complete: {len(segments)} segments")

            if progress_callback:
                progress_callback(2, 2)

            return segments

        finally:
            # Clean up caption file
            downloader.cleanup_captions(caption_path)


# =============================================================================
# Factory Function
# =============================================================================

def get_transcriber(
    engine: Optional[str] = None,
    **kwargs,
) -> BaseTranscriber:
    """
    Factory function to get the appropriate transcriber.

    Args:
        engine: Engine selection ('mlx-whisper', 'captions', or 'auto')
        **kwargs: Additional arguments passed to the transcriber
            - model: MLX Whisper model name (default: 'large-v3-turbo')
            - output_dir: Directory for output files (used by captions)
            - language: Language code for captions (default: 'en')

    Returns:
        Configured transcriber instance

    Environment Variables:
        TRANSCRIPTION_ENGINE: 'mlx-whisper', 'captions', or 'auto'
        MLX_WHISPER_MODEL: Model name (default: 'large-v3-turbo')
        CAPTION_LANGUAGE: Language for YouTube captions (default: 'en')
    """
    if engine is None:
        engine = os.getenv("TRANSCRIPTION_ENGINE", "auto").lower()

    logger.info(f"Initializing transcription engine: {engine}")

    if engine == "captions":
        output_dir = kwargs.pop("output_dir", None) or os.getenv(
            "OUTPUT_DIR", "./output"
        )
        language = kwargs.pop("language", None) or os.getenv("CAPTION_LANGUAGE", "en")
        return CaptionTranscriber(
            output_dir=output_dir,
            language=language,
        )

    elif engine in ("mlx-whisper", "mlx", "whisper"):
        model = kwargs.pop("model", None) or kwargs.pop("model_name", None) or os.getenv(
            "MLX_WHISPER_MODEL", "large-v3-turbo"
        )
        return MLXWhisperTranscriber(model=model)

    else:
        # 'auto' or unknown - default to MLX Whisper
        # The server.py handles trying captions first in 'auto' mode
        model = kwargs.pop("model", None) or kwargs.pop("model_name", None) or os.getenv(
            "MLX_WHISPER_MODEL", "large-v3-turbo"
        )
        return MLXWhisperTranscriber(model=model)


# =============================================================================
# Legacy Compatibility
# =============================================================================

# Aliases for backward compatibility
WhisperTranscriber = MLXWhisperTranscriber
Transcriber = MLXWhisperTranscriber
