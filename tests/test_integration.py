"""Integration tests for the transcript pipeline."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.pipeline_service import process_video
from src.models import Segment


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock configuration."""
        return {
            'transcription_engine': 'captions',
            'mlx_whisper_model': 'large-v3-turbo',
            'caption_language': 'en',
            'caption_fallback_engine': 'mlx-whisper',
            'default_llm': 'claude',
            'anthropic_api_key': 'test-key',
            'openai_api_key': None,
            'claude_model_id': 'claude-sonnet-4-5',
            'openai_model_id': 'gpt-4o-mini',
            'output_dir': str(tmp_path),
        }

    @pytest.fixture
    def mock_metadata(self):
        """Create mock video metadata."""
        return {
            'title': 'Test Video Title',
            'author': 'Test Author',
            'channel': 'Test Channel',
            'upload_date': '20240101',
            'duration': 300,
            'description': 'Test description',
            'url': 'https://www.youtube.com/watch?v=test123',
            'id': 'test123',
        }

    @pytest.fixture
    def mock_segments(self):
        """Create mock transcript segments."""
        return [
            Segment(start=0.0, end=5.0, text="Hello, this is a test video."),
            Segment(start=5.0, end=10.0, text="We are testing the pipeline."),
            Segment(start=10.0, end=15.0, text="This should work correctly."),
        ]

    def test_pipeline_with_mocked_dependencies(
        self, mock_config, mock_metadata, mock_segments, tmp_path
    ):
        """Test full pipeline with mocked external dependencies."""
        # Create audio directory
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        mock_audio_path = audio_dir / "test.mp3"
        mock_audio_path.touch()

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(mock_audio_path),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock-transcriber"
                mock_transcriber.format_transcript.return_value = "\n".join(
                    f"[{s.start}] {s.text}" for s in mock_segments
                )
                mock_transcriber.get_full_text.return_value = " ".join(
                    s.text for s in mock_segments
                )
                mock_get_transcriber.return_value = mock_transcriber

                with patch('src.services.pipeline_service.TranscriptExtractor') as MockExtractor:
                    mock_extractor = MockExtractor.return_value
                    mock_extractor.extract.return_value = "## Summary\nThis is a test summary."

                    result = process_video(
                        url="https://www.youtube.com/watch?v=test123",
                        llm_type="claude",
                        no_extract=False,
                        config=mock_config,
                    )

                    assert result['success'] is True
                    assert result.get('error') is None
                    assert 'transcript_path' in result
                    assert 'summary_path' in result

                    transcript_path = Path(result['transcript_path'])
                    summary_path = Path(result['summary_path'])

                    assert transcript_path.exists()
                    assert summary_path.exists()

    def test_pipeline_no_extract(self, mock_config, mock_metadata, mock_segments, tmp_path):
        """Test pipeline with extraction disabled."""
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        mock_audio_path = audio_dir / "test.mp3"
        mock_audio_path.touch()

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(mock_audio_path),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock-transcriber"
                mock_transcriber.format_transcript.return_value = "Test transcript"
                mock_transcriber.get_full_text.return_value = "Test transcript"
                mock_get_transcriber.return_value = mock_transcriber

                result = process_video(
                    url="https://www.youtube.com/watch?v=test123",
                    llm_type="claude",
                    no_extract=True,
                    config=mock_config,
                )

                assert result['success'] is True
                assert 'transcript_path' in result
                # Summary should be None when extraction is disabled
                assert result.get('summary_path') is None

    def test_pipeline_handles_download_error(self, mock_config, tmp_path):
        """Test pipeline handles download errors gracefully."""
        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.side_effect = Exception("Download failed: Video unavailable")

            result = process_video(
                url="https://www.youtube.com/watch?v=invalid",
                llm_type="claude",
                no_extract=False,
                config=mock_config,
            )

            assert result['success'] is False
            assert 'error' in result
            assert 'Download failed' in result['error'] or 'Video unavailable' in result['error']

    def test_pipeline_handles_transcription_error(self, mock_config, mock_metadata, tmp_path):
        """Test pipeline handles transcription errors gracefully."""
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        mock_audio_path = audio_dir / "test.mp3"
        mock_audio_path.touch()

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (
                str(mock_audio_path),
                mock_metadata
            )
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.side_effect = Exception("Transcription failed")
                mock_get_transcriber.return_value = mock_transcriber

                result = process_video(
                    url="https://www.youtube.com/watch?v=test123",
                    llm_type="claude",
                    no_extract=False,
                    config=mock_config,
                )

                assert result['success'] is False
                assert 'error' in result


class TestProgressCallbacks:
    """Test progress callback functionality."""

    def test_progress_callback_called(self, tmp_path):
        """Test that progress callbacks are invoked during pipeline execution."""
        mock_config = {
            'transcription_engine': 'mlx-whisper',
            'mlx_whisper_model': 'large-v3-turbo',
            'default_llm': 'claude',
            'anthropic_api_key': 'test-key',
            'output_dir': str(tmp_path),
        }

        progress_updates = []

        def track_progress(update):
            progress_updates.append(update)

        mock_metadata = {'title': 'Test', 'author': 'Author', 'duration': 60, 'id': 'test'}
        mock_segments = [Segment(start=0, end=5, text="Test")]

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        mock_audio_path = audio_dir / "test.mp3"
        mock_audio_path.touch()

        with patch('src.services.pipeline_service.VideoDownloader') as MockDownloader:
            mock_downloader = MockDownloader.return_value
            mock_downloader.get_video_info.return_value = mock_metadata
            mock_downloader.download_audio.return_value = (str(mock_audio_path), mock_metadata)
            mock_downloader.cleanup_audio = Mock()

            with patch('src.services.pipeline_service.get_transcriber') as mock_get_transcriber:
                mock_transcriber = Mock()
                mock_transcriber.transcribe.return_value = mock_segments
                mock_transcriber.engine_name = "mock"
                mock_transcriber.format_transcript.return_value = "Test"
                mock_transcriber.get_full_text.return_value = "Test"
                mock_get_transcriber.return_value = mock_transcriber

                with patch('src.services.pipeline_service.TranscriptExtractor') as MockExtractor:
                    mock_extractor = MockExtractor.return_value
                    mock_extractor.extract.return_value = "Summary"

                    process_video(
                        url="https://youtube.com/watch?v=test",
                        llm_type="claude",
                        no_extract=False,
                        config=mock_config,
                        progress_callback=track_progress,
                    )

        assert len(progress_updates) > 0
        statuses = [u.status for u in progress_updates]
        assert any(s in statuses for s in ['downloading', 'transcribing', 'extracting', 'complete'])
