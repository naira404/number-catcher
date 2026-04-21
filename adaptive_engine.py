"""
adaptive_engine.py
Core adaptive difficulty system for Number Catcher.
Tracks performance and adjusts speed, complexity, and hints in real-time.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class DifficultyTier(Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"


@dataclass
class PerformanceSnapshot:
    timestamp: float
    correct: bool
    reaction_time: float   # seconds
    level: int


@dataclass
class AdaptiveConfig:
    """Live configuration that the engine mutates."""
    # Floating number physics
    spawn_rate_ms: int       = 1800   # ms between spawns
    base_speed: float        = 1.2    # pixels per frame
    speed_variance: float    = 0.4    # ±random added to base

    # Math complexity
    max_operand: int         = 9      # biggest number in expressions
    allow_subtraction: bool  = False  # unlocked after consistent success
    multi_step: bool         = False  # Level 3 multi-operand chains

    # Distractors (wrong answers on screen at once)
    distractor_count: int    = 3

    # Hint timing
    hint_delay_ms: int       = 5000   # show hint after this idle time

    # Tier
    tier: DifficultyTier     = DifficultyTier.EASY


class AdaptiveEngine:
    """
    Watches the child's performance across a rolling window and
    adjusts AdaptiveConfig accordingly.

    Rules:
      - 3 consecutive correct + fast  → increase difficulty
      - 2 consecutive wrong / slow    → decrease difficulty
      - Level changes reset the window
    """

    FAST_THRESHOLD  = 4.0   # seconds – considered "fast"
    SLOW_THRESHOLD  = 9.0   # seconds – considered "slow"
    WINDOW_SIZE     = 5     # rolling window for trend detection

    # Per-level speed & complexity presets  (tier: easy / medium / hard)
    PRESETS = {
        1: {
            DifficultyTier.EASY:   AdaptiveConfig(spawn_rate_ms=2200, base_speed=1.0, max_operand=9,  distractor_count=2, tier=DifficultyTier.EASY),
            DifficultyTier.MEDIUM: AdaptiveConfig(spawn_rate_ms=1600, base_speed=1.5, max_operand=9,  distractor_count=3, tier=DifficultyTier.MEDIUM),
            DifficultyTier.HARD:   AdaptiveConfig(spawn_rate_ms=1100, base_speed=2.2, max_operand=9,  distractor_count=4, tier=DifficultyTier.HARD),
        },
        2: {
            DifficultyTier.EASY:   AdaptiveConfig(spawn_rate_ms=2000, base_speed=1.2, max_operand=20, distractor_count=3, allow_subtraction=False, tier=DifficultyTier.EASY),
            DifficultyTier.MEDIUM: AdaptiveConfig(spawn_rate_ms=1500, base_speed=1.8, max_operand=50, distractor_count=4, allow_subtraction=True,  tier=DifficultyTier.MEDIUM),
            DifficultyTier.HARD:   AdaptiveConfig(spawn_rate_ms=1000, base_speed=2.5, max_operand=99, distractor_count=5, allow_subtraction=True,  tier=DifficultyTier.HARD),
        },
        3: {
            DifficultyTier.EASY:   AdaptiveConfig(spawn_rate_ms=1800, base_speed=1.5, max_operand=100, distractor_count=4, allow_subtraction=True, multi_step=False, tier=DifficultyTier.EASY),
            DifficultyTier.MEDIUM: AdaptiveConfig(spawn_rate_ms=1300, base_speed=2.2, max_operand=500, distractor_count=5, allow_subtraction=True, multi_step=True,  tier=DifficultyTier.MEDIUM),
            DifficultyTier.HARD:   AdaptiveConfig(spawn_rate_ms=900,  base_speed=3.0, max_operand=999, distractor_count=6, allow_subtraction=True, multi_step=True,  tier=DifficultyTier.HARD),
        },
    }

    def __init__(self, starting_level: int = 1):
        self.current_level = starting_level
        self.current_tier  = DifficultyTier.EASY
        self.config        = self._get_preset(starting_level, DifficultyTier.EASY)

        self.history: List[PerformanceSnapshot] = []
        self._question_start: Optional[float]   = None

        # Consecutive trackers
        self._consec_correct = 0
        self._consec_wrong   = 0

        # Session totals
        self.total_correct   = 0
        self.total_attempts  = 0

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def start_question(self):
        """Call when a new question is presented to the child."""
        self._question_start = time.time()

    def record_answer(self, correct: bool) -> dict:
        """
        Call when the child submits an answer.
        Returns a feedback dict with keys:
          - 'reaction_time'
          - 'tier_changed' (bool)
          - 'new_tier' (DifficultyTier)
          - 'show_hint' (bool)
          - 'message' (str)
        """
        rt = time.time() - (self._question_start or time.time())
        self._question_start = None

        snap = PerformanceSnapshot(
            timestamp     = time.time(),
            correct       = correct,
            reaction_time = rt,
            level         = self.current_level,
        )
        self.history.append(snap)

        self.total_attempts += 1
        if correct:
            self.total_correct   += 1
            self._consec_correct += 1
            self._consec_wrong    = 0
        else:
            self._consec_wrong   += 1
            self._consec_correct  = 0

        old_tier    = self.current_tier
        show_hint   = False
        message     = ""

        # --- Increase difficulty ---
        if self._consec_correct >= 3 and rt < self.FAST_THRESHOLD:
            self._bump_tier(+1)
            message = "Amazing! Let's try something harder! 🚀"

        # --- Decrease difficulty ---
        elif self._consec_wrong >= 2 or (not correct and rt > self.SLOW_THRESHOLD):
            self._bump_tier(-1)
            show_hint = True
            message   = "No worries! Let's slow down a bit. 😊"

        tier_changed = (self.current_tier != old_tier)

        return {
            "reaction_time": round(rt, 2),
            "tier_changed":  tier_changed,
            "new_tier":      self.current_tier,
            "show_hint":     show_hint,
            "message":       message,
        }

    def set_level(self, level: int):
        """Switch to a new game level, resetting tier to EASY."""
        self.current_level   = level
        self.current_tier    = DifficultyTier.EASY
        self.config          = self._get_preset(level, DifficultyTier.EASY)
        self._consec_correct = 0
        self._consec_wrong   = 0

    def accuracy(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.total_correct / self.total_attempts

    def recent_avg_rt(self, n: int = 5) -> float:
        recent = self.history[-n:]
        if not recent:
            return 0.0
        return sum(s.reaction_time for s in recent) / len(recent)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _bump_tier(self, direction: int):
        """direction: +1 = harder, -1 = easier."""
        tiers = list(DifficultyTier)
        idx   = tiers.index(self.current_tier)
        new_idx = max(0, min(len(tiers) - 1, idx + direction))
        self.current_tier = tiers[new_idx]
        self.config       = self._get_preset(self.current_level, self.current_tier)

    def _get_preset(self, level: int, tier: DifficultyTier) -> AdaptiveConfig:
        level = max(1, min(3, level))
        return self.PRESETS[level][tier]
