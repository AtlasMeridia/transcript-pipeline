"""
FastAPI server for the Transcript Pipeline.
Provides REST API endpoints with Server-Sent Events for real-time progress.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator
from contextlib import redirect_stdout, redirect_stderr
import io

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, HttpUrl

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import load_config, sanitize_filename, ensure_output_path, format_duration
from src.downloader import VideoDownloader
from src.transcriber import Transcriber
from src.extractor import TranscriptExtractor


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

# In-memory job storage (use Redis in production)
jobs: dict = {}


# ============================================================================
# Models
# ============================================================================

class ProcessRequest(BaseModel):
    url: str
    whisper_model: Optional[str] = None
    llm_type: Optional[str] = None
    transcription_engine: Optional[str] = None
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
    transcript_content: Optional[str] = None
    summary_content: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ============================================================================
# Pipeline Processing
# ============================================================================

def create_transcript_markdown(metadata: dict, transcript: str) -> str:
    """Generate transcript markdown content."""
    return f"""# {metadata['title']}

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**URL**: {metadata['url']}
**Duration**: {format_duration(metadata['duration'])}

## Description
{metadata['description'][:500]}{'...' if len(metadata['description']) > 500 else ''}

## Transcript

{transcript}
"""


def create_summary_markdown(metadata: dict, summary: str) -> str:
    """Generate summary markdown content."""
    return f"""# {metadata['title']} - Summary

**Author**: {metadata['author']}
**Date**: {metadata['upload_date']}
**Processed**: {datetime.now().strftime('%Y-%m-%d')}

---

{summary}
"""


async def process_video_async(job_id: str, url: str, whisper_model: str, llm_type: str, transcription_engine: str, extract: bool):
    """
    Process a video asynchronously, updating job status as we go.
    """
    job = jobs[job_id]
    config = load_config()
    output_dir = config.get('output_dir', './output')
    
    # Get transcription configuration
    elevenlabs_api_key = config.get('elevenlabs_api_key')
    scribe_model_id = config.get('scribe_model_id', 'scribe_v2')
    
    try:
        # ----------------------------------------------------------------
        # Step 1: Download
        # ----------------------------------------------------------------
        job['status'] = 'downloading'
        job['phase'] = 'download'
        job['message'] = 'Fetching video metadata...'
        
        # Audio files go to audio subdirectory
        audio_dir = os.path.join(output_dir, "audio")
        downloader = VideoDownloader(output_dir=audio_dir)
        
        # Run blocking download in thread pool
        loop = asyncio.get_running_loop()
        audio_path, metadata = await loop.run_in_executor(
            None, downloader.download_audio, url
        )
        
        job['metadata'] = {
            'title': metadata['title'],
            'author': metadata['author'],
            'date': metadata['upload_date'],
            'duration': format_duration(metadata['duration']),
            'url': metadata['url'],
        }
        job['message'] = f"Downloaded: {metadata['title']}"
        
        # ----------------------------------------------------------------
        # Step 2: Transcribe
        # ----------------------------------------------------------------
        job['status'] = 'transcribing'
        job['phase'] = 'transcribing'
        job['message'] = 'Initializing transcription...'
        
        transcriber = Transcriber(
            model_name=whisper_model,
            model_dir="./models",
            engine=transcription_engine,
            fallback_engine="whisper",
            elevenlabs_api_key=elevenlabs_api_key,
            scribe_model_id=scribe_model_id,
        )
        
        job['message'] = 'Transcribing audio...'
        segments = await loop.run_in_executor(
            None, transcriber.transcribe, audio_path
        )
        
        # Format transcript
        transcript_with_timestamps = transcriber.format_transcript(segments, include_timestamps=True)
        transcript_content = create_transcript_markdown(metadata, transcript_with_timestamps)
        
        # Save transcript file (in transcripts subdirectory)
        filename_base = sanitize_filename(metadata['title'])
        transcript_output_dir = os.path.join(output_dir, "transcripts")
        transcript_path = ensure_output_path(transcript_output_dir, f"{filename_base}-transcript.md")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_content)
        
        job['transcript_path'] = str(transcript_path)
        job['transcript_content'] = transcript_content
        job['message'] = f"Transcription complete ({len(segments)} segments)"
        
        # ----------------------------------------------------------------
        # Step 3: Extract (optional)
        # ----------------------------------------------------------------
        if extract:
            job['status'] = 'extracting'
            job['phase'] = 'extracting'
            job['message'] = 'Sending to Claude for analysis...'
            
            # Get API key
            if llm_type == "claude":
                api_key = config.get('anthropic_api_key')
            else:
                api_key = config.get('openai_api_key')
            
            if api_key:
                model_id = config.get('claude_model_id') if llm_type == "claude" else config.get('openai_model_id')
                extractor = TranscriptExtractor(llm_type=llm_type, api_key=api_key, model_id=model_id)
                full_text = transcriber.get_full_text(segments)
                
                job['message'] = 'Extracting key insights...'
                summary = await loop.run_in_executor(
                    None, extractor.extract, full_text, metadata
                )
                
                summary_content = create_summary_markdown(metadata, summary)
                
                # Save summary file (in summaries subdirectory)
                summary_output_dir = os.path.join(output_dir, "summaries")
                summary_path = ensure_output_path(summary_output_dir, f"{filename_base}-summary.md")
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary_content)
                
                job['summary_path'] = str(summary_path)
                job['summary_content'] = summary_content
                job['message'] = 'Extraction complete'
            else:
                job['message'] = f'Skipped extraction: {llm_type.upper()} API key not found'
        
        # ----------------------------------------------------------------
        # Cleanup and complete
        # ----------------------------------------------------------------
        await loop.run_in_executor(None, downloader.cleanup_audio, audio_path)
        
        job['status'] = 'complete'
        job['phase'] = 'complete'
        job['message'] = 'Pipeline complete'
        job['completed_at'] = datetime.now().isoformat()
        
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        job['message'] = f'Error: {str(e)}'
        job['completed_at'] = datetime.now().isoformat()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
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
    
    # Create job
    job_id = str(uuid.uuid4())[:8]
    whisper_model = request.whisper_model or config.get('whisper_model', 'base')
    llm_type = request.llm_type or config.get('default_llm', 'claude')
    transcription_engine = request.transcription_engine or config.get('transcription_engine', 'scribe')
    
    jobs[job_id] = {
        'job_id': job_id,
        'status': 'pending',
        'phase': None,
        'progress': 0,
        'message': 'Job queued',
        'metadata': None,
        'transcript_path': None,
        'summary_path': None,
        'transcript_content': None,
        'summary_content': None,
        'error': None,
        'created_at': datetime.now().isoformat(),
        'completed_at': None,
    }
    
    # Start processing in background
    background_tasks.add_task(
        process_video_async,
        job_id,
        request.url,
        whisper_model,
        llm_type,
        transcription_engine,
        request.extract
    )
    
    return JobStatus(**jobs[job_id])


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the current status of a processing job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**jobs[job_id])


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    """
    Stream job status updates via Server-Sent Events.
    Connect to this endpoint to receive real-time progress updates.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        last_status = None
        last_message = None
        
        while True:
            job = jobs.get(job_id)
            if not job:
                break
            
            # Send update if status or message changed
            current_state = (job['status'], job['message'])
            if current_state != (last_status, last_message):
                last_status, last_message = current_state
                data = json.dumps(job)
                yield f"data: {data}\n\n"
            
            # Stop streaming when job is complete or errored
            if job['status'] in ('complete', 'error'):
                break
            
            await asyncio.sleep(0.5)  # Poll every 500ms
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/jobs/{job_id}/transcript")
async def get_transcript(job_id: str):
    """Get the transcript content for a completed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if not job.get('transcript_content'):
        raise HTTPException(status_code=404, detail="Transcript not available")
    
    return {
        "content": job['transcript_content'],
        "path": job['transcript_path'],
    }


@app.get("/api/jobs/{job_id}/summary")
async def get_summary(job_id: str):
    """Get the summary content for a completed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if not job.get('summary_content'):
        raise HTTPException(status_code=404, detail="Summary not available")
    
    return {
        "content": job['summary_content'],
        "path": job['summary_path'],
    }


@app.get("/api/jobs/{job_id}/download/{file_type}")
async def download_file(job_id: str, file_type: str):
    """Download the transcript or summary file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
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
    return {
        "whisper_model": config.get('whisper_model', 'base'),
        "default_llm": config.get('default_llm', 'claude'),
        "output_dir": config.get('output_dir', './output'),
        "has_anthropic_key": bool(config.get('anthropic_api_key')),
        "has_openai_key": bool(config.get('openai_api_key')),
        "transcription_engine": config.get('transcription_engine', 'scribe'),
        "has_elevenlabs_key": bool(config.get('elevenlabs_api_key')),
    }


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
