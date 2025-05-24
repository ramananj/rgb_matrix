# File: rpi_app.py
#!/usr/bin/env python3
import time
import threading
import random
import signal
import sys
import socket
import struct
import cv2
import numpy as np
from picamera2 import Picamera2
from PIL import Image, ImageEnhance, ImageSequence, ImageFont, ImageDraw
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

# Configuration
SERVER_IP = "192.168.86.39"
SERVER_PORT = 9000
UDP_PORT = 10000  # Port to listen for goal events
FONT_PATH = "fonts/font_2_5x7.ttf"
FONT_SIZE = 8
GOAL_TEXT_POS = (2, 2)
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (0, 0, 0)
PADDING = 1

# Global picamera instance for cleanup
global_picam2 = None

def frame_sender(picam2):
    """
    Thread to capture frames from shared Picamera2 and send via TCP.
    """
    # Retry connecting
    sock = None
    while sock is None:
        try:
            sock = socket.create_connection((SERVER_IP, SERVER_PORT))
        except Exception:
            time.sleep(2)
    # Send loop
    while True:
        frame = picam2.capture_array()
        bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        _, jpeg = cv2.imencode('.jpg', bgr)
        data = jpeg.tobytes()
        sock.sendall(struct.pack('>L', len(data)) + data)
        time.sleep(0.07)


def goal_listener(goal_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", UDP_PORT))
    while True:
        data, _ = sock.recvfrom(1024)
        if data.decode() == "GOAL":
            goal_event.set()


def cleanup(signum, frame):
    # Gracefully stop camera on exit
    global global_picam2
    if global_picam2:
        try:
            global_picam2.stop()
            global_picam2.close()
        except Exception:
            pass
    sys.exit(0)


def main_display():
    global global_picam2
    # Handle exit signals
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Initialize camera
    picam2 = Picamera2()
    global_picam2 = picam2
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
    picam2.start()

    # Setup LED matrix
    width, height = 64, 32
    geometry = piomatter.Geometry(width=width, height=height,
                                  n_addr_lines=4, rotation=piomatter.Orientation.Normal)
    framebuffer = np.zeros((height, width, 3), dtype=np.uint8)
    matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                                 pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                                 framebuffer=framebuffer, geometry=geometry)

    # Load assets and font
    default_img = Image.open("soccer_images/goalie_waiting_noball.png").convert("RGB").resize((width, height), Image.LANCZOS)
    default_frame = np.asarray(default_img)
    goal_gif = Image.open("soccer_images/soccer_goalie_orange_ball.gif")
    spidey1_gif = Image.open("soccer_images/spiderman_web_swing_building.gif")
    dino1_gif = Image.open("soccer_images/dino_dancing.gif")
    dino2_gif = Image.open("soccer_images/dino-dancing-meme-2.gif")
    spidey2_gif = Image.open("soccer_images/shooting-a-web-spider-man.gif")
    rocket1_gif = Image.open("soccer_images/rocket_launching.gif")
    rocket2_gif = Image.open("soccer_images/rocket_blasting.gif")
    celebration_gifs = [
        spidey1_gif,
        dino1_gif,
        dino2_gif,
        spidey2_gif,
        rocket1_gif,
        rocket2_gif
    ]
    font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)

    goal_count = 0
    goal_event = threading.Event()

    # Start threads
    threading.Thread(target=frame_sender, args=(picam2,), daemon=True).start()
    threading.Thread(target=goal_listener, args=(goal_event,), daemon=True).start()

    # Display loop
    while True:
        if goal_event.is_set():
            for frame in ImageSequence.Iterator(goal_gif):
                rgb = frame.convert("RGB").resize((width, height), Image.LANCZOS)
                enhanced = ImageEnhance.Contrast(rgb).enhance(1.5)
                framebuffer[:] = np.asarray(enhanced)
                matrix.show()
                time.sleep(frame.info.get("duration", 100)/1000.0)
            goal_count += 1
            goal_event.clear()
            if goal_count % 10 == 0:
                random_gif = random.choice(celebration_gifs)
                num_frames = random_gif.n_frames
                num_loops = 20 // num_frames
                if num_loops == 0:
                    num_loops = 1
                for _ in range(num_loops):
                    for frame in ImageSequence.Iterator(random_gif):
                        rgb = frame.convert("RGB").resize((width, height), Image.LANCZOS)
                        enhanced = ImageEnhance.Contrast(rgb).enhance(1.5)
                        framebuffer[:] = np.asarray(enhanced)
                        matrix.show()
                        time.sleep(frame.info.get("duration", 100)/1000.0)
        else:
            base_img = Image.fromarray(default_frame.copy())
            draw = ImageDraw.Draw(base_img)
            text = str(goal_count)
            # Measure text size via font.getbbox()
            bbox = font.getbbox(text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x, y = GOAL_TEXT_POS
            # background rect
            draw.rectangle([x-PADDING, y-PADDING, x+text_w+PADDING, y+text_h+PADDING], fill=BG_COLOR)
            draw.text((x, y), text, fill=TEXT_COLOR, font=font)
            framebuffer[:] = np.asarray(base_img)
            matrix.show()
            time.sleep(0.01)

if __name__ == "__main__":
    main_display()