# Transcript Pipeline - Web Interface

A web-based interface for the Transcript Pipeline, featuring real-time progress streaming and a distinctive terminal-inspired UI.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  - Industrial/terminal aesthetic                            │
│  - Real-time waveform visualization                         │
│  - Server-Sent Events for live progress                     │
│  - Markdown preview with copy/download                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP + SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Server                            │
│  - POST /api/process      → Start job                       │
│  - GET  /api/jobs/{id}    → Get status                      │
│  - GET  /api/jobs/{id}/stream → SSE progress               │
│  - GET  /api/jobs/{id}/download/{type} → Download file     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Python calls
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Existing Pipeline (unchanged)                  │
│  - VideoDownloader (yt-dlp)                                │
│  - Transcriber (Scribe v2 / Whisper)                       │
│  - TranscriptExtractor (Claude / GPT)                      │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Copy files to your transcript-pipeline directory

Copy these files into your existing `transcript-pipeline/` folder:
- `server.py` → `transcript-pipeline/server.py`
- `requirements.txt` → Update your existing `requirements.txt`
- `docker-compose.yml` → Replace or merge with existing
- `Dockerfile` → Replace existing
- `frontend/` → `transcript-pipeline/frontend/`

### 2. Update environment variables

Your `.env` file should have:
```bash
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here        # Optional
ELEVENLABS_API_KEY=your_key_here    # For Scribe v2
DEFAULT_LLM=claude
WHISPER_MODEL=base
TRANSCRIPTION_ENGINE=scribe
OUTPUT_DIR=/app/output
```

### 3. Build and run with Docker

```bash
# Build the image
docker-compose build

# Start the API server
docker-compose up transcript-api

# Server runs on http://localhost:8000
```

### 4. Open the frontend

Option A: Open `frontend/index.html` directly in your browser

Option B: Serve it with any static server:
```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

## API Endpoints

### Start Processing
```bash
POST /api/process
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=...",
  "whisper_model": "base",      # optional
  "llm_type": "claude",         # optional
  "extract": true               # optional
}

# Returns: { "job_id": "abc123", "status": "pending", ... }
```

### Stream Progress (SSE)
```bash
GET /api/jobs/{job_id}/stream

# Returns Server-Sent Events:
data: {"job_id": "abc123", "status": "downloading", "message": "..."}
data: {"job_id": "abc123", "status": "transcribing", "message": "..."}
data: {"job_id": "abc123", "status": "complete", "transcript_content": "..."}
```

### Download Files
```bash
GET /api/jobs/{job_id}/download/transcript
GET /api/jobs/{job_id}/download/summary
```

### Get Config
```bash
GET /api/config

# Returns: { "whisper_model": "base", "default_llm": "claude", ... }
```

## Development

### Run API locally (without Docker)
```bash
pip install -r requirements.txt
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Run CLI (original functionality preserved)
```bash
# With Docker
docker-compose run --rm --profile cli transcript-pipeline https://youtube.com/watch?v=...

# Without Docker
python -m src.main https://youtube.com/watch?v=...
```

## File Structure

```
transcript-pipeline/
├── server.py                 # FastAPI server (NEW)
├── Dockerfile               # Updated for API server
├── docker-compose.yml       # Updated with API service
├── requirements.txt         # Updated with FastAPI deps
├── .env                     # Your API keys
├── src/
│   ├── main.py             # Original CLI (unchanged)
│   ├── downloader.py       # YouTube download
│   ├── transcriber.py      # Scribe/Whisper
│   ├── extractor.py        # Claude/GPT extraction
│   └── utils.py            # Helpers
├── frontend/
│   ├── index.html          # Standalone test page
│   └── TranscriptPipeline.jsx  # React component
├── output/                  # Generated markdown files
└── models/                  # Whisper model cache
```

## Production Deployment

For production (e.g., Railway):

1. **Environment Variables**: Set all API keys in Railway dashboard
2. **Port**: Railway auto-detects port 8000 from the Dockerfile
3. **Frontend**: Deploy as static site or include in same container
4. **Persistence**: Mount volume for `/app/output` to persist files

### Railway Configuration
```toml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "on-failure"
```

## Troubleshooting

### CORS errors
The API allows all origins by default. For production, update `CORSMiddleware` in `server.py`:
```python
allow_origins=["https://your-frontend-domain.com"]
```

### SSE not working
- Ensure no proxy is buffering responses
- Check that `text/event-stream` content type is preserved

### Jobs disappear after restart
Jobs are stored in memory. For persistence, swap the `jobs` dict for Redis:
```python
import redis
r = redis.Redis()
# Store: r.set(f"job:{job_id}", json.dumps(job))
# Retrieve: json.loads(r.get(f"job:{job_id}"))
```
