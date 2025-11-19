from src.transcriber import Transcriber


def test_parse_scribe_response_segments():
    t = Transcriber(engine="scribe", allow_fallback=False)
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
    t = Transcriber(engine="scribe", allow_fallback=False)
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
    t = Transcriber(engine="scribe", allow_fallback=False)
    response = {
        "output": {
            "text": "Single blob transcript text.",
        }
    }

    segments = t._parse_scribe_response(response)
    assert len(segments) == 1
    assert segments[0].text.startswith("Single blob transcript")


