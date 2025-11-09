# Transcript Pipeline

A Dockerized Python CLI tool that transcribes YouTube videos using local Whisper model and extracts key information using AI (Claude or GPT).

## Features

- Download audio from YouTube videos
- Transcribe using OpenAI Whisper (local, privacy-focused)
- Extract key information using Claude or GPT
- Generate formatted markdown files
- Fully containerized with Docker
- Easy to transport between systems

## Project Structure

```
transcript-pipeline/
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose setup
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── PLAN.md                # Implementation plan
├── README.md              # This file
├── src/
│   ├── __init__.py
│   ├── main.py            # CLI entry point
│   ├── downloader.py      # YouTube audio download
│   ├── transcriber.py     # Whisper transcription
│   ├── extractor.py       # AI extraction
│   └── utils.py           # Helper functions
├── output/                # Generated markdown files (gitignored)
└── models/                # Whisper model cache (gitignored)
```

## Prerequisites

- Docker and Docker Compose
- (Optional for local run) Python 3.11+
- API key for Claude (Anthropic) or GPT (OpenAI)

## Setup

### 1. Clone or Copy the Project

```bash
cd transcript-pipeline
```

### 2. Configure Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your API key(s):

```bash
# Use Claude (recommended)
ANTHROPIC_API_KEY=your_anthropic_key_here
DEFAULT_LLM=claude

# OR use GPT
OPENAI_API_KEY=your_openai_key_here
DEFAULT_LLM=gpt

# Whisper model size (tiny, base, small, medium, large)
WHISPER_MODEL=base
```

### 3. Build the Docker Image

```bash
docker-compose build
```

This will:
- Install all system dependencies (ffmpeg, etc.)
- Install Python packages
- Set up the environment
- The first run will download the Whisper model to the `./models` directory

## Usage

### Docker (Recommended)

Process a single YouTube video:

```bash
docker-compose run --rm transcript-pipeline https://www.youtube.com/watch?v=VIDEO_ID
```

With custom options:

```bash
# Use a different Whisper model
docker-compose run --rm transcript-pipeline https://youtu.be/VIDEO_ID --model small

# Use GPT instead of Claude
docker-compose run --rm transcript-pipeline https://youtu.be/VIDEO_ID --llm gpt

# Only transcribe (skip AI extraction)
docker-compose run --rm transcript-pipeline https://youtu.be/VIDEO_ID --no-extract

# Custom output directory
docker-compose run --rm transcript-pipeline https://youtu.be/VIDEO_ID --output-dir /app/output/my-folder
```

### Local Python (Alternative)

If you prefer to run without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python -m src.main https://www.youtube.com/watch?v=VIDEO_ID
```

## Output Files

The tool generates two markdown files in the `output/` directory:

### 1. Transcript: `{video-title}-transcript.md`

Contains:
- Video metadata (title, author, date, duration)
- Full transcript with timestamps

Example:
```markdown
# Introduction to Machine Learning

**Author**: Tech Channel
**Date**: 20240115
**URL**: https://www.youtube.com/watch?v=...
**Duration**: 15m 30s

## Transcript

[00:00:00] Welcome to this introduction to machine learning...
[00:00:15] Today we'll cover the basics of supervised learning...
```

### 2. Summary: `{video-title}-summary.md`

Contains AI-extracted information:
- Executive summary
- Key points
- Important quotes
- Main topics
- Actionable insights

Example:
```markdown
# Introduction to Machine Learning - Summary

**Author**: Tech Channel
**Date**: 20240115
**Processed**: 2024-01-20

---

## Executive Summary
This video provides a comprehensive introduction to machine learning...

## Key Points
- Machine learning is a subset of artificial intelligence
- Supervised learning requires labeled training data
...
```

## CLI Options

```
python -m src.main [-h] [--model {tiny,base,small,medium,large}]
                        [--llm {claude,gpt}] [--output-dir OUTPUT_DIR]
                        [--no-extract]
                        url

Positional arguments:
  url                   YouTube video URL

Optional arguments:
  -h, --help           Show help message
  --model MODEL        Whisper model size (default: base)
  --llm LLM           LLM for extraction: claude or gpt (default: claude)
  --output-dir DIR     Output directory (default: ./output)
  --no-extract         Skip extraction, only transcribe
```

## Whisper Model Sizes

| Model  | Size   | Speed  | Accuracy |
|--------|--------|--------|----------|
| tiny   | 39 MB  | Fastest| Lower    |
| base   | 74 MB  | Fast   | Good     |
| small  | 244 MB | Medium | Better   |
| medium | 769 MB | Slow   | High     |
| large  | 1550 MB| Slowest| Highest  |

**Recommendation**: Start with `base` for a good balance of speed and accuracy.

## Transporting Between Systems

### Export the Docker Image

On the source system:

```bash
# Save the image to a tar file
docker save transcript-pipeline:latest -o transcript-pipeline.tar

# Copy the tar file to your target system
```

On the target system:

```bash
# Load the image
docker load -i transcript-pipeline.tar

# Copy the project files
# Make sure to include:
# - docker-compose.yml
# - .env (with your API keys)
# - models/ directory (optional, saves re-download time)

# Run
docker-compose run --rm transcript-pipeline <youtube-url>
```

### Or Use Docker Hub

```bash
# Tag and push (on source system)
docker tag transcript-pipeline:latest yourusername/transcript-pipeline:latest
docker push yourusername/transcript-pipeline:latest

# Pull and run (on target system)
docker pull yourusername/transcript-pipeline:latest
docker-compose run --rm transcript-pipeline <youtube-url>
```

## Troubleshooting

### "Video unavailable" or "Private video"

The video may be:
- Private or deleted
- Geo-restricted
- Age-restricted

Try a different video URL.

### "API key not found"

Make sure your `.env` file contains the correct API key:
- `ANTHROPIC_API_KEY` for Claude
- `OPENAI_API_KEY` for GPT

### Whisper model download fails

The first run downloads the Whisper model. If it fails:
1. Check your internet connection
2. Try a smaller model size: `--model tiny`
3. Manually download and place in `./models/` directory

### Out of memory errors

If transcribing large videos:
1. Use a smaller Whisper model: `--model tiny` or `--model base`
2. Increase Docker memory allocation in Docker Desktop settings

### ffmpeg not found (local Python)

Install ffmpeg:
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `apt-get install ffmpeg`
- **Windows**: Download from https://ffmpeg.org/

## Advanced Usage

### Batch Processing

Create a script to process multiple videos:

```bash
#!/bin/bash
# process-videos.sh

while IFS= read -r url; do
    echo "Processing: $url"
    docker-compose run --rm transcript-pipeline "$url"
done < video-urls.txt
```

Usage:
```bash
chmod +x process-videos.sh
./process-videos.sh
```

### Custom Extraction Prompts

To customize the extraction prompt, edit `src/extractor.py` and modify the `EXTRACTION_PROMPT` variable.

## License

This project is provided as-is for educational and personal use.

## Contributing

Contributions welcome! Please test thoroughly before submitting pull requests.

## Credits

Built with:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [Anthropic Claude](https://www.anthropic.com/) - AI extraction
- [OpenAI GPT](https://openai.com/) - AI extraction
