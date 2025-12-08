"""Markdown generation service for transcript pipeline.

This module provides functions to generate and save markdown files
for transcripts and summaries.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Union

from ..config import DESCRIPTION_TRUNCATE_LENGTH
from ..utils import format_duration, ensure_output_path

logger = logging.getLogger(__name__)


def create_transcript_markdown(metadata: Dict, transcript: str) -> str:
    """
    Generate transcript markdown content.

    Args:
        metadata: Video metadata dictionary with title, author, url, etc.
        transcript: Formatted transcript text (with timestamps)

    Returns:
        Markdown content as string
    """
    description = metadata.get('description', '')
    truncated_desc = description[:DESCRIPTION_TRUNCATE_LENGTH]
    ellipsis = '...' if len(description) > DESCRIPTION_TRUNCATE_LENGTH else ''

    return f"""# {metadata['title']}

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**URL**: {metadata['url']}
**Duration**: {format_duration(metadata['duration'])}

## Description
{truncated_desc}{ellipsis}

## Transcript

{transcript}
"""


def create_summary_markdown(metadata: Dict, summary: str) -> str:
    """
    Generate summary markdown content.

    Args:
        metadata: Video metadata dictionary
        summary: Extracted summary text

    Returns:
        Markdown content as string
    """
    return f"""# {metadata['title']} - Summary

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**Processed**: {datetime.now().strftime('%Y-%m-%d')}

---

{summary}
"""


def save_transcript_markdown(
    metadata: Dict,
    transcript: str,
    output_dir: str,
    filename_base: str,
) -> Path:
    """
    Generate and save transcript markdown to file.

    Args:
        metadata: Video metadata dictionary
        transcript: Formatted transcript text
        output_dir: Base output directory
        filename_base: Base filename (without extension)

    Returns:
        Path to saved file
    """
    content = create_transcript_markdown(metadata, transcript)

    transcript_dir = str(Path(output_dir) / "transcripts")
    output_path = ensure_output_path(transcript_dir, f"{filename_base}-transcript.md")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Transcript saved: {output_path}")
    return output_path


def save_summary_markdown(
    metadata: Dict,
    summary: str,
    output_dir: str,
    filename_base: str,
) -> Path:
    """
    Generate and save summary markdown to file.

    Args:
        metadata: Video metadata dictionary
        summary: Extracted summary text
        output_dir: Base output directory
        filename_base: Base filename (without extension)

    Returns:
        Path to saved file
    """
    content = create_summary_markdown(metadata, summary)

    summary_dir = str(Path(output_dir) / "summaries")
    output_path = ensure_output_path(summary_dir, f"{filename_base}-summary.md")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Summary saved: {output_path}")
    return output_path
