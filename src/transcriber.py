"""Transcription engine abstraction supporting multiple backends."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

from .utils import format_timestamp
from .config import (
    SEGMENT_GAP_THRESHOLD_SECONDS,
    CHUNK_DURATION_SECONDS,
    CHUNK_OVERLAP_SECONDS,
    MIN_AUDIO_DURATION_FOR_CHUNKING,
)
from .models import Segment

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
    ) -> List[Segment]:
        """
        Transcribe audio file with timestamps.

        Args:
            audio_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es')
            progress_callback: Optional callback(current_chunk, total_chunks)

        Returns:
            List of Segment objects with start, end, and text attributes

        Raises:
            Exception: If transcription fails
        """
        pass

    def format_transcript(self, segments: List[Segment], include_timestamps: bool = True) -> str:
        """
        Format transcript segments into readable text.

        Args:
            segments: List of Segment objects
            include_timestamps: Whether to include timestamps

        Returns:
            Formatted transcript string
        """
        lines = []

        for segment in segments:
            if include_timestamps:
                timestamp = format_timestamp(segment.start)
                lines.append(f"{timestamp} {segment.text}")
            else:
                lines.append(segment.text)

        return "\n".join(lines)

    def get_full_text(self, segments: List[Segment]) -> str:
        """
        Get plain text transcript without timestamps.

        Args:
            segments: List of Segment objects

        Returns:
            Plain text transcript
        """
        return " ".join(segment.text for segment in segments)


# =============================================================================
# Whisper Transcriber (Local)
# =============================================================================

class WhisperTranscriber(BaseTranscriber):
    """Transcribes audio using OpenAI Whisper locally.

    For long audio files (> 30 minutes), automatically splits into chunks
    with overlap to prevent memory issues and enable progress tracking.
    """

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
            self._model = whisper.load_model(self.model_name, download_root=self.model_dir)
            logger.info(f"Whisper model '{self.model_name}' loaded successfully")
        return self._model

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        import subprocess
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (subprocess.SubprocessError, ValueError) as e:
            logger.warning(f"Could not get audio duration via ffprobe: {e}")
        return 0.0

    def _extract_chunk(self, audio_path: str, start_seconds: float, duration_seconds: float, output_path: str) -> bool:
        """Extract a chunk of audio using ffmpeg."""
        import subprocess
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", str(start_seconds),
                    "-i", audio_path,
                    "-t", str(duration_seconds),
                    "-acodec", "copy",
                    output_path
                ],
                capture_output=True,
                timeout=120
            )
            return result.returncode == 0
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to extract audio chunk: {e}")
            return False

    def _transcribe_single(self, audio_path: str, language: Optional[str] = None) -> List[Segment]:
        """Transcribe a single audio file (no chunking)."""
        model = self._ensure_model()

        options = {
            "verbose": False,
            "word_timestamps": False,
        }
        if language:
            options["language"] = language

        result = model.transcribe(audio_path, **options)

        segments = []
        for seg in result.get("segments", []):
            segments.append(Segment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip()
            ))

        if not segments:
            text = result.get("text", "").strip()
            if text:
                segments.append(Segment(start=0.0, end=len(text.split()) * 0.3, text=text))

        return segments

    def _deduplicate_overlap(self, prev_segments: List[Segment], new_segments: List[Segment], overlap_start: float) -> List[Segment]:
        """
        Remove duplicate segments in the overlap region.

        When chunks overlap by 5 seconds, both chunks may transcribe the same speech.
        We keep segments from the previous chunk and discard duplicates from the new chunk.
        """
        if not prev_segments or not new_segments:
            return new_segments

        # Find the last timestamp in previous segments
        last_prev_end = max(seg.end for seg in prev_segments)

        # Keep only new segments that start after the overlap region
        # Allow a small buffer (0.5s) for timing variations
        buffer = 0.5
        filtered = []
        for seg in new_segments:
            if seg.start >= overlap_start + buffer:
                filtered.append(seg)
            elif seg.end > last_prev_end + buffer:
                # Segment spans the boundary - check for text overlap
                # Simple heuristic: if text is very similar to last prev segment, skip
                if prev_segments:
                    last_text = prev_segments[-1].text.lower().strip()
                    new_text = seg.text.lower().strip()
                    # Skip if new text starts with or is contained in last text
                    if last_text.endswith(new_text[:20]) or new_text.startswith(last_text[-20:]):
                        continue
                filtered.append(seg)

        return filtered

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Segment]:
        """
        Transcribe audio using Whisper.

        For audio longer than 30 minutes, automatically splits into chunks
        to prevent memory issues and enable progress tracking.
        """
        model = self._ensure_model()
        duration = self._get_audio_duration(audio_path)

        # If short audio or can't determine duration, transcribe directly
        if duration <= 0 or duration <= MIN_AUDIO_DURATION_FOR_CHUNKING:
            logger.info(f"Transcribing with Whisper ({self.model_name})...")
            if progress_callback:
                progress_callback(0, 1)
            segments = self._transcribe_single(audio_path, language)
            if progress_callback:
                progress_callback(1, 1)
            logger.info(f"Whisper transcription complete: {len(segments)} segments")
            return segments

        # Long audio - use chunked transcription
        logger.info(f"Long audio detected ({duration/60:.1f} min), using chunked transcription...")

        import tempfile
        import shutil

        # Calculate chunks
        chunk_duration = CHUNK_DURATION_SECONDS
        overlap = CHUNK_OVERLAP_SECONDS
        effective_duration = chunk_duration - overlap

        chunks = []
        start = 0.0
        while start < duration:
            chunk_end = min(start + chunk_duration, duration)
            chunks.append((start, chunk_end - start))
            start += effective_duration

        total_chunks = len(chunks)
        logger.info(f"Split into {total_chunks} chunks of ~{chunk_duration/60:.0f} minutes each")

        # Create temp directory for chunk files
        temp_dir = tempfile.mkdtemp(prefix="whisper_chunks_")
        all_segments: List[Segment] = []

        try:
            for i, (chunk_start, chunk_len) in enumerate(chunks):
                chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.mp3")

                logger.info(f"Processing chunk {i+1}/{total_chunks} ({chunk_start/60:.1f}-{(chunk_start+chunk_len)/60:.1f} min)...")

                if progress_callback:
                    progress_callback(i, total_chunks)

                # Extract chunk
                if not self._extract_chunk(audio_path, chunk_start, chunk_len, chunk_path):
                    logger.error(f"Failed to extract chunk {i+1}")
                    continue

                # Transcribe chunk
                chunk_segments = self._transcribe_single(chunk_path, language)

                # Adjust timestamps to original audio timeline
                for seg in chunk_segments:
                    seg.start += chunk_start
                    seg.end += chunk_start

                # Deduplicate overlap region (for all chunks after the first)
                if i > 0 and all_segments:
                    overlap_start = chunk_start
                    chunk_segments = self._deduplicate_overlap(all_segments, chunk_segments, overlap_start)

                all_segments.extend(chunk_segments)

                # Clean up chunk file immediately to save disk space
                try:
                    os.remove(chunk_path)
                except OSError:
                    pass

            if progress_callback:
                progress_callback(total_chunks, total_chunks)

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except OSError as e:
                logger.warning(f"Failed to clean up temp directory: {e}")

        logger.info(f"Chunked Whisper transcription complete: {len(all_segments)} segments")
        return all_segments


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
            if last_end is not None and start - last_end > SEGMENT_GAP_THRESHOLD_SECONDS:
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
    ) -> List[Segment]:
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
        return segments


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
        TRANSCRIPTION_ENGINE: 'whisper', 'elevenlabs', or 'scribe' (default: 'whisper')
        WHISPER_MODEL: Model name for Whisper (default: 'large-v3')
        WHISPER_MODEL_DIR: Directory for model cache
        ELEVENLABS_API_KEY: API key for ElevenLabs
        SCRIBE_MODEL_ID: Model ID for ElevenLabs Scribe
    """
    if engine is None:
        engine = os.getenv("TRANSCRIPTION_ENGINE", "whisper").lower()

    logger.info(f"Initializing transcription engine: {engine}")

    if engine in ("elevenlabs", "scribe"):
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
