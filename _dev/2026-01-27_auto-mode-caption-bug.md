# Bug Fix Task: Auto Mode Not Trying Captions First

**Date:** 2026-01-27
**Status:** Open
**Priority:** High

---

## Problem Summary

When `TRANSCRIPTION_ENGINE=auto` is set, the pipeline should:
1. Try YouTube caption extraction first (fast, no download needed)
2. Fall back to audio download + Whisper only if captions unavailable

**Actual behavior:** The pipeline skips caption extraction and goes straight to audio download, hitting HTTP 403 errors from YouTube.

---

## Evidence

### Server Logs (from failed job)

```
[youtube] KSx9kcFr7XA: Downloading webpage
[youtube] KSx9kcFr7XA: Downloading tv client config
[youtube] KSx9kcFr7XA: Downloading tv player API JSON
[youtube] KSx9kcFr7XA: Downloading web safari player API JSON
WARNING: [youtube] KSx9kcFr7XA: Some web client https formats have been skipped...
[info] KSx9kcFr7XA: Downloading 1 format(s): 18
[download] Sleeping 5.00 seconds as required by the site...
ERROR: unable to download video data: HTTP Error 403: Forbidden
Pipeline error after 13.1s: Failed to download audio: ERROR: unable to download video data: HTTP Error 403: Forbidden
```

### Key Observation

- Log shows "Downloading 1 format(s): 18" — this is audio/video download, NOT caption extraction
- Caption extraction should show: "Extracting YouTube captions..." or similar
- The video DOES have captions (verified with `yt-dlp --list-subs`)

### Verified: Captions Are Available

```bash
yt-dlp --list-subs "https://www.youtube.com/watch?v=KSx9kcFr7XA"
# Shows: [info] Available automatic captions for KSx9kcFr7XA:
# Language: en, af, ar, ... (many languages available)
```

### Manual Caption Extraction Works

```bash
yt-dlp --write-auto-sub --sub-lang en --skip-download -o "test" "https://www.youtube.com/watch?v=KSx9kcFr7XA"
# Successfully downloads tyler-cowen.en.vtt (593KB)
```

---

## Relevant Code Locations

### 1. Pipeline Service (`src/services/pipeline_service.py`)

The `auto` mode logic starts around line with `if transcription_engine == 'auto':`:

```python
if transcription_engine == 'auto':
    # Try captions first (faster, no audio download needed)
    update_progress('download', 'downloading', 'Checking for YouTube captions...', progress=5)

    try:
        caption_transcriber = CaptionTranscriber(...)
        metadata = downloader.get_video_info(url)  # <-- Might be triggering download?
        ...
        segments = caption_transcriber.transcribe(audio_path="", url=url)
        ...
    except CaptionsUnavailableError as e:
        # Fall back to audio download + transcription
        audio_path, metadata = downloader.download_audio(url, metadata=metadata)
```

**Questions to investigate:**
- Is `get_video_info()` accidentally triggering a download?
- Is `caption_transcriber.transcribe()` throwing an exception before trying captions?
- Is something else catching/masking the exception?

### 2. Downloader (`src/downloader.py`)

#### `get_video_info()` method:
```python
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,  # <-- Should this be True to avoid extraction?
}
```

#### `get_captions()` method:
```python
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,  # Don't download video/audio
    'writeautomaticsub': True,
    'subtitleslangs': [language],
    'subtitlesformat': 'vtt',
    'outtmpl': output_template,
}
```

### 3. Transcriber (`src/transcriber.py`)

`CaptionTranscriber.transcribe()` calls:
```python
downloader = VideoDownloader(output_dir=self.output_dir)
caption_path, metadata = downloader.get_captions(url, language=lang)
```

---

## Hypotheses

1. **`get_video_info()` with `extract_flat: False` is triggering format selection/download**
   - yt-dlp might be attempting to resolve formats, which triggers YouTube's SABR streaming block
   - Fix: Change to `extract_flat: True` or add `'skip_download': True`

2. **Exception handling is too broad**
   - An exception in `get_video_info()` or early in caption extraction might be caught and triggering fallback
   - Fix: Add more specific exception handling and logging

3. **yt-dlp version compatibility issue**
   - YouTube changes their API frequently; yt-dlp version in venv might be outdated
   - Fix: Update yt-dlp: `pip install -U yt-dlp`

4. **Code path never reaches caption extraction**
   - Maybe a condition is failing before `caption_transcriber.transcribe()` is called
   - Fix: Add logging to trace the actual execution path

---

## Tasks

### Investigation

1. [ ] Add verbose logging to `pipeline_service.py` auto mode branch
2. [ ] Check if `get_video_info()` is the culprit by running it in isolation
3. [ ] Check yt-dlp version in venv vs system
4. [ ] Trace the actual exception being thrown

### Fixes

1. [ ] Ensure `get_video_info()` doesn't trigger downloads
2. [ ] Ensure caption extraction is actually attempted before fallback
3. [ ] Add better error logging to understand failures
4. [ ] Consider updating yt-dlp in the venv

### Testing

1. [ ] Test with video that has captions: `https://www.youtube.com/watch?v=KSx9kcFr7XA`
2. [ ] Test with video without captions (should fall back gracefully)
3. [ ] Test `captions` mode explicitly
4. [ ] Test `whisper` mode explicitly

---

## Environment

- **Python:** 3.9 (in venv, though system has 3.14)
- **Config:** `TRANSCRIPTION_ENGINE=auto`
- **Server:** uvicorn with --reload
- **Start command:** `./start-local.sh`

---

## Documentation Requirements

After fixing, document:
1. What the root cause was
2. What changes were made (with file paths and line numbers)
3. How to verify the fix
4. Any configuration changes needed

Save documentation to: `_dev/2026-01-27_auto-mode-caption-bug-resolution.md`

---

## Test Command

After making changes, test with:

```bash
# Restart server
pkill -f "uvicorn server:app"
cd ~/Projects/transcript-pipeline && ./start-local.sh

# In another terminal, submit test job
curl -s -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=KSx9kcFr7XA"}'

# Poll for result (replace JOB_ID)
curl -s http://localhost:8000/api/jobs/JOB_ID
```

**Success criteria:** Job completes with `transcription_source: "captions"` (not "whisper" or "mlx-whisper"), no 403 errors.
