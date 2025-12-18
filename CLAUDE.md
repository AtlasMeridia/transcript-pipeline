# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A CLI and Web API tool that downloads YouTube videos, transcribes them using Whisper (local) or ElevenLabs Scribe (cloud), and extracts key insights using Claude or GPT.

**Pipeline flow**: YouTube URL → Audio Download (yt-dlp) → Transcription (Whisper/Scribe) → AI Extraction (Claude/GPT) → Markdown outputs

## Development Commands

**Python Version Requirement**: Use Python 3.11 - 3.13. A `.python-version` file is included.

### Docker (Recommended)
```bash
# Build the image
docker-compose build

# Process a video (CLI mode)
docker-compose run --rm transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID

# With options
docker-compose run --rm transcript-pipeline URL --llm gpt --no-extract

# Run backend API server (port 8000)
docker-compose up transcript-api

# Build with local Whisper transcription (one-time, adds ~2GB to image)
docker-compose build --build-arg INSTALL_WHISPER=true transcript-api
```

**Note**: The default Docker image uses ElevenLabs (cloud) for transcription. To use local Whisper transcription, you must rebuild with `INSTALL_WHISPER=true`. This only needs to be done once - the setting persists in the built image.

### Running the Full Stack (Frontend + Backend)

To run the complete web application locally:

```bash
# Terminal 1: Start the backend API (Docker)
docker-compose up transcript-api

# Terminal 2: Start the frontend (Next.js)
cd web
npm install  # first time only
npm run dev
```

Then open http://localhost:3000 in your browser.

**Important**: The frontend requires `web/.env.local` with:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
This tells the Next.js frontend where to find the backend API.

### Local Python
```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI
python -m src.main https://www.youtube.com/watch?v=VIDEO_ID

# Run API server
python server.py

# Run tests
pytest
pytest tests/test_utils.py -v
pytest tests/test_transcriber_scribe_parsing.py -v
```

## Architecture

### Module Structure
```
src/
├── config.py          # Centralized configuration and constants
├── models.py          # Shared data models (Segment, TranscriptResult, etc.)
├── main.py            # CLI entry point (thin wrapper)
├── downloader.py      # YouTube audio download via yt-dlp
├── transcriber.py     # Whisper and ElevenLabs transcription engines
├── extractor.py       # LLM-based content extraction
├── utils.py           # Utility functions (re-exports from config.py)
└── services/
    ├── pipeline_service.py   # Core pipeline logic (process_video)
    └── markdown_service.py   # Markdown generation functions
server.py              # FastAPI server with SSE streaming
```

### Core Pipeline (src/services/pipeline_service.py)
The `process_video()` function orchestrates a 3-step pipeline:
1. **Download** - Uses `VideoDownloader` to fetch audio via yt-dlp
2. **Transcribe** - Uses `get_transcriber()` factory with configurable engine
3. **Extract** (optional) - Uses `TranscriptExtractor` with chosen LLM

Output files are organized into subdirectories:
- `output/audio/` - Downloaded MP3 files (cleaned up after processing)
- `output/transcripts/` - Full transcripts with timestamps
- `output/summaries/` - AI-generated summaries

### Configuration (src/config.py)
All constants and magic numbers are centralized:
- `CHUNK_DURATION_SECONDS = 1800` - 30 min chunks for long audio
- `MAX_CHARS_PER_CHUNK = 8000` - LLM context budget
- `MAX_TOKENS_OUTPUT = 4000` - LLM response limit
- `DEFAULT_WHISPER_MODEL = "large-v3"` - Default Whisper model
- `DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"` - Default Claude model

### Data Models (src/models.py)
Type-safe data classes used throughout:
- `Segment` - Transcription segment with start, end, text
- `TranscriptResult` - Full transcription with segments and metadata
- `VideoMetadata` - Video information from YouTube
- `PipelineResult` - Complete pipeline result

### Transcription Strategy (src/transcriber.py)
Two transcription engines available:
- **Whisper** (default): Local ML model, no API key required
- **ElevenLabs Scribe**: Cloud API, requires `ELEVENLABS_API_KEY`

**Chunked transcription** for long audio (> 30 minutes):
- Automatically splits audio into 30-minute chunks with 5-second overlap
- Uses ffprobe/ffmpeg for audio splitting
- Deduplicates segments at chunk boundaries
- Progress callbacks for real-time UI updates

### AI Extraction Strategy (src/extractor.py)
Uses **hierarchical summarization** for long content:
- **Short transcripts** (<8000 chars): Single LLM call
- **Long transcripts** (≥8000 chars): Two-phase chunked approach

### Error Handling Patterns
- **Retry with exponential backoff**: All API calls use `retry_with_backoff()` with 3 attempts
- **Path validation**: `ensure_output_path()` prevents directory traversal
- **Early validation**: `validate_config()` checks API keys at startup
- **Graceful degradation**: If extraction fails, transcript is still saved

## API Server (server.py)

FastAPI server with real-time progress via Server-Sent Events.

### Endpoints
- `POST /api/process` - Start processing a video, returns job ID
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/jobs/{job_id}/stream` - SSE stream of job updates
- `GET /api/jobs/{job_id}/transcript` - Get transcript content (reads from disk)
- `GET /api/jobs/{job_id}/summary` - Get summary content (reads from disk)
- `GET /api/jobs/{job_id}/download/{type}` - Download transcript or summary file
- `GET /api/config` - Get current configuration (without secrets)
- `GET /api/health` - Health check

### Thread Safety
- `jobs_lock` (RLock) protects the jobs dictionary
- `queues_lock` (Lock) protects SSE queue registry
- Helper functions: `get_job()`, `set_job()`, `update_job()`

### SSE Streaming
- Push-based with `asyncio.Queue` (no polling)
- 30-second keepalive comments
- Automatic cleanup on disconnect

## Configuration

Environment variables loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSCRIPTION_ENGINE` | `whisper` | `whisper` or `elevenlabs` |
| `WHISPER_MODEL` | `large-v3` | Whisper model size |
| `ELEVENLABS_API_KEY` | - | Required for ElevenLabs |
| `DEFAULT_LLM` | `claude` | `claude` or `gpt` |
| `ANTHROPIC_API_KEY` | - | Required for Claude |
| `OPENAI_API_KEY` | - | Required for GPT |
| `CLAUDE_MODEL_ID` | `claude-sonnet-4-5` | Claude model |
| `OPENAI_MODEL_ID` | `gpt-4o-mini` | OpenAI model |
| `OUTPUT_DIR` | `./output` | Base output directory |

## Testing

Tests use pytest:
- `tests/test_utils.py` - Utility function tests
- `tests/test_transcriber_scribe_parsing.py` - Scribe response parsing tests

Run tests before making changes to transcription or extraction logic.

## Common Patterns

### Adding a new transcription engine
1. Create a new class extending `BaseTranscriber` in `transcriber.py`
2. Implement `transcribe()` returning `List[Segment]`
3. Add engine to `get_transcriber()` factory function
4. Update CLI choices in `src/main.py`

### Modifying extraction prompts
Edit the prompt constants in `TranscriptExtractor`:
- `EXTRACTION_PROMPT` - Single-pass extraction
- `CHUNK_SUMMARY_PROMPT` - Per-chunk summarization
- `FINAL_SUMMARY_PROMPT` - Final synthesis

### Changing output format
Modify functions in `src/services/markdown_service.py`:
- `create_transcript_markdown()`
- `create_summary_markdown()`

### Adding new configuration
1. Add constant to `src/config.py`
2. Add field to `PipelineConfig` dataclass
3. Update `load_pipeline_config()` to read from environment

## Next.js Frontend (web/)

The frontend is a Next.js 16 application with TypeScript located in the `web/` directory.

### Frontend Architecture
```
web/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with font configuration
│   ├── page.tsx           # Main home page
│   └── globals.css        # Global styles & ATLAS Meridia design tokens
├── src/components/        # React components
│   ├── Header.tsx
│   ├── HeroSection.tsx
│   ├── VideoUrlInput.tsx
│   ├── ProcessingStatus.tsx
│   ├── ResultsViewer.tsx
│   └── ActivityLog.tsx
├── src/lib/              # Utilities & API client
│   ├── api.ts           # Backend API client
│   ├── types.ts         # TypeScript types
│   └── providers.tsx    # React Query provider
├── src/stores/          # Zustand state management
│   └── uiStore.ts
└── src/hooks/           # Custom hooks
    └── useJobStream.ts  # SSE streaming hook
```

### Design System: ATLAS Meridia v3.1

The frontend uses a custom design system with these key colors:
- **Navy scale**: `#08090c` to `#3d4754` (backgrounds)
- **Cream**: `#f8f6f1` (light text)
- **Amber-gold accent**: `#c9924a` (primary accent)
- **Fonts**: Cormorant Garamond (headings), DM Sans (UI), IBM Plex Mono (code)

Design tokens are defined in `web/app/globals.css` using Tailwind v4's `@theme` block.

### Tailwind CSS v4 Configuration

**IMPORTANT**: Tailwind v4 uses CSS-first configuration via `@theme` blocks. Be careful with variable naming:

- Font utilities: Use `--font-*` (e.g., `--font-heading`) → generates `.font-heading` class
- Spacing/width: Do NOT use `--spacing-*` for custom values - this conflicts with Tailwind's width utilities like `max-w-3xl`
  - Instead use non-conflicting names like `--space-*` for custom spacing tokens

Example of correct `@theme` configuration:
```css
@theme inline {
  /* Correct: generates .font-heading utility */
  --font-heading: 'Cormorant Garamond', Georgia, serif;

  /* WRONG: --spacing-3xl would break max-w-3xl */
  /* --spacing-3xl: 96px; */

  /* Correct: use non-conflicting name */
  --space-3xl: 96px;
}
```

### Frontend Environment Variables

| Variable | Location | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | `web/.env.local` | Backend API URL (default: `http://localhost:8000`) |

## Docker Image Details

The Dockerfile (Python 3.11-slim base):
- Installs ffmpeg (required by yt-dlp and chunked transcription)
- Mounts `./output` and `./models` as volumes
- Uses `entrypoint.sh` for CLI mode with environment validation

## Known Limitations

- Whisper transcription is CPU-bound and slow for large models
- Long videos (> 30 min) use chunked transcription which adds overhead
- ElevenLabs Scribe requires API key and internet connection
- LLM extraction costs scale with transcript length
- In-memory job storage (jobs lost on server restart)

## Refactoring Documentation

See `dev/REFACTORING.md` for detailed progress on the codebase refactoring.
