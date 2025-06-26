#!/usr/bin/env python3
"""
Flappy‑Bird‑ish for a 64 × 32 RGB LED matrix (Piomatter)
=======================================================
**v1.6.3 – “Defined Bird Shape” (2025‑06‑17)**

Improved the bird rendering to be more bird-like: defined tail, body, wings, head, and beak.

Run:
```bash
sudo python3 flappy_bird_game.py
```
"""
import os
import random
from typing import List, Tuple

import numpy as np
import pygame

try:
    import adafruit_blinka_raspberry_pi5_piomatter as piomatter
except ImportError as exc:
    raise RuntimeError("Piomatter driver missing; install via pip on Pi 5") from exc


class LEDDisplay:
    """NumPy‑backed framebuffer pushed to the panel with Piomatter."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.fb = np.zeros((h, w, 3), dtype=np.uint8)
        geom = piomatter.Geometry(width=w, height=h, n_addr_lines=4,
                                  rotation=piomatter.Orientation.Normal)
        self.matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                                          pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                                          framebuffer=self.fb, geometry=geom)

    def clear(self):
        self.fb.fill(0)

    def set(self, x: int, y: int, rgb: Tuple[int, int, int]):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.fb[y, x] = rgb

    def show(self):
        try:
            self.matrix.show()
        except TimeoutError:
            pass  # drop a frame if DMA busy


# ──────────────────────────── Game Constants ───────────────────────────────
W, H = 64, 32
FPS = 15
GRAVITY = 0.16
FLAP_VY = -1.3
VY_CLAMP = -2.0
PIPE_SPEED = 1
PIPE_WIDTH = 3
GAP_HEIGHT = 11
SPAWN_EVERY = 70

COL_TAIL = (255, 140, 140)
COL_WING = (255, 165,   0)
COL_BODY = (255, 255,  50)
COL_BEAK = (255, 215,   0)
COL_PIPE = (  0, 255,   0)
COL_BOOM = (255,   0,   0)


# ─────────────────────────────── Entities ──────────────────────────────────
class Bird:
    """8 × 4 sprite with tail, wings, body, head, and beak."""
    # 0 blank 1 tail 2 wing 3 body 4 beak
    PATTERN = [
        [0, 1, 0, 2, 3, 3, 3, 4],
        [1, 1, 2, 3, 3, 3, 4, 4],
        [1, 1, 2, 3, 3, 3, 4, 4],
        [0, 1, 0, 2, 3, 3, 3, 0],
    ]
    COLOR = {1: COL_TAIL, 2: COL_WING, 3: COL_BODY, 4: COL_BEAK}

    def __init__(self):
        self.w = len(Bird.PATTERN[0])
        self.h = len(Bird.PATTERN)
        self.x = W // 4
        self.y = H // 2
        self.vy = 0.0
        self.cool = False  # flap cooldown flag

    # physics
    def flap(self):
        if not self.cool:
            self.vy = FLAP_VY
            self.cool = True
    def release_flap(self):
        self.cool = False
    def update(self):
        self.vy += GRAVITY
        self.vy = max(self.vy, VY_CLAMP)
        self.y += self.vy

    # helpers
    def bbox(self):
        return self.x, self.y, self.x + self.w - 1, self.y + self.h - 1
    def draw(self, d: LEDDisplay):
        ix, iy = int(self.x), int(self.y)
        for dy, row in enumerate(Bird.PATTERN):
            for dx, cell in enumerate(row):
                if cell:
                    d.set(ix + dx, iy + dy, Bird.COLOR[cell])


class Pipe:
    def __init__(self, x: int):
        self.x = x
        self.gap_top = random.randint(4, H - GAP_HEIGHT - 4)
    def update(self):
        self.x -= PIPE_SPEED
    def off_screen(self):
        return self.x + PIPE_WIDTH < 0
    def passed(self, bird: Bird):
        return self.x + PIPE_WIDTH - 1 < bird.x < self.x + PIPE_WIDTH + PIPE_SPEED
    def collides(self, bird: Bird):
        bx0, by0, bx1, by1 = bird.bbox()
        in_x = bx1 >= self.x and bx0 <= self.x + PIPE_WIDTH - 1
        in_gap = by1 >= self.gap_top and by0 <= self.gap_top + GAP_HEIGHT - 1
        return in_x and not in_gap
    def draw(self, d: LEDDisplay):
        for x in range(self.x, self.x + PIPE_WIDTH):
            for y in range(0, self.gap_top):
                d.set(x, y, COL_PIPE)
            for y in range(self.gap_top + GAP_HEIGHT, H):
                d.set(x, y, COL_PIPE)


# ───────────────────────────── Game Engine ─────────────────────────────────
class FlappyGame:
    def __init__(self, display: LEDDisplay):
        self.dsp = display
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init(); pygame.joystick.init()
        self.pad = pygame.joystick.Joystick(0) if pygame.joystick.get_count() else None
        if self.pad:
            self.pad.init()
        self.reset(full=True)

    # state helpers
    def reset(self, full=False):
        self.bird = Bird()
        self.pipes: List[Pipe] = []
        self.frame = 0
        self.next_spawn = SPAWN_EVERY if full else 0
        self.boom_frames = 0
        self.boom_pos = (0, 0)
    def trigger_boom(self, cx: int, cy: int):
        self.boom_frames = 6
        self.boom_pos = (cx, cy)

    # input
    def process_events(self):
        press = release = quit_req = False
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                press = True
            elif e.type == pygame.KEYUP and e.key == pygame.K_SPACE:
                release = True
            elif e.type == pygame.JOYBUTTONDOWN and e.button == 0:
                press = True
            elif e.type == pygame.JOYBUTTONUP and e.button == 0:
                release = True
            elif (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE) or (
                e.type == pygame.JOYBUTTONDOWN and e.button in (7, 8, 9)):
                quit_req = True
        return press, release, quit_req

    # world update
    def update_world(self):
        self.bird.update()
        if self.frame >= self.next_spawn:
            self.pipes.append(Pipe(W))
            self.next_spawn = self.frame + SPAWN_EVERY
        for p in list(self.pipes):
            p.update()
            if p.off_screen():
                self.pipes.remove(p)
        # collisions / bounds
        out = self.bird.y < 0 or self.bird.y + self.bird.h >= H
        hit = any(p.collides(self.bird) for p in self.pipes)
        if out or hit:
            cx = int(self.bird.x + self.bird.w / 2)
            cy = int(self.bird.y + self.bird.h / 2)
            self.trigger_boom(cx, cy)
        self.frame += 1

    # rendering
    def draw(self):
        d = self.dsp; d.clear()
        for p in self.pipes:
            p.draw(d)
        self.bird.draw(d)
        if self.boom_frames:
            cx, cy = self.boom_pos
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                d.set(cx + dx, cy + dy, COL_BOOM)
            d.set(cx, cy, COL_BOOM)
            self.boom_frames -= 1
            if self.boom_frames == 0:
                self.reset()
        d.show()

    # main loop
    def run(self):
        clock = pygame.time.Clock()
        running = True
        while running:
            press, release, quit_req = self.process_events()
            if quit_req:
                break
            if self.boom_frames == 0:
                if press:
                    self.bird.flap()
                if release:
                    self.bird.release_flap()
                self.update_world()
            self.draw()
            clock.tick(FPS)


# ───────────────────────────── Entrypoint ───────────────────────────────────
if __name__ == "__main__":
    try:
        FlappyGame(LEDDisplay(W, H)).run()
    except KeyboardInterrupt:
        pass
