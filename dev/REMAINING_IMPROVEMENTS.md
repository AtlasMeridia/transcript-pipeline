# Remaining Improvements for Transcript Pipeline

This document lists the remaining improvements to be implemented. A previous session completed items 1-5; items 6-8 remain.

## Completed Improvements

### 1. API Timeout Specifications (DONE)
- Added `API_TIMEOUT_SECONDS = 120` to `src/config.py`
- Updated `src/extractor.py` to pass `timeout` parameter to both Claude and OpenAI API calls
- Prevents indefinite hanging on slow API responses

### 2. Specific Exception Handling (DONE)
- Replaced broad `exceptions=(Exception,)` in retry logic with specific exceptions:
  - Claude: `(APIError, APIConnectionError, RateLimitError, APITimeoutError)`
  - OpenAI: `(OpenAIError, OpenAIConnectionError, OpenAIRateLimitError)`
- Better error diagnosis and prevents catching unrelated exceptions

### 3. Config Loading (DONE - No Changes Needed)
- Reviewed `src/config.py` - already well-structured
- `load_config()` wraps `load_pipeline_config()` for backward compatibility
- This is the correct pattern, no changes required

### 4. Version Pinned Dependencies (DONE)
- Updated `requirements.txt` with exact versions:
  - yt-dlp==2025.5.22
  - anthropic==0.75.0
  - openai==1.95.0
  - python-dotenv==1.1.1
  - fastapi==0.123.0
  - uvicorn[standard]==0.35.0
  - pydantic==2.11.7
  - pytest==9.0.1

### 5. Environment Example File (DONE)
- Created `.env.example` with all configuration options documented

---

## Remaining Improvements

### 6. OpenAPI/Swagger Documentation Enhancement

**Location:** `server.py`

**Current State:** FastAPI auto-generates basic OpenAPI docs at `/docs`, but they lack detailed descriptions.

**Changes Required:**

1. Add detailed descriptions to the FastAPI app initialization:
```python
app = FastAPI(
    title="Transcript Pipeline API",
    description="""
## Overview
Extract transcripts and AI-powered insights from YouTube videos.

## Features
- Download and transcribe YouTube videos
- Extract key insights using Claude or GPT
- Real-time progress via Server-Sent Events
- Download transcripts and summaries as Markdown

## Authentication
No authentication required for local development.
Configure CORS_ORIGINS for production deployment.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

2. Add response models and examples to endpoints:
```python
from pydantic import Field

class ProcessRequest(BaseModel):
    url: str = Field(..., example="https://www.youtube.com/watch?v=dQw4w9WgXcQ", description="YouTube video URL")
    llm_type: Optional[str] = Field(None, example="claude", description="LLM to use: 'claude' or 'gpt'")
    extract: bool = Field(True, description="Whether to run AI extraction on transcript")
```

3. Add tags to organize endpoints:
```python
@app.post("/api/process", response_model=JobStatus, tags=["Jobs"])
@app.get("/api/jobs/{job_id}", response_model=JobStatus, tags=["Jobs"])
@app.get("/api/health", tags=["System"])
@app.get("/api/config", tags=["System"])
```

---

### 7. React Error Boundary Component

**Location:** Create `web/src/components/ErrorBoundary.tsx`

**Purpose:** Catch JavaScript errors in React component tree and display fallback UI instead of crashing.

**Implementation:**

```tsx
// web/src/components/ErrorBoundary.tsx
'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[200px] flex items-center justify-center p-8">
          <div className="text-center space-y-4">
            <div className="text-red-500 text-lg font-medium">
              Something went wrong
            </div>
            <p className="text-cream-600 text-sm max-w-md">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 bg-amber-gold/20 text-amber-gold rounded hover:bg-amber-gold/30 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

**Integration:** Update `web/app/layout.tsx` to wrap children:
```tsx
import { ErrorBoundary } from '@/src/components/ErrorBoundary';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={...}>
        <Providers>
          <ErrorBoundary>{children}</ErrorBoundary>
        </Providers>
      </body>
    </html>
  );
}
```

---

### 8. Integration Tests for Full Pipeline

**Location:** Create `tests/test_integration.py`

**Purpose:** Test the complete pipeline flow: URL → download → transcribe → extract → save

**Implementation:**

```python
# tests/test_integration.py
"""Integration tests for the transcript pipeline."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.pipeline_service import process_video
from src.models import Segment, TranscriptResult, VideoMetadata


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            'transcription_engine': 'captions',
            'mlx_whisper_model': 'large-v3-turbo',
            'caption_language': 'en',
            'caption_fallback_engine': 'mlx-whisper',
            'default_llm': 'claude',
            'anthropic_api_key': 'test-key',
            'openai_api_key': None,
            'claude_model_id': 'claude-sonnet-4-5',
            'openai_model_id': 'gpt-4o-mini',
            'output_dir': None,  # Will be set per test
        }

    @pytest.fixture
    def mock_metadata(self):
        """Create mock video metadata."""
        return {
            'title': 'Test Video Title',
            'author': 'Test Author',
            'channel': 'Test Channel',
            'upload_date': '20240101',
            'duration': 300,
            'description': 'Test description',
            'url': 'https://www.youtube.com/watch?v=test123',
            'id': 'test123',
        }

    @pytest.fixture
    def mock_segments(self):
        """Create mock transcript segments."""
        return [
            Segment(start=0.0, end=5.0, text="Hello, this is a test video."),
            Segment(start=5.0, end=10.0, text="We are testing the pipeline."),
            Segment(start=10.0, end=15.0, text="This should work correctly."),
        ]

    def test_pipeline_with_mocked_dependencies(
        self, mock_config, mock_metadata, mock_segments, tmp_path
    ):
        """Test full pipeline with mocked external dependencies."""
        mock_config['output_dir'] = str(tmp_path)

        # Mock the downloader
        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(tmp_path / "audio" / "test.mp3"),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            # Mock the transcriber
            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock-transcriber"
                mock_transcriber.format_transcript.return_value = "\n".join(
                    f"[{s.start}] {s.text}" for s in mock_segments
                )
                mock_transcriber.get_full_text.return_value = " ".join(
                    s.text for s in mock_segments
                )
                mock_get_transcriber.return_value = mock_transcriber

                # Mock the extractor
                with patch('src.services.pipeline_service.get_extractor') as mock_get_extractor:
                    mock_extractor = Mock()
                    mock_extractor.extract.return_value = "## Summary\nThis is a test summary."
                    mock_get_extractor.return_value = mock_extractor

                    # Run the pipeline
                    result = process_video(
                        url="https://www.youtube.com/watch?v=test123",
                        llm_type="claude",
                        no_extract=False,
                        config=mock_config,
                    )

                    # Verify result
                    assert result['success'] is True
                    assert result.get('error') is None
                    assert 'transcript_path' in result
                    assert 'summary_path' in result

                    # Verify files were created
                    transcript_path = Path(result['transcript_path'])
                    summary_path = Path(result['summary_path'])

                    assert transcript_path.exists()
                    assert summary_path.exists()

    def test_pipeline_no_extract(self, mock_config, mock_metadata, mock_segments, tmp_path):
        """Test pipeline with extraction disabled."""
        mock_config['output_dir'] = str(tmp_path)

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(tmp_path / "audio" / "test.mp3"),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock-transcriber"
                mock_transcriber.format_transcript.return_value = "Test transcript"
                mock_transcriber.get_full_text.return_value = "Test transcript"
                mock_get_transcriber.return_value = mock_transcriber

                # Run pipeline without extraction
                result = process_video(
                    url="https://www.youtube.com/watch?v=test123",
                    llm_type="claude",
                    no_extract=True,  # Skip extraction
                    config=mock_config,
                )

                assert result['success'] is True
                assert 'transcript_path' in result
                # Summary should not exist when extraction is disabled
                assert result.get('summary_path') is None or not Path(result.get('summary_path', '')).exists()

    def test_pipeline_handles_transcription_error(self, mock_config, mock_metadata, tmp_path):
        """Test pipeline handles transcription errors gracefully."""
        mock_config['output_dir'] = str(tmp_path)

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(tmp_path / "audio" / "test.mp3"),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.side_effect = Exception("Transcription failed")
                mock_get_transcriber.return_value = mock_transcriber

                result = process_video(
                    url="https://www.youtube.com/watch?v=test123",
                    llm_type="claude",
                    no_extract=False,
                    config=mock_config,
                )

                assert result['success'] is False
                assert 'error' in result
                assert 'Transcription failed' in result['error']

    def test_pipeline_handles_extraction_error(
        self, mock_config, mock_metadata, mock_segments, tmp_path
    ):
        """Test pipeline handles extraction errors gracefully."""
        mock_config['output_dir'] = str(tmp_path)

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(tmp_path / "audio" / "test.mp3"),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock-transcriber"
                mock_transcriber.format_transcript.return_value = "Test transcript"
                mock_transcriber.get_full_text.return_value = "Test transcript"
                mock_get_transcriber.return_value = mock_transcriber

                with patch('src.services.pipeline_service.get_extractor') as mock_get_extractor:
                    mock_extractor = Mock()
                    mock_extractor.extract.side_effect = Exception("LLM API error")
                    mock_get_extractor.return_value = mock_extractor

                    result = process_video(
                        url="https://www.youtube.com/watch?v=test123",
                        llm_type="claude",
                        no_extract=False,
                        config=mock_config,
                    )

                    # Pipeline should still succeed but with error in extraction
                    # Transcript should still be saved
                    assert 'transcript_path' in result


class TestProgressCallbacks:
    """Test progress callback functionality."""

    def test_progress_callback_called(self, tmp_path):
        """Test that progress callbacks are invoked during pipeline execution."""
        mock_config = {
            'transcription_engine': 'mlx-whisper',
            'mlx_whisper_model': 'large-v3-turbo',
            'default_llm': 'claude',
            'anthropic_api_key': 'test-key',
            'output_dir': str(tmp_path),
        }

        progress_updates = []

        def track_progress(update):
            progress_updates.append(update)

        mock_metadata = {'title': 'Test', 'author': 'Author', 'duration': 60, 'id': 'test'}
        mock_segments = [Segment(start=0, end=5, text="Test")]

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (str(tmp_path / "test.mp3"), mock_metadata)
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock"
                mock_transcriber.format_transcript.return_value = "Test"
                mock_transcriber.get_full_text.return_value = "Test"
                mock_get_transcriber.return_value = mock_transcriber

                with patch('src.services.pipeline_service.get_extractor') as mock_get_extractor:
                    mock_extractor = Mock()
                    mock_extractor.extract.return_value = "Summary"
                    mock_get_extractor.return_value = mock_extractor

                    process_video(
                        url="https://youtube.com/watch?v=test",
                        llm_type="claude",
                        no_extract=False,
                        config=mock_config,
                        progress_callback=track_progress,
                    )

        # Verify progress callbacks were called
        assert len(progress_updates) > 0
        statuses = [u.status for u in progress_updates]
        assert 'downloading' in statuses or 'transcribing' in statuses
```

**Additional Server API Tests:** Create `tests/test_server.py`

```python
# tests/test_server.py
"""Tests for FastAPI server endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "jobs" in data


class TestConfigEndpoint:
    """Tests for config endpoint."""

    def test_config_returns_non_sensitive_data(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        # Should have boolean flags, not actual keys
        assert "has_anthropic_key" in data
        assert "has_openai_key" in data
        assert isinstance(data["has_anthropic_key"], bool)

        # Should not contain actual API keys
        assert "anthropic_api_key" not in data
        assert "openai_api_key" not in data


class TestProcessEndpoint:
    """Tests for process endpoint."""

    def test_process_returns_job_id(self, client):
        with patch('server.process_video_async') as mock_process:
            response = client.post(
                "/api/process",
                json={"url": "https://www.youtube.com/watch?v=test123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "pending"


class TestJobEndpoints:
    """Tests for job status endpoints."""

    def test_job_not_found(self, client):
        response = client.get("/api/jobs/nonexistent")
        assert response.status_code == 404

    def test_transcript_not_found(self, client):
        response = client.get("/api/jobs/nonexistent/transcript")
        assert response.status_code == 404

    def test_summary_not_found(self, client):
        response = client.get("/api/jobs/nonexistent/summary")
        assert response.status_code == 404
```

---

## Implementation Notes

1. **Run tests after changes**: `pytest -v`
2. **Test the API docs**: Start server and visit `http://localhost:8000/docs`
3. **Test error boundary**: Force an error in a React component to verify it catches

## Files Changed/Created

### Already Changed:
- `src/config.py` - Added `API_TIMEOUT_SECONDS`
- `src/extractor.py` - Added timeouts and specific exceptions
- `requirements.txt` - Pinned versions
- `.env.example` - Created

### To Be Created:
- `web/src/components/ErrorBoundary.tsx`
- `tests/test_integration.py`
- `tests/test_server.py`

### To Be Modified:
- `server.py` - Enhanced OpenAPI documentation
- `web/app/layout.tsx` - Add ErrorBoundary wrapper
