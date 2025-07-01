#!/usr/bin/env python3
"""
Subway Surfers–style Runner for a 64 × 32 RGB LED matrix on Raspberry Pi 5
======================================================================
*Piomatter + pygame edition*

Controls:
- Joystick/HAT left/right: change lanes
- Button 0: jump
- Buttons 7–9: exit

Run with:
    sudo python3 subway_surfer_matrix_game.py
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
    """Simple NumPy → Piomatter framebuffer push"""
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.fb = np.zeros((h, w, 3), dtype=np.uint8)
        geom = piomatter.Geometry(width=w, height=h, n_addr_lines=4,
                                  rotation=piomatter.Orientation.Normal)
        self.matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=piomatter.Pinout.AdafruitMatrixBonnet,
            framebuffer=self.fb,
            geometry=geom
        )
    def clear(self):
        self.fb.fill(0)
    def set(self, x: int, y: int, rgb: tuple):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.fb[y, x] = rgb
    def show(self):
        try:
            self.matrix.show()
        except TimeoutError:
            pass

# ─────────────────────────── Configuration ─────────────────────────────
W, H = 64, 32
FPS = 20
LANES = 3
LANE_X = [int(W * (i + 1) / (LANES + 1)) for i in range(LANES)]  # e.g., [16,32,48]
GROUND_Y = H - 4
GRAVITY = -0.8
JUMP_STRENGTH = 8
OBSTACLE_W, OBSTACLE_H = 4, 4
COIN_SZ = 2
# Colors
COL_RUNNER = (255, 255, 255)
COL_OBSTACLE = (255, 0, 0)
COL_COIN = (255, 215, 0)
COL_GROUND = (50, 50, 50)
SPAWN_OBS_PROB = 0.03
SPAWN_COIN_PROB = 0.02

# ─────────────────────────── Game Objects ─────────────────────────────
class Runner:
    def __init__(self):
        self.lane = 1  # start center
        self.x = LANE_X[self.lane]
        self.w, self.h = 4, 6
        self.reset()
    def reset(self):
        self.y = GROUND_Y - self.h
        self.vy = 0.0
        self.on_ground = True
        self.x = LANE_X[self.lane]
    def jump(self):
        if self.on_ground:
            self.vy = JUMP_STRENGTH
            self.on_ground = False
    def move_left(self):
        self.lane = max(0, self.lane - 1)
        self.x = LANE_X[self.lane]
    def move_right(self):
        self.lane = min(LANES - 1, self.lane + 1)
        self.x = LANE_X[self.lane]
    def update(self, dt):
        if not self.on_ground:
            self.vy += GRAVITY * dt * FPS
            self.y -= self.vy * dt * FPS
            if self.y >= GROUND_Y - self.h:
                self.y = GROUND_Y - self.h
                self.vy = 0.0
                self.on_ground = True
    def pixels(self):
        x0 = int(self.x - self.w // 2)
        y0 = int(self.y)
        for px in range(x0, x0 + self.w):
            for py in range(y0, y0 + self.h):
                yield px, py

class Obstacle:
    def __init__(self):
        self.lane = random.randrange(LANES)
        self.x = W
        self.w, self.h = OBSTACLE_W, OBSTACLE_H
        self.y = GROUND_Y - self.h
    def update(self, dt):
        self.x -= int(100 * dt * FPS / 30)
    def pixels(self):
        x0 = int(self.x - self.w // 2)
        for px in range(x0, x0 + self.w):
            for py in range(self.y, self.y + self.h):
                yield px, py

class Coin:
    def __init__(self):
        self.lane = random.randrange(LANES)
        self.x = W
        self.sz = COIN_SZ
        self.y = GROUND_Y - self.h - 2 if hasattr(self, 'h') else GROUND_Y - self.sz - 1
    def update(self, dt):
        self.x -= int(120 * dt * FPS / 30)
    def pixels(self):
        x0 = int(self.x - self.sz // 2)
        y0 = GROUND_Y - self.sz - 1
        for px in range(x0, x0 + self.sz):
            for py in range(y0, y0 + self.sz):
                yield px, py

# ───────────────────────────── Game Loop ───────────────────────────────
def main():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init(); pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No USB gamepad detected – exiting"); sys.exit(1)
    pad = pygame.joystick.Joystick(0); pad.init()

    dsp = LEDDisplay(W, H)
    clock = pygame.time.Clock()

    runner = Runner()
    obstacles = []
    coins = []
    score = 0

    last_time = time.time()
    running = True
    while running:
        now = time.time(); dt = now - last_time; last_time = now
        # Input
        for e in pygame.event.get():
            if e.type == pygame.JOYBUTTONDOWN:
                if e.button == 0: runner.jump()
                elif e.button in (7,8,9): running = False
            elif e.type == pygame.JOYAXISMOTION and e.axis == 0:
                if e.value < -0.5: runner.move_left()
                elif e.value > 0.5: runner.move_right()
            elif e.type == pygame.JOYHATMOTION:
                if e.value[0] == -1: runner.move_left()
                elif e.value[0] == 1: runner.move_right()
        # Update
        runner.update(dt)
        if random.random() < SPAWN_OBS_PROB:
            obstacles.append(Obstacle())
        if random.random() < SPAWN_COIN_PROB:
            coins.append(Coin())
        for o in obstacles: o.update(dt)
        for c in coins: c.update(dt)
        obstacles = [o for o in obstacles if o.x > -o.w]
        coins = [c for c in coins if c.x > -c.sz]
        # Collisions
        for o in obstacles:
            if any((px,py) in runner.pixels() for px,py in o.pixels()):
                runner.reset(); obstacles.clear(); coins.clear(); break
        for c in coins:
            if any((px,py) in runner.pixels() for px,py in c.pixels()):
                score += 1; coins.remove(c); break
        # Draw
        dsp.clear()
        # ground
        for x in range(W): dsp.set(x, GROUND_Y, COL_GROUND)
        # runne r
        for px,py in runner.pixels(): dsp.set(px, py, COL_RUNNER)
        # obstacles
        for o in obstacles:
            color = COL_OBSTACLE
            for px,py in o.pixels(): dsp.set(px, py, color)
        # coins
        for c in coins:
            for px,py in c.pixels(): dsp.set(px, py, COL_COIN)
        dsp.show()
        clock.tick(FPS)
    pygame.quit()

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
