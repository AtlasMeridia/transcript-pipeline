"""Main CLI interface for transcript pipeline."""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from .utils import load_config, sanitize_filename, ensure_output_path, format_duration
from .downloader import VideoDownloader
from .transcriber import Transcriber
from .extractor import TranscriptExtractor

logger = logging.getLogger(__name__)


def create_transcript_markdown(metadata: dict, transcript: str, output_path: Path) -> None:
    """
    Create transcript markdown file.

    Args:
        metadata: Video metadata dictionary
        transcript: Formatted transcript text
        output_path: Path to save the markdown file
    """
    content = f"""# {metadata['title']}

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**URL**: {metadata['url']}
**Duration**: {format_duration(metadata['duration'])}

## Description
{metadata['description'][:500]}{'...' if len(metadata['description']) > 500 else ''}

## Transcript

{transcript}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Transcript saved: {output_path}")


def create_summary_markdown(metadata: dict, summary: str, output_path: Path) -> None:
    """
    Create summary markdown file.

    Args:
        metadata: Video metadata dictionary
        summary: Extracted summary text
        output_path: Path to save the markdown file
    """
    from datetime import datetime

    content = f"""# {metadata['title']} - Summary

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**Processed**: {datetime.now().strftime('%Y-%m-%d')}

---

{summary}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"Summary saved: {output_path}")


def process_video(
    url: str,
    llm_type: str,
    output_dir: str,
    elevenlabs_api_key: Optional[str],
    scribe_model_id: str,
    no_extract: bool = False,
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """
    Process a YouTube video: download, transcribe, and extract.

    Args:
        url: YouTube video URL
        llm_type: LLM type for extraction
        output_dir: Output directory for markdown files
        elevenlabs_api_key: API key for ElevenLabs (required for Scribe)
        scribe_model_id: ElevenLabs Scribe model identifier
        no_extract: Skip extraction step
        raise_on_error: If True, raise exceptions instead of exiting

    Returns:
        Dictionary with keys: 'success', 'transcript_path', 'summary_path' (if extracted), 'error' (if failed)
    """
    config = load_config()
    result: Dict[str, Any] = {
        'success': False,
        'transcript_path': None,
        'summary_path': None,
        'error': None,
    }

    try:
        # Step 1: Download audio
        logger.info("=" * 60)
        logger.info("STEP 1: Downloading Audio")
        logger.info("=" * 60)
        # Keep media files in a dedicated audio subdirectory under the output dir
        audio_dir = os.path.join(output_dir, "audio")
        downloader = VideoDownloader(output_dir=audio_dir)
        audio_path, metadata = downloader.download_audio(url)

        # Step 2: Transcribe
        logger.info("=" * 60)
        logger.info("STEP 2: Transcribing Audio")
        logger.info("=" * 60)
        transcriber = Transcriber(
            elevenlabs_api_key=elevenlabs_api_key,
            scribe_model_id=scribe_model_id,
        )
        segments = transcriber.transcribe(audio_path)

        # Format transcript with timestamps
        transcript_with_timestamps = transcriber.format_transcript(segments, include_timestamps=True)

        # Save transcript
        filename_base = sanitize_filename(metadata['title'])
        transcript_output_dir = os.path.join(output_dir, "transcripts")
        transcript_path = ensure_output_path(transcript_output_dir, f"{filename_base}-transcript.md")
        create_transcript_markdown(metadata, transcript_with_timestamps, transcript_path)

        # Step 3: Extract (optional)
        if not no_extract:
            logger.info("=" * 60)
            logger.info("STEP 3: Extracting Key Information")
            logger.info("=" * 60)

            # Get API key based on LLM type
            if llm_type == "claude":
                api_key = config.get('anthropic_api_key')
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not found. Skipping extraction.")
                    result['success'] = True  # Transcript was successful
                    result['transcript_path'] = str(transcript_path)
                    return result
            else:
                api_key = config.get('openai_api_key')
                if not api_key:
                    logger.warning("OPENAI_API_KEY not found. Skipping extraction.")
                    result['success'] = True  # Transcript was successful
                    result['transcript_path'] = str(transcript_path)
                    return result

            # Extract information
            model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
            extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)
            full_text = transcriber.get_full_text(segments)
            summary = extractor.extract(full_text, metadata)

            # Save summary
            summary_output_dir = os.path.join(output_dir, "summaries")
            summary_path = ensure_output_path(summary_output_dir, f"{filename_base}-summary.md")
            create_summary_markdown(metadata, summary, summary_path)

        # Cleanup
        logger.info("=" * 60)
        logger.info("Cleaning up...")
        logger.info("=" * 60)
        downloader.cleanup_audio(audio_path)

        logger.info("=" * 60)
        logger.info("COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"Transcript: {transcript_path}")
        if not no_extract:
            logger.info(f"Summary: {summary_path}")

        result['success'] = True
        result['transcript_path'] = str(transcript_path)
        if not no_extract:
            result['summary_path'] = str(summary_path)

        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error: {error_msg}")
        result['error'] = error_msg
        if raise_on_error:
            raise
        # For CLI usage, exit with error code (only when called from CLI)
        # When raise_on_error=False, return result dict instead of exiting
        if not raise_on_error and __name__ == '__main__':
            print(f"\nError: {error_msg}", file=sys.stderr)
            sys.exit(1)
        return result


def main():
    """Main CLI entry point."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Transcribe YouTube videos and extract key information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://www.youtube.com/watch?v=VIDEO_ID
  %(prog)s URL --model small --llm gpt
  %(prog)s URL --no-extract
        """
    )

    parser.add_argument(
        'url',
        help='YouTube video URL'
    )

    parser.add_argument(
        '--llm',
        default=None,
        choices=['claude', 'gpt'],
        help='LLM for extraction (default: from .env or "claude")'
    )

    parser.add_argument(
        '--output-dir',
        default=None,
        help='Output directory for markdown files (default: from .env or "./output")'
    )

    parser.add_argument(
        '--no-extract',
        action='store_true',
        help='Skip extraction, only transcribe'
    )

    args = parser.parse_args()

    # Load config and apply defaults
    config = load_config()
    llm_type = args.llm or config.get('default_llm', 'claude')
    output_dir = args.output_dir or config.get('output_dir', './output')
    elevenlabs_api_key = config.get('elevenlabs_api_key')
    scribe_model_id = config.get('scribe_model_id', 'scribe_v2')
    llm_model_id = config.get('claude_model_id') if llm_type == 'claude' else config.get('openai_model_id')

    logger.info("Transcript Pipeline")
    logger.info("=" * 60)
    logger.info(f"URL: {args.url}")
    logger.info("Transcription Engine: scribe (ElevenLabs)")
    logger.info(f"LLM: {llm_type}")
    logger.info(f"LLM Model: {llm_model_id or '(default)'}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Extract: {not args.no_extract}")
    logger.info("")

    process_video(
        url=args.url,
        llm_type=llm_type,
        output_dir=output_dir,
        elevenlabs_api_key=elevenlabs_api_key,
        scribe_model_id=scribe_model_id,
        no_extract=args.no_extract
    )


if __name__ == '__main__':
    main()
