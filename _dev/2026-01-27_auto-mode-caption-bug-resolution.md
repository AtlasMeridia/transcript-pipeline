# Resolution: Auto Mode Caption Bug

**Date:** 2026-01-27
**Status:** Resolved
**Original Bug:** `_dev/2026-01-27_auto-mode-caption-bug.md`

---

## Root Cause

The bug had **two root causes**:

### 1. yt-dlp PO Token Requirement
YouTube now requires a Proof of Origin (PO) token for caption extraction via yt-dlp. This is a new anti-bot measure. Even when captions were available (verified with `--list-subs`), the actual extraction would fail with:

```
WARNING: There are missing subtitles languages because a PO token was not provided
```

This caused `get_captions()` to fail silently, returning `None`, which triggered `CaptionsUnavailableError` and fallback to audio download.

### 2. Audio Download 403 Errors
The fallback to audio download also failed due to YouTube's SABR streaming protocol changes. Even with `skip_download: True`, format resolution in `get_video_info()` could trigger 403 errors.

---

## Solution

Replaced yt-dlp-based caption extraction with `youtube-transcript-api` library, which:
- Accesses YouTube's transcript API directly
- Does not require PO tokens
- Is more reliable for caption extraction

---

## Files Modified

| File | Changes |
|------|---------|
| `src/transcriber.py:203-358` | Rewrote `CaptionTranscriber` to use `youtube-transcript-api` instead of yt-dlp |
| `src/transcriber.py:211-222` | Added `_extract_video_id()` helper function |
| `src/downloader.py:39-43` | Added `skip_download: True` and `format: None` to `get_video_info()` (belt-and-suspenders) |
| `src/downloader.py:137-203` | Updated `get_captions()` signature to accept pre-fetched metadata |
| `src/services/pipeline_service.py:175-179` | Pass metadata through to caption transcriber |
| `requirements.txt` | Added `youtube-transcript-api>=1.2.3` |

---

## Key Code Changes

### CaptionTranscriber.transcribe() (src/transcriber.py)

Old approach:
```python
# Uses yt-dlp
downloader = VideoDownloader(output_dir=self.output_dir)
caption_path, metadata = downloader.get_captions(url, language=lang)
# Parse VTT file
segments = parse_vtt(caption_path)
```

New approach:
```python
# Uses youtube-transcript-api directly
from youtube_transcript_api import YouTubeTranscriptApi

video_id = _extract_video_id(url)
ytt = YouTubeTranscriptApi()
transcript_list = ytt.list(video_id)
transcript = transcript_list.find_generated_transcript([lang])
entries = transcript.fetch()

# Convert to Segment objects
segments = [Segment(start=e.start, end=e.start + e.duration, text=e.text) for e in entries]
```

---

## Verification

Tested with: `https://www.youtube.com/watch?v=KSx9kcFr7XA`

**Before fix:**
- Caption extraction failed silently
- Fell back to audio download
- Audio download failed with HTTP 403

**After fix:**
- Caption extraction succeeds via youtube-transcript-api
- Job completes with `transcription_source: "captions"`
- ~50 second processing time (vs ~13s error before)

---

## Test Commands

```bash
# Restart server
pkill -f "uvicorn server:app"
cd ~/Projects/transcript-pipeline
.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --reload &

# Submit test job
curl -s -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=KSx9kcFr7XA"}'

# Check job status (replace JOB_ID)
curl -s http://localhost:8000/api/jobs/JOB_ID | jq '{status, phase, progress}'
```

**Success criteria:**
- Job status: `complete`
- No 403 errors in logs
- Transcript file created

---

## Dependencies Added

```
youtube-transcript-api>=1.2.3
```

Install with: `pip install youtube-transcript-api`

---

## Notes

1. The old yt-dlp caption extraction code in `downloader.py:get_captions()` is now unused by `CaptionTranscriber` but retained for potential future use or other callers.

2. The `get_video_info()` fix (`skip_download: True`, `format: None`) is still valuable as a belt-and-suspenders measure for avoiding unnecessary YouTube API calls that could trigger rate limits or 403 errors.

3. youtube-transcript-api version 1.2.3 has a different exception hierarchy than earlier versions. The code uses `CouldNotRetrieveTranscript` instead of the deprecated `NoTranscriptAvailable`.

---

*Resolution documented: 2026-01-27*
