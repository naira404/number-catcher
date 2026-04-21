# 🌟 Kawkabi – Number Catcher
### Therapeutic Math Game for Children with ADHD

---

## Project Structure

```
kawkabi_number_catcher/
├── main.py               ← Entry point
├── game.py               ← Main game orchestrator & state machine
├── adaptive_engine.py    ← AdaptiveEngine class (core difficulty logic)
├── question_generator.py ← Level 1/2/3 question factories
├── entities.py           ← FloatingBubble, BurstEffect, StarReward
├── audio_manager.py      ← TTS + procedural SFX
├── pose_tracker.py       ← MediaPipe Pose wrapper (mouse fallback)
├── ui.py                 ← HUD, LevelSelectScreen, RoundEndScreen
└── requirements.txt
```

---

## Setup

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the game
python main.py
```

**Minimum Python version:** 3.9+

---

## Controls

| Input | Action |
|-------|--------|
| Mouse click | Touch a floating bubble |
| Body movement (wrist) | Touch bubbles (when MediaPipe camera active) |
| ESC | Return to level select |

---

## Architecture

### `AdaptiveEngine`
Central intelligence. Watches a rolling window of 5 answers:

```
3 consecutive CORRECT + reaction time < 4s  →  bump tier UP   (harder)
2 consecutive WRONG  / reaction time > 9s   →  bump tier DOWN (easier)
```

Each tier change reconfigures: spawn rate, bubble speed, operand range,
distractor count, and whether subtraction or multi-step chains are allowed.

### `QuestionGenerator`
Stateless factory, parameterised by `AdaptiveConfig`:

| Level | Type | Example |
|-------|------|---------|
| 1 | Comparison (>, <, =) | "Touch a number greater than 7" |
| 2 | Two-operand arithmetic | "Collect 13 → touch 6 then 7" |
| 3 | Multi-step / Hundreds | "Solve: 120 + 45 − 30 = ?" |

### `FloatingBubble`
Each bubble drifts left→right with sinusoidal wobble. Correct-answer
bubbles have a pulsing gold glow ring. On touch, a `BurstEffect`
(particle explosion) fires at the bubble's position.

### `PoseTracker`
Attempts to start MediaPipe in a background thread. If camera or
MediaPipe are unavailable, transparently falls back to mouse cursor
mode — so the game is always playable without hardware.

---

## Adaptive Difficulty Tiers per Level

| Level | Easy | Medium | Hard |
|-------|------|--------|------|
| 1 | 2.2s spawn, speed 1.0 | 1.6s, speed 1.5 | 1.1s, speed 2.2 |
| 2 | 2.0s, max 20, +only | 1.5s, max 50, ± | 1.0s, max 99, ± |
| 3 | 1.8s, max 100 | 1.3s, max 500, chain | 0.9s, max 999, chain |

---

## Feedback System

- **Correct answer** → ascending arpeggio + ⭐ star burst overlay + TTS praise
- **Wrong answer** → low descending tone + red flash + hint card
- **Tier up** → fanfare + "Amazing! Let's try something harder! 🚀" (TTS)
- **Tier down** → gentle message + "No worries! Let's slow down! 😊" (TTS)
- **Hint** → shown after 5 seconds of inactivity, coaching text in orange card

---

## Design System (Kawkabi)

| Token | Value |
|-------|-------|
| Background | `#120A28` (Deep Space Purple) |
| Card | `#231446` semi-transparent |
| Accent Purple | `#8A2BE2` |
| Accent Teal | `#40E0D0` |
| Accent Gold | `#FFD700` |
| Correct | `#48C78E` |
| Wrong | `#FF5252` |
| Font | Nunito → Comfortaa → Comic Sans (system fallback) |
