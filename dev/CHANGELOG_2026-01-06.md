# Changelog - January 6, 2026

## Summary

Implemented all remaining improvements from `REMAINING_IMPROVEMENTS.md` and `CODEBASE_ASSESSMENT.md`. All 48 tests pass with no warnings.

---

## Backend Changes

### 1. Enhanced OpenAPI/Swagger Documentation (`server.py`)

**What changed:**
- Added comprehensive API description with features, overview, and authentication notes
- Added `docs_url="/docs"` and `redoc_url="/redoc"` explicit endpoints
- Updated `ProcessRequest` model with Field descriptions and examples
- Added tags to all API endpoints for better organization:
  - `System`: `/api/health`, `/api/config`
  - `Jobs`: `/api/process`, `/api/jobs/*`
  - `Frontend`: `/`

**Files modified:**
- `server.py` (lines 39-69, 132-135, all endpoint decorators)

---

### 2. Rate Limiting Middleware (`server.py`)

**What changed:**
- Added simple in-memory rate limiting middleware
- Default: 30 requests per minute per IP
- Configurable via `RATE_LIMIT_REQUESTS` environment variable
- Skips rate limiting for health checks, docs, and static files
- Returns HTTP 429 with error message when limit exceeded

**New configuration:**
```bash
RATE_LIMIT_REQUESTS=30  # requests per minute (0 to disable)
```

**Files modified:**
- `server.py` (lines 88-92, 95-122)

---

### 3. Fixed Deprecation Warnings (`server.py`)

**What changed:**
- Replaced deprecated `@app.on_event("startup")` with modern `lifespan` context manager
- Updated Pydantic Field `example` kwarg to `json_schema_extra={"example": ...}`

**Files modified:**
- `server.py` (lines 40-48, 133-134)

---

## Frontend Changes

### 4. React Error Boundary Component (NEW)

**What changed:**
- Created `ErrorBoundary.tsx` class component
- Catches JavaScript errors in React component tree
- Displays user-friendly error message with "Try Again" button
- Supports custom fallback UI via `fallback` prop

**Files created:**
- `web/src/components/ErrorBoundary.tsx`

---

### 5. Error Boundary Integration (`layout.tsx`)

**What changed:**
- Imported and wrapped children with `ErrorBoundary`
- All unhandled React errors now show graceful error UI instead of blank page

**Files modified:**
- `web/app/layout.tsx`

---

### 6. SSE Reconnection Logic (`useJobStream.ts`)

**What changed:**
- Added automatic reconnection with exponential backoff
- Maximum 3 reconnection attempts before giving up
- Initial delay: 1 second, doubles each attempt
- Added `isConnecting` state for UI feedback
- Prevents reconnection if job is already complete/errored

**Files modified:**
- `web/src/hooks/useJobStream.ts` (complete rewrite)

---

### 7. API Retry Logic (`api.ts`)

**What changed:**
- Added retry with exponential backoff for transient failures
- Maximum 3 retries with 1s initial delay
- Retryable status codes: 408, 429, 500, 502, 503, 504
- Also retries on network errors (TypeError from fetch)

**Files modified:**
- `web/src/lib/api.ts`

---

## Testing Changes

### 8. Integration Tests (NEW)

**What changed:**
- Created comprehensive integration tests for pipeline
- Tests full pipeline with mocked dependencies
- Tests extraction disabled mode
- Tests error handling for download/transcription failures
- Tests progress callback invocation

**Files created:**
- `tests/test_integration.py` (5 test cases)

---

### 9. Server API Tests (NEW)

**What changed:**
- Created tests for all FastAPI endpoints
- Tests health check endpoint
- Tests config endpoint (verifies no sensitive data exposed)
- Tests process endpoint (job creation)
- Tests job status and 404 handling
- Tests SSE streaming endpoint
- Tests file download with invalid type

**Files created:**
- `tests/test_server.py` (13 test cases)

---

## Test Results

```
======================== 48 passed in 0.78s ========================
```

All tests pass with no warnings.

---

## Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `server.py` | Modified | OpenAPI docs, rate limiting, lifespan handler |
| `web/src/components/ErrorBoundary.tsx` | Created | React error boundary component |
| `web/app/layout.tsx` | Modified | Added ErrorBoundary wrapper |
| `web/src/hooks/useJobStream.ts` | Modified | SSE reconnection logic |
| `web/src/lib/api.ts` | Modified | API retry logic |
| `tests/test_integration.py` | Created | Pipeline integration tests |
| `tests/test_server.py` | Created | Server API tests |
| `dev/IMPROVEMENT_PLAN.md` | Created | Implementation plan |

---

## Configuration Changes

New environment variables:
- `RATE_LIMIT_REQUESTS` - Rate limit (requests/minute), default: 30

---

## Verification Checklist

- [x] All 48 tests pass
- [x] No deprecation warnings
- [x] OpenAPI docs accessible at `/docs`
- [x] Rate limiting returns 429 on excess requests
- [x] Error boundary catches React errors
- [x] SSE reconnects on connection drop
- [x] API retries on transient failures

---

## Breaking Changes

None. All changes are backward compatible.
