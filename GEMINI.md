# Transcript Pipeline

## Project Overview

This project is a **Dockerized Python CLI and Web API tool** designed to download audio from YouTube videos, transcribe it into text, and extract key information using AI. It features a robust architecture with a service layer for shared logic between CLI and API interfaces.

**Key Features:**
*   **Dual Interface:** CLI tool and FastAPI web server with real-time SSE streaming
*   **Download:** Fetches audio from YouTube using `yt-dlp`.
*   **Transcription:**
    *   **Default:** OpenAI Whisper (local model) - no API key required
    *   **Cloud Option:** ElevenLabs Scribe v2 (Realtime API)
    *   **Long Audio Support:** Whisper uses chunking (30-minute chunks with 5s overlap) for memory efficiency
*   **Extraction:** Summarizes content using Anthropic's Claude (default) or OpenAI's GPT. Implements hierarchical summarization for long transcripts (>8000 chars).
*   **Output:** Generates formatted Markdown files for transcripts and summaries.

## Building and Running

The project is designed to run primarily via Docker, but supports local Python execution.

### Docker (Recommended)

**Build the image:**
```bash
docker-compose build
```

**Run the API server:**
```bash
docker-compose up transcript-api
```

**Run the CLI:**
```bash
docker-compose run --rm --profile cli transcript-pipeline <YOUTUBE_URL>
```

**Common Options:**
*   `--llm [claude|gpt]`: Select LLM for extraction.
*   `--no-extract`: Skip the summarization step.

### Local Development

**Prerequisites:**
*   Python 3.11 - 3.13
*   `ffmpeg` installed on the system.

**Setup:**
```bash
pip install -r requirements.txt
cp .env.example .env  # Configure API keys in .env
```

**Run CLI:**
```bash
python -m src.main <YOUTUBE_URL>
```

**Run API server:**
```bash
python server.py
```

**Testing:**
```bash
pytest
```

## Codebase Structure

```
src/
├── config.py           # Centralized configuration and constants
├── models.py           # Shared data models (Segment, TranscriptResult, etc.)
├── main.py             # CLI entry point (thin wrapper around services)
├── downloader.py       # YouTube audio download via yt-dlp
├── transcriber.py      # Whisper and ElevenLabs transcription engines
├── extractor.py        # LLM-based content extraction (Claude/GPT)
├── utils.py            # Helper functions (re-exports from config.py)
└── services/
    ├── pipeline_service.py   # Core pipeline logic (process_video)
    └── markdown_service.py   # Markdown generation functions

server.py               # FastAPI web server with SSE streaming
entrypoint.sh           # Docker CLI entrypoint with environment validation
```

### Key Modules

*   **`src/config.py`**: Centralized configuration with `PipelineConfig` dataclass and all constants (chunk sizes, model defaults, etc.)
*   **`src/models.py`**: Type-safe data models (`Segment`, `TranscriptResult`, `VideoMetadata`, `PipelineResult`)
*   **`src/services/pipeline_service.py`**: Core `process_video()` function used by both CLI and API
*   **`src/services/markdown_service.py`**: Shared markdown generation functions
*   **`src/transcriber.py`**: Contains `WhisperTranscriber` and `ElevenLabsTranscriber` classes with chunking logic
*   **`src/extractor.py`**: `TranscriptExtractor` class with hierarchical summarization for long content
*   **`server.py`**: FastAPI server with push-based SSE streaming and thread-safe job management

## Development Conventions

*   **Configuration:** Environment variables managed via `.env`, centralized in `src/config.py`
*   **Service Layer:** Core logic in `src/services/` shared between CLI and API
*   **Error Handling:** Uses `retry_with_backoff` for API calls and graceful degradation
*   **Type Hinting:** Dataclasses and type hints throughout (e.g., `List[Segment]`, `Optional[str]`)
*   **Testing:** `pytest` suite - run tests before committing changes to core logic
*   **Logging:** f-string style logging with `TimedOperation` context manager for performance tracking
*   **Thread Safety:** Server uses `RLock` for job access and `Lock` for SSE queue management

## API Endpoints

*   `POST /api/process` - Start processing a video
*   `GET /api/jobs/{job_id}` - Get job status
*   `GET /api/jobs/{job_id}/stream` - SSE stream of real-time updates
*   `GET /api/jobs/{job_id}/transcript` - Get transcript content
*   `GET /api/jobs/{job_id}/summary` - Get summary content
*   `GET /api/jobs/{job_id}/download/{type}` - Download files
*   `GET /api/config` - Get configuration (non-sensitive)
*   `GET /api/health` - Health check

## Documentation

*   **`CLAUDE.md`**: Detailed architecture documentation for Claude Code
*   **`dev/REFACTORING.md`**: Refactoring progress and changelog
