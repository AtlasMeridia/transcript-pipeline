"""Transcription engine supporting ElevenLabs Scribe with Whisper fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional

import whisper

from .utils import format_timestamp

try:
    from elevenlabs.client import ElevenLabs
except ImportError:  # pragma: no cover - handled at runtime when dependency missing
    ElevenLabs = None


@dataclass
class Segment:
    """Container for transcription segments."""

    start: float
    end: float
    text: str

    def as_dict(self) -> Dict[str, Any]:
        return {"start": float(self.start), "end": float(self.end), "text": self.text.strip()}


class Transcriber:
    """Transcribes audio prioritising ElevenLabs Scribe with Whisper fallback."""

    # Whisper can handle up to ~30 minutes efficiently
    MAX_CHUNK_DURATION = 30 * 60  # 30 minutes in seconds
    CHUNK_OVERLAP = 5  # 5 seconds overlap between chunks

    def __init__(
        self,
        model_name: str = "base",
        model_dir: Optional[str] = None,
        engine: str = "scribe",
        fallback_engine: str = "whisper",
        elevenlabs_api_key: Optional[str] = None,
        scribe_model_id: str = "scribe_v2",
        allow_fallback: bool = True,
    ):
        """
        Initialize the transcriber.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            model_dir: Directory to cache Whisper models
            engine: Preferred transcription engine ("scribe" or "whisper")
            fallback_engine: Secondary engine to use when primary fails
            elevenlabs_api_key: API key for ElevenLabs Scribe
            scribe_model_id: ElevenLabs Scribe model identifier
            allow_fallback: Whether to automatically fall back to the secondary engine
        """
        self.model_name = model_name
        self.model_dir = model_dir or os.path.expanduser("~/.cache/whisper")
        self.engine = engine
        self.fallback_engine = fallback_engine
        self.allow_fallback = allow_fallback
        self.elevenlabs_api_key = elevenlabs_api_key
        self.scribe_model_id = scribe_model_id

        # Set environment variable for model cache
        if model_dir:
            os.environ["WHISPER_CACHE_DIR"] = model_dir

        self._whisper_model = None
        self._scribe_client: Optional[ElevenLabs] = None

    # --------------------------------------------------------------------- Scribe
    def _ensure_scribe_client(self) -> ElevenLabs:
        if ElevenLabs is None:
            raise RuntimeError("The 'elevenlabs' package is not installed. Please install it to use Scribe.")
        if not self.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured.")
        if self._scribe_client is None:
            print("Initializing ElevenLabs Scribe client...")
            self._scribe_client = ElevenLabs(api_key=self.elevenlabs_api_key)
        return self._scribe_client

    def _coerce_response_to_dict(self, response: Any) -> Dict[str, Any]:
        if response is None:
            return {}
        if isinstance(response, dict):
            return response
        if hasattr(response, "model_dump"):
            try:  # pydantic style
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

    def _transcribe_with_scribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Segment]:
        client = self._ensure_scribe_client()
        print(f"Transcribing with ElevenLabs Scribe ({self.scribe_model_id})...")

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

        print(f"Scribe transcription complete: {len(segments)} segments")
        return segments

    # ------------------------------------------------------------------- Whisper
    def _ensure_whisper_model(self) -> None:
        if self._whisper_model is None:
            print(f"Loading Whisper model: {self.model_name}")
            self._whisper_model = whisper.load_model(self.model_name, download_root=self.model_dir)
            print("Whisper model loaded successfully")

    def _transcribe_with_whisper(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Segment]:
        self._ensure_whisper_model()
        print("Transcribing with Whisper fallback...")

        options = {"task": "transcribe", "verbose": False}
        if language:
            options["language"] = language

        result = self._whisper_model.transcribe(audio_path, **options)

        segments: List[Segment] = []
        for segment in result.get("segments", []):
            segments.append(
                Segment(
                    start=float(segment["start"]),
                    end=float(segment["end"]),
                    text=segment["text"].strip(),
                )
            )

        print(f"Whisper transcription complete: {len(segments)} segments")
        return segments

    # -------------------------------------------------------------------- Public
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
        engines_to_try: List[str] = []
        if self.engine:
            engines_to_try.append(self.engine)
        if self.allow_fallback and self.fallback_engine and self.fallback_engine not in engines_to_try:
            engines_to_try.append(self.fallback_engine)

        last_error: Optional[Exception] = None

        for idx, engine in enumerate(engines_to_try):
            try:
                if engine == "scribe":
                    segments = self._transcribe_with_scribe(audio_path, language, progress_callback)
                elif engine == "whisper":
                    segments = self._transcribe_with_whisper(audio_path, language, progress_callback)
                else:
                    raise ValueError(f"Unknown transcription engine: {engine}")

                return [segment.as_dict() for segment in segments]

            except Exception as exc:
                last_error = exc
                engine_name = engine.capitalize()
                if idx < len(engines_to_try) - 1:
                    print(f"{engine_name} transcription failed ({exc}). Trying fallback engine...")
                else:
                    print(f"{engine_name} transcription failed ({exc}). No further fallbacks configured.")

        raise Exception(f"Transcription failed: {last_error}") from last_error

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
