"""Regression tests for issues found in the final PR review."""
import os
import re
import sys
import types

import numpy as np
import pytest

from focusguard import runtime_state as rs
from focusguard.behavior import BehaviorAnalyzer, Observation
from focusguard.evaluation.synthetic import noisy, random_gallery
from focusguard.identity import CONFIRMED, IdentityManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------ tracker: phone != tracking
def test_phone_detection_uses_a_separate_yolo_instance(monkeypatch):
    calls = []

    class FakeYOLO:
        instances = []

        def __init__(self, path):
            FakeYOLO.instances.append(self)

        def track(self, **kw):
            calls.append(("track", self, tuple(kw["classes"])))
            return []

        def predict(self, **kw):
            calls.append(("predict", self, tuple(kw["classes"])))
            return []

        def __call__(self, *a, **kw):  # the old code path; must not be used
            calls.append(("call", self, tuple(kw.get("classes", ()))))
            return []

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=FakeYOLO))
    sys.modules.pop("tracker", None)
    import tracker
    t = tracker.PersonTracker("yolov8n.pt")
    t.track(object())
    t.detect_phones(object())
    assert len(FakeYOLO.instances) == 2
    track_model = next(c[1] for c in calls if c[0] == "track")
    phone_model = next(c[1] for c in calls if c[0] == "predict")
    assert track_model is not phone_model
    assert ("track", track_model, (0,)) in calls and ("predict", phone_model, (67,)) in calls
    assert not any(c[0] == "call" for c in calls)
    sys.modules.pop("tracker", None)


def test_classroom_pipeline_uses_phone_detector_and_session_bound_runtime():
    src = open(os.path.join(ROOT, "classroom_ai.py"), encoding="utf-8").read()
    assert "self.tracker.detect_phones(frame)" in src
    assert "self.tracker.model(" not in src
    assert "classroom_runtime(self.class_id, self.class_session_id)" in src


# ----------------------------------------- runtime scoping for the camera
def test_classroom_camera_never_feeds_online_or_newer_session(manager):
    rt = manager.start_class(1, mode="classroom")
    assert manager.classroom_runtime(1, rt.class_session_id) is rt
    online = manager.start_class(1, mode="online")          # teacher switches to an online class
    assert manager.classroom_runtime(1) is None
    assert manager.classroom_runtime(1, rt.class_session_id) is None
    manager.end_class(1)
    rt2 = manager.start_class(1, mode="classroom")
    assert manager.classroom_runtime(1, rt.class_session_id) is None   # stale session id
    assert manager.classroom_runtime(1, rt2.class_session_id) is rt2
    manager.end_class(1)
    assert online.active is False


# ------------------------------------------------------------- CameraHub
class FakePipeline:
    def __init__(self, name):
        self.name = name
        self.released = False
        self.frames = 0

    def get_frame(self):
        self.frames += 1
        return (b"jpg-" + self.name.encode(), False, "OK")

    def release(self):
        self.released = True


def test_camera_hub_refcounts_viewers_and_stops_stale_generators():
    from app import CameraHub
    hub = CameraHub()
    a, gen_a = hub.acquire(("classroom", 1, 10), lambda: FakePipeline("a"))
    a2, gen_a2 = hub.acquire(("classroom", 1, 10), lambda: FakePipeline("unused"))
    assert a is a2 and gen_a == gen_a2 and hub.users == 2
    hub.release(gen_a)                       # one tab closes
    assert not a.released and hub.read(gen_a2)[0] == b"jpg-a"
    b, gen_b = hub.acquire(("personal", 3), lambda: FakePipeline("b"))
    assert a.released and gen_b != gen_a
    assert not hub.is_current(gen_a) and hub.read(gen_a) is None    # old generator stops, no reopen
    hub.release(gen_a2)                      # stale release must not close the new pipeline
    assert not b.released
    hub.force_release(lambda key: key == ("personal", 3))
    assert b.released and hub.pipeline is None


# ------------------------------------------------ identity: stranger on track
def test_unenrolled_face_on_locked_track_releases_identity():
    gallery = random_gallery(4, seed=11)
    stranger = random_gallery(1, seed=4242)[1]
    mgr = IdentityManager(gallery)
    rng = np.random.default_rng(0)
    t = 0.0
    for _ in range(20):                      # student 2 locks on track 5
        t += 0.1
        d = mgr.process_frame([(5, noisy(gallery[2], 0.03, rng))], t)
    assert d[5].status == CONFIRMED and d[5].student_id == 2
    for _ in range(30):                      # tracker id switch: a stranger now on track 5
        t += 0.1
        d = mgr.process_frame([(5, noisy(stranger, 0.03, rng))], t)
    assert d[5].student_id is None
    assert mgr.track_for_student(2) is None


def test_missing_face_does_not_release_locked_identity():
    gallery = random_gallery(3, seed=5)
    mgr = IdentityManager(gallery)
    rng = np.random.default_rng(1)
    t = 0.0
    for _ in range(20):
        t += 0.1
        mgr.process_frame([(1, noisy(gallery[1], 0.03, rng))], t)
    for _ in range(50):                      # face turned away / occluded, body still tracked
        t += 0.1
        d = mgr.process_frame([(1, None)], t)
    assert d[1].student_id == 1


# ------------------------------------------------- no face is not "focused"
def test_body_visible_without_face_is_unmeasured_not_focused():
    an = BehaviorAnalyzer(1)
    for i in range(30):
        u = an.update(Observation(timestamp=100 + i * 0.1, visible=True, face_visible=False))
    assert u.focus_state == rs.FOCUS_UNKNOWN and u.visibility_status == rs.VIS_VISIBLE


def test_no_face_freezes_score_in_runtime():
    from focusguard.session_runtime import SessionRuntime
    rt = SessionRuntime(enrolled=[{"student_id": 1, "display_name": "A"}], started_at=0.0)
    t = 0.0
    for _ in range(20):
        t += 0.1
        rt.process_frame(t, {1: Observation(timestamp=t, visible=True, face_visible=True, ear=0.3, yaw=0, pitch=0)})
    rt.process_frame(t + 0.1, {1: Observation(timestamp=t + 0.1, visible=True, face_visible=False)})
    t += 0.1
    score = rt.states[1].focus_score
    for _ in range(50):
        t += 0.1
        rt.process_frame(t, {1: Observation(timestamp=t, visible=True, face_visible=False)})
    assert rt.states[1].focus_score == score          # frozen: neither recovery nor penalty
    assert rt.student_view(1)["focus_state"] == rs.FOCUS_UNKNOWN


# ------------------------------------------- online class relink + staleness
def test_student_in_self_study_is_linked_when_online_class_starts(manager, clock, repo):
    session_id = manager.start_personal_session(3)
    manager.route_observation(3, Observation(timestamp=clock.advance(0.2), visible=True, ear=0.3, yaw=0, pitch=0))
    rt = manager.start_class(1, mode="online")
    assert manager.runtime_for_student(3) is rt
    assert manager.registry.personal_runtime(3) is None
    for _ in range(10):
        manager.route_observation(3, Observation(timestamp=clock.advance(0.2), visible=True, ear=0.3, yaw=0, pitch=0))
    s = rt.student_view(3)
    assert s["attendance_status"] == rs.ATT_PRESENT and s["connection_status"] == rs.CONN_ONLINE
    manager.end_class(1)
    assert repo.get_session(session_id)["end_time"] is not None


def test_online_class_marks_only_the_stalled_student_no_signal(manager, clock):
    rt = manager.start_class(1, mode="online")
    ids = rt.enrolled_ids()[:2]
    for _ in range(10):
        t = clock.advance(0.2)
        for sid in ids:
            rt.ingest(sid, Observation(timestamp=t, visible=True, ear=0.3, yaw=0, pitch=0))
    for _ in range(30):                      # only the first student's camera keeps sending
        t = clock.advance(0.2)
        rt.ingest(ids[0], Observation(timestamp=t, visible=True, ear=0.3, yaw=0, pitch=0))
    rt.heartbeat(clock())
    assert rt.student_view(ids[0])["visibility_status"] == rs.VIS_VISIBLE
    assert rt.student_view(ids[1])["visibility_status"] == rs.VIS_NO_SIGNAL
    assert rt.class_view(clock())["statistics"]["visible"] == 1
    assert rt.camera_status == "ACTIVE"
    manager.end_class(1)


# ------------------------------------------ class analytics exclude self-study
def test_class_analytics_exclude_personal_sessions(manager, clock, repo):
    manager.start_personal_session(3)
    for i in range(60):
        manager.route_observation(3, Observation(timestamp=clock.advance(0.2), visible=True, ear=0.3, yaw=0, pitch=0,
                                                 phone_confidence=0.9 if i > 5 else None))
    manager.stop_personal_session(3)
    assert [e["type"] for e in repo.get_focus_events(student_id=3)] == ["PHONE"]
    data = manager.class_analytics(1)
    assert data["breakdown"]["total"] == 0 and data["breakdown"]["status"] == "insufficient_data"
    assert all(r.get("class_id") is None for r in repo.get_focus_events(student_id=3))


# ------------------------------------------------------------ frontend
def test_admin_tables_escape_user_controlled_values():
    js = open(os.path.join(ROOT, "static", "js", "main.js"), encoding="utf-8").read()
    for raw in ("${u.username}", "${u.display_name}", "${u.class_name}", "${c.class_name}", "${u.display_name.charAt(0)}"):
        assert raw not in js, raw


def test_teacher_snapshots_are_scoped_to_selected_class():
    js = open(os.path.join(ROOT, "static", "js", "main.js"), encoding="utf-8").read()
    assert "emit('request_class_snapshot', {})" not in js
    assert "data.class_id !== classId" in js


def test_teacher_template_has_no_hardcoded_numbers():
    html = open(os.path.join(ROOT, "templates", "teacher_dashboard.html"), encoding="utf-8").read()
    for fake in ("28/28", "27/28", "0/28", ">84%<", ">88%<", ">92%<", ">95%<", "20/05/2026"):
        assert fake not in html, fake


def test_teacher_display_name_xss_payload_is_stored_but_rendered_escaped(login_as, app):
    payload = "<img src=x onerror=alert(1)>"
    t = login_as("teacher")
    assert t.post("/api/teacher/settings", json={"display_name": payload}).status_code == 200
    page = t.get("/teacher/dashboard").get_data(as_text=True)
    assert payload not in page and "&lt;img src=x onerror=alert(1)&gt;" in page


def test_reset_face_rejects_non_numeric_user_id(login_as):
    admin = login_as("admin")
    assert admin.post("/api/admin/reset_face", json={"user_id": "abc"}).status_code == 400
