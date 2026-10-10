"""Offline labeling transport tests.

DISCLOSED MOCK: these tests monkeypatch ``labeling._post_and_read`` (the httpx
POST+streamed-read step) to return crafted OpenAI-compatible responses. They
verify the client's *contract* — strict validation, error mapping, and that a
provider response is required — without a live GPU. Real Teacher labeling against
a self-hosted endpoint remains UNVERIFIED until run by the operator.
"""

import json

import pytest

from app.autolearn import labeling


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", "http://127.0.0.1:18080/v1")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "qa/mock-vlm")
    monkeypatch.setattr(labeling.config, "VLM_API_KEY", "")


def _mock_response(content: str, status_code: int = 200):
    async def _fake(url, body, headers, timeout):
        payload = json.dumps(
            {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 7}}
        ).encode()
        return status_code, payload
    return _fake


def test_labeled_valid_response(provider, monkeypatch):
    monkeypatch.setattr(labeling, "_post_and_read", _mock_response('{"label": "occupied", "confidence": 0.88}'))
    cand = labeling.classify_sync(b"img", prompt="is it occupied?", labels=["occupied", "empty"])
    assert cand.status == "labeled"
    assert cand.label == "occupied"
    assert cand.confidence == 0.88
    # The provider omitted a model: the ACTUAL model is unknown and is NOT faked
    # from the configured alias (C-007). The alias stays separately in raw.
    assert cand.model is None
    assert cand.raw["configured_alias"] == "qa/mock-vlm"
    assert cand.method == "chat_json"
    assert cand.attempted is True


def test_invalid_json_surfaced(provider, monkeypatch):
    monkeypatch.setattr(labeling, "_post_and_read", _mock_response("occupied, pretty sure"))
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "invalid_response"
    assert cand.label is None


def test_unknown_label_surfaced(provider, monkeypatch):
    monkeypatch.setattr(labeling, "_post_and_read", _mock_response('{"label": "spaceship", "confidence": 0.9}'))
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "invalid_response"


def test_http_error_mapped(provider, monkeypatch):
    monkeypatch.setattr(labeling, "_post_and_read", _mock_response("{}", status_code=500))
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "error"


def test_auth_failure_mapped(provider, monkeypatch):
    monkeypatch.setattr(labeling, "_post_and_read", _mock_response("{}", status_code=401))
    cand = labeling.classify_sync(b"img", prompt="q", labels=["occupied", "empty"])
    assert cand.status == "error"
    assert "authentication" in (cand.detail or "")


def test_oversize_image_rejected_before_request(provider, monkeypatch):
    monkeypatch.setattr(labeling.config, "AUTOLEARN_LABEL_MAX_IMAGE_BYTES", 10)
    cand = labeling.classify_sync(b"x" * 100, prompt="q", labels=["occupied", "empty"])
    assert cand.status == "error"
    assert "byte cap" in (cand.detail or "")
