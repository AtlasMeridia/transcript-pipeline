"""Pipeline service for transcript processing.

This module provides the core pipeline logic used by both CLI and API interfaces.
It orchestrates the download → transcribe → extract workflow.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import time

from ..config import load_config, PipelineConfig
from ..models import Segment, PipelineResult
from ..utils import sanitize_filename, format_duration, TimedOperation
from ..downloader import VideoDownloader
from ..transcriber import get_transcriber, BaseTranscriber, CaptionTranscriber, CaptionsUnavailableError
from ..extractor import TranscriptExtractor
from .markdown_service import save_transcript_markdown, save_summary_markdown

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Progress update for pipeline status callbacks."""
    phase: str          # download, transcribe, extract, cleanup, complete, error
    status: str         # downloading, transcribing, extracting, complete, error, etc.
    message: Optional[str] = None
    progress: Optional[int] = None  # 0-100 percentage
    metadata: Optional[Dict[str, Any]] = None  # Video metadata when available


# Type alias for status callback (legacy simple version)
StatusCallback = Callable[[str, str, Optional[str]], None]

# Type alias for progress callback (new detailed version)
ProgressCallback = Callable[[ProgressUpdate], None]


def process_video(
    url: str,
    llm_type: str = "claude",
    output_dir: Optional[str] = None,
    transcription_engine: Optional[str] = None,
    no_extract: bool = False,
    config: Optional[Dict[str, Any]] = None,
    status_callback: Optional[StatusCallback] = None,
    progress_callback: Optional[ProgressCallback] = None,
    filename_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a YouTube video: download, transcribe, and optionally extract insights.

    This is the core pipeline function used by both CLI and API interfaces.

    Args:
        url: YouTube video URL
        llm_type: LLM type for extraction ('claude' or 'gpt')
        output_dir: Output directory for markdown files (uses config default if not provided)
        transcription_engine: Override transcription engine ('whisper' or 'elevenlabs')
        no_extract: Skip extraction step
        config: Optional pre-loaded configuration dictionary
        status_callback: Optional legacy callback(phase, status, message) for progress updates
        progress_callback: Optional detailed callback(ProgressUpdate) with progress percentages
        filename_prefix: Optional prefix for output files (e.g., date prefix)

    Returns:
        Dictionary with:
            - success: bool
            - transcript_path: str or None
            - summary_path: str or None
            - transcript_content: str or None
            - summary_content: str or None
            - metadata: dict or None
            - segments: List[Segment] or None
            - error: str or None
    """
    # Load config if not provided
    if config is None:
        config = load_config()

    # Set defaults from config
    output_dir = output_dir or config.get('output_dir', './output')
    transcription_engine = transcription_engine or config.get('transcription_engine', 'whisper')

    def update_progress(
        phase: str,
        status: str,
        message: Optional[str] = None,
        progress: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Helper to call both legacy and new callbacks."""
        if status_callback:
            status_callback(phase, status, message)
        if progress_callback:
            progress_callback(ProgressUpdate(
                phase=phase,
                status=status,
                message=message,
                progress=progress,
                metadata=metadata,
            ))
        if message:
            logger.info(message)

    # Legacy alias for backward compatibility
    def update_status(phase: str, status: str, message: Optional[str] = None):
        update_progress(phase, status, message)

    result: Dict[str, Any] = {
        'success': False,
        'transcript_path': None,
        'summary_path': None,
        'transcript_content': None,
        'summary_content': None,
        'metadata': None,
        'segments': None,
        'error': None,
    }

    pipeline_start = time.perf_counter()

    try:
        audio_dir = os.path.join(output_dir, "audio")
        downloader = VideoDownloader(output_dir=audio_dir)
        audio_path = None  # Track if we downloaded audio (for cleanup)
        segments: List[Segment] = []
        metadata = None
        transcriber = None
        transcription_source = transcription_engine

        # ================================================================
        # Step 1: Get transcript (captions-first if engine is 'auto')
        # ================================================================

        # Helper to format metadata for callbacks
        def format_metadata_for_callback(meta: Dict) -> Dict[str, Any]:
            return {
                'title': meta['title'],
                'author': meta['author'],
                'date': meta['upload_date'],
                'duration': format_duration(meta['duration']),
                'url': meta['url'],
            }

        if transcription_engine == 'auto':
            # Try captions first (faster, no audio download needed)
            update_progress('download', 'downloading', 'Checking for YouTube captions...', progress=5)

            try:
                caption_transcriber = CaptionTranscriber(
                    output_dir=output_dir,
                    language=config.get('caption_language', 'en'),
                )

                # Get metadata without downloading audio
                metadata = downloader.get_video_info(url)
                result['metadata'] = metadata

                update_progress(
                    'download', 'downloading',
                    f"Found: {metadata['title']}",
                    progress=10,
                    metadata=format_metadata_for_callback(metadata),
                )

                update_progress('transcribe', 'transcribing', 'Extracting YouTube captions...', progress=15)

                with TimedOperation("Caption extraction"):
                    segments = caption_transcriber.transcribe(
                        audio_path="",  # Not used for captions
                        url=url,
                    )

                transcriber = caption_transcriber
                transcription_source = 'captions'
                update_progress('transcribe', 'complete', f'Captions extracted ({len(segments)} segments)', progress=70)

            except CaptionsUnavailableError as e:
                logger.info(f"Captions unavailable: {e}, falling back to audio transcription")
                update_progress('download', 'downloading', 'Captions unavailable, downloading audio...', progress=15)

                # Fall back to audio download + transcription
                with TimedOperation("Audio download"):
                    audio_path, metadata = downloader.download_audio(url)

                result['metadata'] = metadata
                update_progress(
                    'download', 'complete',
                    f"Downloaded: {metadata['title']}",
                    progress=20,
                    metadata=format_metadata_for_callback(metadata),
                )

                # Use fallback engine (mlx-whisper by default)
                fallback_engine = config.get('caption_fallback_engine', 'mlx-whisper')
                update_progress('transcribe', 'transcribing', f'Transcribing with {fallback_engine}...', progress=25)

                transcriber = get_transcriber(
                    engine=fallback_engine,
                    model=config.get('mlx_whisper_model', 'large-v3-turbo'),
                )

                # Progress callback for transcription
                def transcription_progress(current: int, total: int):
                    if total > 0:
                        pct = int(25 + (current / total) * 45)
                        msg = f'Transcribing... ({current}/{total})'
                    else:
                        pct = 30
                        msg = f'Transcribing with {transcriber.engine_name}...'
                    update_progress('transcribe', 'transcribing', msg, progress=pct)

                with TimedOperation(f"Transcription ({fallback_engine})"):
                    segments = transcriber.transcribe(audio_path, progress_callback=transcription_progress)

                transcription_source = fallback_engine
                update_progress('transcribe', 'complete', f'Transcription complete ({len(segments)} segments)', progress=70)

        else:
            # Explicit engine specified - use traditional flow
            update_progress('download', 'downloading', 'Fetching video metadata...', progress=0)

            if transcription_engine == 'captions':
                # Captions-only mode (will fail if captions unavailable)
                metadata = downloader.get_video_info(url)
                result['metadata'] = metadata

                update_progress(
                    'download', 'downloading',
                    f"Found: {metadata['title']}",
                    progress=10,
                    metadata=format_metadata_for_callback(metadata),
                )

                update_progress('transcribe', 'transcribing', 'Extracting YouTube captions...', progress=15)

                transcriber = get_transcriber(
                    engine='captions',
                    output_dir=output_dir,
                    language=config.get('caption_language', 'en'),
                )

                with TimedOperation("Caption extraction"):
                    segments = transcriber.transcribe(audio_path="", url=url)

                update_progress('transcribe', 'complete', f'Captions extracted ({len(segments)} segments)', progress=70)
            else:
                # Audio-based transcription
                with TimedOperation("Audio download"):
                    audio_path, metadata = downloader.download_audio(url)

                result['metadata'] = metadata
                update_progress(
                    'download', 'complete',
                    f"Downloaded: {metadata['title']}",
                    progress=20,
                    metadata=format_metadata_for_callback(metadata),
                )

                update_progress('transcribe', 'transcribing', f'Transcribing with {transcription_engine}...', progress=25)

                transcriber = get_transcriber(
                    engine=transcription_engine,
                    model=config.get('mlx_whisper_model', 'large-v3-turbo'),
                )

                # Progress callback for transcription
                def transcription_progress_explicit(current: int, total: int):
                    if total > 0:
                        pct = int(25 + (current / total) * 45)
                        msg = f'Transcribing... ({current}/{total})'
                    else:
                        pct = 30
                        msg = f'Transcribing with {transcriber.engine_name}...'
                    update_progress('transcribe', 'transcribing', msg, progress=pct)

                with TimedOperation(f"Transcription ({transcription_engine})"):
                    segments = transcriber.transcribe(audio_path, progress_callback=transcription_progress_explicit)

                update_progress('transcribe', 'complete', f'Transcription complete ({len(segments)} segments)', progress=70)

        result['segments'] = segments

        # ================================================================
        # Step 2: Save transcript
        # ================================================================
        transcript_with_timestamps = transcriber.format_transcript(segments, include_timestamps=True)

        # Build filename with optional prefix
        sanitized_title = sanitize_filename(metadata['title'])
        if filename_prefix:
            filename_base = f"{filename_prefix} {sanitized_title}"
        else:
            filename_base = sanitized_title

        transcript_path = save_transcript_markdown(
            metadata=metadata,
            transcript=transcript_with_timestamps,
            output_dir=output_dir,
            filename_base=filename_base,
        )

        result['transcript_path'] = str(transcript_path)
        result['transcript_content'] = Path(transcript_path).read_text(encoding='utf-8')

        # ================================================================
        # Step 3: Extract (optional)
        # ================================================================
        if not no_extract:
            update_progress('extract', 'extracting', f'Sending to {llm_type.upper()} for analysis...', progress=75)

            # Get API key based on LLM type
            if llm_type == "claude":
                api_key = config.get('anthropic_api_key')
            else:
                api_key = config.get('openai_api_key')

            if api_key:
                model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
                extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)

                full_text = transcriber.get_full_text(segments)

                update_progress('extract', 'extracting', 'Extracting key insights...', progress=80)

                with TimedOperation(f"Extraction ({llm_type})"):
                    summary = extractor.extract(full_text, metadata)

                summary_path = save_summary_markdown(
                    metadata=metadata,
                    summary=summary,
                    output_dir=output_dir,
                    filename_base=filename_base,
                )

                result['summary_path'] = str(summary_path)
                result['summary_content'] = Path(summary_path).read_text(encoding='utf-8')

                update_progress('extract', 'complete', 'Extraction complete', progress=95)
            else:
                update_progress('extract', 'skipped', f'Skipped extraction: {llm_type.upper()} API key not found', progress=95)

        # ================================================================
        # Cleanup
        # ================================================================
        if audio_path:
            downloader.cleanup_audio(audio_path)

        result['success'] = True
        total_time = time.perf_counter() - pipeline_start
        logger.info(f"Pipeline completed in {total_time:.1f}s (source: {transcription_source})")
        update_progress('complete', 'complete', f'Pipeline complete', progress=100)

        return result

    except Exception as e:
        error_msg = str(e)
        result['error'] = error_msg
        total_time = time.perf_counter() - pipeline_start
        logger.error(f"Pipeline error after {total_time:.1f}s: {error_msg}")
        update_progress('error', 'error', f'Error: {error_msg}', progress=None)
        return result
