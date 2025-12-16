# Server.py Changes Required

## 1. Update imports (line ~27)

**Before:**
```python
from src.transcriber import get_transcriber, BaseTranscriber, CaptionTranscriber, CaptionsUnavailableError
```

**After:**
```python
from src.transcriber import get_transcriber, CaptionTranscriber, CaptionsUnavailableError
```

---

## 2. Simplify config loading in `process_video_async` (around line ~140)

**Remove these lines:**
```python
elevenlabs_api_key = config.get('elevenlabs_api_key')
scribe_model_id = config.get('scribe_model_id', 'scribe_v2')
```

**Replace with:**
```python
mlx_model = config.get('mlx_whisper_model', 'large-v3-turbo')
```

---

## 3. Simplify fallback transcriber creation (around line ~200)

**Before:**
```python
transcriber = get_transcriber(
    engine=fallback_engine,
    api_key=elevenlabs_api_key,
    scribe_model_id=scribe_model_id,
    model_name=config.get('whisper_model'),
    model_dir=config.get('whisper_model_dir'),
)
```

**After:**
```python
transcriber = get_transcriber(
    engine='mlx-whisper',
    model=mlx_model,
)
```

---

## 4. Simplify explicit engine transcriber creation (around line ~270)

**Before:**
```python
transcriber = get_transcriber(
    engine=transcription_engine,
    api_key=elevenlabs_api_key,
    scribe_model_id=scribe_model_id,
    model_name=config.get('whisper_model'),
    model_dir=config.get('whisper_model_dir'),
)
```

**After:**
```python
transcriber = get_transcriber(
    engine=transcription_engine,
    model=mlx_model,
)
```

---

## 5. Update `/api/config` endpoint (around line ~680)

**Before:**
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

**After:**
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

---

## 6. Update .env.example

**Remove:**
```
ELEVENLABS_API_KEY=your_elevenlabs_key_here
SCRIBE_MODEL_ID=scribe_v2
WHISPER_MODEL=large-v3
WHISPER_MODEL_DIR=/path/to/models
```

**Add:**
```
# Transcription Engine: 'auto', 'captions', or 'mlx-whisper'
# 'auto' tries captions first, falls back to mlx-whisper
TRANSCRIPTION_ENGINE=auto

# MLX Whisper model (Apple Silicon only)
# Options: tiny, base, small, medium, large, large-v3, large-v3-turbo, distil-large-v3
MLX_WHISPER_MODEL=large-v3-turbo
```

---

## Summary

Lines removed: ~200+ (ElevenLabs transcriber, Whisper chunking logic, related config)
Lines added: ~50 (MLXWhisperTranscriber)
Net reduction: ~150+ lines

The codebase becomes simpler and faster on Apple Silicon.
