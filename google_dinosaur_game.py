#!/usr/bin/env python3
"""
Chrome Dino Game for a 64 × 32 RGB LED matrix on Raspberry Pi 5
================================================================
*Piomatter + pygame edition*

Controls: USB gamepad button 0 to jump

Run with:
    sudo python3 dino_matrix_game.py
"""
import os
import sys
import time
import random
import numpy as np
import pygame

# ───────────────────── Piomatter Framebuffer Wrapper ────────────────────────
try:
    import adafruit_blinka_raspberry_pi5_piomatter as piomatter
except ImportError as exc:
    raise RuntimeError(
        "Piomatter library missing. Install with pip and use a Pi 5-compatible kernel"
    ) from exc

class LEDDisplay:
    """Simple NumPy → Piomatter framebuffer push"""

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

    def set(self, x: int, y: int, rgb: tuple):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.fb[y, x] = rgb

    def show(self):
        try:
            self.matrix.show()
        except TimeoutError:
            pass  # skip on timeout

# ─────────────────────────── Configuration ───────────────────────────
W, H = 64, 32
FPS = 20
DINO_W, DINO_H = 6, 6
GROUND_Y = H - 4
GRAVITY = -0.8
JUMP_STRENGTH = 8
OBSTACLE_WIDTH = 4
OBSTACLE_HEIGHT = 6
OBSTACLE_COLOR = (0, 255, 0)
DINO_COLOR = (255, 255, 255)
GROUND_COLOR = (50, 50, 50)
SPAWN_PROB = 0.02  # chance per frame

# ─────────────────────────── Game Objects ───────────────────────────
class Dino:
    def __init__(self):
        self.w, self.h = DINO_W, DINO_H
        self.x = 10
        self.reset()

    def reset(self):
        self.y = GROUND_Y - self.h
        self.vy = 0.0
        self.on_ground = True

    def jump(self):
        if self.on_ground:
            self.vy = JUMP_STRENGTH
            self.on_ground = False

    def update(self, dt):
        if not self.on_ground:
            self.vy += GRAVITY * dt * FPS
            self.y -= self.vy * dt * FPS
            if self.y >= GROUND_Y - self.h:
                self.y = GROUND_Y - self.h
                self.vy = 0.0
                self.on_ground = True

    def pixels(self):
        x0 = int(self.x)
        y0 = int(self.y)
        for px in range(x0, x0 + self.w):
            for py in range(y0, y0 + self.h):
                yield px, py

class Obstacle:
    def __init__(self):
        self.w = OBSTACLE_WIDTH
        self.h = OBSTACLE_HEIGHT
        self.x = W
        self.y = GROUND_Y - self.h

    def update(self, dt):
        self.x -= int(120 * dt * FPS / 30)

    def pixels(self):
        for px in range(int(self.x), int(self.x) + self.w):
            for py in range(self.y, self.y + self.h):
                yield px, py

# ───────────────────────────── Game Loop ─────────────────────────────
def main():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No USB gamepad detected – exiting")
        sys.exit(1)
    pad = pygame.joystick.Joystick(0)
    pad.init()

    dsp = LEDDisplay(W, H)
    clock = pygame.time.Clock()

    dino = Dino()
    obstacles = []

    last_time = time.time()
    running = True

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        # ─── Input ─────────────────────────────────────────
        for e in pygame.event.get():
            if e.type == pygame.JOYBUTTONDOWN:
                if e.button == 0:
                    dino.jump()
                elif e.button in (3):
                    running = False

        # ─── Update ────────────────────────────────────────
        dino.update(dt)
        if random.random() < SPAWN_PROB:
            obstacles.append(Obstacle())
        for obs in obstacles:
            obs.update(dt)
        obstacles = [o for o in obstacles if o.x + o.w > 0]

        # ─── Collision ────────────────────────────────────
        for obs in obstacles:
            if (dino.x < obs.x + obs.w and
                dino.x + dino.w > obs.x and
                dino.y < obs.y + obs.h and
                dino.y + dino.h > obs.y):
                dino.reset()
                obstacles.clear()
                break

        # ─── Draw ────────────────────────────────────────
        dsp.clear()
        # ground line
        for x in range(W):
            dsp.set(x, GROUND_Y, GROUND_COLOR)
        # dino
        for px, py in dino.pixels(): dsp.set(px, py, DINO_COLOR)
        # obstacles
        for obs in obstacles:
            for px, py in obs.pixels(): dsp.set(px, py, OBSTACLE_COLOR)
        dsp.show()

        # ─── Frame rate ──────────────────────────────────
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass