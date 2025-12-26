"""
FastAPI server for the Transcript Pipeline.
Provides REST API endpoints with Server-Sent Events for real-time progress.
"""

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, AsyncGenerator, Set
import io

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config
from src.services import process_video, ProgressUpdate


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

# Job TTL configuration
COMPLETED_JOB_TTL_HOURS = int(os.getenv("JOB_TTL_HOURS", "24"))
JOB_CLEANUP_INTERVAL_MINUTES = 30


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
# Job TTL Cleanup
# ============================================================================

def cleanup_expired_jobs() -> int:
    """
    Remove completed/errored jobs older than TTL.
    Returns number of jobs removed.
    """
    if COMPLETED_JOB_TTL_HOURS <= 0:
        return 0  # TTL disabled

    cutoff = datetime.now() - timedelta(hours=COMPLETED_JOB_TTL_HOURS)
    expired_ids = []

    with jobs_lock:
        for job_id, job in jobs.items():
            # Only clean up terminal states
            if job.get('status') not in ('complete', 'error'):
                continue

            # Check completed_at timestamp
            completed_at = job.get('completed_at')
            if completed_at:
                try:
                    completed_time = datetime.fromisoformat(completed_at)
                    if completed_time < cutoff:
                        expired_ids.append(job_id)
                except (ValueError, TypeError):
                    pass  # Invalid timestamp, skip

        # Remove expired jobs
        for job_id in expired_ids:
            del jobs[job_id]

    if expired_ids:
        logger.info(f"Cleaned up {len(expired_ids)} expired jobs (TTL: {COMPLETED_JOB_TTL_HOURS}h)")

    return len(expired_ids)


async def job_cleanup_task():
    """Background task that periodically cleans up expired jobs."""
    logger.info(f"Job cleanup task started (interval: {JOB_CLEANUP_INTERVAL_MINUTES}m, TTL: {COMPLETED_JOB_TTL_HOURS}h)")
    while True:
        await asyncio.sleep(JOB_CLEANUP_INTERVAL_MINUTES * 60)
        try:
            cleanup_expired_jobs()
        except Exception as e:
            logger.error(f"Job cleanup error: {e}")


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

    This is a thin wrapper around process_video() from pipeline_service that:
    - Runs the synchronous pipeline in a thread pool executor
    - Translates progress callbacks to SSE broadcasts
    """
    config = load_config()
    loop = asyncio.get_running_loop()

    def progress_callback(update: ProgressUpdate):
        """Translate pipeline progress to job updates and SSE broadcasts."""
        updates = {
            'status': update.status,
            'phase': update.phase,
            'message': update.message,
        }
        if update.progress is not None:
            updates['progress'] = update.progress
        if update.metadata is not None:
            updates['metadata'] = update.metadata
        if update.status in ('complete', 'error'):
            updates['completed_at'] = datetime.now().isoformat()

        _update_and_broadcast(job_id, **updates)

    def run_pipeline():
        """Run the pipeline with progress callback."""
        date_prefix = datetime.now().strftime('%Y-%m-%d')

        result = process_video(
            url=url,
            llm_type=llm_type,
            no_extract=not extract,
            config=config,
            progress_callback=progress_callback,
            filename_prefix=date_prefix,
        )
        return result

    try:
        result = await loop.run_in_executor(None, run_pipeline)

        # Update job with final paths
        final_updates = {}
        if result.get('transcript_path'):
            final_updates['transcript_path'] = result['transcript_path']
        if result.get('summary_path'):
            final_updates['summary_path'] = result['summary_path']

        if result.get('success'):
            final_updates.update(
                status='complete',
                phase='complete',
                progress=100,
                completed_at=datetime.now().isoformat()
            )
        elif result.get('error'):
            final_updates.update(
                status='error',
                error=result['error'],
                message=f"Error: {result['error']}",
                completed_at=datetime.now().isoformat()
            )

        if final_updates:
            _update_and_broadcast(job_id, **final_updates)

    except Exception as e:
        _update_and_broadcast(job_id,
            status='error',
            error=str(e),
            message=f'Error: {str(e)}',
            completed_at=datetime.now().isoformat()
        )


# ============================================================================
# Application Lifecycle
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    asyncio.create_task(job_cleanup_task())


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
    with jobs_lock:
        job_count = len(jobs)
        completed_count = sum(1 for j in jobs.values() if j.get('status') == 'complete')
        error_count = sum(1 for j in jobs.values() if j.get('status') == 'error')
        active_count = job_count - completed_count - error_count

    return {
        "service": "Transcript Pipeline API",
        "version": "1.0.0",
        "status": "healthy",
        "jobs": {
            "total": job_count,
            "active": active_count,
            "completed": completed_count,
            "errored": error_count,
        },
        "job_ttl_hours": COMPLETED_JOB_TTL_HOURS,
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
