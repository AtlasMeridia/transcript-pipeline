"""
FastAPI server for the Transcript Pipeline.
Provides REST API endpoints with Server-Sent Events for real-time progress.
"""

import asyncio
import json
import os
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, AsyncGenerator, Set
import io

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, sanitize_filename, ensure_output_path, format_duration
from src.downloader import VideoDownloader
from src.transcriber import get_transcriber, CaptionTranscriber, CaptionsUnavailableError
from src.extractor import TranscriptExtractor
from src.services import create_transcript_markdown, create_summary_markdown


# ============================================================================
# App Configuration
# ============================================================================

app = FastAPI(
    title="Transcript Pipeline API",
    description="Extract transcripts and insights from YouTube videos",
    version="1.0.0"
)

# CORS for frontend
# Allow origins from environment variable, default to "*" for development
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
if allowed_origins == ["*"]:
    # Development mode: allow all origins
    cors_origins = ["*"]
else:
    # Production mode: specific origins
    cors_origins = [origin.strip() for origin in allowed_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage with thread-safe access
jobs: Dict[str, dict] = {}
jobs_lock = threading.RLock()

# SSE event queues for real-time streaming (job_id -> set of queues)
job_event_queues: Dict[str, Set[asyncio.Queue]] = {}
queues_lock = threading.Lock()


# ============================================================================
# Models
# ============================================================================

class ProcessRequest(BaseModel):
    url: str
    llm_type: Optional[str] = None
    extract: bool = True


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, downloading, transcribing, extracting, complete, error
    phase: Optional[str] = None
    progress: Optional[int] = None
    message: Optional[str] = None
    metadata: Optional[dict] = None
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    # Note: content is read from disk on demand via /transcript and /summary endpoints
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ============================================================================
# Thread-Safe Job Access
# ============================================================================

def get_job(job_id: str) -> Optional[dict]:
    """Thread-safe job retrieval."""
    with jobs_lock:
        return jobs.get(job_id)


def set_job(job_id: str, job: dict) -> None:
    """Thread-safe job creation/update."""
    with jobs_lock:
        jobs[job_id] = job


def update_job(job_id: str, **updates) -> Optional[dict]:
    """Thread-safe job field updates. Returns updated job or None if not found."""
    with jobs_lock:
        if job_id not in jobs:
            return None
        jobs[job_id].update(updates)
        return jobs[job_id].copy()


# ============================================================================
# SSE Event Broadcasting
# ============================================================================

def broadcast_job_update(job_id: str, job_data: dict) -> None:
    """
    Push job update to all connected SSE clients for this job.
    This is called from the processing thread and schedules async queue puts.
    """
    with queues_lock:
        queues = job_event_queues.get(job_id, set())
        for queue in queues:
            try:
                # Use call_soon_threadsafe to schedule from sync context
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(queue.put_nowait, job_data)
            except RuntimeError:
                # Event loop not running, skip
                pass
            except asyncio.QueueFull:
                # Queue full, skip this update
                pass


def register_sse_queue(job_id: str, queue: asyncio.Queue) -> None:
    """Register an SSE queue for a job."""
    with queues_lock:
        if job_id not in job_event_queues:
            job_event_queues[job_id] = set()
        job_event_queues[job_id].add(queue)


def unregister_sse_queue(job_id: str, queue: asyncio.Queue) -> None:
    """Unregister an SSE queue for a job."""
    with queues_lock:
        if job_id in job_event_queues:
            job_event_queues[job_id].discard(queue)
            if not job_event_queues[job_id]:
                del job_event_queues[job_id]


# ============================================================================
# Pipeline Processing
# ============================================================================

def _update_and_broadcast(job_id: str, **updates) -> None:
    """Helper to update job and broadcast to SSE clients."""
    job = update_job(job_id, **updates)
    if job:
        broadcast_job_update(job_id, job)


async def process_video_async(job_id: str, url: str, llm_type: str, extract: bool):
    """
    Process a video asynchronously, updating job status as we go.
    Uses thread-safe job updates and broadcasts events to SSE clients.

    Implements caption-first strategy: tries YouTube auto-captions first,
    falls back to audio transcription if captions are unavailable.
    """
    config = load_config()
    output_dir = config.get('output_dir', './output')

    # Get transcription configuration
    transcription_engine = config.get('transcription_engine', 'auto')
    mlx_model = config.get('mlx_whisper_model', 'large-v3-turbo')
    caption_language = config.get('caption_language', 'en')

    loop = asyncio.get_running_loop()
    audio_dir = os.path.join(output_dir, "audio")
    downloader = VideoDownloader(output_dir=audio_dir)

    audio_path = None  # Track if we downloaded audio (for cleanup)
    segments = []
    metadata = None
    transcriber = None

    try:
        # ----------------------------------------------------------------
        # Step 1: Get transcript (captions-first if engine is 'auto')
        # ----------------------------------------------------------------

        if transcription_engine == 'auto':
            # Try captions first (faster, no audio download needed)
            _update_and_broadcast(job_id,
                status='downloading',
                phase='download',
                message='Checking for YouTube captions...',
                progress=5
            )

            try:
                # Get metadata first
                metadata = await loop.run_in_executor(
                    None, downloader.get_video_info, url
                )

                job_metadata = {
                    'title': metadata['title'],
                    'author': metadata['author'],
                    'date': metadata['upload_date'],
                    'duration': format_duration(metadata['duration']),
                    'url': metadata['url'],
                }
                _update_and_broadcast(job_id,
                    metadata=job_metadata,
                    message=f"Found: {metadata['title']}",
                    progress=10
                )

                _update_and_broadcast(job_id,
                    status='transcribing',
                    phase='transcribing',
                    message='Extracting YouTube captions...',
                    progress=15
                )

                caption_transcriber = CaptionTranscriber(
                    output_dir=output_dir,
                    language=caption_language,
                )

                # Extract captions
                segments = await loop.run_in_executor(
                    None,
                    lambda: caption_transcriber.transcribe(audio_path="", url=url)
                )

                transcriber = caption_transcriber
                _update_and_broadcast(job_id,
                    message=f'Captions extracted ({len(segments)} segments)',
                    progress=70
                )

            except CaptionsUnavailableError as e:
                # Fall back to audio transcription
                _update_and_broadcast(job_id,
                    status='downloading',
                    phase='download',
                    message='Captions unavailable, downloading audio...',
                    progress=15
                )

                audio_path, metadata = await loop.run_in_executor(
                    None, downloader.download_audio, url
                )

                job_metadata = {
                    'title': metadata['title'],
                    'author': metadata['author'],
                    'date': metadata['upload_date'],
                    'duration': format_duration(metadata['duration']),
                    'url': metadata['url'],
                }
                _update_and_broadcast(job_id,
                    metadata=job_metadata,
                    message=f"Downloaded: {metadata['title']}",
                    progress=20
                )

                # Use fallback engine
                fallback_engine = config.get('caption_fallback_engine', 'mlx-whisper')
                _update_and_broadcast(job_id,
                    status='transcribing',
                    phase='transcribing',
                    message=f'Transcribing with {fallback_engine}...',
                    progress=25
                )

                transcriber = get_transcriber(
                    engine=fallback_engine,
                    model=mlx_model,
                )

                def transcription_progress(current: int, total: int, message: str = None):
                    if total > 0:
                        pct = int(25 + (current / total) * 45)
                        msg = message or f'Transcribing... ({current}/{total})'
                    else:
                        pct = 30
                        msg = message or f'Transcribing with {transcriber.engine_name}...'
                    _update_and_broadcast(job_id, progress=pct, message=msg)

                segments = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe(audio_path, progress_callback=transcription_progress)
                )

                _update_and_broadcast(job_id,
                    message=f'Transcription complete ({len(segments)} segments)',
                    progress=70
                )

        else:
            # Explicit engine specified
            _update_and_broadcast(job_id,
                status='downloading',
                phase='download',
                message='Fetching video metadata...',
                progress=0
            )

            if transcription_engine == 'captions':
                # Captions-only mode
                metadata = await loop.run_in_executor(
                    None, downloader.get_video_info, url
                )

                job_metadata = {
                    'title': metadata['title'],
                    'author': metadata['author'],
                    'date': metadata['upload_date'],
                    'duration': format_duration(metadata['duration']),
                    'url': metadata['url'],
                }
                _update_and_broadcast(job_id,
                    metadata=job_metadata,
                    message=f"Found: {metadata['title']}",
                    progress=10
                )

                _update_and_broadcast(job_id,
                    status='transcribing',
                    phase='transcribing',
                    message='Extracting YouTube captions...',
                    progress=15
                )

                transcriber = get_transcriber(
                    engine='captions',
                    output_dir=output_dir,
                    language=caption_language,
                )

                segments = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe(audio_path="", url=url)
                )

                _update_and_broadcast(job_id,
                    message=f'Captions extracted ({len(segments)} segments)',
                    progress=70
                )

            else:
                # Audio-based transcription
                audio_path, metadata = await loop.run_in_executor(
                    None, downloader.download_audio, url
                )

                job_metadata = {
                    'title': metadata['title'],
                    'author': metadata['author'],
                    'date': metadata['upload_date'],
                    'duration': format_duration(metadata['duration']),
                    'url': metadata['url'],
                }
                _update_and_broadcast(job_id,
                    metadata=job_metadata,
                    message=f"Downloaded: {metadata['title']}",
                    progress=20
                )

                _update_and_broadcast(job_id,
                    status='transcribing',
                    phase='transcribing',
                    message='Initializing transcription...',
                    progress=25
                )

                transcriber = get_transcriber(
                    engine=transcription_engine,
                    model=mlx_model,
                )

                def transcription_progress(current: int, total: int, message: str = None):
                    if total > 0:
                        pct = int(25 + (current / total) * 45)
                        msg = message or f'Transcribing... ({current}/{total})'
                    else:
                        pct = 30
                        msg = message or f'Transcribing with {transcriber.engine_name}...'
                    _update_and_broadcast(job_id, progress=pct, message=msg)

                _update_and_broadcast(job_id,
                    message=f'Transcribing audio with {transcriber.engine_name}...',
                    progress=30
                )

                segments = await loop.run_in_executor(
                    None,
                    lambda: transcriber.transcribe(audio_path, progress_callback=transcription_progress)
                )

                _update_and_broadcast(job_id,
                    message=f'Transcription complete ({len(segments)} segments)',
                    progress=70
                )

        # ----------------------------------------------------------------
        # Step 2: Save transcript
        # ----------------------------------------------------------------
        transcript_with_timestamps = transcriber.format_transcript(segments, include_timestamps=True)
        transcript_content = create_transcript_markdown(metadata, transcript_with_timestamps)

        date_prefix = datetime.now().strftime('%Y-%m-%d')
        filename_base = f"{date_prefix} {sanitize_filename(metadata['title'])}"
        transcript_output_dir = os.path.join(output_dir, "transcripts")
        transcript_path = ensure_output_path(transcript_output_dir, f"{filename_base}-transcript.md")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_content)

        _update_and_broadcast(job_id,
            transcript_path=str(transcript_path),
            progress=70
        )

        # ----------------------------------------------------------------
        # Step 3: Extract (optional)
        # ----------------------------------------------------------------
        if extract:
            _update_and_broadcast(job_id,
                status='extracting',
                phase='extracting',
                message=f'Sending to {llm_type.upper()} for analysis...',
                progress=75
            )

            if llm_type == "claude":
                api_key = config.get('anthropic_api_key')
            else:
                api_key = config.get('openai_api_key')

            if api_key:
                model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
                extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)
                full_text = transcriber.get_full_text(segments)

                _update_and_broadcast(job_id,
                    message='Extracting key insights...',
                    progress=80
                )

                summary = await loop.run_in_executor(
                    None, extractor.extract, full_text, metadata
                )

                summary_content = create_summary_markdown(metadata, summary)

                summary_output_dir = os.path.join(output_dir, "summaries")
                summary_path = ensure_output_path(summary_output_dir, f"{filename_base}-summary.md")
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary_content)

                _update_and_broadcast(job_id,
                    summary_path=str(summary_path),
                    message='Extraction complete',
                    progress=95
                )
            else:
                _update_and_broadcast(job_id,
                    message=f'Skipped extraction: {llm_type.upper()} API key not found',
                    progress=95
                )

        # ----------------------------------------------------------------
        # Cleanup and complete
        # ----------------------------------------------------------------
        if audio_path:
            await loop.run_in_executor(None, downloader.cleanup_audio, audio_path)

        _update_and_broadcast(job_id,
            status='complete',
            phase='complete',
            message='Pipeline complete',
            progress=100,
            completed_at=datetime.now().isoformat()
        )

    except Exception as e:
        _update_and_broadcast(job_id,
            status='error',
            error=str(e),
            message=f'Error: {str(e)}',
            completed_at=datetime.now().isoformat()
        )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the frontend HTML."""
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return {"error": "Frontend not found"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "service": "Transcript Pipeline API",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.post("/api/process", response_model=JobStatus)
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Start processing a YouTube video.
    Returns a job ID that can be used to track progress.
    """
    config = load_config()

    # Create job with thread-safe access
    job_id = str(uuid.uuid4())[:8]
    llm_type = request.llm_type or config.get('default_llm', 'claude')

    job = {
        'job_id': job_id,
        'status': 'pending',
        'phase': None,
        'progress': 0,
        'message': 'Job queued',
        'metadata': None,
        'transcript_path': None,
        'summary_path': None,
        # Note: content is read from disk on demand, not stored in job
        'error': None,
        'created_at': datetime.now().isoformat(),
        'completed_at': None,
    }
    set_job(job_id, job)

    # Start processing in background
    background_tasks.add_task(
        process_video_async,
        job_id,
        request.url,
        llm_type,
        request.extract
    )

    return JobStatus(**job)


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the current status of a processing job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    """
    Stream job status updates via Server-Sent Events.
    Connect to this endpoint to receive real-time progress updates.
    Uses push-based streaming via asyncio.Queue for near-instant updates.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Create a queue for this SSE connection
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        register_sse_queue(job_id, queue)

        try:
            # Send initial state immediately
            current_job = get_job(job_id)
            if current_job:
                yield f"data: {json.dumps(current_job)}\n\n"

                # If already complete, stop
                if current_job['status'] in ('complete', 'error'):
                    return

            # Wait for pushed updates
            while True:
                try:
                    # Wait for next update with timeout
                    job_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(job_data)}\n\n"

                    # Stop streaming when job is complete or errored
                    if job_data.get('status') in ('complete', 'error'):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"

                    # Check if job still exists
                    current_job = get_job(job_id)
                    if not current_job or current_job['status'] in ('complete', 'error'):
                        break
        finally:
            unregister_sse_queue(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.get("/api/jobs/{job_id}/transcript")
async def get_transcript(job_id: str):
    """Get the transcript content for a completed job.

    Content is read from disk on demand for memory efficiency.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    transcript_path = job.get('transcript_path')
    if not transcript_path or not Path(transcript_path).exists():
        raise HTTPException(status_code=404, detail="Transcript not available")

    # Read from disk on demand
    try:
        content = Path(transcript_path).read_text(encoding='utf-8')
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript: {e}")

    return {
        "content": content,
        "path": transcript_path,
    }


@app.get("/api/jobs/{job_id}/summary")
async def get_summary(job_id: str):
    """Get the summary content for a completed job.

    Content is read from disk on demand for memory efficiency.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    summary_path = job.get('summary_path')
    if not summary_path or not Path(summary_path).exists():
        raise HTTPException(status_code=404, detail="Summary not available")

    # Read from disk on demand
    try:
        content = Path(summary_path).read_text(encoding='utf-8')
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read summary: {e}")

    return {
        "content": content,
        "path": summary_path,
    }


@app.get("/api/jobs/{job_id}/download/{file_type}")
async def download_file(job_id: str, file_type: str):
    """Download the transcript or summary file."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if file_type == "transcript":
        path = job.get('transcript_path')
    elif file_type == "summary":
        path = job.get('summary_path')
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")

    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="text/markdown",
        filename=Path(path).name
    )


@app.get("/api/config")
async def get_config():
    """Get current pipeline configuration (without sensitive data)."""
    config = load_config()
    transcription_engine = config.get('transcription_engine', 'auto')
    
    return {
        "default_llm": config.get('default_llm', 'claude'),
        "output_dir": config.get('output_dir', './output'),
        "has_anthropic_key": bool(config.get('anthropic_api_key')),
        "has_openai_key": bool(config.get('openai_api_key')),
        # Transcription configuration
        "transcription_engine": transcription_engine,
        "mlx_whisper_model": config.get('mlx_whisper_model', 'large-v3-turbo'),
    }


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
