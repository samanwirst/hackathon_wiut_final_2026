"""Deterministic NL -> DSL compiler tests (M2-AC1).

Covers: successful compilation of the supported trigger families, strict
rejection of unsupported/ambiguous requests, visual-predicate detection, and
the guarantee that the draft is always validatable by WorkflowDSL (no free-form
or executable output)."""

from app.nl_compiler import compile_text
from app.schemas import WorkflowDSL

ZONES = [{"id": 7, "name": "Service Bay A"}]


def test_enter_compiles_to_valid_dsl():
    r = compile_text("Alert me when a car enters Service Bay A", 1, ZONES)
    assert r.ok and r.draft is not None
    assert r.draft["object_class"] == "car"
    assert r.draft["trigger"]["type"] == "object_entered_zone"
    assert r.draft["trigger"]["zone_id"] == 7
    assert r.draft["requires_approval"] is True
    WorkflowDSL.model_validate(r.draft)  # must satisfy the strict DSL


def test_dwell_parses_duration():
    r = compile_text("notify when a truck stays in Service Bay A for 10 minutes", 1, ZONES)
    assert r.ok, r.errors
    assert r.draft["trigger"]["type"] == "dwell_in_zone"
    assert r.draft["trigger"]["duration_seconds"] == 600.0


def test_count_parses_threshold():
    r = compile_text("tell me when more than 3 cars are in Service Bay A", 1, ZONES)
    assert r.ok, r.errors
    assert r.draft["trigger"]["type"] == "object_count_exceeded"
    assert r.draft["trigger"]["threshold"] == 3


def test_dwell_without_duration_rejected():
    r = compile_text("notify when a car stays in Service Bay A", 1, ZONES)
    assert not r.ok
    assert any("duration" in e for e in r.errors)


def test_unsupported_class_rejected():
    r = compile_text("alert when a spaceship enters Service Bay A", 1, ZONES)
    assert not r.ok
    assert any("object class" in e for e in r.errors)


def test_ambiguous_vehicle_rejected():
    r = compile_text("alert when a vehicle enters Service Bay A", 1, ZONES)
    assert not r.ok
    assert any("ambiguous" in e.lower() or "vehicle" in e.lower() for e in r.errors)


def test_unknown_trigger_rejected():
    r = compile_text("do something interesting with a car", 1, ZONES)
    assert not r.ok
    assert any("trigger" in e for e in r.errors)


def test_ambiguous_zone_rejected_when_multiple():
    zones = [{"id": 1, "name": "Bay A"}, {"id": 2, "name": "Bay B"}]
    r = compile_text("alert when a car enters", 1, zones)
    assert not r.ok
    assert any("zone" in e.lower() for e in r.errors)


def test_single_zone_assumed_with_warning():
    r = compile_text("alert when a car enters", 1, ZONES)
    assert r.ok, r.errors
    assert any("assuming zone" in w for w in r.warnings)


def test_external_delivery_rejected():
    r = compile_text("when a car enters Service Bay A send a webhook", 1, ZONES)
    assert not r.ok
    assert any("external delivery" in e for e in r.errors)


def test_visual_predicate_detected():
    r = compile_text(
        "when a car enters Service Bay A, verify the hood is open", 1, ZONES
    )
    assert r.ok, r.errors
    assert "visual_predicate" in r.draft
    vp = r.draft["visual_predicate"]
    assert vp["expected_label"] in vp["labels"]
    WorkflowDSL.model_validate(r.draft)


def test_empty_rejected():
    assert not compile_text("", 1, ZONES).ok
    assert not compile_text("  ", 1, ZONES).ok
