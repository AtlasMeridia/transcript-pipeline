#!/bin/bash
# Entrypoint script for Docker CLI mode
# Validates environment and runs the transcript pipeline CLI

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required environment based on configuration
validate_environment() {
    local errors=0

    # Check transcription engine requirements
    ENGINE="${TRANSCRIPTION_ENGINE:-whisper}"

    if [ "$ENGINE" = "elevenlabs" ]; then
        if [ -z "$ELEVENLABS_API_KEY" ]; then
            log_error "ELEVENLABS_API_KEY is required when TRANSCRIPTION_ENGINE=elevenlabs"
            errors=$((errors + 1))
        fi
    fi

    # Check LLM requirements (only if extraction is enabled)
    LLM="${DEFAULT_LLM:-claude}"

    # Note: We don't fail here because --no-extract might be used
    # The actual validation happens in the Python code
    if [ "$LLM" = "claude" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
        log_warn "ANTHROPIC_API_KEY not set. Extraction will be skipped unless --no-extract is used."
    elif [ "$LLM" = "gpt" ] && [ -z "$OPENAI_API_KEY" ]; then
        log_warn "OPENAI_API_KEY not set. Extraction will be skipped unless --no-extract is used."
    fi

    if [ $errors -gt 0 ]; then
        log_error "Environment validation failed. Please check your configuration."
        exit 1
    fi
}

# Pre-download Whisper model if needed
preload_whisper_model() {
    ENGINE="${TRANSCRIPTION_ENGINE:-whisper}"

    if [ "$ENGINE" = "whisper" ]; then
        MODEL="${WHISPER_MODEL:-large-v3}"
        MODEL_DIR="${WHISPER_MODEL_DIR:-/app/models}"

        # Check if model needs to be downloaded
        if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR 2>/dev/null)" ]; then
            log_info "Pre-downloading Whisper model '$MODEL'..."
            python -c "import whisper; whisper.load_model('$MODEL', download_root='$MODEL_DIR')" 2>/dev/null || true
        fi
    fi
}

# Main execution
main() {
    log_info "Transcript Pipeline CLI"
    log_info "======================"

    # Validate environment
    validate_environment

    # Pre-download model if needed (optional, don't fail if it errors)
    preload_whisper_model || true

    # Run the pipeline with all arguments passed to this script
    exec python -m src.main "$@"
}

# Run main with all script arguments
main "$@"
