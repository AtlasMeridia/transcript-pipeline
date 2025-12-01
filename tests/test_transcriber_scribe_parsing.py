"""Tests for ElevenLabs Scribe response parsing."""

from src.transcriber import ElevenLabsTranscriber


def test_parse_scribe_response_segments():
    """Test parsing response with segments."""
    t = ElevenLabsTranscriber(api_key="test-key")
    response = {
        "output": {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": "world"},
            ]
        }
    }

    segments = t._parse_scribe_response(response)
    assert len(segments) == 2
    assert segments[0].text == "Hello"
    assert segments[1].text == "world"


def test_parse_scribe_response_words_fallback():
    """Test parsing response with word-level timestamps."""
    t = ElevenLabsTranscriber(api_key="test-key")
    response = {
        "output": {
            "words": [
                {"start": 0.0, "end": 0.5, "word": "Hello"},
                {"start": 0.5, "end": 1.0, "word": "world!"},
            ]
        }
    }

    segments = t._parse_scribe_response(response)
    # Words should be grouped into a single segment "Hello world!"
    assert len(segments) == 1
    assert "Hello" in segments[0].text
    assert "world" in segments[0].text


def test_parse_scribe_response_text_fallback():
    """Test parsing response with single text blob."""
    t = ElevenLabsTranscriber(api_key="test-key")
    response = {
        "output": {
            "text": "Single blob transcript text.",
        }
    }

    segments = t._parse_scribe_response(response)
    assert len(segments) == 1
    assert segments[0].text.startswith("Single blob transcript")


def test_legacy_transcriber_alias():
    """Test that the Transcriber alias still works for backward compatibility."""
    from src.transcriber import Transcriber
    
    # Should be an alias to ElevenLabsTranscriber
    assert Transcriber is ElevenLabsTranscriber
