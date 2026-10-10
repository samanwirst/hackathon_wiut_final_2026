"""AutoLearn API integration test (M3 vertical slice).

Exercises the real path end to end with the genuine frozen ResNet18 encoder and a
fitted torch Student: create task -> import disclosed QA_ONLY synthetic sessions
-> offline labeling reports UNAVAILABLE (no provider) -> human verification ->
leakage-free split + real training -> held-out evaluation -> shadow comparison
(zero actions) -> gated activation (reject + approve branches) -> rollback ->
offline Student classification.

The QA_ONLY synthetic data is procedurally generated; no metric here is a
real-world quality claim. Ground-truth verification labels are obtained by
regenerating the deterministic fixtures and matching on content hash (a human
reviewer would instead look at the image).
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.autolearn import encoder, fixtures
from app.main import app


@pytest.fixture(scope="module")
def encoder_available():
    try:
        encoder.get_encoder()
    except encoder.EncoderUnavailable as exc:  # pragma: no cover
        pytest.skip(f"pretrained encoder weights unavailable: {exc}")


@pytest.fixture(scope="module")
def client(encoder_available):
    with TestClient(app) as c:
        yield c


def _truth_map(task_id, n_sessions, per_class):
    samples = fixtures.generate_sessions(
        n_sessions=n_sessions, per_class_per_session=per_class, task_slug=f"t{task_id}"
    )
    return {s.image_hash: s.label for s in samples}


def test_full_autolearn_vertical_slice(client, monkeypatch):
    # 1. create task
    r = client.post("/api/autolearn/tasks", json={
        "name": "Bay occupancy (QA)",
        "visual_prompt": "Is the service bay occupied by a vehicle?",
        "positive_label": "occupied",
        "negative_label": "empty",
    })
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    # 2. import disclosed QA_ONLY synthetic sessions
    n_sessions, per_class = 5, 3
    r = client.post(f"/api/autolearn/tasks/{task_id}/import-synthetic",
                    json={"n_sessions": n_sessions, "per_class_per_session": per_class})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qa_only"] is True
    imported = body["imported"]
    assert imported == n_sessions * per_class * 2

    # 3. offline labeling with no provider -> UNAVAILABLE, labels stay pending
    monkeypatch.setattr(config, "VLM_BASE_URL", "")
    monkeypatch.setattr(config, "VLM_MODEL", "")
    r = client.post(f"/api/autolearn/tasks/{task_id}/label")
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"
    # audit recorded the unavailable attempts (no synthetic label invented)
    audit = client.get(f"/api/autolearn/tasks/{task_id}/audit").json()
    assert audit and all(a["status"] == "unavailable" for a in audit)

    # 4. training before verification is refused (no verified labels)
    r = client.post(f"/api/autolearn/tasks/{task_id}/train")
    assert r.status_code == 422

    # 5. human verification — leave two samples unverified to prove exclusion
    samples = client.get(f"/api/autolearn/tasks/{task_id}/samples").json()
    truth = _truth_map(task_id, n_sessions, per_class)
    verified_count = 0
    for s in samples[:-2]:
        label = truth[s["image_hash"]]
        rr = client.post(f"/api/autolearn/samples/{s['id']}/review",
                         json={"verified_label": label, "reviewer": "qa-tester"})
        assert rr.status_code == 200, rr.text
        assert rr.json()["verified"] is True
        verified_count += 1

    # immutable: re-reviewing is refused
    rr = client.post(f"/api/autolearn/samples/{samples[0]['id']}/review",
                     json={"verified_label": truth[samples[0]['image_hash']], "reviewer": "qa-tester"})
    assert rr.status_code == 422

    # 6. train — only verified samples enter the split
    r = client.post(f"/api/autolearn/tasks/{task_id}/train")
    assert r.status_code == 200, r.text
    tr = r.json()
    counts = tr["counts"]
    assert counts["train"] + counts["val"] + counts["test"] == verified_count
    assert tr["metrics"]["support"] == counts["test"]
    assert tr["dataset_hash"] and tr["split_hash"]
    version_id = tr["version_id"]

    # 7. evaluate reproduces held-out metrics from the reloaded artifact
    r = client.post(f"/api/autolearn/versions/{version_id}/evaluate")
    assert r.status_code == 200
    assert "f1" in r.json()["metrics"]

    # 8. shadow mode: comparisons only, every item action == none
    r = client.get(f"/api/autolearn/tasks/{task_id}/shadow")
    assert r.status_code == 200
    shadow = r.json()
    assert shadow["compared"] > 0
    assert all(item["action"] == "none" for item in shadow["items"])

    # 9a. activation declined by human -> not activated
    r = client.post(f"/api/autolearn/versions/{version_id}/activate",
                    json={"approve": False, "approver": "operator"})
    assert r.status_code == 200
    assert r.json()["activated"] is False

    # 9b. gate failure path (raise the bar so even a good model fails)
    monkeypatch.setattr(config, "AUTOLEARN_GATE_MIN_F1", 1.01)
    r = client.post(f"/api/autolearn/versions/{version_id}/activate",
                    json={"approve": True, "approver": "operator"})
    assert r.status_code == 200
    assert r.json()["activated"] is False
    assert "gate" in r.json()["reason"]

    # 9c. gate pass + approval -> activated (gate is config-driven; lower it)
    monkeypatch.setattr(config, "AUTOLEARN_GATE_MIN_F1", 0.0)
    monkeypatch.setattr(config, "AUTOLEARN_GATE_MIN_TEST", 1)
    r = client.post(f"/api/autolearn/versions/{version_id}/activate",
                    json={"approve": True, "approver": "operator"})
    assert r.status_code == 200
    assert r.json()["activated"] is True

    # 10. train a second version and activate it, then roll back to the first
    r = client.post(f"/api/autolearn/tasks/{task_id}/train")
    v2 = r.json()["version_id"]
    r = client.post(f"/api/autolearn/versions/{v2}/activate",
                    json={"approve": True, "approver": "operator"})
    assert r.json()["activated"] is True
    r = client.post(f"/api/autolearn/tasks/{task_id}/rollback", json={"approver": "operator"})
    assert r.status_code == 200
    assert r.json()["rolled_back_to"] == 1

    # activation history persisted
    acts = client.get(f"/api/autolearn/tasks/{task_id}/activations").json()
    actions = [a["action"] for a in acts]
    assert "activate" in actions and "rollback" in actions and "reject" in actions

    # 11. offline Student classification (zero actions) on a QA image
    qa = fixtures.generate_sessions(n_sessions=1, per_class_per_session=1, task_slug="probe")
    img = qa[0].image_bytes
    r = client.post(f"/api/autolearn/tasks/{task_id}/classify",
                    files={"file": ("probe.jpg", img, "image/jpeg")})
    assert r.status_code == 200
    out = r.json()
    assert out["action"] == "none"
    assert out["status"] in {"student", "teacher_fallback", "unknown"}


def test_encoder_is_frozen_and_deterministic(encoder_available):
    enc = encoder.get_encoder()
    assert enc.frozen() is True
    qa = fixtures.generate_sessions(n_sessions=1, per_class_per_session=1, task_slug="enc")
    blob = qa[0].image_bytes
    e1, _ = enc.embed_bytes([blob])
    e2, _ = enc.embed_bytes([blob])
    assert e1.shape == (1, encoder.EMBED_DIM)
    # deterministic in eval mode
    import numpy as np
    np.testing.assert_allclose(e1, e2, rtol=0, atol=1e-5)
