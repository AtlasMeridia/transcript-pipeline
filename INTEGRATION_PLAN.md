# Integration Plan: Web Interface for Transcript Pipeline

## Overview

The `files/` directory contains a complete web interface implementation that needs to be integrated into the main transcript-pipeline project. This will add a FastAPI-based web API and React frontend while preserving the existing CLI functionality.

## Current State Assessment

### Existing Project Structure
- **CLI Tool**: Fully functional command-line interface
- **Core Pipeline**: `src/` modules (downloader, transcriber, extractor, utils)
- **Docker Support**: Existing Dockerfile and docker-compose.yml for CLI usage
- **Features**: 
  - Scribe v2 (ElevenLabs) with Whisper fallback
  - Claude/GPT extraction
  - Markdown output generation

### New Files to Integrate
- **`server.py`**: FastAPI server wrapping the pipeline
- **`index.html`**: Standalone HTML frontend (embedded React)
- **`TranscriptPipeline.jsx`**: React component (for reference/alternative builds)
- **Updated Dockerfile**: Supports API server mode
- **Updated docker-compose.yml**: Adds API service alongside CLI
- **Updated requirements.txt**: Adds FastAPI dependencies

## Integration Steps

### Phase 1: Backend Integration 🔧

#### 1.1 Update `server.py` to Match Existing Functionality
**Issues to Fix:**
- Missing `transcription_engine` parameter support (Scribe v2)
- Missing `elevenlabs_api_key` and `scribe_model_id` configuration
- Transcriber initialization doesn't match CLI implementation
- Missing model_id support for Claude/GPT
- Output files going to wrong directories (missing subdirs)
- `/api/config` endpoint missing transcription info

**Actions:**
1. Update `ProcessRequest` model to include `transcription_engine` option
2. Update `process_video_async()` to pass all transcriber parameters
3. Update Transcriber initialization to match `src/main.py` pattern:
   ```python
   # Current (line 157):
   transcriber = Transcriber(model_name=whisper_model, model_dir="./models")
   
   # Should be:
   transcriber = Transcriber(
       model_name=whisper_model,
       model_dir="./models",
       engine=transcription_engine,
       fallback_engine="whisper",
       elevenlabs_api_key=elevenlabs_api_key,
       scribe_model_id=scribe_model_id,
   )
   ```
4. Add `model_id` to TranscriptExtractor initialization:
   ```python
   # Current (line 193):
   extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key)
   
   # Should be:
   model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
   extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)
   ```
5. Fix output directory structure to match CLI:
   ```python
   # Audio directory (line 133):
   # Current:  VideoDownloader(output_dir=output_dir)
   # Fix:      VideoDownloader(output_dir=os.path.join(output_dir, "audio"))
   
   # Transcript path (line 170):
   # Current:  ensure_output_path(output_dir, ...)
   # Fix:      ensure_output_path(os.path.join(output_dir, "transcripts"), ...)
   
   # Summary path (line 204):
   # Current:  ensure_output_path(output_dir, ...)
   # Fix:      ensure_output_path(os.path.join(output_dir, "summaries"), ...)
   ```
6. Update `/api/config` endpoint to include transcription info:
   ```python
   # Add to return dict:
   "transcription_engine": config.get('transcription_engine', 'scribe'),
   "has_elevenlabs_key": bool(config.get('elevenlabs_api_key')),
   ```

#### 1.2 Merge Requirements
**Current state:**
- Main `requirements.txt`: Has `elevenlabs` and `pytest`
- Files `requirements.txt`: Has FastAPI dependencies but missing `elevenlabs`

**Action:**
- Merge both files, ensuring all dependencies are included

**Complete merged requirements.txt:**
```
# Core dependencies
yt-dlp>=2024.0.0
openai-whisper>=20231117
anthropic>=0.18.0
openai>=1.0.0
python-dotenv>=1.0.0
elevenlabs>=1.0.0

# API server dependencies
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.0.0

# Development
pytest>=8.0.0
```

**Critical:** The `elevenlabs` package is required for Scribe v2 transcription to work via the API.

#### 1.3 Update Dockerfile
**Current state:**
- Main Dockerfile: CLI-focused with entrypoint script, has full build dependencies
- Files Dockerfile: API-focused, simpler structure, **missing critical build deps**

**Issues with files/Dockerfile:**
The files/Dockerfile is missing build dependencies required for Whisper:
```dockerfile
# Main Dockerfile has (required):
build-essential
pkg-config
libopenblas-dev
libffi-dev
libssl-dev

# files/Dockerfile only has:
ffmpeg
curl
git
```

**Action:**
- Create unified Dockerfile that supports both modes
- Keep entrypoint script for CLI compatibility
- Add CMD for API server as default
- **Include all build dependencies from main Dockerfile**

**Unified Dockerfile structure:**
```dockerfile
FROM python:3.11-slim

# Install ALL system dependencies (from main Dockerfile)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    pkg-config \
    libopenblas-dev \
    libffi-dev \
    libssl-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY server.py .

RUN mkdir -p /app/output /app/models

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV WHISPER_CACHE_DIR=/app/models

# Create entrypoint for CLI mode
RUN echo '#!/bin/bash\n\
set -e\n\
if [ -z "$(ls -A /app/models)" ]; then\n\
    echo "Downloading Whisper base model to cache..."\n\
    python -c "import whisper; whisper.load_model(\"base\", download_root=\"/app/models\")"\n\
fi\n\
exec python -m src.main "$@"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Default: API server
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 1.4 Update docker-compose.yml
**Current state:**
- Main: Single CLI service with all env vars
- Files: Two services (API + CLI with profiles) but **missing env vars**

**Missing environment variables in files/docker-compose.yml:**
| Variable | In Main | In files/ |
|----------|---------|-----------|
| `CLAUDE_MODEL_ID` | ✅ | ❌ |
| `OPENAI_MODEL_ID` | ✅ | ❌ |
| `SCRIBE_MODEL_ID` | ✅ | ❌ |

**Action:**
- Merge configurations
- Keep CLI service with profile
- Add API service as primary
- **Add all environment variables from main to both services**

**Complete environment block for both services:**
```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
  - DEFAULT_LLM=${DEFAULT_LLM:-claude}
  - CLAUDE_MODEL_ID=${CLAUDE_MODEL_ID:-claude-sonnet-4-5}
  - OPENAI_MODEL_ID=${OPENAI_MODEL_ID:-gpt-4o-mini}
  - WHISPER_MODEL=${WHISPER_MODEL:-base}
  - TRANSCRIPTION_ENGINE=${TRANSCRIPTION_ENGINE:-scribe}
  - SCRIBE_MODEL_ID=${SCRIBE_MODEL_ID:-scribe_v2}
  - OUTPUT_DIR=/app/output
```

### Phase 2: Frontend Setup 📁

#### 2.1 Create Frontend Directory Structure
**Action:**
- Create `frontend/` directory in project root
- Move `index.html` to `frontend/index.html`
- Optionally organize React components if building a full React app

#### 2.2 Update API Base URL Configuration
**Action:**
- Ensure frontend can detect API URL dynamically
- Support both development (localhost:8000) and production environments

### Phase 3: Testing & Validation 🧪

#### 3.1 Verify CLI Still Works
- Test: `docker-compose run --rm --profile cli transcript-pipeline <url>`
- Ensure no breaking changes

#### 3.2 Test API Server
- Start API: `docker-compose up transcript-api`
- Test endpoints: `/api/process`, `/api/jobs/{id}`, `/api/jobs/{id}/stream`
- Verify SSE streaming works

#### 3.3 Test Frontend
- Open `frontend/index.html` in browser
- Test full pipeline: download → transcribe → extract
- Verify real-time progress updates
- Test download functionality

### Phase 4: Documentation & Cleanup 📝

#### 4.1 Update README
- Add web interface section
- Document API endpoints
- Update usage examples

#### 4.2 Clean Up
- Remove `files/` directory after integration
- Update `.gitignore` if needed
- Add any missing environment variables to `.env.example`

## File Mapping

| Source (files/) | Destination | Action |
|----------------|-------------|--------|
| `server.py` | `server.py` (root) | Copy & update |
| `requirements.txt` | `requirements.txt` | Merge |
| `Dockerfile` | `Dockerfile` | Merge/update |
| `docker-compose.yml` | `docker-compose.yml` | Merge |
| `index.html` | `frontend/index.html` | Move |
| `TranscriptPipeline.jsx` | `frontend/TranscriptPipeline.jsx` | Move (optional) |

## Summary of Code Changes Required

### server.py Changes (8 modifications)
1. **Line 58-63**: Add `transcription_engine: Optional[str] = None` to `ProcessRequest`
2. **Line 117**: Add `transcription_engine`, `elevenlabs_api_key`, `scribe_model_id` parameters to function signature
3. **Line 123**: Load transcription config from environment
4. **Line 133**: Change audio output dir to `os.path.join(output_dir, "audio")`
5. **Line 157**: Update Transcriber init with all engine parameters
6. **Line 170**: Change transcript path to `os.path.join(output_dir, "transcripts")`
7. **Line 193**: Add `model_id` parameter to TranscriptExtractor
8. **Line 204**: Change summary path to `os.path.join(output_dir, "summaries")`
9. **Line 397-403**: Add transcription config to `/api/config` response

### requirements.txt Changes
- Add `elevenlabs>=1.0.0` from main
- Add `pytest>=8.0.0` from main

### Dockerfile Changes
- Add build dependencies: `build-essential`, `pkg-config`, `libopenblas-dev`, `libffi-dev`, `libssl-dev`
- Add `WHISPER_CACHE_DIR` env var
- Add entrypoint script for CLI mode

### docker-compose.yml Changes
- Add `CLAUDE_MODEL_ID`, `OPENAI_MODEL_ID`, `SCRIBE_MODEL_ID` to both services

---

## Key Technical Considerations

### 1. Transcriber Configuration
The server must support:
- `transcription_engine`: "scribe" or "whisper"
- `elevenlabs_api_key`: For Scribe v2
- `scribe_model_id`: Model identifier
- `whisper_model`: Fallback model size
- Automatic fallback logic

### 2. Output Directory Structure
Ensure consistency:
```
output/
├── audio/          # Temporary audio files
├── transcripts/    # Transcript markdown files
└── summaries/      # Summary markdown files
```

### 3. Environment Variables
All existing vars must be supported:
- `ELEVENLABS_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `TRANSCRIPTION_ENGINE`
- `SCRIBE_MODEL_ID`
- `DEFAULT_LLM`
- `CLAUDE_MODEL_ID`
- `OPENAI_MODEL_ID`
- `WHISPER_MODEL`
- `OUTPUT_DIR`

### 4. API Request/Response Compatibility
- `ProcessRequest` should accept all CLI options
- Job status should include all metadata
- SSE stream should match frontend expectations

## Risk Assessment

### Low Risk ✅
- Frontend integration (standalone HTML, no build step)
- Requirements merging (straightforward file merge)

### Medium Risk ⚠️
- Server.py updates (must match CLI behavior exactly)
- Transcriber initialization (Scribe v2 support)
- Output path consistency (subdirectory structure)
- Docker configuration (build dependencies critical for Whisper)

### High Risk Items to Watch ⚠️
1. **Scribe v2 via API**: Requires `elevenlabs` in requirements AND proper Transcriber init
2. **Whisper in Docker**: Missing build deps (`libopenblas-dev`, etc.) will cause runtime failures
3. **Model IDs**: Both Transcriber and Extractor need model IDs passed correctly

### Mitigation
- Test each phase independently
- Keep CLI functionality as reference
- Verify transcriber behavior matches CLI
- **Test Scribe v2 transcription via API specifically**
- **Test Docker build and Whisper fallback**

## Success Criteria

1. ⬜ CLI functionality unchanged
2. ⬜ API server starts and processes videos
3. ⬜ Frontend connects to API and displays progress
4. ⬜ SSE streaming works in real-time
5. ⬜ All transcription engines work (Scribe + Whisper fallback)
6. ⬜ All LLM options work (Claude + GPT)
7. ⬜ Output files match CLI format (correct subdirectories)
8. ⬜ Docker compose supports both modes
9. ⬜ Model IDs passed correctly to extractors

## Next Steps

1. Review and approve this plan
2. Execute Phase 1 (Backend Integration)
3. Execute Phase 2 (Frontend Setup)
4. Execute Phase 3 (Testing)
5. Execute Phase 4 (Documentation)

---

**Estimated Time**: 2-3 hours for full integration (including testing)
**Dependencies**: None (all files are self-contained)
**Breaking Changes**: None expected (additive only)

**Revision History:**
- Initial plan created
- Revised to add: specific code fixes, missing dependencies, Dockerfile build deps, docker-compose env vars

