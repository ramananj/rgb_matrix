#!/usr/bin/env python3
import numpy as np
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

# setup (same as simpletest)
width, height = 64, 32
geometry = piomatter.Geometry(width=width, height=height, n_addr_lines=4)
framebuffer = np.zeros((height, width, 3), dtype=np.uint8)
matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.AdafruitMatrixBonnet,
    framebuffer=framebuffer,
    geometry=geometry
)

# fill red
framebuffer[:] = [255, 0, 0]
matrix.show()
input("Did you see a solid red screen? Press Enter to exit.")
