"""
ui.py
Renders the HUD, level card, score panel, hint panel, and
level-select / game-over screens.
Uses only Pygame primitives + system fonts (Nunito fallback).
"""

import pygame
import math
import time
from typing import Optional, Tuple
from adaptive_engine import DifficultyTier


# ─────────────────────────────────────────────────────────────────────────────
#  Colours
# ─────────────────────────────────────────────────────────────────────────────
BG         = (18,  10,  40)
CARD_BG    = (255, 255, 255, 45)
ACCENT_P   = (138,  43, 226)
ACCENT_T   = ( 64, 224, 208)
ACCENT_G   = (255, 215,   0)
CORRECT_C  = ( 72, 199, 142)
WRONG_C    = (255,  82,  82)
WHITE      = (255, 255, 255)
DIM        = (180, 170, 210)
DEEP_CARD  = ( 35,  20,  70)

TIER_COLORS = {
    DifficultyTier.EASY:   ( 72, 199, 142),
    DifficultyTier.MEDIUM: (255, 165,   0),
    DifficultyTier.HARD:   (255,  82,  82),
}


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    for name in ("Nunito", "Comfortaa", "Baloo", "Comic Sans MS",
                 "Arial Rounded MT Bold", None):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


# ─────────────────────────────────────────────────────────────────────────────
#  Card helper
# ─────────────────────────────────────────────────────────────────────────────
def draw_card(surf: pygame.Surface, rect: pygame.Rect,
              color=DEEP_CARD, alpha: int = 180,
              radius: int = 20, border_color=None):
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    if border_color:
        pygame.draw.rect(s, (*border_color, 160), s.get_rect(),
                         width=2, border_radius=radius)
    surf.blit(s, rect.topleft)


# ─────────────────────────────────────────────────────────────────────────────
#  HUD
# ─────────────────────────────────────────────────────────────────────────────
class HUD:
    def __init__(self, screen_w: int, screen_h: int):
        self.w  = screen_w
        self.h  = screen_h
        self.f_sm  = _load_font(22)
        self.f_med = _load_font(30, bold=True)
        self.f_big = _load_font(44, bold=True)
        self.f_xl  = _load_font(64, bold=True)
        self._star_t = 0.0

    def draw_background(self, surf: pygame.Surface, t: float):
        """Animated deep-space gradient background."""
        surf.fill(BG)
        # Subtle nebula blobs
        for i, (cx, cy, cr, color, speed) in enumerate([
            (self.w * 0.15, self.h * 0.3,  220, (80, 0, 140, 18), 0.0008),
            (self.w * 0.80, self.h * 0.6,  180, (0, 80, 120, 18), 0.0012),
            (self.w * 0.50, self.h * 0.15, 150, (60, 0, 100, 14), 0.0005),
        ]):
            drift = math.sin(t * speed * math.pi * 2 + i) * 25
            blob  = pygame.Surface((cr * 2, cr * 2), pygame.SRCALPHA)
            pygame.draw.circle(blob, color, (cr, cr), cr)
            surf.blit(blob, (int(cx + drift) - cr, int(cy) - cr))

        # Star field
        rng_state = 42
        for _ in range(80):
            rng_state = (rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
            sx = rng_state % self.w
            rng_state = (rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
            sy = rng_state % self.h
            alpha = int(100 + 80 * math.sin(t * 0.001 * math.pi * 2 + rng_state))
            r2    = 1 if rng_state % 3 else 2
            s2    = pygame.Surface((r2 * 2, r2 * 2), pygame.SRCALPHA)
            pygame.draw.circle(s2, (255, 255, 255, max(0, min(255, alpha))), (r2, r2), r2)
            surf.blit(s2, (sx, sy))

    def draw_top_bar(self, surf: pygame.Surface, level: int, score: int,
                     streak: int, tier: DifficultyTier, accuracy: float):
        bar_rect = pygame.Rect(0, 0, self.w, 64)
        draw_card(surf, bar_rect, color=DEEP_CARD, alpha=200, radius=0)

        # Level badge
        lbl = self.f_med.render(f"Level {level}", True, ACCENT_T)
        surf.blit(lbl, (20, (64 - lbl.get_height()) // 2))

        # Score
        sc  = self.f_med.render(f"⭐ {score}", True, ACCENT_G)
        surf.blit(sc, (self.w // 2 - sc.get_width() // 2, (64 - sc.get_height()) // 2))

        # Streak
        if streak > 0:
            st = self.f_sm.render(f"🔥 {streak}×", True, (255, 140, 0))
            surf.blit(st, (self.w // 2 + 80, (64 - st.get_height()) // 2))

        # Tier dot
        tier_color = TIER_COLORS[tier]
        pygame.draw.circle(surf, tier_color, (self.w - 80, 32), 10)
        tl = self.f_sm.render(tier.value.upper(), True, tier_color)
        surf.blit(tl, (self.w - 65, 32 - tl.get_height() // 2))

        # Accuracy
        acc_str = f"{int(accuracy * 100)}%"
        al  = self.f_sm.render(acc_str, True, DIM)
        surf.blit(al, (self.w - 130, 32 - al.get_height() // 2))

    def draw_question_card(self, surf: pygame.Surface, prompt: str,
                            collected: list, target_count: int,
                            show_hint: bool, hint_text: str):
        card_w  = min(700, self.w - 60)
        card_h  = 110
        card_x  = (self.w - card_w) // 2
        card_y  = 76
        rect    = pygame.Rect(card_x, card_y, card_w, card_h)
        draw_card(surf, rect, color=DEEP_CARD, alpha=220,
                  radius=22, border_color=ACCENT_P)

        # Prompt text
        pl = self.f_big.render(prompt, True, WHITE)
        surf.blit(pl, (card_x + 20, card_y + 12))

        # Collected dots
        dot_y = card_y + 65
        for i in range(target_count):
            cx_ = card_x + 20 + i * 36
            filled = i < len(collected)
            color  = CORRECT_C if filled else (80, 60, 110)
            pygame.draw.circle(surf, color, (cx_, dot_y), 12)
            if filled:
                txt = self.f_sm.render(str(collected[i]), True, WHITE)
                surf.blit(txt, (cx_ - txt.get_width() // 2,
                                dot_y - txt.get_height() // 2))

        # Hint panel
        if show_hint:
            hx = card_x
            hy = card_y + card_h + 8
            hr = pygame.Rect(hx, hy, card_w, 50)
            draw_card(surf, hr, color=(80, 30, 10), alpha=200,
                      radius=14, border_color=(255, 140, 0))
            hl = self.f_sm.render(f"💡 {hint_text}", True, (255, 200, 80))
            surf.blit(hl, (hx + 14, hy + (50 - hl.get_height()) // 2))

    def draw_progress_bar(self, surf: pygame.Surface,
                           current: int, total: int, level: int):
        """Bottom progress strip."""
        bar_h  = 8
        y      = self.h - bar_h - 2
        frac   = current / max(total, 1)
        full   = pygame.Rect(0, y, self.w, bar_h)
        filled = pygame.Rect(0, y, int(self.w * frac), bar_h)
        pygame.draw.rect(surf, (50, 30, 80), full)
        colors = {1: ACCENT_T, 2: ACCENT_P, 3: ACCENT_G}
        pygame.draw.rect(surf, colors.get(level, ACCENT_T), filled)

    def draw_feedback_banner(self, surf: pygame.Surface,
                              text: str, correct: bool, alpha: int):
        if alpha <= 0:
            return
        color  = CORRECT_C if correct else WRONG_C
        label  = self.f_xl.render(text, True, color)
        s      = pygame.Surface((label.get_width() + 40,
                                  label.get_height() + 20), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, min(180, alpha)),
                         s.get_rect(), border_radius=16)
        s.blit(label, (20, 10))
        s.set_alpha(alpha)
        surf.blit(s, (self.w // 2 - s.get_width()  // 2,
                       self.h // 2 - s.get_height() // 2))


# ─────────────────────────────────────────────────────────────────────────────
#  Level Select Screen
# ─────────────────────────────────────────────────────────────────────────────
class LevelSelectScreen:
    LEVEL_INFO = {
        1: ("Comparison",       "Find >, < or = numbers",   ACCENT_T,  "🔵"),
        2: ("Arithmetic",       "Touch numbers that add up", ACCENT_P,  "🟣"),
        3: ("Advanced Math",    "Hundreds & multi-step",    ACCENT_G,  "⭐"),
    }

    def __init__(self, screen_w: int, screen_h: int):
        self.w  = screen_w
        self.h  = screen_h
        self.f_title = _load_font(72, bold=True)
        self.f_sub   = _load_font(28)
        self.f_btn   = _load_font(36, bold=True)
        self.f_desc  = _load_font(22)
        self.buttons: dict = {}
        self._t = 0.0

    def handle_click(self, pos) -> Optional[int]:
        for level, rect in self.buttons.items():
            if rect.collidepoint(pos):
                return level
        return None

    def draw(self, surf: pygame.Surface, t: float) -> dict:
        self._t = t
        surf.fill(BG)

        # Title
        title = self.f_title.render("🌟 Number Catcher", True, WHITE)
        surf.blit(title, (self.w // 2 - title.get_width() // 2, 40))

        sub = self.f_sub.render("Kawkabi Therapeutic Math Game", True, DIM)
        surf.blit(sub, (self.w // 2 - sub.get_width() // 2, 120))

        # Level cards
        card_w = 280
        card_h = 200
        gap    = 40
        total  = 3 * card_w + 2 * gap
        start_x = (self.w - total) // 2
        y      = self.h // 2 - card_h // 2

        self.buttons.clear()
        for i, level in enumerate([1, 2, 3]):
            name, desc, color, icon = self.LEVEL_INFO[level]
            cx = start_x + i * (card_w + gap)
            rect = pygame.Rect(cx, y, card_w, card_h)
            self.buttons[level] = rect

            hover_lift = int(6 * abs(math.sin(t * 0.002 + i * 1.2)))
            draw_rect  = rect.move(0, -hover_lift)

            draw_card(surf, draw_rect, color=DEEP_CARD, alpha=230,
                      radius=24, border_color=color)

            # Icon
            ic = self.f_title.render(icon, True, WHITE)
            surf.blit(ic, (draw_rect.centerx - ic.get_width() // 2,
                           draw_rect.y + 20))

            # Level number
            lv = self.f_btn.render(f"Level {level}", True, color)
            surf.blit(lv, (draw_rect.centerx - lv.get_width() // 2,
                           draw_rect.y + 95))

            # Name
            nm = self.f_sub.render(name, True, WHITE)
            surf.blit(nm, (draw_rect.centerx - nm.get_width() // 2,
                           draw_rect.y + 132))

            # Desc
            dc = self.f_desc.render(desc, True, DIM)
            surf.blit(dc, (draw_rect.centerx - dc.get_width() // 2,
                           draw_rect.y + 162))

        hint = self.f_desc.render(
            "Click a level or use body movement to select!", True, DIM)
        surf.blit(hint, (self.w // 2 - hint.get_width() // 2, self.h - 50))

        return self.buttons


# ─────────────────────────────────────────────────────────────────────────────
#  Game Over / Round End Screen
# ─────────────────────────────────────────────────────────────────────────────
class RoundEndScreen:
    def __init__(self, screen_w: int, screen_h: int):
        self.w = screen_w
        self.h = screen_h
        self.f_big  = _load_font(64, bold=True)
        self.f_med  = _load_font(36, bold=True)
        self.f_sm   = _load_font(26)
        self.btn_rect: Optional[pygame.Rect] = None

    def draw(self, surf: pygame.Surface,
             score: int, accuracy: float,
             correct: int, total: int,
             level: int, avg_rt: float) -> Optional[pygame.Rect]:

        draw_card(surf,
                  pygame.Rect(self.w // 2 - 300, self.h // 2 - 220, 600, 440),
                  color=DEEP_CARD, alpha=240, radius=30,
                  border_color=ACCENT_G)

        # Title
        title = self.f_big.render("Round Over!", True, ACCENT_G)
        surf.blit(title, (self.w // 2 - title.get_width() // 2,
                          self.h // 2 - 200))

        # Stats
        stats = [
            (f"Score:    {score}",           WHITE),
            (f"Accuracy: {int(accuracy*100)}%", CORRECT_C if accuracy >= 0.7 else WRONG_C),
            (f"Correct:  {correct} / {total}", WHITE),
            (f"Avg Time: {avg_rt:.1f}s",        ACCENT_T),
        ]
        for i, (text, color) in enumerate(stats):
            lbl = self.f_med.render(text, True, color)
            surf.blit(lbl, (self.w // 2 - lbl.get_width() // 2,
                            self.h // 2 - 110 + i * 52))

        # Play Again button
        btn = pygame.Rect(self.w // 2 - 130, self.h // 2 + 150, 260, 58)
        draw_card(surf, btn, color=ACCENT_P, alpha=240, radius=16)
        bl = self.f_med.render("Play Again  ▶", True, WHITE)
        surf.blit(bl, (btn.centerx - bl.get_width() // 2,
                       btn.centery - bl.get_height() // 2))
        self.btn_rect = btn
        return btn
