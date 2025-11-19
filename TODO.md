## Project TODOs

- **Wire ElevenLabs Scribe through Docker/Docker Compose**
  - Ensure `ELEVENLABS_API_KEY`, `TRANSCRIPTION_ENGINE`, and `SCRIBE_MODEL_ID` are correctly passed into the container.
  - Confirm that Scribe runs as the default engine when configured, with Whisper as a fallback.

- **Implement chunked Whisper transcription for long audio**
  - Use `MAX_CHUNK_DURATION` and `CHUNK_OVERLAP` in `Transcriber` to process long audio files in chunks.
  - Stitch segments back together while preserving timestamps.

- **Make LLM extraction scalable for long transcripts**
  - Chunk long transcripts and summarize chunks first.
  - Use a second-pass summary to produce the final markdown output.

- **Add a minimal test suite**
  - Cover `utils.py` helpers: `sanitize_filename`, `ensure_output_path`, `format_timestamp`, `format_duration`, `retry_with_backoff`.
  - Add tests for Scribe response parsing in `Transcriber`.

- **Improve logging and library-style reuse**
  - Replace ad-hoc `print` statements with a basic logging setup.
  - Allow `process_video` to optionally raise exceptions instead of exiting so it can be imported and reused.


