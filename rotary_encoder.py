#!/usr/bin/env python3
"""
Read two STEMMA-QT rotary encoders on one I²C bus (Pi GPIO 2/3 = I²C-1)
and report rotations + push-button events individually.
"""

import time
import board
import busio
from adafruit_seesaw.seesaw   import Seesaw
from adafruit_seesaw.rotaryio import IncrementalEncoder
from adafruit_seesaw.digitalio import DigitalIO
import digitalio                               # Direction & Pull live here

ENCODER_ADDRS = (0x36, 0x38)      # whatever i2cdetect shows

# Bring up I²C once
i2c = busio.I2C(board.SCL, board.SDA)

# One object set per encoder
encoders = []
for addr in ENCODER_ADDRS:
    ss  = Seesaw(i2c, addr=addr)
    enc = IncrementalEncoder(ss)
    btn = DigitalIO(ss, 24)                     # switch on seesaw pin 24
    btn.direction = digitalio.Direction.INPUT
    btn.pull      = digitalio.Pull.UP           # active-low
    encoders.append({"addr": addr,
                     "enc":  enc,
                     "btn":  btn,
                     "last": enc.position})

print("Running…  Ctrl-C to quit")
try:
    while True:
        for dev in encoders:
            pos = dev["enc"].position
            if pos != dev["last"]:
                delta = pos - dev["last"]
                print(f"[0x{dev['addr']:02X}] rotate {delta:+d}  (abs {pos})")
                dev["last"] = pos

            if not dev["btn"].value:            # button pressed
                print(f"[0x{dev['addr']:02X}] ↵  button press")
                while not dev["btn"].value:     # crude debounce
                    time.sleep(0.01)

        time.sleep(0.005)

except KeyboardInterrupt:
    print("\nBye!")
