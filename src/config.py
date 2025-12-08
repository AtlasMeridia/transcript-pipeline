"""Centralized configuration for transcript pipeline.

This module provides:
- All constants and magic numbers in one place
- PipelineConfig dataclass for typed configuration
- Configuration loading and validation functions
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# =============================================================================
# Constants - Centralized Magic Numbers
# =============================================================================

# Transcription
DEFAULT_TRANSCRIPTION_ENGINE = "whisper"
DEFAULT_WHISPER_MODEL = "large-v3"
DEFAULT_SCRIBE_MODEL = "scribe_v2"
SEGMENT_GAP_THRESHOLD_SECONDS = 1.2  # Gap threshold for word-to-segment grouping

# Chunked transcription for long audio (memory safety)
CHUNK_DURATION_SECONDS = 30 * 60  # 30 minutes per chunk
CHUNK_OVERLAP_SECONDS = 5  # 5 second overlap for deduplication
MIN_AUDIO_DURATION_FOR_CHUNKING = 30 * 60  # Only chunk audio > 30 minutes

# Extraction
MAX_CHARS_PER_CHUNK = 8000  # Character budget per chunk for LLM context
MAX_TOKENS_OUTPUT = 4000  # Max tokens for LLM response
GPT_TEMPERATURE = 0.3  # Temperature for GPT completions

# LLM Models
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"
DEFAULT_GPT_MODEL = "gpt-4o-mini"
DEFAULT_LLM = "claude"

# Deprecated model mappings
DEPRECATED_CLAUDE_MODELS = {
    "claude-3-5-sonnet-20241022": DEFAULT_CLAUDE_MODEL,
    "claude-3-5-sonnet-latest": DEFAULT_CLAUDE_MODEL,
}

# Output formatting
MAX_FILENAME_LENGTH = 200  # Max length for sanitized filenames
DESCRIPTION_TRUNCATE_LENGTH = 500  # Max chars for video description in output

# Output directories
DEFAULT_OUTPUT_DIR = "./output"


# =============================================================================
# Exceptions
# =============================================================================

class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass
class PipelineConfig:
    """Typed configuration for the transcript pipeline.

    This dataclass holds all configuration values with proper types
    and default values. Use `load_pipeline_config()` to create an
    instance from environment variables.
    """

    # Transcription settings
    transcription_engine: str = DEFAULT_TRANSCRIPTION_ENGINE
    whisper_model: str = DEFAULT_WHISPER_MODEL
    whisper_model_dir: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    scribe_model_id: str = DEFAULT_SCRIBE_MODEL

    # LLM settings
    default_llm: str = DEFAULT_LLM
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    claude_model_id: str = DEFAULT_CLAUDE_MODEL
    openai_model_id: str = DEFAULT_GPT_MODEL

    # Output settings
    output_dir: str = DEFAULT_OUTPUT_DIR

    # Server settings (for API mode)
    cors_origins: str = "*"
    port: int = 8000

    def validate(self, no_extract: bool = False) -> None:
        """
        Validate configuration and check required API keys.

        Args:
            no_extract: If True, skip validation of LLM API keys

        Raises:
            ConfigurationError: If required configuration is missing
        """
        errors = []

        # Validate transcription engine requirements
        if self.transcription_engine in ("elevenlabs", "scribe"):
            if not self.elevenlabs_api_key:
                errors.append(
                    "ELEVENLABS_API_KEY is required when TRANSCRIPTION_ENGINE=elevenlabs/scribe. "
                    "Set the environment variable or use TRANSCRIPTION_ENGINE=whisper for local transcription."
                )

        # Validate LLM requirements (unless extraction is disabled)
        if not no_extract:
            if self.default_llm == "claude" and not self.anthropic_api_key:
                errors.append(
                    "ANTHROPIC_API_KEY is required when DEFAULT_LLM=claude. "
                    "Set the environment variable, use --llm gpt, or use --no-extract to skip extraction."
                )
            elif self.default_llm == "gpt" and not self.openai_api_key:
                errors.append(
                    "OPENAI_API_KEY is required when DEFAULT_LLM=gpt. "
                    "Set the environment variable, use --llm claude, or use --no-extract to skip extraction."
                )

        if errors:
            raise ConfigurationError("\n".join(errors))

    def to_dict(self) -> dict:
        """Convert config to dictionary (for backward compatibility)."""
        return {
            'transcription_engine': self.transcription_engine,
            'whisper_model': self.whisper_model,
            'whisper_model_dir': self.whisper_model_dir,
            'elevenlabs_api_key': self.elevenlabs_api_key,
            'scribe_model_id': self.scribe_model_id,
            'default_llm': self.default_llm,
            'anthropic_api_key': self.anthropic_api_key,
            'openai_api_key': self.openai_api_key,
            'claude_model_id': self.claude_model_id,
            'openai_model_id': self.openai_model_id,
            'output_dir': self.output_dir,
            'cors_origins': self.cors_origins,
            'port': self.port,
        }


# =============================================================================
# Configuration Loading
# =============================================================================

def load_pipeline_config() -> PipelineConfig:
    """
    Load configuration from environment variables into PipelineConfig.

    Returns:
        PipelineConfig instance with values from environment
    """
    load_dotenv()

    return PipelineConfig(
        # Transcription
        transcription_engine=os.getenv('TRANSCRIPTION_ENGINE', DEFAULT_TRANSCRIPTION_ENGINE).lower(),
        whisper_model=os.getenv('WHISPER_MODEL', DEFAULT_WHISPER_MODEL),
        whisper_model_dir=os.getenv('WHISPER_MODEL_DIR'),
        elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
        scribe_model_id=os.getenv('SCRIBE_MODEL_ID', DEFAULT_SCRIBE_MODEL),

        # LLM
        default_llm=os.getenv('DEFAULT_LLM', DEFAULT_LLM),
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        claude_model_id=os.getenv('CLAUDE_MODEL_ID', DEFAULT_CLAUDE_MODEL),
        openai_model_id=os.getenv('OPENAI_MODEL_ID', DEFAULT_GPT_MODEL),

        # Output
        output_dir=os.getenv('OUTPUT_DIR', DEFAULT_OUTPUT_DIR),

        # Server
        cors_origins=os.getenv('CORS_ORIGINS', '*'),
        port=int(os.getenv('PORT', '8000')),
    )


def load_config() -> dict:
    """
    Load configuration from environment variables.

    This is a backward-compatible function that returns a dictionary.
    For new code, prefer using load_pipeline_config() which returns
    a typed PipelineConfig dataclass.

    Returns:
        Dictionary containing configuration values
    """
    config = load_pipeline_config()
    return config.to_dict()


def validate_config(config: dict, no_extract: bool = False) -> None:
    """
    Validate configuration dictionary.

    This is a backward-compatible function for dict-based config.
    For new code, prefer using PipelineConfig.validate() directly.

    Args:
        config: Configuration dictionary
        no_extract: If True, skip validation of LLM API keys

    Raises:
        ConfigurationError: If required configuration is missing
    """
    errors = []

    # Validate transcription engine requirements
    engine = config.get('transcription_engine', DEFAULT_TRANSCRIPTION_ENGINE)

    if engine in ('elevenlabs', 'scribe'):
        if not config.get('elevenlabs_api_key'):
            errors.append(
                "ELEVENLABS_API_KEY is required when TRANSCRIPTION_ENGINE=elevenlabs/scribe. "
                "Set the environment variable or use TRANSCRIPTION_ENGINE=whisper for local transcription."
            )

    # Validate LLM requirements (unless extraction is disabled)
    if not no_extract:
        llm = config.get('default_llm', DEFAULT_LLM)

        if llm == 'claude' and not config.get('anthropic_api_key'):
            errors.append(
                "ANTHROPIC_API_KEY is required when DEFAULT_LLM=claude. "
                "Set the environment variable, use --llm gpt, or use --no-extract to skip extraction."
            )
        elif llm == 'gpt' and not config.get('openai_api_key'):
            errors.append(
                "OPENAI_API_KEY is required when DEFAULT_LLM=gpt. "
                "Set the environment variable, use --llm claude, or use --no-extract to skip extraction."
            )

    if errors:
        raise ConfigurationError("\n".join(errors))
