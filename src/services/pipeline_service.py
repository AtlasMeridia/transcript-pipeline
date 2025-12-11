"""Pipeline service for transcript processing.

This module provides the core pipeline logic used by both CLI and API interfaces.
It orchestrates the download → transcribe → extract workflow.
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import time

from ..config import load_config, PipelineConfig
from ..models import Segment, PipelineResult
from ..utils import sanitize_filename, TimedOperation
from ..downloader import VideoDownloader
from ..transcriber import get_transcriber, BaseTranscriber, CaptionTranscriber, CaptionsUnavailableError
from ..extractor import TranscriptExtractor
from .markdown_service import save_transcript_markdown, save_summary_markdown

logger = logging.getLogger(__name__)


# Type alias for status callback
StatusCallback = Callable[[str, str, Optional[str]], None]


def process_video(
    url: str,
    llm_type: str = "claude",
    output_dir: Optional[str] = None,
    transcription_engine: Optional[str] = None,
    no_extract: bool = False,
    config: Optional[Dict[str, Any]] = None,
    status_callback: Optional[StatusCallback] = None,
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
        status_callback: Optional callback(phase, status, message) for progress updates

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

    # Helper to call status callback if provided
    def update_status(phase: str, status: str, message: Optional[str] = None):
        if status_callback:
            status_callback(phase, status, message)
        if message:
            logger.info(message)

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

        if transcription_engine == 'auto':
            # Try captions first (faster, no audio download needed)
            update_status('download', 'downloading', 'Checking for YouTube captions...')

            try:
                caption_transcriber = CaptionTranscriber(
                    output_dir=output_dir,
                    language=config.get('caption_language', 'en'),
                )

                # Get metadata without downloading audio
                metadata = downloader.get_video_info(url)
                result['metadata'] = metadata

                update_status('transcribe', 'transcribing', 'Extracting YouTube captions...')

                with TimedOperation("Caption extraction"):
                    segments = caption_transcriber.transcribe(
                        audio_path="",  # Not used for captions
                        url=url,
                    )

                transcriber = caption_transcriber
                transcription_source = 'captions'
                update_status('transcribe', 'complete', f'Captions extracted ({len(segments)} segments)')

            except CaptionsUnavailableError as e:
                logger.info(f"Captions unavailable: {e}, falling back to audio transcription")
                update_status('download', 'downloading', 'Captions unavailable, downloading audio...')

                # Fall back to audio download + transcription
                with TimedOperation("Audio download"):
                    audio_path, metadata = downloader.download_audio(url)

                result['metadata'] = metadata
                update_status('download', 'complete', f"Downloaded: {metadata['title']}")

                # Use fallback engine (whisper by default)
                fallback_engine = config.get('caption_fallback_engine', 'whisper')
                update_status('transcribe', 'transcribing', f'Transcribing with {fallback_engine}...')

                transcriber = get_transcriber(
                    engine=fallback_engine,
                    api_key=config.get('elevenlabs_api_key'),
                    scribe_model_id=config.get('scribe_model_id', 'scribe_v2'),
                    model_name=config.get('whisper_model', 'large-v3'),
                    model_dir=config.get('whisper_model_dir'),
                )

                with TimedOperation(f"Transcription ({fallback_engine})"):
                    segments = transcriber.transcribe(audio_path)

                transcription_source = fallback_engine
                update_status('transcribe', 'complete', f'Transcription complete ({len(segments)} segments)')

        else:
            # Explicit engine specified - use traditional flow
            update_status('download', 'downloading', 'Fetching video metadata...')

            if transcription_engine == 'captions':
                # Captions-only mode (will fail if captions unavailable)
                metadata = downloader.get_video_info(url)
                result['metadata'] = metadata

                update_status('transcribe', 'transcribing', 'Extracting YouTube captions...')

                transcriber = get_transcriber(
                    engine='captions',
                    output_dir=output_dir,
                    language=config.get('caption_language', 'en'),
                )

                with TimedOperation("Caption extraction"):
                    segments = transcriber.transcribe(audio_path="", url=url)

                update_status('transcribe', 'complete', f'Captions extracted ({len(segments)} segments)')
            else:
                # Audio-based transcription
                with TimedOperation("Audio download"):
                    audio_path, metadata = downloader.download_audio(url)

                result['metadata'] = metadata
                update_status('download', 'complete', f"Downloaded: {metadata['title']}")

                update_status('transcribe', 'transcribing', f'Transcribing with {transcription_engine}...')

                transcriber = get_transcriber(
                    engine=transcription_engine,
                    api_key=config.get('elevenlabs_api_key'),
                    scribe_model_id=config.get('scribe_model_id', 'scribe_v2'),
                    model_name=config.get('whisper_model', 'large-v3'),
                    model_dir=config.get('whisper_model_dir'),
                )

                with TimedOperation(f"Transcription ({transcription_engine})"):
                    segments = transcriber.transcribe(audio_path)

                update_status('transcribe', 'complete', f'Transcription complete ({len(segments)} segments)')

        result['segments'] = segments

        # ================================================================
        # Step 2: Save transcript
        # ================================================================
        transcript_with_timestamps = transcriber.format_transcript(segments, include_timestamps=True)
        filename_base = sanitize_filename(metadata['title'])

        transcript_path = save_transcript_markdown(
            metadata=metadata,
            transcript=transcript_with_timestamps,
            output_dir=output_dir,
            filename_base=filename_base,
        )

        result['transcript_path'] = str(transcript_path)
        result['transcript_content'] = open(transcript_path, 'r', encoding='utf-8').read()

        # ================================================================
        # Step 3: Extract (optional)
        # ================================================================
        if not no_extract:
            update_status('extract', 'extracting', 'Extracting key insights...')

            # Get API key based on LLM type
            if llm_type == "claude":
                api_key = config.get('anthropic_api_key')
            else:
                api_key = config.get('openai_api_key')

            if api_key:
                model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
                extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)

                full_text = transcriber.get_full_text(segments)

                with TimedOperation(f"Extraction ({llm_type})"):
                    summary = extractor.extract(full_text, metadata)

                summary_path = save_summary_markdown(
                    metadata=metadata,
                    summary=summary,
                    output_dir=output_dir,
                    filename_base=filename_base,
                )

                result['summary_path'] = str(summary_path)
                result['summary_content'] = open(summary_path, 'r', encoding='utf-8').read()

                update_status('extract', 'complete', 'Extraction complete')
            else:
                update_status('extract', 'skipped', f'{llm_type.upper()} API key not found, skipping extraction')

        # ================================================================
        # Cleanup
        # ================================================================
        if audio_path:
            update_status('cleanup', 'cleaning', 'Cleaning up temporary files...')
            downloader.cleanup_audio(audio_path)

        result['success'] = True
        total_time = time.perf_counter() - pipeline_start
        logger.info(f"Pipeline completed in {total_time:.1f}s (source: {transcription_source})")
        update_status('complete', 'complete', f'Processing complete! (total: {total_time:.1f}s)')

        return result

    except Exception as e:
        error_msg = str(e)
        result['error'] = error_msg
        total_time = time.perf_counter() - pipeline_start
        logger.error(f"Pipeline error after {total_time:.1f}s: {error_msg}")
        update_status('error', 'error', f'Error: {error_msg}')
        return result
