# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Dockerized CLI tool that downloads YouTube videos, transcribes them using ElevenLabs Scribe (with Whisper fallback), and extracts key insights using Claude or GPT.

**Pipeline flow**: YouTube URL → Audio Download (yt-dlp) → Transcription (Scribe/Whisper) → AI Extraction (Claude/GPT) → Markdown outputs

## Development Commands

**Python Version Requirement**: Use Python 3.11 - 3.13. A `.python-version` file is included to specify the recommended version.

### Docker (Recommended)
```bash
# Build the image
docker-compose build

# Process a video
docker-compose run --rm transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID

# With options
docker-compose run --rm transcript-pipeline URL --model small --llm gpt --no-extract
```

### Local Python
```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI
python -m src.main https://www.youtube.com/watch?v=VIDEO_ID

# Run tests
pytest
pytest tests/test_utils.py -v
pytest tests/test_transcriber_scribe_parsing.py -v
```

## Architecture

### Core Pipeline (src/main.py)
The `process_video()` function orchestrates a 3-step pipeline:
1. **Download** - Uses VideoDownloader to fetch audio via yt-dlp
2. **Transcribe** - Uses Transcriber with configurable engine (Scribe or Whisper)
3. **Extract** (optional) - Uses TranscriptExtractor with chosen LLM

Output files are organized into subdirectories:
- `output/audio/` - Downloaded MP3 files (cleaned up after processing)
- `output/transcripts/` - Full transcripts with timestamps
- `output/summaries/` - AI-generated summaries

### Transcription Strategy (src/transcriber.py)
The Transcriber implements a **primary + fallback** pattern:
- **Primary engine**: ElevenLabs Scribe (real-time streaming API)
- **Fallback engine**: Whisper (local ML model)
- **Automatic fallback**: If Scribe fails or API key is missing, falls back to Whisper

**Scribe parsing**: The `_parse_scribe_response()` method handles multiple possible response formats from the ElevenLabs API (segments, words, or raw text) using a flexible parsing strategy.

### AI Extraction Strategy (src/extractor.py)
The TranscriptExtractor uses **hierarchical summarization** for long content:
- **Short transcripts** (<8000 chars): Single LLM call with full context
- **Long transcripts** (≥8000 chars): Two-phase approach
  1. Split into chunks and summarize each chunk independently
  2. Combine chunk summaries into final extraction

This prevents context window overflow and maintains quality for long videos.

### Error Handling Patterns
- **Retry with exponential backoff** (utils.py): All LLM API calls use `retry_with_backoff()` with 3 attempts
- **Path validation** (utils.py): `ensure_output_path()` prevents directory traversal attacks
- **Graceful degradation**: If extraction fails, transcript is still saved

## Configuration

Environment variables are loaded from `.env` (use `.env.example` as template):
- `ELEVENLABS_API_KEY` - Required for Scribe transcription
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` - Required for extraction
- `DEFAULT_LLM` - Set to `claude` (default) or `gpt`
- `WHISPER_MODEL` - Model size: tiny, base (default), small, medium, large
- `OUTPUT_DIR` - Base directory for all outputs (default: `./output`)

## Testing

Tests use pytest. Key test files:
- `tests/test_utils.py` - Tests for sanitization, timestamps, retries, path validation
- `tests/test_transcriber_scribe_parsing.py` - Tests for Scribe response parsing flexibility

Run tests before making changes to transcription or extraction logic.

## Common Patterns

### Adding a new transcription engine
1. Add engine initialization in `Transcriber.__init__()`
2. Implement `_transcribe_with_{engine}()` method that returns `List[Segment]`
3. Add engine selection logic in `transcribe()` method
4. Update CLI argument choices in `src/main.py`

### Modifying extraction prompts
Edit the prompt constants in `TranscriptExtractor`:
- `EXTRACTION_PROMPT` - Single-pass extraction for short transcripts
- `CHUNK_SUMMARY_PROMPT` - Per-chunk summarization for long transcripts
- `FINAL_SUMMARY_PROMPT` - Final synthesis across chunk summaries

### Updating Claude model version
The Claude model is specified in `src/extractor.py:204`. Currently uses `claude-sonnet-4-5-20250929`. Update this if a newer model becomes available.

### Changing output format
Modify `create_transcript_markdown()` or `create_summary_markdown()` in `src/main.py`.

## Docker Image Details

The Dockerfile (Python 3.11-slim base):
- Installs ffmpeg (required by yt-dlp for audio extraction)
- Pre-caches Whisper base model on first run (see entrypoint.sh)
- Mounts `./output` and `./models` as volumes for persistence
- Uses `/app/entrypoint.sh` to auto-download Whisper model if cache is empty

## Known Limitations

- Whisper transcription is CPU-bound and slow for large models
- Long videos may take several minutes to process
- ElevenLabs Scribe requires API key and internet connection
- LLM extraction costs scale with transcript length
