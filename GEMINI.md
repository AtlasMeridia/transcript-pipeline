# Transcript Pipeline

## Project Overview

This project is a **Dockerized Python CLI tool** designed to download audio from YouTube videos, transcribe it into text, and extract key information using AI. It features a robust architecture with fallback mechanisms and supports multiple AI models.

**Key Features:**
*   **Download:** Fetches audio from YouTube using `yt-dlp`.
*   **Transcription:**
    *   **Primary:** ElevenLabs Scribe v2 (Realtime API).
    *   **Fallback:** OpenAI Whisper (local model) for offline use or API failures.
    *   **Long Audio Support:** Whisper implementation uses chunking (30-minute chunks with 5s overlap) for memory efficiency.
*   **Extraction:** Summarizes content using Anthropic's Claude (default) or OpenAI's GPT. Implements hierarchical summarization for long transcripts (>8000 chars).
*   **Output:** Generates formatted Markdown files for transcripts and summaries.

## Building and Running

The project is designed to run primarily via Docker, but supports local Python execution.

### Docker (Recommended)

**Build the image:**
```bash
docker-compose build
```

**Run the pipeline:**
```bash
docker-compose run --rm transcript-pipeline <YOUTUBE_URL>
```

**Common Options:**
*   `--model [tiny|base|small|medium|large]`: Select Whisper model size.
*   `--llm [claude|gpt]`: Select LLM for extraction.
*   `--engine [scribe|whisper]`: Force specific transcription engine.
*   `--no-extract`: Skip the summarization step.

### Local Development

**Prerequisites:**
*   Python 3.11 - 3.13
*   `ffmpeg` installed on the system.

**Setup:**
```bash
pip install -r requirements.txt
cp .env.example .env  # Configure API keys in .env
```

**Run:**
```bash
python -m src.main <YOUTUBE_URL>
```

**Testing:**
```bash
pytest
```

## Codebase Structure

*   **`src/main.py`**: The CLI entry point. Orchestrates the download -> transcribe -> extract pipeline.
*   **`src/transcriber.py`**: Handles speech-to-text. Contains logic for both Scribe API and local Whisper models (including chunking logic).
*   **`src/extractor.py`**: Handles text-to-summary. Interfaces with Claude and OpenAI APIs. Contains prompt definitions.
*   **`src/downloader.py`**: Wrapper around `yt-dlp` for audio extraction.
*   **`src/utils.py`**: Helper functions for file handling, timestamp formatting, and API retries.
*   **`tests/`**: Contains `pytest` suites for unit testing.

## Development Conventions

*   **Configuration:** Environment variables are managed via `.env`.
*   **Error Handling:** The pipeline uses `retry_with_backoff` for API calls and graceful degradation (e.g., saving the transcript even if summarization fails).
*   **Type Hinting:** Code uses Python type hints (e.g., `List[Segment]`, `Optional[str]`).
*   **Testing:** `pytest` is used for testing. Run tests before committing changes to core logic.
*   **Style:** Adhere to standard Python PEP 8 guidelines.
