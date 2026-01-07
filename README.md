# Transcript Pipeline

A Python tool that transcribes YouTube videos and extracts key information using AI. Available as both a **CLI tool** and a **web interface** with REST API.

## Features

- **Dual Interface**: Command-line tool and web-based UI with REST API
- **Fast Local Transcription**: [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) optimized for Apple Silicon (5-10x faster than standard Whisper)
- **YouTube Captions**: Extract auto-generated captions when available (fastest option)
- **AI Extraction**: Extracts key insights using Claude or GPT with hierarchical summarization
- **Real-time Progress**: Web interface shows live progress via Server-Sent Events
- **One-Command Setup**: `./start-local.sh` handles environment setup and dependencies
- **Library-style API**: `process_video()` can be imported and reused programmatically

## Project Structure

```
transcript-pipeline/
├── start-local.sh          # One-command local setup and run script
├── requirements-local.txt  # Python dependencies (with MLX Whisper)
├── requirements.txt        # Minimal dependencies (for Docker/cloud)
├── server.py               # FastAPI web server with SSE streaming
├── .env.example            # Environment variables template
├── README.md               # This file
├── CLAUDE.md               # Claude Code guidance
├── Dockerfile              # Docker image configuration (alternative)
├── docker-compose.yml      # Docker Compose setup (alternative)
├── src/
│   ├── __init__.py
│   ├── main.py             # CLI entry point (thin wrapper)
│   ├── config.py           # Centralized configuration and constants
│   ├── models.py           # Shared data models (Segment, etc.)
│   ├── downloader.py       # YouTube audio download via yt-dlp
│   ├── transcriber.py      # Whisper/ElevenLabs transcription engines
│   ├── extractor.py        # LLM-based content extraction
│   ├── utils.py            # Helper functions and utilities
│   └── services/
│       ├── __init__.py
│       ├── pipeline_service.py   # Core pipeline logic (process_video)
│       └── markdown_service.py   # Markdown generation functions
├── frontend/
│   └── index.html          # Web interface (standalone HTML)
├── tests/                  # Test suite
│   ├── test_utils.py
│   └── test_transcriber_scribe_parsing.py
├── dev/
│   └── REFACTORING.md      # Refactoring progress documentation
├── output/                 # Generated files (gitignored)
│   ├── audio/              # Temporary audio files
│   ├── transcripts/        # Transcript markdown files
│   └── summaries/          # Summary markdown files
└── models/                 # Whisper model cache (gitignored)
```

## Prerequisites

- **macOS with Apple Silicon** (M1/M2/M3/M4) - recommended for MLX Whisper
- **Python 3.11 - 3.13** (Python 3.14+ not supported)
- **ffmpeg** - for audio processing (`brew install ffmpeg`)
- **API key** for Claude (Anthropic) or GPT (OpenAI) - for AI extraction

**Note**: Docker is available as an alternative but does not support MLX Whisper (local transcription). Use Docker for deployment or non-macOS environments.

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# 2. Start the backend (installs dependencies automatically)
./start-local.sh

# 3. In another terminal, start the frontend
cd web && npm install && npm run dev

# 4. Open http://localhost:3000
```

The `start-local.sh` script automatically:
- Creates a Python virtual environment (`.venv/`)
- Installs all dependencies including MLX Whisper
- Starts the FastAPI server on port 8000 with hot-reload

## Setup

### 1. Configure Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Transcription Engine: 'auto', 'mlx-whisper', or 'captions'
# - auto: Try YouTube captions first, fall back to MLX Whisper (recommended)
# - mlx-whisper: Always use local transcription
# - captions: Only use YouTube captions
TRANSCRIPTION_ENGINE=auto

# MLX Whisper model (when using mlx-whisper)
# Options: tiny, base, small, medium, large, large-v3, large-v3-turbo, distil-large-v3
MLX_WHISPER_MODEL=large-v3-turbo

# LLM for AI extraction (required)
ANTHROPIC_API_KEY=your_anthropic_key_here  # For Claude (recommended)
# OPENAI_API_KEY=your_openai_key_here       # For GPT (alternative)

DEFAULT_LLM=claude
```

See `.env.example` for all available options.

### 2. Start the Application

```bash
# Start backend
./start-local.sh

# In another terminal, start frontend
cd web && npm run dev
```

## Usage

### Web Interface (Recommended)

The web interface at `http://localhost:3000` provides:
- Real-time progress updates via Server-Sent Events
- Model selection (MLX Whisper sizes)
- Direct download of transcripts and summaries
- Activity log with detailed status

### CLI Mode

Process videos directly from the command line:

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Process a video
python -m src.main https://www.youtube.com/watch?v=VIDEO_ID

# Use GPT instead of Claude
python -m src.main https://youtu.be/VIDEO_ID --llm gpt

# Only transcribe (skip AI extraction)
python -m src.main https://youtu.be/VIDEO_ID --no-extract
```

### Docker (Alternative)

For deployment or non-macOS environments. Note: MLX Whisper is not available in Docker.

```bash
# Build and start API server
docker-compose build
docker-compose up transcript-api

# CLI mode
docker-compose run --rm --profile cli transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID
```

### REST API

The API server provides REST endpoints for programmatic access:

**Start Processing:**
```bash
POST /api/process
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=VIDEO_ID",
  "llm_type": "claude",  # optional
  "extract": true        # optional
}

# Returns: {"job_id": "abc123", "status": "pending", ...}
```

**Get Job Status:**
```bash
GET /api/jobs/{job_id}

# Returns: {"job_id": "abc123", "status": "complete", "transcript_path": "...", ...}
```

**Stream Progress (Server-Sent Events):**
```bash
GET /api/jobs/{job_id}/stream

# Returns SSE stream with real-time updates
```

**Download Files:**
```bash
GET /api/jobs/{job_id}/download/transcript
GET /api/jobs/{job_id}/download/summary
```

**Get Configuration (non-sensitive):**
```bash
GET /api/config

# Returns: {
#   "default_llm": "claude",
#   "transcription_engine": "whisper",  # or "elevenlabs"
#   "whisper_model": "large-v3",         # if using whisper
#   "has_elevenlabs_key": true,
#   ...
# }
```

**Interactive API Documentation:**
Visit `http://localhost:8000/docs` when the server is running for Swagger UI with interactive testing.

## Output Files

The tool generates organized output files in the `output/` directory:

```
output/
├── audio/                    # Temporary audio files (cleaned up after processing)
├── transcripts/              # Transcript markdown files
│   └── {video-title}-transcript.md
└── summaries/               # Summary markdown files
    └── {video-title}-summary.md
```

### 1. Transcript: `transcripts/{video-title}-transcript.md`

Contains:
- Video metadata (title, author, date, duration, URL)
- Video description (truncated to 500 chars)
- Full transcript with timestamps

Example:
```markdown
# Introduction to Machine Learning

**Author**: Tech Channel
**Date**: 20240115
**URL**: https://www.youtube.com/watch?v=...
**Duration**: 15m 30s

## Description
This video covers the fundamentals of machine learning...

## Transcript

[00:00:00] Welcome to this introduction to machine learning...
[00:00:15] Today we'll cover the basics of supervised learning...
```

### 2. Summary: `summaries/{video-title}-summary.md`

Contains AI-extracted information:
- Executive summary
- Key points
- Important quotes (with timestamps)
- Main topics
- Actionable insights

Example:
```markdown
# Introduction to Machine Learning - Summary

**Author**: Tech Channel
**Date**: 20240115
**Processed**: 2024-01-20

---

## Executive Summary
This video provides a comprehensive introduction to machine learning...

## Key Points
- Machine learning is a subset of artificial intelligence
- Supervised learning requires labeled training data
...
```

## CLI Options

```
python -m src.main [-h]
                        [--llm {claude,gpt}] [--output-dir OUTPUT_DIR]
                        [--no-extract]
                        url

Positional arguments:
  url                   YouTube video URL

Optional arguments:
  -h, --help           Show help message
  --llm LLM           LLM for extraction: claude or gpt (default: claude)
  --output-dir DIR     Output directory (default: ./output)
  --no-extract         Skip extraction, only transcribe
```

## Docker Deployment

Docker is available for deployment to cloud platforms or non-macOS environments. The Docker image supports YouTube caption extraction but not MLX Whisper (local transcription).

```bash
# Build and run
docker-compose build
docker-compose up transcript-api
```

Services:
- **`transcript-api`**: FastAPI web server on port 8000
- **`transcript-pipeline`**: CLI mode (use `--profile cli`)

## Troubleshooting

### "mlx-whisper is not installed"

This error occurs when running in Docker. MLX Whisper requires Apple Silicon and cannot run in Docker containers. Solutions:

1. **Run locally** (recommended): Use `./start-local.sh` instead of Docker
2. **Use captions**: Set `TRANSCRIPTION_ENGINE=captions` in `.env` to use YouTube auto-captions

### "Video unavailable" or "Private video"

The video may be:
- Private or deleted
- Geo-restricted
- Age-restricted

Try a different video URL.

### "API key not found"

Make sure your `.env` file contains the correct API key:
- `ANTHROPIC_API_KEY` for Claude
- `OPENAI_API_KEY` for GPT

### MLX Whisper model download slow

The first run downloads the model from Hugging Face. This is normal:
- `small` model: ~500MB
- `large-v3-turbo` model: ~1.5GB

Models are cached in `~/.cache/huggingface/` for future use.

### Out of memory errors

If transcribing large videos, use a smaller model:
```bash
MLX_WHISPER_MODEL=small  # In .env
```

### ffmpeg not found

Install ffmpeg (required for audio processing):
```bash
brew install ffmpeg
```

### CORS errors in production

Configure CORS origins via the `CORS_ORIGINS` environment variable:
```bash
CORS_ORIGINS=https://yourdomain.com
```

## Advanced Usage

### Batch Processing

Create a script to process multiple videos:

```bash
#!/bin/bash
# process-videos.sh

source .venv/bin/activate
while IFS= read -r url; do
    echo "Processing: $url"
    python -m src.main "$url"
done < video-urls.txt
```

Usage:
```bash
chmod +x process-videos.sh
./process-videos.sh
```

### Programmatic Usage

The `process_video()` function can be imported from the services package and used as a library:

```python
from src.services import process_video

result = process_video(
    url="https://youtube.com/watch?v=VIDEO_ID",
    llm_type="claude",
    output_dir="./output",
    transcription_engine="whisper",  # or "elevenlabs"
    no_extract=False,  # Set True to skip extraction
)

if result['success']:
    print(f"Transcript: {result['transcript_path']}")
    print(f"Summary: {result['summary_path']}")
    print(f"Segments: {len(result['segments'])}")
else:
    print(f"Error: {result['error']}")
```

You can also provide a status callback for progress updates:

```python
def my_callback(phase, status, message):
    print(f"[{phase}] {status}: {message}")

result = process_video(
    url="https://youtube.com/watch?v=VIDEO_ID",
    status_callback=my_callback,
)
```

### Custom Extraction Prompts

To customize the extraction prompt, edit `src/extractor.py` and modify:
- `EXTRACTION_PROMPT` - Single-pass extraction for short transcripts
- `CHUNK_SUMMARY_PROMPT` - Per-chunk summarization for long transcripts
- `FINAL_SUMMARY_PROMPT` - Final synthesis across chunk summaries

### Long Video Handling

The pipeline automatically handles long videos:
- **Transcription**: Videos >30 minutes are chunked with 5-second overlaps
- **Extraction**: Transcripts >8000 characters use hierarchical summarization (chunk summaries → final summary)

## License

This project is provided as-is for educational and personal use.

## Contributing

Contributions welcome! Please test thoroughly before submitting pull requests.

## Testing

Run the test suite:

```bash
# Activate virtual environment and run tests
source .venv/bin/activate
pytest

# Or run specific tests
pytest tests/test_utils.py -v
```

Tests cover:
- Utility functions (filename sanitization, timestamps, path validation)
- Transcription parsing
- Retry logic with exponential backoff

## Credits

Built with:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) - Fast local transcription on Apple Silicon
- [Anthropic Claude](https://www.anthropic.com/) - AI extraction
- [OpenAI GPT](https://openai.com/) - AI extraction (alternative)
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Next.js](https://nextjs.org/) - Frontend framework
