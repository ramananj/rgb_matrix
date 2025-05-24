import socket
import cv2
import struct
import time
from picamera2 import Picamera2
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

SERVER_IP = "192.168.86.39"
SERVER_PORT = 9000

def connect():
    while True:
        try:
            print("Connecting...")
            sock = socket.create_connection((SERVER_IP, SERVER_PORT))
            print("Connected.")
            return sock
        except Exception as e:
            print("Retrying in 2 seconds...", e)
            time.sleep(2)

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

sock = connect()

while True:
    try:
        # --- ⏱ Start timing
        capture_start = time.perf_counter()

        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        _, jpeg = cv2.imencode('.jpg', frame)
        data = jpeg.tobytes()

        encode_end = time.perf_counter()
        sock.sendall(struct.pack('>L', len(data)) + data)
        send_end = time.perf_counter()

        # --- Print timings
        capture_encode_time = (encode_end - capture_start) * 1000
        total_send_time = (send_end - capture_start) * 1000
        logging.info(f"[Sender] Encode: {capture_encode_time:.2f} ms, Total Send: {total_send_time:.2f} ms")

        time.sleep(0.05)  # ~20 fps

    except (BrokenPipeError, ConnectionResetError):
        print("Disconnected. Reconnecting...")
        sock.close()
        sock = connect()
