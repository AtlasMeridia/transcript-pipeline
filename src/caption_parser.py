"""Parser for WebVTT caption files.

This module converts YouTube auto-generated captions (VTT format)
into Segment objects compatible with the transcription pipeline.
"""

import logging
import re
from typing import List

from .models import Segment

logger = logging.getLogger(__name__)

# VTT timestamp pattern: HH:MM:SS.mmm or MM:SS.mmm
VTT_TIMESTAMP_PATTERN = re.compile(
    r'(\d{1,2}:)?(\d{2}):(\d{2})\.(\d{3})'
)

# VTT cue pattern: start --> end
VTT_CUE_PATTERN = re.compile(
    r'(\d{1,2}:)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{1,2}:)?(\d{2}):(\d{2})\.(\d{3})'
)


def parse_vtt_timestamp(timestamp: str) -> float:
    """
    Parse VTT timestamp into seconds.

    Args:
        timestamp: VTT timestamp string (HH:MM:SS.mmm or MM:SS.mmm)

    Returns:
        Time in seconds as float
    """
    match = VTT_TIMESTAMP_PATTERN.match(timestamp.strip())
    if not match:
        raise ValueError(f"Invalid VTT timestamp: {timestamp}")

    hours_str, minutes, seconds, millis = match.groups()
    hours = int(hours_str.rstrip(':')) if hours_str else 0
    return hours * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def clean_vtt_text(text: str) -> str:
    """
    Clean VTT caption text by removing formatting tags and extra whitespace.

    Args:
        text: Raw caption text that may contain VTT formatting

    Returns:
        Cleaned text string
    """
    # Remove VTT formatting tags like <c>, </c>, <00:00:00.000>
    text = re.sub(r'<[^>]+>', '', text)
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_vtt(vtt_path: str) -> List[Segment]:
    """
    Parse WebVTT file into Segment objects.

    Handles YouTube auto-caption quirks:
    - Duplicate/overlapping segments (common in auto-captions)
    - Formatting tags embedded in text
    - Multi-line cue text

    Args:
        vtt_path: Path to .vtt file

    Returns:
        List of Segment objects with timestamps

    Raises:
        FileNotFoundError: If VTT file doesn't exist
        ValueError: If VTT file is malformed
    """
    segments: List[Segment] = []

    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into blocks (cues are separated by blank lines)
    blocks = content.split('\n\n')

    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        # Skip WEBVTT header and NOTE blocks
        if lines[0].startswith('WEBVTT') or lines[0].startswith('NOTE'):
            continue

        # Find the timing line
        timing_line = None
        text_start_idx = 0

        for i, line in enumerate(lines):
            if VTT_CUE_PATTERN.match(line):
                timing_line = line
                text_start_idx = i + 1
                break

        if not timing_line:
            continue

        # Parse timing
        match = VTT_CUE_PATTERN.match(timing_line)
        if not match:
            continue

        # Extract start and end timestamps
        start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = match.groups()

        start_hours = int(start_h.rstrip(':')) if start_h else 0
        start_time = start_hours * 3600 + int(start_m) * 60 + int(start_s) + int(start_ms) / 1000

        end_hours = int(end_h.rstrip(':')) if end_h else 0
        end_time = end_hours * 3600 + int(end_m) * 60 + int(end_s) + int(end_ms) / 1000

        # Get and clean text
        text_lines = lines[text_start_idx:]
        text = ' '.join(clean_vtt_text(line) for line in text_lines)
        text = text.strip()

        if not text:
            continue

        segments.append(Segment(
            start=start_time,
            end=end_time,
            text=text
        ))

    # Deduplicate overlapping segments (common in YouTube auto-captions)
    segments = deduplicate_segments(segments)

    logger.info(f"Parsed {len(segments)} segments from VTT file")
    return segments


def deduplicate_segments(segments: List[Segment]) -> List[Segment]:
    """
    Remove duplicate and heavily overlapping segments.

    YouTube auto-captions often include duplicate text with slightly
    different timestamps. This function merges such duplicates.

    Args:
        segments: List of segments that may contain duplicates

    Returns:
        Deduplicated list of segments
    """
    if not segments:
        return []

    # Sort by start time
    sorted_segments = sorted(segments, key=lambda s: s.start)
    result: List[Segment] = []

    for seg in sorted_segments:
        # Skip if this segment's text is identical to the previous
        # and timestamps overlap significantly
        if result:
            prev = result[-1]

            # Check for duplicate text
            if seg.text == prev.text:
                # Extend the previous segment's end time if needed
                if seg.end > prev.end:
                    result[-1] = Segment(
                        start=prev.start,
                        end=seg.end,
                        text=prev.text
                    )
                continue

            # Check for significant overlap (>50% of segment duration)
            overlap = max(0, min(prev.end, seg.end) - max(prev.start, seg.start))
            seg_duration = seg.end - seg.start
            if seg_duration > 0 and overlap / seg_duration > 0.5:
                # If texts are very similar (one contains the other), keep the longer
                if prev.text in seg.text:
                    result[-1] = Segment(
                        start=prev.start,
                        end=max(prev.end, seg.end),
                        text=seg.text
                    )
                    continue
                elif seg.text in prev.text:
                    continue

        result.append(seg)

    return result
