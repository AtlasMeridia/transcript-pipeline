"""Tests for transcription engine implementations."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.transcriber import (
    BaseTranscriber,
    MLXWhisperTranscriber,
    CaptionTranscriber,
    CaptionsUnavailableError,
    get_transcriber,
    Transcriber,
    WhisperTranscriber,
)
from src.models import Segment


# =============================================================================
# MLXWhisperTranscriber Tests
# =============================================================================

class TestMLXWhisperTranscriber:
    """Tests for MLXWhisperTranscriber."""

    def test_model_shortcut_resolution(self):
        """Test that model shortcuts resolve to full HuggingFace paths."""
        t = MLXWhisperTranscriber(model="small")
        assert t.model_path == "mlx-community/whisper-small-mlx"
        assert t.model_name == "small"

    def test_model_large_v3_turbo(self):
        """Test the default/recommended model."""
        t = MLXWhisperTranscriber(model="large-v3-turbo")
        assert t.model_path == "mlx-community/whisper-large-v3-turbo"

    def test_custom_model_path(self):
        """Test that custom HuggingFace paths are passed through."""
        custom_path = "my-org/custom-whisper-model"
        t = MLXWhisperTranscriber(model=custom_path)
        assert t.model_path == custom_path
        assert t.model_name == custom_path

    def test_engine_name_includes_model(self):
        """Test that engine_name includes the model identifier."""
        t = MLXWhisperTranscriber(model="medium")
        assert "mlx-whisper" in t.engine_name
        assert "medium" in t.engine_name

    def test_lazy_import_not_triggered_on_init(self):
        """Test that mlx_whisper is not imported during initialization."""
        t = MLXWhisperTranscriber(model="tiny")
        # Should not have loaded the module yet
        assert t._mlx_whisper is None

    def test_transcribe_with_mocked_mlx(self):
        """Test transcribe method with mocked mlx_whisper."""
        t = MLXWhisperTranscriber(model="tiny")

        # Mock the mlx_whisper module
        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {
            "segments": [
                {"start": 0.0, "end": 1.5, "text": " Hello world "},
                {"start": 1.5, "end": 3.0, "text": " How are you? "},
            ]
        }
        t._mlx_whisper = mock_mlx

        segments = t.transcribe("/fake/audio.mp3")

        assert len(segments) == 2
        assert segments[0].text == "Hello world"
        assert segments[0].start == 0.0
        assert segments[1].text == "How are you?"
        mock_mlx.transcribe.assert_called_once()

    def test_transcribe_text_fallback(self):
        """Test fallback when no segments but text is available."""
        t = MLXWhisperTranscriber(model="tiny")

        mock_mlx = MagicMock()
        mock_mlx.transcribe.return_value = {
            "text": "Single text blob without segments"
        }
        t._mlx_whisper = mock_mlx

        segments = t.transcribe("/fake/audio.mp3")

        assert len(segments) == 1
        assert "Single text blob" in segments[0].text


# =============================================================================
# CaptionTranscriber Tests
# =============================================================================

class TestCaptionTranscriber:
    """Tests for CaptionTranscriber."""

    def test_initialization(self):
        """Test CaptionTranscriber initialization."""
        t = CaptionTranscriber(output_dir="./test_output", language="es")
        assert t.output_dir == "./test_output"
        assert t.language == "es"

    def test_engine_name(self):
        """Test engine_name property."""
        t = CaptionTranscriber()
        assert t.engine_name == "captions"

    def test_transcribe_requires_url(self):
        """Test that transcribe raises ValueError without URL."""
        t = CaptionTranscriber()
        with pytest.raises(ValueError, match="requires 'url' parameter"):
            t.transcribe("/fake/audio.mp3")


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestGetTranscriber:
    """Tests for get_transcriber factory function."""

    def test_returns_mlx_whisper_for_whisper_engine(self):
        """Test factory returns MLXWhisperTranscriber for whisper engines."""
        for engine in ["mlx-whisper", "mlx", "whisper"]:
            t = get_transcriber(engine=engine)
            assert isinstance(t, MLXWhisperTranscriber)

    def test_returns_caption_transcriber(self):
        """Test factory returns CaptionTranscriber for captions engine."""
        t = get_transcriber(engine="captions")
        assert isinstance(t, CaptionTranscriber)

    def test_auto_defaults_to_mlx_whisper(self):
        """Test 'auto' engine defaults to MLXWhisperTranscriber."""
        t = get_transcriber(engine="auto")
        assert isinstance(t, MLXWhisperTranscriber)

    def test_respects_model_kwarg(self):
        """Test that model kwarg is passed to MLXWhisperTranscriber."""
        t = get_transcriber(engine="mlx-whisper", model="small")
        assert isinstance(t, MLXWhisperTranscriber)
        assert t.model_name == "small"

    @patch.dict(os.environ, {"TRANSCRIPTION_ENGINE": "captions"})
    def test_reads_engine_from_environment(self):
        """Test factory reads engine from TRANSCRIPTION_ENGINE env var."""
        t = get_transcriber()
        assert isinstance(t, CaptionTranscriber)


# =============================================================================
# Base Class Method Tests
# =============================================================================

class TestBaseTranscriberMethods:
    """Tests for BaseTranscriber utility methods."""

    def test_format_transcript_with_timestamps(self):
        """Test format_transcript includes timestamps."""
        t = MLXWhisperTranscriber(model="tiny")
        segments = [
            Segment(start=0.0, end=1.0, text="Hello"),
            Segment(start=65.0, end=66.0, text="World"),
        ]

        result = t.format_transcript(segments, include_timestamps=True)

        assert "[00:00:00]" in result
        assert "[00:01:05]" in result
        assert "Hello" in result
        assert "World" in result

    def test_format_transcript_without_timestamps(self):
        """Test format_transcript excludes timestamps when requested."""
        t = MLXWhisperTranscriber(model="tiny")
        segments = [
            Segment(start=0.0, end=1.0, text="Hello"),
            Segment(start=1.0, end=2.0, text="World"),
        ]

        result = t.format_transcript(segments, include_timestamps=False)

        assert "[" not in result
        assert "Hello" in result
        assert "World" in result

    def test_get_full_text(self):
        """Test get_full_text joins segment text."""
        t = MLXWhisperTranscriber(model="tiny")
        segments = [
            Segment(start=0.0, end=1.0, text="Hello"),
            Segment(start=1.0, end=2.0, text="beautiful"),
            Segment(start=2.0, end=3.0, text="world"),
        ]

        result = t.get_full_text(segments)

        assert result == "Hello beautiful world"


# =============================================================================
# Legacy Alias Tests
# =============================================================================

class TestLegacyAliases:
    """Tests for backward compatibility aliases."""

    def test_transcriber_alias(self):
        """Test that Transcriber alias points to MLXWhisperTranscriber."""
        assert Transcriber is MLXWhisperTranscriber

    def test_whisper_transcriber_alias(self):
        """Test that WhisperTranscriber alias points to MLXWhisperTranscriber."""
        assert WhisperTranscriber is MLXWhisperTranscriber

    def test_aliases_are_instantiable(self):
        """Test that aliases can be instantiated."""
        t1 = Transcriber(model="tiny")
        t2 = WhisperTranscriber(model="tiny")

        assert isinstance(t1, MLXWhisperTranscriber)
        assert isinstance(t2, MLXWhisperTranscriber)
