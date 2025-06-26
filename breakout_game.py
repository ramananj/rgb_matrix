#!/usr/bin/env python3
"""
Breakout for a 64 × 32 RGB LED matrix on Raspberry Pi 5
======================================================
*Piomatter‑only edition*

### 2025‑06‑17 — v1.4 “Even Chiller”
The ball was **still** zipping too fast, so we dialled it back again:

* **Frame rate** → **20 FPS** (was 30)
* **Ball base speed** remains 1 px, but at 20 FPS that’s one‑third slower than v1.3
* Paddle sensitivity unchanged (× 2)

Everything else is identical.

Run with:
```bash
sudo python3 breakout_game.py
```
"""
import os
import sys
from typing import List, Tuple

import numpy as np
import pygame

# ───────────────────── Piomatter Framebuffer Wrapper ────────────────────────
try:
    import adafruit_blinka_raspberry_pi5_piomatter as piomatter
except ImportError as exc:
    raise RuntimeError(
        "Piomatter library missing. Install with pip and use a Pi 5‑compatible kernel"
    ) from exc

class LEDDisplay:
    """Simple NumPy → Piomatter framebuffer push"""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.fb = np.zeros((h, w, 3), dtype=np.uint8)
        geom = piomatter.Geometry(width=w, height=h, n_addr_lines=4,
                                  rotation=piomatter.Orientation.Normal)
        self.matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                                          pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                                          framebuffer=self.fb,
                                          geometry=geom)
    def clear(self):
        self.fb.fill(0)

    def set(self, x: int, y: int, rgb: Tuple[int, int, int]):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.fb[y, x] = rgb

    def show(self):
        try:
            self.matrix.show()
        except TimeoutError:
            pass  # occasionally Piomatter times out; skip frame

# ─────────────────────────── Gameplay Constants ─────────────────────────────
W, H = 64, 32
FPS = 10                     # ↓ from 30 (v1.3) and 60 (original)
PADDLE_W, PADDLE_H = 16, 2
BALL_SZ = 2
BALL_SPEED = 1               # already minimal integer speed
BRICK_ROWS, BRICK_COLS = 4, 8
BRICK_W, BRICK_H = W // BRICK_COLS, 3
LIVES_START = 3

COL_PADDLE = (255, 255, 255)
COL_BALL   = (255,   0,   0)
BRICK_COLORS = [
    (255,  80,  80), (255, 165,   0), (255, 255,   0), (  0, 255,   0),
    (  0, 180, 255), (  0,   0, 255), (170,   0, 255), (255,   0, 255),
]

# ───────────────────────────── Game Objects ─────────────────────────────────
class Paddle:
    def __init__(self):
        self.w, self.h = PADDLE_W, PADDLE_H
        self.x = (W - self.w) // 2
        self.y = H - 3
        self.v = 0.0

    def update(self):
        self.x = max(0, min(W - self.w, self.x + int(self.v)))

class Ball:
    def __init__(self, paddle: "Paddle"):
        self.sz = BALL_SZ
        self.reset(paddle)

    def reset(self, paddle: "Paddle"):
        self.x = paddle.x + paddle.w // 2
        self.y = paddle.y - self.sz - 1
        self.dx, self.dy = BALL_SPEED, -BALL_SPEED
        self.stuck = True

    def release(self):
        self.stuck = False

    def update(self, paddle: "Paddle", bricks: List[Tuple[int, int]]):
        if self.stuck:
            self.x = paddle.x + paddle.w // 2
            self.y = paddle.y - self.sz - 1
            return 0
        self.x += self.dx
        self.y += self.dy
        score = 0
        if self.x <= 0 or self.x >= W - self.sz:
            self.dx *= -1
        if self.y <= 0:
            self.dy *= -1
        if (
            paddle.y <= self.y + self.sz <= paddle.y + paddle.h and
            paddle.x <= self.x <= paddle.x + paddle.w and self.dy > 0
        ):
            self.dy = -BALL_SPEED
            offset = ((self.x - paddle.x) / paddle.w) - 0.5
            self.dx = int(offset * 4) or (1 if self.dx >= 0 else -1)
        for bx, by in bricks:
            if bx <= self.x <= bx + BRICK_W - 1 and by <= self.y <= by + BRICK_H - 1:
                bricks.remove((bx, by))
                self.dy *= -1
                score += 1
                break
        return score

    def pixels(self):
        """Return integer pixel coordinates the ball occupies."""
        ix = int(round(self.x))
        iy = int(round(self.y))
        for px in range(ix, ix + self.sz):
            for py in range(iy, iy + self.sz):
                yield px, py

# ─────────────────────────────── Game Loop ──────────────────────────────────
class Breakout:
    def __init__(self, display: LEDDisplay):
        self.dsp = display
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init(); pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            print("No USB gamepad detected – exiting")
            sys.exit(1)
        self.pad = pygame.joystick.Joystick(0); self.pad.init()
        self.reset()

    def reset(self):
        self.score, self.lives = 0, LIVES_START
        self.paddle = Paddle()
        self.ball = Ball(self.paddle)
        self.bricks = [(c*BRICK_W, 2 + r*BRICK_H) for r in range(BRICK_ROWS) for c in range(BRICK_COLS)]

    @staticmethod
    def brick_color(bx, by):
        return BRICK_COLORS[(bx//BRICK_W + by//BRICK_H) % len(BRICK_COLORS)]

    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            # Input
            self.paddle.v = 0.0
            for e in pygame.event.get():
                if e.type == pygame.JOYBUTTONDOWN and e.button in (7, 8, 9):
                    running = False
                elif e.type == pygame.JOYBUTTONDOWN and e.button == 0 and self.ball.stuck:
                    self.ball.release()
                elif e.type == pygame.JOYAXISMOTION and e.axis == 0:
                    self.paddle.v = e.value * 3  # sensitivity unchanged
                elif e.type == pygame.JOYHATMOTION:
                    self.paddle.v = e.value[0] * 3
            if abs(self.pad.get_axis(0)) > 0.1 and abs(self.paddle.v) < 0.1:
                self.paddle.v = self.pad.get_axis(0) * 3

            # Update
            self.paddle.update()
            self.score += self.ball.update(self.paddle, self.bricks)
            if self.ball.y >= H:
                self.lives -= 1
                if self.lives == 0:
                    self.reset()
                else:
                    self.ball.reset(self.paddle)
            if not self.bricks:
                self.bricks = [(c*BRICK_W, 2 + r*BRICK_H) for r in range(BRICK_ROWS) for c in range(BRICK_COLS)]
                self.ball.dx *= 1.1; self.ball.dy *= 1.1

            # Draw
            d = self.dsp; d.clear()
            for bx, by in self.bricks:
                col = self.brick_color(bx, by)
                for x in range(bx, bx + BRICK_W):
                    for y in range(by, by + BRICK_H):
                        d.set(x, y, col)
            # Paddle
            for x in range(self.paddle.x, self.paddle.x + self.paddle.w):
                for y in range(self.paddle.y, self.paddle.y + self.paddle.h):
                    d.set(x, y, COL_PADDLE)
            # Ball
            for px, py in self.ball.pixels():
                d.set(px, py, COL_BALL)
            # Push frame to LEDs and regulate FPS
            d.show()
            clock.tick(FPS)

def main():
    Breakout(LEDDisplay(W, H)).run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
