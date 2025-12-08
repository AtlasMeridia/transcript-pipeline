"""Utility functions for transcript pipeline."""

import re
import time
import logging
from pathlib import Path
from typing import Callable, Any

# Re-export config functions for backward compatibility
from .config import (
    load_config,
    validate_config,
    ConfigurationError,
    load_pipeline_config,
    PipelineConfig,
    # Constants
    MAX_FILENAME_LENGTH,
    DESCRIPTION_TRUNCATE_LENGTH,
)

logger = logging.getLogger(__name__)


def sanitize_filename(title: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """
    Sanitize video title into filesystem-safe slug.

    Args:
        title: The video title to sanitize
        max_length: Maximum length of the sanitized filename

    Returns:
        A filesystem-safe slug
    """
    # Remove or replace problematic characters
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')

    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]

    # Ensure not empty
    if not slug:
        slug = "untitled"

    return slug


def format_timestamp(seconds: float) -> str:
    """
    Format seconds into [HH:MM:SS] timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"


def ensure_output_path(output_dir: str, filename: str) -> Path:
    """
    Ensure the output path is within the configured output directory.

    Args:
        output_dir: Base output directory
        filename: Filename to write

    Returns:
        Validated Path object

    Raises:
        ValueError: If the path escapes the output directory
    """
    output_path = Path(output_dir).resolve()
    file_path = (output_path / filename).resolve()

    # Ensure the file path is within output_dir
    if not str(file_path).startswith(str(output_path)):
        raise ValueError(f"Invalid path: {filename} escapes output directory")

    # Create directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    return file_path


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} attempts failed.")

    raise last_exception


def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1h 23m 45s")
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


class TimedOperation:
    """Context manager for timing operations with logging.

    Usage:
        with TimedOperation("Transcribing audio"):
            result = transcriber.transcribe(audio_path)
        # Logs: "Transcribing audio completed in 45.2s"
    """

    def __init__(self, operation_name: str, log_level: str = "info"):
        """
        Initialize the timed operation.

        Args:
            operation_name: Description of the operation being timed
            log_level: Logging level ('debug', 'info', 'warning')
        """
        self.operation_name = operation_name
        self.log_level = log_level
        self.start_time = None
        self.elapsed = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start_time

        if exc_type is None:
            msg = f"{self.operation_name} completed in {self.elapsed:.1f}s"
        else:
            msg = f"{self.operation_name} failed after {self.elapsed:.1f}s"

        log_func = getattr(logger, self.log_level, logger.info)
        log_func(msg)

        return False  # Don't suppress exceptions
