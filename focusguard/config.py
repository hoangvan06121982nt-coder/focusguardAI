"""Centralised, typed configuration for the vision + behaviour pipeline.

Every threshold that used to be hard-coded inside camera_ai.py / classroom_ai.py
lives here so it can be tuned in one place, overridden from the environment and
reported alongside evaluation results.
"""
from dataclasses import dataclass, field, asdict, replace
import os


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class IdentityConfig:
    # Cosine similarity a face embedding must reach to be a candidate match.
    similarity_threshold: float = 0.45
    # best - second_best must be at least this, otherwise the match is ambiguous.
    min_margin: float = 0.08
    # A candidate must win this many consecutive recognitions ...
    confirm_consecutive: int = 3
    # ... spread over at least this many seconds before the track is locked.
    confirm_min_seconds: float = 0.6
    # Once locked, this many consecutive contradicting recognitions are needed
    # before the lock is dropped (protects against one bad frame / crossing).
    unlock_consecutive: int = 4
    # ... and they must span at least this long (FPS-independent).
    unlock_min_seconds: float = 1.0
    # After a track loses its identity, the same student cannot be re-bound to a
    # *different* track for this many seconds unless the evidence is strong.
    conflict_cooldown_seconds: float = 2.0
    # Similarity required to steal an identity from another live track.
    steal_similarity: float = 0.60
    # Track that has not been observed for this long is considered lost.
    track_lost_seconds: float = 3.0
    # Seconds a lost track's identity is remembered for recovery on a new track.
    recovery_window_seconds: float = 10.0
    # Consecutive matches needed to re-bind a recently lost student to a new
    # track (tracker re-assigned an id after occlusion).
    recovery_consecutive: int = 2


@dataclass(frozen=True)
class BehaviorConfig:
    # Eye aspect ratio below which eyes are considered closed.
    ear_threshold: float = 0.22
    # Head-pose limits (degrees) outside of which the head is "away".
    yaw_limit_deg: float = 20.0
    pitch_limit_deg: float = 20.0
    # Minimum continuous duration before a raw signal becomes a behaviour.
    drowsy_min_seconds: float = 1.5
    head_away_min_seconds: float = 2.0
    phone_min_seconds: float = 1.0
    # Gaps shorter than this inside an active episode do not end it
    # (e.g. one missed phone detection mid-episode).
    gap_tolerance_seconds: float = 0.5
    # Not visible for less than this is TEMPORARILY_NOT_VISIBLE,
    # longer is AWAY (left the seat).
    away_min_seconds: float = 10.0
    # Minimum detector confidence for a phone box to count.
    phone_min_confidence: float = 0.35
    # Fraction of the phone box that must lie inside the person's box.
    phone_min_containment: float = 0.6


@dataclass(frozen=True)
class FocusConfig:
    # Score change per second. Positive rates recover, negative penalise.
    recovery_per_second: float = 0.5
    penalty_per_second: dict = field(default_factory=lambda: {
        "PHONE": 2.0,
        "DROWSY": 1.5,
        "HEAD_AWAY": 1.0,
        "AWAY": 1.0,
        "TEMPORARILY_NOT_VISIBLE": 0.0,
    })
    initial_score: float = 100.0
    min_score: float = 0.0
    max_score: float = 100.0
    # Largest time step the engine will integrate at once. Longer gaps (e.g. a
    # stalled camera) are clamped so a single stall cannot wipe the score.
    max_step_seconds: float = 2.0


@dataclass(frozen=True)
class AttendanceConfig:
    # Seconds after class start after which a first sighting is "late".
    late_after_seconds: float = 300.0


@dataclass(frozen=True)
class PipelineConfig:
    identity: IdentityConfig = field(default_factory=IdentityConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    focus: FocusConfig = field(default_factory=FocusConfig)
    attendance: AttendanceConfig = field(default_factory=AttendanceConfig)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_env(cls):
        ident = IdentityConfig()
        ident = replace(
            ident,
            similarity_threshold=_env_float("FG_FACE_SIM_THRESHOLD", ident.similarity_threshold),
            min_margin=_env_float("FG_FACE_MIN_MARGIN", ident.min_margin),
        )
        beh = BehaviorConfig()
        beh = replace(
            beh,
            ear_threshold=_env_float("FG_EAR_THRESHOLD", beh.ear_threshold),
            drowsy_min_seconds=_env_float("FG_DROWSY_MIN_SECONDS", beh.drowsy_min_seconds),
            head_away_min_seconds=_env_float("FG_HEAD_AWAY_MIN_SECONDS", beh.head_away_min_seconds),
            phone_min_seconds=_env_float("FG_PHONE_MIN_SECONDS", beh.phone_min_seconds),
            phone_min_confidence=_env_float("FG_PHONE_MIN_CONFIDENCE", beh.phone_min_confidence),
        )
        att = AttendanceConfig(late_after_seconds=_env_float("FG_LATE_AFTER_SECONDS", 300.0))
        return cls(identity=ident, behavior=beh, attendance=att)

    def with_behavior(self, **kwargs):
        return replace(self, behavior=replace(self.behavior, **kwargs))


DEFAULT_CONFIG = PipelineConfig()
