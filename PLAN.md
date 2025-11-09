# Transcript Pipeline - Implementation Plan

## Project Overview
A Dockerized Python CLI tool that transcribes YouTube videos using local Whisper model and extracts key information using AI (Claude/GPT).

## User Requirements
- **Transcription Method**: Local Whisper model (privacy-focused, no API costs)
- **Extraction Method**: AI summarization using GPT/Claude API
- **Language**: Python
- **Interface**: CLI (Command-line interface)
- **Deployment**: Docker container for easy transport between systems

## Project Structure

```
transcript-pipeline/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── downloader.py        # YouTube audio download (yt-dlp)
│   ├── transcriber.py       # Whisper transcription
│   ├── extractor.py         # AI-based extraction
│   └── utils.py             # Helper functions
├── output/                  # Volume mount for generated files
└── models/                  # Volume mount for Whisper models

```

## Core Components

### 1. YouTube Audio Downloader (`downloader.py`)
- Use `yt-dlp` to download audio from YouTube URLs
- Extract video metadata (title, author, date, description)
- Convert to format suitable for Whisper (WAV/MP3)
- Handle errors (invalid URLs, private videos, geo-restrictions)

### 2. Transcription Engine (`transcriber.py`)
- Use OpenAI Whisper (local model)
- Support multiple model sizes (tiny, base, small, medium, large)
- Default to `base` model for balance of speed/accuracy
- Include timestamps in transcript
- Handle long videos with deterministic chunking (e.g., 30-minute max segments with 5-second overlap) to preserve context and respect Whisper memory limits

### 3. AI Extraction (`extractor.py`)
- Support both Anthropic Claude and OpenAI GPT
- Configurable via environment variables
- Extract:
  - Key points and main ideas
  - Important quotes
  - Actionable insights
  - Topic categorization
  - Summary (executive summary style)
- Use structured prompts for consistent output

### 4. CLI Interface (`main.py`)
- Simple command: `python main.py <youtube-url>`
- Optional flags:
  - `--model <whisper-model>` - Choose Whisper model size
  - `--llm <claude|gpt>` - Choose extraction LLM
  - `--output-dir <path>` - Custom output directory
  - `--no-extract` - Skip extraction, only transcribe

### 5. Utility Helpers (`utils.py`)
- Sanitize video titles into filesystem-safe slugs for output filenames and directories
- Centralize common timestamp formatting, retry logic, and configuration loading
- Provide helper to ensure paths stay within the configured output directory

## Docker Configuration

### Dockerfile
- Base image: `python:3.11-slim`
- Install system dependencies:
  - `ffmpeg` (required by Whisper and yt-dlp)
  - `build-essential`, `pkg-config`, `libopenblas-dev` (for Whisper/torch builds)
  - `libffi-dev`, `libssl-dev`, `git`, `curl` (for Anthropic/OpenAI SDKs and source installs)
- Install Python dependencies
- Set working directory
- Configure entry point script that verifies the Whisper model cache

### docker-compose.yml
- Service: `transcript-pipeline`
- Volume mounts:
  - `./output:/app/output` - For markdown outputs
  - `./models:/app/models` - For Whisper model cache (persisted across runs)
- Entry point downloads the default Whisper model into `/app/models` during container startup if the cache volume is empty
- Environment variables from `.env` file
- Easy command: `docker-compose run transcript-pipeline <youtube-url>`

## Dependencies (requirements.txt)

```
yt-dlp>=2024.0.0
openai-whisper>=20231117
anthropic>=0.18.0
openai>=1.0.0
python-dotenv>=1.0.0
```

## Output Format

- Output filenames derive from sanitized video-title slugs to ensure cross-platform compatibility

### Transcript File: `{video-title}-transcript.md`
```markdown
# [Video Title]

**Author**: [Channel Name]
**Date**: [Upload Date]
**URL**: [YouTube URL]
**Duration**: [Video Length]

## Description
[Video Description]

## Transcript

[00:00:00] Speaker text here...
[00:00:15] More text...
```

### Summary File: `{video-title}-summary.md`
```markdown
# [Video Title] - Summary

**Author**: [Channel Name]
**Date**: [Upload Date]
**Processed**: [Current Date]

## Executive Summary
[2-3 sentence overview]

## Key Points
- Point 1
- Point 2
- Point 3

## Important Quotes
> "Quote here"
> - Timestamp: [00:15:30]

## Main Topics
- Topic 1
- Topic 2

## Actionable Insights
1. Insight 1
2. Insight 2

## Full Details
[Detailed extraction with context]
```

## Environment Configuration (.env.example)

```env
# LLM API Keys (choose one or both)
ANTHROPIC_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here

# Default LLM for extraction (claude or gpt)
DEFAULT_LLM=claude

# Whisper model size (tiny, base, small, medium, large)
WHISPER_MODEL=base

# Output directory
OUTPUT_DIR=/app/output
```

## Implementation Steps

1. **Setup Project Structure**
   - Create directory structure
   - Initialize Python package
   - Create configuration files

2. **Implement Downloader**
   - YouTube audio download with yt-dlp
   - Metadata extraction
   - Error handling

3. **Implement Transcriber**
   - Whisper integration
   - Model loading and caching
   - Timestamp formatting
   - Chunking implementation with overlap and optional progress callbacks

4. **Implement Extractor**
   - Claude/GPT API integration
   - Prompt engineering for extraction
   - Structured output formatting

5. **Create CLI Interface**
   - Argument parsing
   - Progress indicators
   - Error messages and logging
   - Call into utilities for safe output path generation

6. **Docker Configuration**
   - Write Dockerfile
   - Create docker-compose.yml
   - Test build and execution, including first-run model download into mounted volume

7. **Documentation**
   - README with setup instructions
   - Usage examples
   - Troubleshooting guide

8. **Testing**
   - Test with various YouTube URLs
   - Test different Whisper models
   - Test both Claude and GPT extraction
   - Verify Docker portability

## Usage Examples

### Docker (Recommended)
```bash
# First time setup
docker-compose build

# Process a single video
docker-compose run transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID

# Use specific Whisper model
docker-compose run transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID --model small

# Use GPT instead of Claude
docker-compose run transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID --llm gpt
```

### Local Python
```bash
# Install dependencies
pip install -r requirements.txt

# Run
python src/main.py https://www.youtube.com/watch?v=VIDEO_ID
```

## Error Handling

- Invalid YouTube URL → Clear error message
- Private/unavailable video → Notify user
- API key missing → Prompt for configuration
- Network errors → Retry logic with exponential backoff
- Whisper model download failure → Fallback to smaller model
- LLM API errors → Save transcript, skip extraction with warning

## Future Enhancements (Out of Scope)

- Batch processing multiple URLs
- Web interface
- Support for other video platforms
- Custom extraction templates
- Multiple language support
- Speaker diarization

## Success Criteria

- ✅ Successfully downloads and transcribes YouTube videos
- ✅ Generates properly formatted markdown files
- ✅ Runs entirely in Docker container
- ✅ Easy to transport between systems
- ✅ Works with both Claude and GPT APIs
- ✅ Handles errors gracefully
- ✅ Clear documentation for setup and usage

## Timeline Estimate

- Project setup: 30 minutes
- Core implementation: 2-3 hours
- Docker configuration: 1 hour
- Testing and documentation: 1 hour
- **Total**: 4-5 hours

---

**Status**: Ready for Review
**Next Step**: Await approval, then begin implementation
