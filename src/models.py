"""Shared data models for transcript pipeline.

This module provides typed data classes used throughout the pipeline
to ensure consistent data structures between components.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Segment:
    """A single transcription segment with timing information.

    Represents a portion of transcribed audio with start/end timestamps.
    Used by all transcription engines to provide a consistent output format.
    """

    start: float
    end: float
    text: str

    def as_dict(self) -> Dict[str, Any]:
        """Convert segment to dictionary format.

        Returns:
            Dictionary with 'start', 'end', and 'text' keys
        """
        return {
            "start": float(self.start),
            "end": float(self.end),
            "text": self.text.strip()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segment":
        """Create a Segment from a dictionary.

        Args:
            data: Dictionary with 'start', 'end', and 'text' keys

        Returns:
            Segment instance
        """
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")).strip()
        )


@dataclass
class TranscriptResult:
    """Result of transcription operation.

    Contains the transcribed segments and metadata about the transcription.
    """

    segments: List[Segment]
    engine: str  # 'whisper' or 'elevenlabs'
    model: str  # Model identifier used
    duration_seconds: Optional[float] = None  # Audio duration if known

    @property
    def text(self) -> str:
        """Get full transcript text without timestamps."""
        return " ".join(seg.text for seg in self.segments)

    @property
    def formatted(self) -> str:
        """Get formatted transcript with timestamps."""
        from .utils import format_timestamp
        lines = []
        for seg in self.segments:
            timestamp = format_timestamp(seg.start)
            lines.append(f"{timestamp} {seg.text}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "segments": [seg.as_dict() for seg in self.segments],
            "engine": self.engine,
            "model": self.model,
            "duration_seconds": self.duration_seconds,
            "text": self.text,
        }


@dataclass
class VideoMetadata:
    """Metadata about a video being processed."""

    title: str
    author: str
    url: str
    duration: int  # Duration in seconds
    upload_date: str
    description: str = ""
    video_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "duration": self.duration,
            "upload_date": self.upload_date,
            "description": self.description,
            "video_id": self.video_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoMetadata":
        """Create VideoMetadata from a dictionary."""
        return cls(
            title=data.get("title", "Unknown"),
            author=data.get("author", "Unknown"),
            url=data.get("url", ""),
            duration=data.get("duration", 0),
            upload_date=data.get("upload_date", ""),
            description=data.get("description", ""),
            video_id=data.get("video_id"),
        )


@dataclass
class PipelineResult:
    """Result of the full pipeline operation.

    Contains all outputs from processing a video: transcript, summary,
    and file paths.
    """

    success: bool
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    error: Optional[str] = None

    # Optional detailed results
    metadata: Optional[VideoMetadata] = None
    transcript: Optional[TranscriptResult] = None
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API responses."""
        result = {
            "success": self.success,
            "transcript_path": self.transcript_path,
            "summary_path": self.summary_path,
            "error": self.error,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        if self.transcript:
            result["transcript"] = self.transcript.to_dict()
        if self.summary:
            result["summary"] = self.summary
        return result
