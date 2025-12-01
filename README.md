# Transcript Pipeline

A Dockerized Python tool that transcribes YouTube videos and extracts key information using AI. Available as both a **CLI tool** and a **web interface** with REST API.

## Features

- **Dual Interface**: Command-line tool and web-based UI with REST API
- **Flexible Transcription**: Choose between [OpenAI Whisper](https://github.com/openai/whisper) (local) or [ElevenLabs Scribe v2](https://elevenlabs.io/blog/introducing-scribe-v2-realtime) (cloud)
- **Chunked Processing**: Handles long videos with intelligent chunking and overlap
- **AI Extraction**: Extracts key insights using Claude or GPT with hierarchical summarization for long content
- **Real-time Progress**: Web interface shows live progress via Server-Sent Events
- **Fully Containerized**: Easy Docker deployment with both CLI and API modes
- **Library-style API**: `process_video()` can be imported and reused programmatically

## Project Structure

```
transcript-pipeline/
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose setup (API + CLI services)
├── requirements.txt        # Python dependencies
├── server.py              # FastAPI web server
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI entry point
│   ├── downloader.py      # YouTube audio download
│   ├── transcriber.py     # Scribe/Whisper transcription
│   ├── extractor.py       # AI extraction
│   └── utils.py           # Helper functions
├── frontend/
│   └── index.html         # Web interface (standalone HTML)
├── tests/                 # Test suite
│   ├── test_utils.py
│   └── test_transcriber_scribe_parsing.py
├── output/                # Generated files (gitignored)
│   ├── audio/             # Temporary audio files
│   ├── transcripts/       # Transcript markdown files
│   └── summaries/         # Summary markdown files
└── models/                # Whisper model cache (gitignored)
```

## Prerequisites

- Docker and Docker Compose
- (Optional for local run) Python 3.11 - 3.13 (Python 3.14+ not supported)
- API key for Claude (Anthropic) or GPT (OpenAI)
- **For local transcription**: No additional API keys needed (uses Whisper)
- **For cloud transcription**: ElevenLabs API key for Scribe v2

## Setup

### 1. Clone or Copy the Project

```bash
cd transcript-pipeline
```

### 2. Configure Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys (see `.env.example` for all available options):

```bash
# Transcription Engine: 'whisper' (local) or 'elevenlabs' (cloud)
# Default: whisper
TRANSCRIPTION_ENGINE=whisper

# Whisper Configuration (for local transcription)
WHISPER_MODEL=large-v3  # Options: tiny, base, small, medium, large, large-v2, large-v3
# WHISPER_MODEL_DIR=/path/to/models  # Optional: custom model cache directory

# ElevenLabs Configuration (for cloud transcription)
# Required only if TRANSCRIPTION_ENGINE=elevenlabs
ELEVENLABS_API_KEY=your_elevenlabs_key_here
# SCRIBE_MODEL_ID=scribe_v2

# LLM for AI extraction
# Use Claude (recommended)
ANTHROPIC_API_KEY=your_anthropic_key_here

# OR use GPT
# OPENAI_API_KEY=your_openai_key_here

# Default LLM for extraction (claude or gpt)
DEFAULT_LLM=claude

# Optional overrides for specific model versions
# CLAUDE_MODEL_ID=claude-sonnet-4-5
# OPENAI_MODEL_ID=gpt-4o-mini
```

### 3. Build the Docker Image

```bash
# Standard build (ElevenLabs cloud transcription - lean image for Railway)
docker-compose build

# With Whisper support (local transcription - larger image)
docker-compose build --build-arg INSTALL_WHISPER=true
```

This will:
- Install all system dependencies (ffmpeg, etc.)
- Install Python packages
- Optionally install Whisper dependencies (~2GB additional)
- Set up the environment

## Usage

### Web Interface (Recommended for Interactive Use)

Start the API server:

```bash
docker-compose up transcript-api
```

The API will be available at `http://localhost:8000`

Open the web interface:
- Option 1: Open `frontend/index.html` directly in your browser
- Option 2: Serve it with a static server:
  ```bash
  cd frontend && python -m http.server 3000
  # Then open http://localhost:3000
  ```

The web interface provides:
- Real-time progress updates via Server-Sent Events
- Interactive job management
- Direct download of transcripts and summaries
- Configuration display

### CLI Mode

Process a single YouTube video via command line:

```bash
docker-compose run --rm --profile cli transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID
```

> **Note**: The `--profile cli` flag is required for CLI mode. Without it, docker-compose will try to start the API server.

> The CLI streams audio to ElevenLabs Scribe v2 Realtime when `ELEVENLABS_API_KEY` is configured.

With custom options:

```bash
# Use GPT instead of Claude
docker-compose run --rm --profile cli transcript-pipeline https://youtu.be/VIDEO_ID --llm gpt

# Only transcribe (skip AI extraction)
docker-compose run --rm --profile cli transcript-pipeline https://youtu.be/VIDEO_ID --no-extract

# Custom output directory
docker-compose run --rm --profile cli transcript-pipeline https://youtu.be/VIDEO_ID --output-dir /app/output/my-folder
```

### Local Python (Alternative)

If you prefer to run without Docker:

```bash
# Install dependencies (ElevenLabs cloud transcription only)
pip install -r requirements.txt

# OR install with Whisper support (local transcription)
pip install -r requirements-local.txt

# Run CLI
python -m src.main https://www.youtube.com/watch?v=VIDEO_ID

# Run API server
python -m uvicorn server:app --host 0.0.0.0 --port 8000
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

## Docker Services

The `docker-compose.yml` provides two services:

1. **`transcript-api`** (default): Runs the FastAPI web server on port 8000
   ```bash
   docker-compose up transcript-api
   ```

2. **`transcript-pipeline`** (CLI profile): Command-line interface
   ```bash
   docker-compose run --rm --profile cli transcript-pipeline <url>
   ```

Both services share the same Docker image and environment variables.

## Transporting Between Systems

### Export the Docker Image

On the source system:

```bash
# Save the image to a tar file
docker save transcript-pipeline:latest -o transcript-pipeline.tar

# Copy the tar file to your target system
```

On the target system:

```bash
# Load the image
docker load -i transcript-pipeline.tar

# Copy the project files
# Make sure to include:
# - docker-compose.yml
# - .env (with your API keys)
# - models/ directory (optional, saves re-download time)

# Run API server
docker-compose up transcript-api

# Or run CLI
docker-compose run --rm --profile cli transcript-pipeline <youtube-url>
```

### Or Use Docker Hub

```bash
# Tag and push (on source system)
docker tag transcript-pipeline:latest yourusername/transcript-pipeline:latest
docker push yourusername/transcript-pipeline:latest

# Pull and run (on target system)
docker pull yourusername/transcript-pipeline:latest
docker-compose up transcript-api
```

## Troubleshooting

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
- `ELEVENLABS_API_KEY` for Scribe

See `.env.example` for a complete list of configuration options.

### Whisper model download fails

The first run downloads the Whisper model. If it fails:
1. Check your internet connection
2. Try a smaller model size: `--model tiny`
3. Manually download and place in `./models/` directory

### Out of memory errors

If transcribing large videos:
1. Use a smaller Whisper model: `--model tiny` or `--model base`
2. Increase Docker memory allocation in Docker Desktop settings

### ElevenLabs API errors

If Scribe requests fail or you are offline:
1. Confirm `ELEVENLABS_API_KEY` is present and valid.
2. Check your ElevenLabs usage limits.
3. Alternatively, switch to local Whisper transcription: `TRANSCRIPTION_ENGINE=whisper`

### CORS errors in production

If deploying the web interface, configure CORS origins via the `CORS_ORIGINS` environment variable:

```bash
# Allow specific origins (comma-separated)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Or allow all origins (development only, not recommended for production)
CORS_ORIGINS=*
```

### ffmpeg not found (local Python)

Install ffmpeg:
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `apt-get install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/

## Advanced Usage

### Batch Processing

Create a script to process multiple videos:

```bash
#!/bin/bash
# process-videos.sh

while IFS= read -r url; do
    echo "Processing: $url"
    docker-compose run --rm --profile cli transcript-pipeline "$url"
done < video-urls.txt
```

Usage:
```bash
chmod +x process-videos.sh
./process-videos.sh
```

### Programmatic Usage

The `process_video()` function can be imported and used as a library:

```python
from src.main import process_video

result = process_video(
    url="https://youtube.com/watch?v=VIDEO_ID",
    llm_type="claude",
    output_dir="./output",
    transcription_engine="scribe",
    elevenlabs_api_key="your_key",
    scribe_model_id="scribe_v2",
    raise_on_error=True  # Returns result dict instead of exiting
)

if result['success']:
    print(f"Transcript: {result['transcript_path']}")
    print(f"Summary: {result['summary_path']}")
else:
    print(f"Error: {result['error']}")
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
# With Docker (run pytest in the container)
docker-compose run --rm --profile cli transcript-pipeline python -m pytest

# Local Python
pytest
```

Tests cover:
- Utility functions (filename sanitization, timestamps, path validation)
- Scribe response parsing (flexible format handling)
- Retry logic with exponential backoff

## Credits

Built with:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [OpenAI Whisper](https://github.com/openai/whisper) - Local transcription
- [ElevenLabs Scribe](https://elevenlabs.io/) - Cloud transcription
- [Anthropic Claude](https://www.anthropic.com/) - AI extraction
- [OpenAI GPT](https://openai.com/) - AI extraction
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
