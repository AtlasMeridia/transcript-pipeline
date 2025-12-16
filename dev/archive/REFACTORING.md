# Transcript Pipeline Refactoring Progress

This document tracks the incremental refactoring of the transcript-pipeline codebase for improved efficiency and stability.

## Overview

**Goal**: Redesign for efficiency and stability, supporting both CLI and Web interfaces.

**Approach**:
- Incremental phases with clear stopping points
- In-memory job storage (no persistence)
- No caching (process fresh each time)

---

## Phase 1: Critical Bug Fixes

**Status**: Complete

### 1.1 Create missing `entrypoint.sh`
- **Issue**: Docker CLI mode (`--profile cli`) references non-existent `/app/entrypoint.sh`
- **Fix**: Created `entrypoint.sh` with environment validation and Whisper model pre-download
- **Files**: `entrypoint.sh` (new), `Dockerfile` (updated to copy it)

### 1.2 Wire transcriber factory into `main.py`
- **Issue**: `main.py:122` hardcodes `ElevenLabsTranscriber` via `Transcriber` alias
- **Fix**: Use `get_transcriber()` factory function, respects `TRANSCRIPTION_ENGINE` env var
- **Files**: `src/main.py` (updated imports and `process_video()` function)

### 1.3 Add early API key validation
- **Issue**: API keys not validated until first API call fails
- **Fix**: Added `validate_config()` function with `ConfigurationError` exception
- **Files**: `src/utils.py` (new function), `src/main.py` (calls validation at startup)

---

## Phase 2: Centralized Configuration

**Status**: Complete

### 2.1 Create `src/config.py`
- **New file** with centralized configuration
- `PipelineConfig` dataclass with typed fields
- `load_pipeline_config()` returns typed config
- `load_config()` backward-compatible dict version
- `validate_config()` moved here from utils.py
- `ConfigurationError` exception class

### 2.2 Centralized Constants
All magic numbers now in `src/config.py`:
- `MAX_CHARS_PER_CHUNK = 8000` - LLM chunk size
- `MAX_TOKENS_OUTPUT = 4000` - LLM response limit
- `GPT_TEMPERATURE = 0.3` - GPT temperature setting
- `SEGMENT_GAP_THRESHOLD_SECONDS = 1.2` - Word grouping threshold
- `MAX_FILENAME_LENGTH = 200` - Filename truncation
- `DESCRIPTION_TRUNCATE_LENGTH = 500` - Description truncation
- Model defaults: `DEFAULT_CLAUDE_MODEL`, `DEFAULT_GPT_MODEL`, etc.

### 2.3 Updated Files
- `src/utils.py` - Re-exports from config.py for backward compatibility
- `src/extractor.py` - Uses constants from config.py
- `src/transcriber.py` - Uses `SEGMENT_GAP_THRESHOLD_SECONDS`
- `src/main.py` - Uses `DESCRIPTION_TRUNCATE_LENGTH`

---

## Phase 3: Unified Types

**Status**: Complete

### 3.1 Create `src/models.py`
New file with shared data models:
- `Segment` - Transcription segment with start, end, text
- `TranscriptResult` - Full transcription result with segments and metadata
- `VideoMetadata` - Video information dataclass
- `PipelineResult` - Full pipeline result with paths and content

### 3.2 Update `transcriber.py`
- Import `Segment` from `models.py` (removed local definition)
- Changed `transcribe()` return type: `List[Dict]` → `List[Segment]`
- Updated `format_transcript()` and `get_full_text()` to accept `List[Segment]`
- Use attribute access (`segment.text`) instead of dict access (`segment["text"]`)

### Benefits
- Type-safe data flow through the pipeline
- IDE autocomplete and type checking support
- Clear contracts between components
- `TranscriptResult` provides convenient `.text` and `.formatted` properties

---

## Phase 4: Service Layer

**Status**: Complete

### 4.1 Create `src/services/` Package
New package structure:
- `src/services/__init__.py` - Exports shared functions
- `src/services/markdown_service.py` - Markdown generation
- `src/services/pipeline_service.py` - Core pipeline logic

### 4.2 `markdown_service.py`
Consolidated markdown generation (was duplicated in main.py and server.py):
- `create_transcript_markdown(metadata, transcript)` - Generate transcript markdown
- `create_summary_markdown(metadata, summary)` - Generate summary markdown
- `save_transcript_markdown(...)` - Generate and save to file
- `save_summary_markdown(...)` - Generate and save to file

### 4.3 `pipeline_service.py`
Core pipeline logic shared by CLI and API:
- `process_video(url, llm_type, output_dir, ...)` - Full pipeline function
- `StatusCallback` type alias for progress callbacks
- Returns dict with success, paths, content, metadata, segments, error

### 4.4 Factory Functions
Added factory functions to modules:
- `get_downloader(output_dir)` in `downloader.py`
- `get_extractor(llm_type, api_key, model_id, config)` in `extractor.py`

### 4.5 Updated `main.py`
Simplified CLI to thin wrapper around pipeline service:
- Reduced from ~315 lines to ~138 lines
- Imports `process_video` from services
- CLI just handles argument parsing and output display
- Status callback formats progress for terminal output

### 4.6 Updated `server.py`
Removed duplicate code:
- Imports `create_transcript_markdown`, `create_summary_markdown` from services
- Removed duplicate function definitions
- Keeps async-specific logic for SSE and job status updates

### Benefits
- Single source of truth for markdown generation
- CLI and API share the same core logic
- Easier to test and maintain
- Cleaner separation of concerns

---

## Phase 5: Efficiency Improvements

**Status**: Complete

### 5.1 True SSE Streaming
Replaced 500ms polling with push-based event streaming:
- Added `asyncio.Queue` per SSE connection for instant updates
- `register_sse_queue()` / `unregister_sse_queue()` for connection management
- `broadcast_job_update()` pushes events to all connected clients
- Keepalive comments every 30 seconds to prevent connection timeout
- Added `X-Accel-Buffering: no` header for nginx compatibility

### 5.2 Progress Callbacks
Wired progress callback infrastructure:
- `transcription_progress(current, total, message)` callback in server
- Scales progress from 25-70% during transcription phase
- Granular progress updates (0%, 20%, 25%, 30%, 70%, 75%, 80%, 95%, 100%)
- Ready for Phase 6 chunked transcription to invoke callbacks

### 5.3 Thread-Safe Job Access
Protected concurrent job operations:
- `jobs_lock = threading.RLock()` for job dictionary
- `queues_lock = threading.Lock()` for SSE queue registry
- `get_job()`, `set_job()`, `update_job()` helper functions
- `_update_and_broadcast()` combines update + push atomically

### Benefits
- Near-instant UI updates (vs 500ms polling delay)
- Progress bar infrastructure ready for granular updates
- Safe concurrent access from multiple requests
- Better scalability for multiple simultaneous jobs

---

## Phase 6: Memory Safety

**Status**: Complete

### 6.1 Chunked Whisper Transcription
For audio > 30 minutes, automatically splits into chunks:
- Added constants to `config.py`:
  - `CHUNK_DURATION_SECONDS = 1800` (30 minutes per chunk)
  - `CHUNK_OVERLAP_SECONDS = 5` (overlap for deduplication)
  - `MIN_AUDIO_DURATION_FOR_CHUNKING = 1800` (threshold)
- `_get_audio_duration()` - Uses ffprobe to get audio length
- `_extract_chunk()` - Uses ffmpeg to extract audio segments
- `_transcribe_single()` - Transcribes one chunk
- `_deduplicate_overlap()` - Removes duplicate segments at chunk boundaries
- Progress callbacks invoked per chunk for real-time UI updates
- Temp files cleaned up after each chunk to save disk space

### 6.2 Memory-Efficient Job Storage
Reduced server memory footprint:
- Jobs store file paths only, not content
- Removed `transcript_content` and `summary_content` from job dict
- Updated `JobStatus` model to remove content fields
- `/api/jobs/{job_id}/transcript` reads from disk on demand
- `/api/jobs/{job_id}/summary` reads from disk on demand
- Long transcripts no longer held in memory after processing

### Benefits
- Can process multi-hour videos without memory issues
- Per-chunk progress updates during long transcriptions
- Server memory usage stays constant regardless of transcript size
- Automatic cleanup of temporary chunk files

---

## Phase 7: Documentation & Cleanup

**Status**: Complete

### 7.1 Updated CLAUDE.md
Comprehensive documentation rewrite:
- Added module structure diagram
- Documented new architecture (services, config, models)
- Added API server section with all endpoints
- Added configuration table with defaults
- Updated common patterns for new structure
- Added reference to refactoring documentation

### 7.2 Standardized Logging
Converted all logging to f-string style:
- `src/extractor.py` - Chunk summarization logging
- `src/downloader.py` - Download and cleanup logging
- Consistent formatting across all modules

### 7.3 Added Timing Info
Created `TimedOperation` context manager in `utils.py`:
- Logs operation duration on completion
- Reports timing even on failure
- Configurable log level

Added timing to key operations in `pipeline_service.py`:
- Audio download timing
- Transcription timing (with engine name)
- Extraction timing (with LLM name)
- Total pipeline timing

### Benefits
- Documentation matches current codebase
- Consistent logging style throughout
- Performance visibility for all operations
- Easy to identify slow operations

---

## Refactoring Complete!

All 7 phases have been completed:
1. ✅ Critical Bug Fixes
2. ✅ Centralized Configuration
3. ✅ Unified Types
4. ✅ Service Layer
5. ✅ Efficiency Improvements
6. ✅ Memory Safety
7. ✅ Documentation & Cleanup

---

## Changelog

### 2024-12-08
- **Phase 7 Complete**
  - Rewrote CLAUDE.md with complete architecture documentation
  - Standardized all logging to f-string style
  - Added TimedOperation context manager
  - Added timing to download, transcribe, extract operations
  - All tests passing (13/13)

- **Phase 6 Complete**
  - Implemented chunked Whisper transcription for audio > 30 minutes
  - Uses ffprobe/ffmpeg for audio splitting with 5-second overlap
  - Added deduplication logic for chunk boundaries
  - Memory-efficient job storage (paths only, content read on demand)
  - Updated server endpoints to read files from disk
  - All tests passing (13/13)

- **Phase 5 Complete**
  - Implemented push-based SSE streaming with asyncio.Queue
  - Added thread-safe job access with RLock
  - Wired progress callback infrastructure
  - Updated all server endpoints to use thread-safe access
  - All tests passing (13/13)

- **Phase 4 Complete**
  - Created `src/services/` package with `markdown_service.py` and `pipeline_service.py`
  - Added `get_downloader()` factory to `downloader.py`
  - Added `get_extractor()` factory to `extractor.py`
  - Rewrote `main.py` to use pipeline service (reduced from 315 to 138 lines)
  - Updated `server.py` to use shared markdown functions
  - Removed ~60 lines of duplicate code
  - All tests passing (13/13)

### 2024-12-07
- **Phase 3 Complete**
  - Created `src/models.py` with `Segment`, `TranscriptResult`, `VideoMetadata`, `PipelineResult`
  - Updated `transcriber.py` to return `List[Segment]` instead of `List[Dict]`
  - Type-safe data flow through the pipeline
  - All tests passing (13/13)

- **Phase 2 Complete**
  - Created `src/config.py` with `PipelineConfig` dataclass
  - Centralized all magic numbers as named constants
  - Moved config/validation logic from `utils.py` to `config.py`
  - Updated `extractor.py`, `transcriber.py`, `main.py` to use constants
  - Backward compatibility maintained via re-exports in `utils.py`
  - All tests passing (13/13)

- **Phase 1 Complete**
  - Created `entrypoint.sh` for Docker CLI mode with environment validation
  - Updated `main.py` to use `get_transcriber()` factory (respects `TRANSCRIPTION_ENGINE`)
  - Added `validate_config()` function to `utils.py` with `ConfigurationError` exception
  - Updated `Dockerfile` to copy `entrypoint.sh`
  - All tests passing (13/13)
