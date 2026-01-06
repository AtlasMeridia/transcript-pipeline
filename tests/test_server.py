"""Tests for FastAPI server endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "jobs" in data
        assert "total" in data["jobs"]


class TestConfigEndpoint:
    """Tests for config endpoint."""

    def test_config_returns_non_sensitive_data(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        # Should have boolean flags, not actual keys
        assert "has_anthropic_key" in data
        assert "has_openai_key" in data
        assert isinstance(data["has_anthropic_key"], bool)
        assert isinstance(data["has_openai_key"], bool)

        # Should not contain actual API keys
        assert "anthropic_api_key" not in data
        assert "openai_api_key" not in data

    def test_config_includes_transcription_engine(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        assert "transcription_engine" in data
        assert "mlx_whisper_model" in data


class TestProcessEndpoint:
    """Tests for process endpoint."""

    def test_process_returns_job_id(self, client):
        response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=test123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["progress"] == 0

    def test_process_with_options(self, client):
        response = client.post(
            "/api/process",
            json={
                "url": "https://www.youtube.com/watch?v=test123",
                "llm_type": "gpt",
                "extract": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestJobEndpoints:
    """Tests for job status endpoints."""

    def test_job_not_found(self, client):
        response = client.get("/api/jobs/nonexistent")
        assert response.status_code == 404

    def test_transcript_not_found(self, client):
        response = client.get("/api/jobs/nonexistent/transcript")
        assert response.status_code == 404

    def test_summary_not_found(self, client):
        response = client.get("/api/jobs/nonexistent/summary")
        assert response.status_code == 404

    def test_job_status_after_creation(self, client):
        # Create a job first
        create_response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=test123"}
        )
        job_id = create_response.json()["job_id"]

        # Now get the status
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["job_id"] == job_id

    def test_download_invalid_type(self, client):
        # Create a job first
        create_response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=test123"}
        )
        job_id = create_response.json()["job_id"]

        # Try to download with invalid file type
        response = client.get(f"/api/jobs/{job_id}/download/invalid")
        assert response.status_code == 400


class TestSSEStream:
    """Tests for SSE streaming endpoint."""

    def test_stream_job_not_found(self, client):
        response = client.get("/api/jobs/nonexistent/stream")
        assert response.status_code == 404

    def test_stream_returns_event_stream(self, client):
        # Create a job first
        create_response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=test123"}
        )
        job_id = create_response.json()["job_id"]

        # Connect to stream (will timeout but should have correct headers)
        with client.stream("GET", f"/api/jobs/{job_id}/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            # Read at least the first event
            for line in response.iter_lines():
                if line:
                    assert line.startswith("data:") or line.startswith(":")
                    break


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_endpoint(self, client):
        response = client.get("/")
        # Should return HTML or error if frontend not found
        assert response.status_code in [200, 404]
