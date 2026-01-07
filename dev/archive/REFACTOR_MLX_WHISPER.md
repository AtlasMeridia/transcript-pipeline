# Refactor: Replace Whisper + ElevenLabs with MLX Whisper

## Overview

This refactor removes the ElevenLabs transcription engine and replaces the OpenAI Whisper implementation with MLX Whisper, which is optimized for Apple Silicon. This reduces the codebase by ~500 lines and significantly improves transcription speed on M1/M2/M3/M4 Macs.

## Files Provided

Unzip `files.zip` in this directory to access:
- `transcriber.py` — Complete replacement for `src/transcriber.py`
- `requirements-local.txt` — Updated dependencies
- `.env.example` — Simplified environment configuration
- `SERVER_CHANGES.md` — Reference for server.py changes (do not copy directly)

## Instructions

### Step 1: Replace `src/transcriber.py`

Replace the entire contents of `src/transcriber.py` with the provided `transcriber.py` file.

```bash
cp dev/transcriber.py src/transcriber.py
```

### Step 2: Update `requirements-local.txt`

Replace the project root `requirements-local.txt` with the provided version.

```bash
cp dev/requirements-local.txt requirements-local.txt
```

### Step 3: Update `requirements.txt` (for hosted/Docker deployment)

Edit `requirements.txt` to remove ElevenLabs:

**Remove this line:**
```
elevenlabs>=1.0.0
```

**Note:** The hosted version should use `TRANSCRIPTION_ENGINE=captions` only, since MLX Whisper requires Apple Silicon.

### Step 4: Update `.env.example`

Replace with the provided `.env.example`:

```bash
cp dev/.env.example .env.example
```

### Step 5: Update `server.py`

Make the following targeted changes to `server.py`:

#### 5.1 Update imports (around line 27)

**Find:**
```python
from src.transcriber import get_transcriber, BaseTranscriber, CaptionTranscriber, CaptionsUnavailableError
```

**Replace with:**
```python
from src.transcriber import get_transcriber, CaptionTranscriber, CaptionsUnavailableError
```

#### 5.2 Update config loading in `process_video_async` (around line 140)

**Find and remove these lines:**
```python
elevenlabs_api_key = config.get('elevenlabs_api_key')
scribe_model_id = config.get('scribe_model_id', 'scribe_v2')
```

**Add this line instead:**
```python
mlx_model = config.get('mlx_whisper_model', 'large-v3-turbo')
```

#### 5.3 Update fallback transcriber creation (around line 200)

**Find:**
```python
fallback_engine = config.get('caption_fallback_engine', 'whisper')
```

**Replace with:**
```python
fallback_engine = config.get('caption_fallback_engine', 'mlx-whisper')
```

**Find:**
```python
transcriber = get_transcriber(
    engine=fallback_engine,
    api_key=elevenlabs_api_key,
    scribe_model_id=scribe_model_id,
    model_name=config.get('whisper_model'),
    model_dir=config.get('whisper_model_dir'),
)
```

**Replace with:**
```python
transcriber = get_transcriber(
    engine=fallback_engine,
    model=mlx_model,
)
```

#### 5.4 Update explicit engine transcriber creation (around line 270)

**Find:**
```python
transcriber = get_transcriber(
    engine=transcription_engine,
    api_key=elevenlabs_api_key,
    scribe_model_id=scribe_model_id,
    model_name=config.get('whisper_model'),
    model_dir=config.get('whisper_model_dir'),
)
```

**Replace with:**
```python
transcriber = get_transcriber(
    engine=transcription_engine,
    model=mlx_model,
)
```

#### 5.5 Update `/api/config` endpoint (around line 680)

**Find:**
```python
return {
    "default_llm": config.get('default_llm', 'claude'),
    "output_dir": config.get('output_dir', './output'),
    "has_anthropic_key": bool(config.get('anthropic_api_key')),
    "has_openai_key": bool(config.get('openai_api_key')),
    # Transcription configuration
    "transcription_engine": transcription_engine,
    "whisper_model": config.get('whisper_model', 'large-v3') if transcription_engine == 'whisper' else None,
    "has_elevenlabs_key": bool(config.get('elevenlabs_api_key')),
    "scribe_model_id": config.get('scribe_model_id', 'scribe_v2') if transcription_engine == 'elevenlabs' else None,
}
```

**Replace with:**
```python
return {
    "default_llm": config.get('default_llm', 'claude'),
    "output_dir": config.get('output_dir', './output'),
    "has_anthropic_key": bool(config.get('anthropic_api_key')),
    "has_openai_key": bool(config.get('openai_api_key')),
    # Transcription configuration
    "transcription_engine": transcription_engine,
    "mlx_whisper_model": config.get('mlx_whisper_model', 'large-v3-turbo'),
}
```

### Step 6: Update `src/utils.py` - `load_config` function

Ensure `load_config()` reads the new environment variables. 

**Add these config mappings if not present:**
```python
'mlx_whisper_model': os.getenv('MLX_WHISPER_MODEL', 'large-v3-turbo'),
```

**Remove these deprecated mappings if present:**
```python
'elevenlabs_api_key': os.getenv('ELEVENLABS_API_KEY'),
'scribe_model_id': os.getenv('SCRIBE_MODEL_ID', 'scribe_v2'),
'whisper_model': os.getenv('WHISPER_MODEL', 'large-v3'),
'whisper_model_dir': os.getenv('WHISPER_MODEL_DIR'),
```

### Step 7: Update `src/config.py`

Remove any constants related to Whisper chunking that are no longer needed:

**These can be removed if only used by the old WhisperTranscriber:**
```python
CHUNK_DURATION_SECONDS
CHUNK_OVERLAP_SECONDS
MIN_AUDIO_DURATION_FOR_CHUNKING
```

**Keep this (still used by caption parsing):**
```python
SEGMENT_GAP_THRESHOLD_SECONDS
```

### Step 8: Update the Dockerfile (optional)

If you want to maintain Docker support for captions-only mode:

**Find and remove Whisper-related installations:**
```dockerfile
# Remove any lines installing openai-whisper or its dependencies
```

**Ensure the transcription engine defaults to captions:**
```dockerfile
ENV TRANSCRIPTION_ENGINE=captions
```

### Step 9: Update `frontend/index.html`

Update the config display to reflect the new transcription engine options.

**Find any references to:**
- `has_elevenlabs_key`
- `scribe_model_id`
- `whisper_model`

**Replace with references to:**
- `mlx_whisper_model`

### Step 10: Install dependencies and test

```bash
# Install MLX Whisper
pip install mlx-whisper

# Or reinstall all local dependencies
pip install -r requirements-local.txt

# Run the server
python server.py

# Test with a YouTube URL
```

## Verification Checklist

After making changes, verify:

- [ ] `src/transcriber.py` contains only `BaseTranscriber`, `MLXWhisperTranscriber`, `CaptionTranscriber`, and `get_transcriber`
- [ ] No imports of `ElevenLabs` or `whisper` (the OpenAI package) remain in the codebase
- [ ] `server.py` has no references to `elevenlabs_api_key` or `scribe_model_id`
- [ ] `.env.example` uses `MLX_WHISPER_MODEL` instead of `WHISPER_MODEL`
- [ ] Running `python -c "from src.transcriber import get_transcriber; print(get_transcriber())"` works
- [ ] Transcription works with `TRANSCRIPTION_ENGINE=mlx-whisper`

## Rollback

If issues occur, the original files can be restored from git:

```bash
git checkout HEAD -- src/transcriber.py server.py requirements-local.txt .env.example
```

## Notes

- **Apple Silicon Only**: MLX Whisper requires M1/M2/M3/M4 Macs. For Linux/hosted deployment, use `TRANSCRIPTION_ENGINE=captions` only.
- **First Run**: The first transcription will download the model (~1.5GB for large-v3-turbo) to `~/.cache/huggingface/`.
- **Model Options**: `large-v3-turbo` is recommended for best speed/accuracy balance. Use `distil-large-v3` for even faster transcription with slightly lower accuracy.
