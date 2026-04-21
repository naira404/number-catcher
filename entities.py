"""
entities.py
Floating number bubbles, particle effects, and balloon burst animations.
All rendering is pure Pygame – no external assets required.
"""

import pygame
import random
import math
import time
from typing import List, Tuple, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  Design Tokens (Kawkabi Design System)
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = {
    "bg":            (18,  10,  40),    # Deep space purple
    "card":          (255, 255, 255, 60),
    "accent_purple": (138,  43, 226),
    "accent_teal":   ( 64, 224, 208),
    "accent_gold":   (255, 215,   0),
    "accent_pink":   (255, 105, 180),
    "correct":       ( 72, 199, 142),
    "wrong":         (255,  82,  82),
    "text_white":    (255, 255, 255),
    "text_dim":      (180, 170, 210),
}

BUBBLE_COLORS = [
    (138,  43, 226),  # purple
    ( 64, 224, 208),  # teal
    (255, 105, 180),  # pink
    (255, 165,   0),  # orange
    ( 50, 205,  50),  # green
    ( 30, 144, 255),  # blue
    (255, 215,   0),  # gold
]


# ─────────────────────────────────────────────────────────────────────────────
#  Particle
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x: float, y: float, color: Tuple):
        angle  = random.uniform(0, 2 * math.pi)
        speed  = random.uniform(2, 7)
        self.x  = x
        self.y  = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - random.uniform(1, 3)
        self.color   = color
        self.radius  = random.randint(4, 10)
        self.life    = 1.0
        self.decay   = random.uniform(0.025, 0.06)
        self.gravity = 0.18

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += self.gravity
        self.life -= self.decay
        self.vx *= 0.98

    def draw(self, surf: pygame.Surface):
        if self.life <= 0:
            return
        alpha  = max(0, int(self.life * 255))
        r      = max(1, int(self.radius * self.life))
        color  = (*self.color[:3], alpha)
        s      = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, color, (r, r), r)
        surf.blit(s, (int(self.x) - r, int(self.y) - r))

    @property
    def alive(self) -> bool:
        return self.life > 0


# ─────────────────────────────────────────────────────────────────────────────
#  FloatingBubble
# ─────────────────────────────────────────────────────────────────────────────
class FloatingBubble:
    """
    A number displayed inside a coloured translucent bubble that
    drifts across the screen with slight sinusoidal wobble.
    """

    def __init__(self, value: int, screen_w: int, screen_h: int,
                 speed: float = 1.5, is_correct: bool = False):
        self.value      = value
        self.screen_w   = screen_w
        self.screen_h   = screen_h
        self.is_correct = is_correct

        self.radius     = random.randint(42, 58)
        self.color      = random.choice(BUBBLE_COLORS)
        self.speed      = speed + random.uniform(-0.3, 0.5)

        # Spawn on left edge, random height
        self.x   = float(-self.radius * 2)
        self.y   = float(random.randint(int(screen_h * 0.15),
                                         int(screen_h * 0.85)))

        # Drift direction (mostly right, slight upward/downward)
        angle    = random.uniform(-0.2, 0.2)
        self.vx  = math.cos(angle) * self.speed
        self.vy  = math.sin(angle) * self.speed * 0.3

        # Wobble
        self.wobble_amp   = random.uniform(0.5, 1.5)
        self.wobble_speed = random.uniform(0.03, 0.07)
        self.wobble_t     = random.uniform(0, 2 * math.pi)

        # Hover pulse
        self.pulse_t      = random.uniform(0, 2 * math.pi)

        # Touch detection
        self.touched      = False
        self.burst_time   = None

        # Glow ring for correct bubbles
        self.glow_alpha   = 0
        self._glow_dir    = 1

    # ── Update ────────────────────────────────────────────────────────────

    def update(self):
        self.wobble_t += self.wobble_speed
        self.pulse_t  += 0.05

        self.x += self.vx
        self.y += math.sin(self.wobble_t) * self.wobble_amp

        # Glow animation for correct bubble
        if self.is_correct:
            self.glow_alpha += 3 * self._glow_dir
            if self.glow_alpha >= 120 or self.glow_alpha <= 30:
                self._glow_dir *= -1

    @property
    def off_screen(self) -> bool:
        return self.x > self.screen_w + self.radius * 2

    def contains_point(self, px: float, py: float) -> bool:
        dx = px - self.x
        dy = py - self.y
        return math.hypot(dx, dy) <= self.radius + 6

    # ── Draw ─────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, font: pygame.font.Font):
        cx = int(self.x)
        cy = int(self.y)
        r  = self.radius

        # Glow ring (correct bubbles)
        if self.is_correct and self.glow_alpha > 0:
            glow_r = r + 14
            gs     = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*PALETTE["accent_gold"], self.glow_alpha),
                               (glow_r + 1, glow_r + 1), glow_r, 4)
            surf.blit(gs, (cx - glow_r - 1, cy - glow_r - 1))

        # Shadow
        shadow_s = pygame.Surface((r * 2 + 16, r * 2 + 16), pygame.SRCALPHA)
        pygame.draw.circle(shadow_s, (0, 0, 0, 60),
                           (r + 8, r + 10), r)
        surf.blit(shadow_s, (cx - r - 8, cy - r - 8))

        # Body
        body_s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(body_s, (*self.color, 210), (r, r), r)
        # Inner highlight
        hl_r = max(4, r // 3)
        pygame.draw.circle(body_s, (255, 255, 255, 80),
                           (r - r // 4, r - r // 4), hl_r)
        surf.blit(body_s, (cx - r, cy - r))

        # Border
        pygame.draw.circle(surf, (255, 255, 255, 180), (cx, cy), r, 2)

        # Number label
        label = font.render(str(self.value), True, PALETTE["text_white"])
        lx    = cx - label.get_width()  // 2
        ly    = cy - label.get_height() // 2
        surf.blit(label, (lx, ly))


# ─────────────────────────────────────────────────────────────────────────────
#  BurstEffect  (balloon pop)
# ─────────────────────────────────────────────────────────────────────────────
class BurstEffect:
    """Colourful particle explosion at the point a bubble is popped."""

    def __init__(self, x: float, y: float, color: Tuple,
                 correct: bool = True, count: int = 22):
        burst_color = PALETTE["correct"] if correct else PALETTE["wrong"]
        self.particles: List[Particle] = [
            Particle(x, y, burst_color if i % 3 == 0 else color)
            for i in range(count)
        ]
        # Star flash
        self.flash_alpha = 220
        self.x = x
        self.y = y
        self.correct = correct

    def update(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.alive]
        self.flash_alpha = max(0, self.flash_alpha - 18)

    def draw(self, surf: pygame.Surface):
        if self.flash_alpha > 0:
            r     = 50
            flash = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            color = PALETTE["correct"] if self.correct else PALETTE["wrong"]
            pygame.draw.circle(flash, (*color, self.flash_alpha), (r, r), r)
            surf.blit(flash, (int(self.x) - r, int(self.y) - r))
        for p in self.particles:
            p.draw(surf)

    @property
    def alive(self) -> bool:
        return bool(self.particles) or self.flash_alpha > 0


# ─────────────────────────────────────────────────────────────────────────────
#  StarReward  (correct-answer celebration overlay)
# ─────────────────────────────────────────────────────────────────────────────
class StarReward:
    def __init__(self, screen_w: int, screen_h: int):
        self.cx     = screen_w // 2
        self.cy     = screen_h // 2
        self.life   = 1.0
        self.scale  = 0.0
        self.stars: List[Tuple] = [
            (random.randint(0, screen_w),
             random.randint(0, screen_h),
             random.uniform(0, 2 * math.pi),
             random.choice(BUBBLE_COLORS))
            for _ in range(18)
        ]

    def update(self):
        self.life  -= 0.015
        self.scale  = min(1.0, self.scale + 0.07)

    def draw(self, surf: pygame.Surface, font_big: pygame.font.Font):
        if self.life <= 0:
            return
        alpha = max(0, int(self.life * 220))

        # Flying stars
        for sx, sy, angle, color in self.stars:
            r = 12
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, alpha), (r + 1, r + 1), r)
            surf.blit(s, (sx - r, sy - r))

        # Central "✓" or "⭐"
        label = font_big.render("⭐ Great! ⭐", True, PALETTE["accent_gold"])
        lw    = int(label.get_width()  * self.scale)
        lh    = int(label.get_height() * self.scale)
        if lw > 0 and lh > 0:
            scaled = pygame.transform.smoothscale(label, (lw, lh))
            s2     = pygame.Surface((lw, lh), pygame.SRCALPHA)
            s2.blit(scaled, (0, 0))
            s2.set_alpha(alpha)
            surf.blit(s2, (self.cx - lw // 2, self.cy - lh // 2))

    @property
    def alive(self) -> bool:
        return self.life > 0
