"""VLM router tests (M2-AC4): caching, sampling, cooldown, budget, in-flight
dedup, versioned invalidation and counters. No real provider is used; a fake
teacher counts invocations so we can prove unnecessary calls are suppressed."""

import threading

from app.teacher import TeacherAdapter, TeacherResult
from app.vlm_router import VersionedTTLCache, VlmRouter


class FakeTeacher(TeacherAdapter):
    provider_name = "fake"
    model = "fake-vlm"

    def __init__(self, status="ok", label="yes"):
        self._status = status
        self._label = label
        self.calls = 0
        self._lock = threading.Lock()

    def classify(self, image_bytes, prompt, labels):
        with self._lock:
            self.calls += 1
        return TeacherResult(
            status=self._status, label=self._label, confidence=0.8,
            model=self.model, latency_ms=1.0, usage={"total_tokens": 5},
        )


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_router(teacher, clock=None, **kw):
    clk = clock or Clock()
    return VlmRouter(teacher_provider=lambda: teacher, clock=clk, **kw)


def route(router, roi=b"roi-a", scope="scope", task="task"):
    return router.route(
        task_key=task, scope=scope, prompt="is the hood open?",
        labels=["yes", "no"], image_bytes=roi,
    )


def test_cache_hit_suppresses_second_call():
    t = FakeTeacher()
    r = make_router(t)
    d1 = route(r)
    d2 = route(r)  # identical ROI
    assert d1.status == "called"
    assert d2.status == "cache_hit"
    assert t.calls == 1
    assert r.counters.cache_hits == 1


def test_changed_roi_invalidates_reuse():
    t = FakeTeacher()
    r = make_router(t, budget_per_task=10, sample_interval_s=0, cooldown_s=0)
    route(r, roi=b"roi-a")
    route(r, roi=b"roi-b")  # different ROI -> different key -> new call
    assert t.calls == 2


def test_budget_exhaustion_suppresses_without_call():
    t = FakeTeacher()
    r = make_router(t, budget_per_task=1, sample_interval_s=0, cooldown_s=0)
    d1 = route(r, roi=b"roi-a")
    d2 = route(r, roi=b"roi-b")
    assert d1.status == "called"
    assert d2.status == "suppressed_budget"
    assert t.calls == 1
    assert r.counters.suppressed_budget == 1


def test_sampling_interval_suppresses():
    t = FakeTeacher()
    clk = Clock()
    r = make_router(t, clock=clk, budget_per_task=10, sample_interval_s=100, cooldown_s=0)
    route(r, roi=b"roi-a")  # call at t=1000
    clk.t += 1  # still within interval
    d2 = route(r, roi=b"roi-b")
    assert d2.status == "suppressed_sampling"
    assert t.calls == 1


def test_sampling_allows_after_interval():
    t = FakeTeacher()
    clk = Clock()
    r = make_router(t, clock=clk, budget_per_task=10, sample_interval_s=10, cooldown_s=0)
    route(r, roi=b"roi-a")
    clk.t += 20
    d2 = route(r, roi=b"roi-b")
    assert d2.status == "called"
    assert t.calls == 2


def test_cooldown_suppresses_same_scope():
    t = FakeTeacher()
    clk = Clock()
    r = make_router(t, clock=clk, budget_per_task=10, sample_interval_s=0, cooldown_s=100)
    route(r, roi=b"roi-a", scope="s1")
    clk.t += 1
    d2 = route(r, roi=b"roi-b", scope="s1")
    assert d2.status == "suppressed_cooldown"
    assert t.calls == 1


def test_counters_track_outcomes():
    t = FakeTeacher()
    r = make_router(t, budget_per_task=10, sample_interval_s=0, cooldown_s=0)
    route(r, roi=b"roi-a")
    route(r, roi=b"roi-a")  # cache hit
    snap = r.counters.snapshot()
    assert snap["calls"] == 1
    assert snap["cache_hits"] == 1
    assert snap["confirmed"] == 1


def test_failure_status_not_cached_and_not_confirmed():
    t = FakeTeacher(status="error", label=None)
    r = make_router(t, budget_per_task=10, sample_interval_s=0, cooldown_s=0)
    d1 = route(r, roi=b"roi-a")
    assert d1.confirmed is False
    # transient error not cached: a second identical ROI calls again
    d2 = route(r, roi=b"roi-a")
    assert d2.status == "called"
    assert t.calls == 2
    assert r.counters.failed == 2


def test_ttl_cache_expires():
    clk = Clock()
    cache = VersionedTTLCache(max_entries=10, ttl_seconds=5)
    res = TeacherResult(status="ok", label="yes")
    cache.put("k", res, clk())
    assert cache.get("k", clk()) is not None
    clk.t += 6
    assert cache.get("k", clk()) is None


def test_cache_lru_eviction():
    cache = VersionedTTLCache(max_entries=2, ttl_seconds=100)
    res = TeacherResult(status="ok", label="yes")
    cache.put("a", res, 0)
    cache.put("b", res, 0)
    cache.put("c", res, 0)  # evicts "a"
    assert cache.get("a", 0) is None
    assert cache.get("c", 0) is not None
    assert cache.evictions == 1


def test_unavailable_teacher_route_not_confirmed():
    from app.teacher import UnavailableTeacher

    r = make_router(UnavailableTeacher(), budget_per_task=10, sample_interval_s=0, cooldown_s=0)
    d = route(r)
    assert d.status == "called"
    assert d.result.status == "missing_credentials"
    assert d.confirmed is False
