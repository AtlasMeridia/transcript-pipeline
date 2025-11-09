"""Transcription engine using OpenAI Whisper."""

import os
from typing import Optional, Callable, List, Dict
import whisper
from .utils import format_timestamp


class Transcriber:
    """Transcribes audio using OpenAI Whisper model."""

    # Whisper can handle up to ~30 minutes efficiently
    MAX_CHUNK_DURATION = 30 * 60  # 30 minutes in seconds
    CHUNK_OVERLAP = 5  # 5 seconds overlap between chunks

    def __init__(self, model_name: str = "base", model_dir: Optional[str] = None):
        """
        Initialize the transcriber.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large)
            model_dir: Directory to cache Whisper models
        """
        self.model_name = model_name
        self.model_dir = model_dir or os.path.expanduser("~/.cache/whisper")

        # Set environment variable for model cache
        if model_dir:
            os.environ["WHISPER_CACHE_DIR"] = model_dir

        self.model = None

    def load_model(self) -> None:
        """Load the Whisper model."""
        if self.model is None:
            print(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name, download_root=self.model_dir)
            print("Model loaded successfully")

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
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
        self.load_model()

        try:
            print(f"Transcribing audio: {audio_path}")

            # Transcribe with timestamps
            options = {
                "task": "transcribe",
                "verbose": False,
            }

            if language:
                options["language"] = language

            result = self.model.transcribe(audio_path, **options)

            # Extract segments with timestamps
            segments = []
            for segment in result.get("segments", []):
                segments.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })

            print(f"Transcription complete: {len(segments)} segments")
            return segments

        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")

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
                lines.append(segment['text'])

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
