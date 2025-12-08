"""Main CLI interface for transcript pipeline."""

import argparse
import logging
import sys
from typing import Dict, Any

from .config import load_config, validate_config, ConfigurationError

# Import process_video from services for backward compatibility
from .services import process_video

logger = logging.getLogger(__name__)


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
  %(prog)s URL --llm gpt
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
    transcription_engine = config.get('transcription_engine', 'whisper')

    # Display transcription engine info
    if transcription_engine == 'elevenlabs':
        scribe_model_id = config.get('scribe_model_id', 'scribe_v2')
        engine_display = f"elevenlabs (Scribe {scribe_model_id})"
    else:
        whisper_model = config.get('whisper_model', 'large-v3')
        engine_display = f"whisper ({whisper_model})"

    llm_model_id = config.get('claude_model_id') if llm_type == 'claude' else config.get('openai_model_id')

    logger.info("Transcript Pipeline")
    logger.info("=" * 60)
    logger.info(f"URL: {args.url}")
    logger.info(f"Transcription Engine: {engine_display}")
    logger.info(f"LLM: {llm_type}")
    logger.info(f"LLM Model: {llm_model_id or '(default)'}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Extract: {not args.no_extract}")
    logger.info("")

    # Validate configuration before starting
    try:
        validate_config(config, no_extract=args.no_extract)
    except ConfigurationError as e:
        logger.error(f"Configuration error:\n{e}")
        sys.exit(1)

    # Process video using pipeline service
    def cli_status_callback(phase: str, status: str, message: str = None):
        """Status callback for CLI that logs with visual separators."""
        if phase == 'download' and status == 'downloading':
            logger.info("=" * 60)
            logger.info("STEP 1: Downloading Audio")
            logger.info("=" * 60)
        elif phase == 'transcribe' and status == 'transcribing':
            logger.info("=" * 60)
            logger.info("STEP 2: Transcribing Audio")
            logger.info("=" * 60)
        elif phase == 'extract' and status == 'extracting':
            logger.info("=" * 60)
            logger.info("STEP 3: Extracting Key Information")
            logger.info("=" * 60)
        elif phase == 'cleanup':
            logger.info("=" * 60)
            logger.info("Cleaning up...")
            logger.info("=" * 60)
        elif phase == 'complete':
            logger.info("=" * 60)
            logger.info("COMPLETE!")
            logger.info("=" * 60)

    result = process_video(
        url=args.url,
        llm_type=llm_type,
        output_dir=output_dir,
        transcription_engine=transcription_engine,
        no_extract=args.no_extract,
        config=config,
        status_callback=cli_status_callback,
    )

    # Handle result
    if result['success']:
        logger.info(f"Transcript: {result['transcript_path']}")
        if result.get('summary_path'):
            logger.info(f"Summary: {result['summary_path']}")
    else:
        logger.error(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
