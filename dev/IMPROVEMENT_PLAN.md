# Transcript Pipeline Improvement Plan

**Created:** January 6, 2026
**Based on:** `dev/REMAINING_IMPROVEMENTS.md`, `dev/CODEBASE_ASSESSMENT.md`

---

## Overview

This plan outlines all remaining improvements to be implemented from the codebase assessment documents. Items are organized by priority and grouped for efficient implementation.

---

## Status of Previous Work

### Completed (Already Done)
- [x] API Timeout Specifications (Item 1)
- [x] Specific Exception Handling (Item 2)
- [x] Config Loading Review (Item 3)
- [x] Version Pinned Dependencies (Item 4)
- [x] Environment Example File (Item 5)
- [x] MLX Whisper Refactor (from REFACTOR_MLX_WHISPER.md)

---

## Remaining Improvements

### Phase 1: Backend Enhancements

#### 1.1 OpenAPI/Swagger Documentation Enhancement
**File:** `server.py`
**Priority:** High
**Effort:** ~30 minutes

**Changes:**
1. Update FastAPI app initialization with detailed description
2. Add Field descriptions to Pydantic models
3. Add tags to organize endpoints

**Code Changes:**

```python
# Update FastAPI app initialization (lines 37-41)
app = FastAPI(
    title="Transcript Pipeline API",
    description="""
## Overview
Extract transcripts and AI-powered insights from YouTube videos.

## Features
- Download and transcribe YouTube videos using YouTube captions or MLX Whisper
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

# Update ProcessRequest model (lines 78-82)
class ProcessRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL", example="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    llm_type: Optional[str] = Field(None, description="LLM to use: 'claude' or 'gpt'", example="claude")
    extract: bool = Field(True, description="Whether to run AI extraction on transcript")

# Add tags to endpoints
@app.get("/api/health", tags=["System"])
@app.get("/api/config", tags=["System"])
@app.post("/api/process", response_model=JobStatus, tags=["Jobs"])
@app.get("/api/jobs/{job_id}", response_model=JobStatus, tags=["Jobs"])
@app.get("/api/jobs/{job_id}/stream", tags=["Jobs"])
@app.get("/api/jobs/{job_id}/transcript", tags=["Jobs"])
@app.get("/api/jobs/{job_id}/summary", tags=["Jobs"])
@app.get("/api/jobs/{job_id}/download/{file_type}", tags=["Jobs"])
```

---

#### 1.2 Rate Limiting Middleware
**File:** `server.py`
**Priority:** Medium
**Effort:** ~20 minutes

**Changes:**
Add simple in-memory rate limiting middleware to prevent API abuse.

**Code to Add:**

```python
from collections import defaultdict
import time
from fastapi import Request
from fastapi.responses import JSONResponse

# Rate limiting configuration
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Rate limiting state
request_timestamps: Dict[str, list] = defaultdict(list)
rate_limit_lock = threading.Lock()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware."""
    # Skip rate limiting for health checks and static files
    if request.url.path in ("/api/health", "/"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    with rate_limit_lock:
        # Clean old timestamps
        request_timestamps[client_ip] = [
            ts for ts in request_timestamps[client_ip]
            if now - ts < RATE_LIMIT_WINDOW
        ]

        # Check rate limit
        if len(request_timestamps[client_ip]) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Please try again later."}
            )

        # Record this request
        request_timestamps[client_ip].append(now)

    return await call_next(request)
```

---

### Phase 2: Frontend Enhancements

#### 2.1 React Error Boundary Component
**File:** `web/src/components/ErrorBoundary.tsx` (new file)
**Priority:** High
**Effort:** ~15 minutes

**Code:**

```tsx
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

---

#### 2.2 Integrate Error Boundary
**File:** `web/app/layout.tsx`
**Priority:** High
**Effort:** ~5 minutes

**Changes:**

```tsx
import { ErrorBoundary } from '@/src/components/ErrorBoundary';

// In the return statement, wrap Providers children:
<Providers>
  <ErrorBoundary>{children}</ErrorBoundary>
</Providers>
```

---

#### 2.3 SSE Reconnection Logic
**File:** `web/src/hooks/useJobStream.ts`
**Priority:** Medium
**Effort:** ~20 minutes

**Changes:**
Add exponential backoff reconnection when SSE connection drops.

**Updated Code:**

```tsx
import { useEffect, useState, useRef, useCallback } from 'react';
import type { Job } from '@/src/lib/types';

const getApiBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || window.location.origin;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

const MAX_RECONNECT_ATTEMPTS = 3;
const INITIAL_RECONNECT_DELAY = 1000;

export function useJobStream(jobId: string | null) {
  const [status, setStatus] = useState<Job | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!jobId) return;

    setIsConnecting(true);
    const url = `${getApiBaseUrl()}/api/jobs/${jobId}/stream`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0; // Reset on successful connection
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        setStatus(data);
        setError(null);

        if (data.status === 'complete' || data.status === 'error') {
          eventSource.close();
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to parse SSE data'));
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setIsConnecting(false);

      // Don't reconnect if job is already complete
      if (status?.status === 'complete' || status?.status === 'error') {
        return;
      }

      // Attempt reconnection with exponential backoff
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current);
        reconnectAttemptsRef.current++;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        setError(new Error('Connection lost. Please refresh the page.'));
      }
    };
  }, [jobId, status?.status]);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      setError(null);
      return;
    }

    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      reconnectAttemptsRef.current = 0;
    };
  }, [jobId, connect]);

  return { status, error, isConnecting };
}
```

---

#### 2.4 API Retry Logic
**File:** `web/src/lib/api.ts`
**Priority:** Medium
**Effort:** ~15 minutes

**Changes:**
Add retry with exponential backoff for transient failures.

**Code to Add:**

```typescript
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY = 1000;
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

async function fetchWithRetry<T>(
  endpoint: string,
  options?: RequestInit,
  retries = MAX_RETRIES
): Promise<T> {
  const url = `${getApiBaseUrl()}${endpoint}`;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        // Only retry on specific status codes
        if (RETRYABLE_STATUS_CODES.includes(response.status) && attempt < retries) {
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt);
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }

        throw new ApiError(
          `API request failed: ${response.statusText}`,
          response.status,
          response
        );
      }

      return response.json();
    } catch (error) {
      // Retry on network errors
      if (error instanceof TypeError && attempt < retries) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      throw error;
    }
  }

  throw new ApiError('Max retries exceeded', undefined, undefined);
}

// Update fetchApi to use fetchWithRetry
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  return fetchWithRetry<T>(endpoint, options);
}
```

---

### Phase 3: Testing

#### 3.1 Integration Tests
**File:** `tests/test_integration.py` (new file)
**Priority:** High
**Effort:** ~45 minutes

**Code:** (See full implementation in REMAINING_IMPROVEMENTS.md)

Key test cases:
- `test_pipeline_with_mocked_dependencies` - Full pipeline flow
- `test_pipeline_no_extract` - Transcript-only mode
- `test_pipeline_handles_transcription_error` - Error handling
- `test_pipeline_handles_extraction_error` - Graceful degradation
- `test_progress_callback_called` - Progress callback verification

---

#### 3.2 Server API Tests
**File:** `tests/test_server.py` (new file)
**Priority:** High
**Effort:** ~30 minutes

**Code:** (See full implementation in REMAINING_IMPROVEMENTS.md)

Key test cases:
- `TestHealthEndpoint` - Health check returns OK
- `TestConfigEndpoint` - Config returns non-sensitive data
- `TestProcessEndpoint` - Process returns job ID
- `TestJobEndpoints` - Job status, 404 handling

---

## Implementation Order

1. **Backend (server.py)**
   - OpenAPI documentation
   - Rate limiting middleware

2. **Frontend**
   - ErrorBoundary component
   - Layout integration
   - SSE reconnection
   - API retry logic

3. **Tests**
   - Integration tests
   - Server API tests

4. **Documentation**
   - Create CHANGELOG.md with all changes

---

## Verification Checklist

After implementation, verify:

- [ ] `/docs` endpoint shows enhanced API documentation
- [ ] Rate limiting returns 429 after exceeding limit
- [ ] ErrorBoundary catches and displays React errors
- [ ] SSE reconnects automatically on connection drop
- [ ] API calls retry on transient failures
- [ ] All tests pass: `pytest -v`
- [ ] Server starts without errors: `python server.py`
- [ ] Frontend builds: `cd web && npm run build`

---

## Estimated Total Effort

| Phase | Items | Time |
|-------|-------|------|
| Backend | OpenAPI + Rate Limiting | ~50 min |
| Frontend | ErrorBoundary + SSE + Retry | ~55 min |
| Tests | Integration + Server | ~75 min |
| Documentation | Changelog | ~15 min |
| **Total** | | **~3 hours** |

---

## Notes

- All changes are additive and don't break existing functionality
- Rate limiting can be disabled by setting `RATE_LIMIT_REQUESTS=0`
- Error boundary catches component errors but not async errors
- SSE reconnection has a maximum of 3 attempts before giving up
- API retry is limited to specific HTTP status codes
