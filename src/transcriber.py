"""Transcription engine abstraction supporting multiple backends."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

from .utils import format_timestamp

logger = logging.getLogger(__name__)

# Optional imports for backends
try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None

try:
    import whisper
except ImportError:
    whisper = None


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Segment:
    """Container for transcription segments."""

    start: float
    end: float
    text: str

    def as_dict(self) -> Dict[str, Any]:
        return {"start": float(self.start), "end": float(self.end), "text": self.text.strip()}


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
    ) -> List[Dict]:
        """
        Transcribe audio file with timestamps.

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            progress_callback: Optional callback(current_chunk, total_chunks)

        Returns:
            List of segment dictionaries with 'start', 'end', and 'text' keys

        Raises:
            Exception: If transcription fails
        """
        pass

    def format_transcript(self, segments: List[Dict], include_timestamps: bool = True) -> str:
        """
        Format transcript segments into readable text.

        Args:
            segments: List of segment dictionaries
            include_timestamps: Whether to include timestamps

        Returns:
            Formatted transcript string
        """
        lines = []

        for segment in segments:
            if include_timestamps:
                timestamp = format_timestamp(segment["start"])
                lines.append(f"{timestamp} {segment['text']}")
            else:
                lines.append(segment["text"])

        return "\n".join(lines)

    def get_full_text(self, segments: List[Dict]) -> str:
        """
        Get plain text transcript without timestamps.

        Args:
            segments: List of segment dictionaries

        Returns:
            Plain text transcript
        """
        return " ".join(segment["text"] for segment in segments)


# =============================================================================
# Whisper Transcriber (Local)
# =============================================================================

class WhisperTranscriber(BaseTranscriber):
    """Transcribes audio using OpenAI Whisper locally."""

    def __init__(
        self,
        model_name: str = "large-v3",
        model_dir: Optional[str] = None,
    ):
        """
        Initialize the Whisper transcriber.

        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large, large-v2, large-v3)
            model_dir: Directory to store model files (persistent cache)
        """
        if whisper is None:
            raise RuntimeError(
                "The 'openai-whisper' package is not installed. "
                "Install it with: pip install openai-whisper"
            )

        self.model_name = model_name
        self.model_dir = model_dir or os.getenv("WHISPER_MODEL_DIR", os.path.expanduser("~/.cache/whisper"))
        self._model = None

    @property
    def engine_name(self) -> str:
        return "whisper"

    def _ensure_model(self):
        """Load the Whisper model, downloading if necessary."""
        if self._model is None:
            logger.info(f"Loading Whisper model '{self.model_name}' from {self.model_dir}...")
            # Set download root for model persistence
            self._model = whisper.load_model(self.model_name, download_root=self.model_dir)
            logger.info(f"Whisper model '{self.model_name}' loaded successfully")
        return self._model

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict]:
        """Transcribe audio using Whisper."""
        model = self._ensure_model()
        logger.info(f"Transcribing with Whisper ({self.model_name})...")

        # Whisper transcription options
        options = {
            "verbose": False,
            "word_timestamps": False,
        }
        if language:
            options["language"] = language

        result = model.transcribe(audio_path, **options)

        # Convert Whisper segments to our format
        segments = []
        for seg in result.get("segments", []):
            segments.append(Segment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip()
            ))

        if not segments:
            # Fall back to full text if no segments
            text = result.get("text", "").strip()
            if text:
                segments.append(Segment(start=0.0, end=len(text.split()) * 0.3, text=text))

        logger.info(f"Whisper transcription complete: {len(segments)} segments")
        return [seg.as_dict() for seg in segments]


# =============================================================================
# ElevenLabs Transcriber (Cloud)
# =============================================================================

class ElevenLabsTranscriber(BaseTranscriber):
    """Transcribes audio using ElevenLabs Scribe API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        scribe_model_id: str = "scribe_v2",
    ):
        """
        Initialize the ElevenLabs transcriber.

        Args:
            api_key: ElevenLabs API key (defaults to ELEVENLABS_API_KEY env var)
            scribe_model_id: ElevenLabs Scribe model identifier
        """
        if ElevenLabs is None:
            raise RuntimeError(
                "The 'elevenlabs' package is not installed. "
                "Install it with: pip install elevenlabs"
            )

        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.scribe_model_id = scribe_model_id
        self._client: Optional[ElevenLabs] = None

    @property
    def engine_name(self) -> str:
        return "elevenlabs"

    def _ensure_client(self) -> ElevenLabs:
        """Initialize the ElevenLabs client."""
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured.")
        if self._client is None:
            logger.info("Initializing ElevenLabs Scribe client...")
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def _coerce_response_to_dict(self, response: Any) -> Dict[str, Any]:
        """Convert various response types to dictionary."""
        if response is None:
            return {}
        if isinstance(response, dict):
            return response
        if hasattr(response, "model_dump"):
            try:
                return response.model_dump()
            except Exception:
                pass
        if hasattr(response, "model_dump_json"):
            try:
                return json.loads(response.model_dump_json())
            except Exception:
                pass
        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"text": response}
        return {"raw": response}

    def _build_segments_from_words(self, words: List[Dict[str, Any]]) -> List[Segment]:
        """Build segments from word-level timestamps."""
        segments: List[Segment] = []
        if not words:
            return segments

        current_words: List[str] = []
        segment_start: Optional[float] = None
        last_end: Optional[float] = None

        def finalize_segment():
            nonlocal current_words, segment_start, last_end
            if current_words and segment_start is not None and last_end is not None:
                text = " ".join(current_words).strip()
                if text:
                    segments.append(Segment(start=segment_start, end=last_end, text=text))
            current_words = []
            segment_start = None
            last_end = None

        for word in words:
            text = word.get("word") or word.get("text") or ""
            if not text:
                continue

            start = (
                word.get("start")
                or word.get("start_timestamp")
                or word.get("timestamp")
                or word.get("offset")
                or 0.0
            )
            end = (
                word.get("end")
                or word.get("end_timestamp")
                or word.get("timestamp_end")
                or word.get("offset_end")
                or start
            )

            start = float(start)
            end = float(end)

            if segment_start is None:
                segment_start = start

            # Create a new segment if there is a large gap or punctuation
            if last_end is not None and start - last_end > 1.2:
                finalize_segment()
                segment_start = start

            current_words.append(text)
            last_end = max(end, start)

            if text.endswith((".", "!", "?", ";")):
                finalize_segment()

        finalize_segment()
        return segments

    def _extract_segments_from_container(self, container: Dict[str, Any]) -> List[Segment]:
        """Extract segments from API response container."""
        if not container:
            return []

        possible_keys = [
            "segments",
            "paragraphs",
            "chunks",
            "utterances",
            "items",
            "results",
        ]
        for key in possible_keys:
            value = container.get(key)
            if isinstance(value, list):
                segments: List[Segment] = []
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text") or item.get("transcript")
                    if not text:
                        continue
                    start = float(item.get("start") or item.get("start_timestamp") or item.get("timestamp") or 0.0)
                    end = float(item.get("end") or item.get("end_timestamp") or start)
                    segments.append(Segment(start=start, end=end, text=text))
                if segments:
                    return segments

        # Fall back to words
        words = container.get("words") or container.get("word_timestamps")
        if isinstance(words, list):
            return self._build_segments_from_words(words)

        # Single text blob
        text = container.get("text") or container.get("transcript")
        if isinstance(text, str) and text.strip():
            return [Segment(start=0.0, end=max(0.1, len(text.split()) * 0.3), text=text.strip())]

        return []

    def _parse_scribe_response(self, response: Any) -> List[Segment]:
        """Parse the Scribe API response into segments."""
        data = self._coerce_response_to_dict(response)
        if not data:
            return []

        containers = [data]
        for key in ("output", "transcript", "result", "results", "data"):
            value = data.get(key)
            if isinstance(value, dict):
                containers.append(value)

        for container in containers:
            segments = self._extract_segments_from_container(container)
            if segments:
                return segments

        return []

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict]:
        """Transcribe audio using ElevenLabs Scribe."""
        client = self._ensure_client()
        logger.info(f"Transcribing with ElevenLabs Scribe ({self.scribe_model_id})...")

        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        buffer = BytesIO(audio_bytes)
        buffer.name = os.path.basename(audio_path)

        options: Dict[str, Any] = {"model_id": self.scribe_model_id}
        if language:
            options["language_code"] = language

        response = client.speech_to_text.convert(file=buffer, **options)

        segments = self._parse_scribe_response(response)
        if not segments:
            raise RuntimeError("ElevenLabs Scribe returned no transcript segments.")

        logger.info(f"Scribe transcription complete: {len(segments)} segments")
        return [seg.as_dict() for seg in segments]


# =============================================================================
# Factory Function
# =============================================================================

def get_transcriber(
    engine: Optional[str] = None,
    **kwargs,
) -> BaseTranscriber:
    """
    Factory function to get the appropriate transcriber based on configuration.

    Args:
        engine: Override engine selection ('whisper' or 'elevenlabs')
        **kwargs: Additional arguments passed to the transcriber constructor

    Returns:
        Configured transcriber instance

    Environment Variables:
        TRANSCRIPTION_ENGINE: 'whisper' or 'elevenlabs' (default: 'whisper')
        WHISPER_MODEL: Model name for Whisper (default: 'large-v3')
        WHISPER_MODEL_DIR: Directory for model cache
        ELEVENLABS_API_KEY: API key for ElevenLabs
        SCRIBE_MODEL_ID: Model ID for ElevenLabs Scribe
    """
    if engine is None:
        engine = os.getenv("TRANSCRIPTION_ENGINE", "whisper").lower()

    logger.info(f"Initializing transcription engine: {engine}")

    if engine == "elevenlabs":
        api_key = kwargs.pop("api_key", None) or kwargs.pop("elevenlabs_api_key", None)
        scribe_model_id = kwargs.pop("scribe_model_id", None) or os.getenv("SCRIBE_MODEL_ID", "scribe_v2")
        return ElevenLabsTranscriber(
            api_key=api_key,
            scribe_model_id=scribe_model_id,
        )
    else:  # Default to whisper
        model_name = kwargs.pop("model_name", None) or os.getenv("WHISPER_MODEL", "large-v3")
        model_dir = kwargs.pop("model_dir", None) or os.getenv("WHISPER_MODEL_DIR")
        return WhisperTranscriber(
            model_name=model_name,
            model_dir=model_dir,
        )


# =============================================================================
# Legacy Compatibility
# =============================================================================

# Alias for backward compatibility
Transcriber = ElevenLabsTranscriber
