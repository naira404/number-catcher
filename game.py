"""
game.py
Main game orchestrator for Number Catcher.
Manages game states, levels, scoring, and ties all subsystems together.
"""

import pygame
import random
import time
import math
from typing import List, Optional

from adaptive_engine  import AdaptiveEngine, DifficultyTier
from question_generator import QuestionGenerator, Question
from entities         import FloatingBubble, BurstEffect, StarReward, PALETTE
from audio_manager    import AudioManager
from pose_tracker     import PoseTracker
from ui               import HUD, LevelSelectScreen, RoundEndScreen, _load_font


# ─────────────────────────────────────────────────────────────────────────────
#  Game States
# ─────────────────────────────────────────────────────────────────────────────
class State:
    LEVEL_SELECT = "level_select"
    PLAYING      = "playing"
    ROUND_END    = "round_end"


# ─────────────────────────────────────────────────────────────────────────────
#  Core
# ─────────────────────────────────────────────────────────────────────────────
QUESTIONS_PER_ROUND = 10
FPS                 = 60


class NumberCatcherGame:

    def __init__(self, screen: pygame.Surface):
        self.screen  = screen
        self.W, self.H = screen.get_size()
        self.clock   = pygame.time.Clock()

        # Sub-systems
        self.audio   = AudioManager()
        self.pose    = PoseTracker(self.W, self.H)
        self.engine  = AdaptiveEngine(starting_level=1)
        self.gen     = QuestionGenerator(self.engine.config)
        self.hud     = HUD(self.W, self.H)
        self.sel_scr = LevelSelectScreen(self.W, self.H)
        self.end_scr = RoundEndScreen(self.W, self.H)

        self.font_med = _load_font(34, bold=True)
        self.font_big = _load_font(56, bold=True)

        # Game state
        self.state   = State.LEVEL_SELECT
        self.level   = 1
        self.score   = 0
        self.streak  = 0
        self.q_count = 0        # questions answered this round
        self.correct_count = 0

        # Playing state
        self.question: Optional[Question] = None
        self.bubbles: List[FloatingBubble] = []
        self.bursts:  List[BurstEffect]    = []
        self.rewards: List[StarReward]     = []
        self.collected: List[int]          = []    # operands touched so far

        self._spawn_timer   = 0
        self._hint_timer    = 0
        self._show_hint     = False
        self._hint_text     = ""
        self._feedback_text = ""
        self._feedback_alpha= 0
        self._feedback_ok   = True

        self._t    = 0        # frame counter for animations
        self._last_hand_pos = []

    # ------------------------------------------------------------------ #
    #  Main Loop                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._t += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.pose.stop()
                    return
                if event.type == pygame.VIDEORESIZE:
                    self.W, self.H = event.w, event.h
                    self.screen = pygame.display.set_mode(
                        (self.W, self.H), pygame.RESIZABLE)
                    self._rebuild_ui()
                self._handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------ #
    #  Event Handling                                                      #
    # ------------------------------------------------------------------ #

    def _handle_event(self, event):
        if self.state == State.LEVEL_SELECT:
            if event.type == pygame.MOUSEBUTTONDOWN:
                level = self.sel_scr.handle_click(event.pos)
                if level:
                    self._start_level(level)

        elif self.state == State.PLAYING:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._check_touch(event.pos)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.state = State.LEVEL_SELECT

        elif self.state == State.ROUND_END:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.end_scr.btn_rect and \
                   self.end_scr.btn_rect.collidepoint(event.pos):
                    self.state = State.LEVEL_SELECT

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    def _update(self, dt: int):
        if self.state == State.PLAYING:
            self._update_playing(dt)

        # Feedback fade
        if self._feedback_alpha > 0:
            self._feedback_alpha = max(0, self._feedback_alpha - 3)

    def _update_playing(self, dt: int):
        cfg = self.engine.config

        # Spawn new bubbles
        self._spawn_timer += dt
        if self._spawn_timer >= cfg.spawn_rate_ms and self.question:
            self._spawn_timer = 0
            self._spawn_bubble()

        # Update bubbles
        for b in self.bubbles:
            b.update()
        self.bubbles = [b for b in self.bubbles if not b.off_screen]

        # Update effects
        for fx in self.bursts:  fx.update()
        for rw in self.rewards: rw.update()
        self.bursts  = [fx for fx in self.bursts  if fx.alive]
        self.rewards = [rw for rw in self.rewards if rw.alive]

        # Hint timer
        self._hint_timer += dt
        if self._hint_timer > cfg.hint_delay_ms and self.question:
            self._show_hint = True
            self._hint_text = self.question.hint

        # Pose / hand interaction
        hand_positions = self.pose.get_pixel_positions()
        for pos in hand_positions:
            self._check_touch(pos, from_pose=True)

    # ------------------------------------------------------------------ #
    #  Touch / Collision                                                   #
    # ------------------------------------------------------------------ #

    def _check_touch(self, pos, from_pose: bool = False):
        if not self.question:
            return
        px, py = pos

        for bubble in list(self.bubbles):
            if bubble.touched:
                continue
            if bubble.contains_point(px, py):
                self._on_bubble_touched(bubble)
                break

    def _on_bubble_touched(self, bubble: FloatingBubble):
        q = self.question
        bubble.touched = True
        self.audio.play_tick()

        if self.level == 1:
            # For Level 1, any touching the bubble pool is valid or invalid
            correct_val = q.operands[0]
            is_correct  = (bubble.value == correct_val)

            self.bursts.append(BurstEffect(
                bubble.x, bubble.y, bubble.color, correct=is_correct))
            self.bubbles.remove(bubble)

            if is_correct:
                self._on_correct()
            else:
                self._on_wrong()

        else:
            # Levels 2 & 3: must collect operands in order
            expected_idx = len(self.collected)
            if expected_idx < len(q.operands):
                expected = q.operands[expected_idx]
                is_correct = (bubble.value == expected)
            else:
                is_correct = False

            self.bursts.append(BurstEffect(
                bubble.x, bubble.y, bubble.color, correct=is_correct))
            self.bubbles.remove(bubble)

            if is_correct:
                self.collected.append(bubble.value)
                if len(self.collected) == len(q.operands):
                    self._on_correct()
                # else: keep collecting
            else:
                self._on_wrong()

    # ------------------------------------------------------------------ #
    #  Correct / Wrong handlers                                            #
    # ------------------------------------------------------------------ #

    def _on_correct(self):
        feedback = self.engine.record_answer(correct=True)
        self.gen.update_config(self.engine.config)

        self.score  += self._calc_score(feedback["reaction_time"])
        self.streak += 1
        self.correct_count += 1
        self.q_count       += 1

        self.audio.play_correct()
        self.rewards.append(StarReward(self.W, self.H))
        self._show_feedback("✓  Correct!", True)

        if feedback["tier_changed"]:
            self.audio.play_level_up()
            self.audio.speak(feedback["message"])

        self._next_question()

    def _on_wrong(self):
        feedback = self.engine.record_answer(correct=False)
        self.gen.update_config(self.engine.config)

        self.streak = 0
        self.q_count += 1

        self.audio.play_wrong()
        self._show_feedback("✗  Try Again!", False)
        self._show_hint = True
        self._hint_text = self.question.hint if self.question else ""

        if feedback["tier_changed"]:
            self.audio.speak(feedback["message"])

        if self.q_count >= QUESTIONS_PER_ROUND:
            self._end_round()
        else:
            self._next_question()

    def _calc_score(self, rt: float) -> int:
        base   = {1: 10, 2: 20, 3: 30}.get(self.level, 10)
        speed  = max(1, int(10 / max(rt, 0.5)))
        streak = min(self.streak, 5) * 2
        return base + speed + streak

    # ------------------------------------------------------------------ #
    #  Question lifecycle                                                  #
    # ------------------------------------------------------------------ #

    def _next_question(self):
        if self.q_count >= QUESTIONS_PER_ROUND:
            self._end_round()
            return

        self.collected    = []
        self._show_hint   = False
        self._hint_timer  = 0
        self.question     = self.gen.generate(self.level)
        self.engine.start_question()

        self.audio.speak(self.question.audio_prompt)

        # Ensure correct bubbles exist on screen
        self._repopulate_bubbles()

    def _repopulate_bubbles(self):
        """Clear old bubbles, seed with correct operands + distractors."""
        self.bubbles.clear()
        q   = self.question
        cfg = self.engine.config

        # All values to show
        all_vals = list(q.operands) + list(q.distractors)
        random.shuffle(all_vals)

        for val in all_vals:
            is_corr = val in q.operands
            b = FloatingBubble(
                value     = val,
                screen_w  = self.W,
                screen_h  = self.H,
                speed     = cfg.base_speed,
                is_correct= is_corr,
            )
            # Spread initial x positions so not all start at edge
            b.x = random.uniform(-b.radius * 2, self.W * 0.3)
            self.bubbles.append(b)

    def _spawn_bubble(self):
        """Spawn a distractor or extra operand copy."""
        if not self.question:
            return
        cfg = self.engine.config
        q   = self.question

        pool = list(q.distractors) + list(q.operands)
        val  = random.choice(pool)
        b    = FloatingBubble(
            value     = val,
            screen_w  = self.W,
            screen_h  = self.H,
            speed     = cfg.base_speed + random.uniform(0, cfg.speed_variance),
            is_correct= val in q.operands,
        )
        self.bubbles.append(b)

    # ------------------------------------------------------------------ #
    #  Level / Round management                                            #
    # ------------------------------------------------------------------ #

    def _start_level(self, level: int):
        self.level       = level
        self.q_count     = 0
        self.correct_count = 0
        self.score       = 0
        self.streak      = 0
        self.collected   = []
        self.bubbles.clear()
        self.bursts.clear()
        self.rewards.clear()

        self.engine.set_level(level)
        self.gen.update_config(self.engine.config)

        self.state = State.PLAYING
        self._next_question()

        self.audio.speak(f"Level {level}. Let's go!")

    def _end_round(self):
        self.state = State.ROUND_END
        acc = self.engine.accuracy()
        if acc >= 0.8:
            self.audio.speak("Fantastic! You did amazing!")
        elif acc >= 0.5:
            self.audio.speak("Good job! Keep practising!")
        else:
            self.audio.speak("Keep trying! You'll get better!")

    def _show_feedback(self, text: str, ok: bool):
        self._feedback_text  = text
        self._feedback_alpha = 255
        self._feedback_ok    = ok

    def _rebuild_ui(self):
        self.hud     = HUD(self.W, self.H)
        self.sel_scr = LevelSelectScreen(self.W, self.H)
        self.end_scr = RoundEndScreen(self.W, self.H)

    # ------------------------------------------------------------------ #
    #  Draw                                                                #
    # ------------------------------------------------------------------ #

    def _draw(self):
        if self.state == State.LEVEL_SELECT:
            self.sel_scr.draw(self.screen, self._t)

        elif self.state == State.PLAYING:
            self._draw_playing()

        elif self.state == State.ROUND_END:
            self.hud.draw_background(self.screen, self._t)
            self.end_scr.draw(
                self.screen,
                score    = self.score,
                accuracy = self.engine.accuracy(),
                correct  = self.correct_count,
                total    = self.q_count,
                level    = self.level,
                avg_rt   = self.engine.recent_avg_rt(),
            )

    def _draw_playing(self):
        # 1. رسم الكاميرا أو الخلفية الفضائية (الطبقة السفلى)
        if hasattr(self.pose, 'current_frame') and self.pose.current_frame is not None:
            # استخدام surfarray لتحويل الفريم من OpenCV لـ Pygame
            frame_surface = pygame.surfarray.make_surface(self.pose.current_frame)
            self.screen.blit(pygame.transform.scale(frame_surface, (self.W, self.H)), (0,0))
        else:
            self.hud.draw_background(self.screen, self._t)

        # 2. رسم الفقاعات (Bubbles)
        for b in self.bubbles:
            b.draw(self.screen, self.font_med)

        # 3. رسم المؤثرات البصرية (Effects & Rewards)
        for fx in self.bursts:
            fx.draw(self.screen)
        for rw in self.rewards:
            rw.draw(self.screen, self.font_big)

        # 4. رسم واجهة البيانات (HUD) - تلتزم بالـ Design System الخاص بكِ [cite: 1971]
        self.hud.draw_top_bar(
            self.screen,
            level    = self.level,
            score    = self.score,
            streak   = self.streak,
            tier     = self.engine.current_tier,
            accuracy = self.engine.accuracy(),
        )

        # 5. كارت السؤال والتعليمات
        if self.question:
            self.hud.draw_question_card(
                self.screen,
                prompt       = self.question.prompt,
                collected    = self.collected,
                target_count = len(self.question.operands),
                show_hint    = self._show_hint,
                hint_text    = self._hint_text,
            )

        # 6. شريط التقدم (Progress Bar)
        self.hud.draw_progress_bar(
            self.screen,
            current = self.q_count,
            total   = QUESTIONS_PER_ROUND,
            level   = self.level,
        )

        # 7. رسم نقاط تتبع اليدين (Pose Overlay)
        # هذا الجزء هو "عصب" كوكب الحركة لضمان تتبع الـ 33 نقطة للجسم [cite: 1853]
        self.pose.draw_overlay(self.screen)

        # 8. تلميح الخروج (ESC)
        esc = self.hud.f_sm.render("ESC = Menu", True, (100, 80, 130))
        self.screen.blit(esc, (self.W - esc.get_width() - 10, self.H - 28))