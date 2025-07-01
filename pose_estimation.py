#!/usr/bin/env python3
"""
MoveNet Thunder Headless Stream + Optional Preview
===================================================
Streams pose overlay to LED matrix and optionally serves an MJPEG preview
via Flask. Disable the preview to save CPU and clear >10 FPS.

Usage:
  sudo python3 pose_stream_flask.py \
    --model movenet_thunder_int8.tflite \
    [--min-conf 0.05] [--no-preview]

Flags:
  --min-conf      Landmark confidence threshold (default 0.2)
  --no-preview    Disable MJPEG preview (only matrix output)
  --no-matrix     Disable LED matrix output (stream only)
"""
import argparse
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, render_template_string, stream_with_context
from picamera2 import Picamera2
from tflite_runtime.interpreter import Interpreter
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

# Pose skeleton edges (COCO order)
EDGES = [
    (0, 1), (1, 3), (0, 2), (2, 4),
    (0, 5), (0, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 6), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]
# Visualization colors (BGR)
CV_SKEL   = (0, 255, 0)
CV_DOT    = (0, 255, 255)
CV_BOX    = (255, 255, 0)
# Matrix LED color (g, r, b)
MAT_COLOR = (0, 255, 0)

# Flask app
app = Flask(__name__)
latest_jpeg = None
jpeg_lock = threading.Lock()

PREVIEW_HTML = """
<!doctype html>
<title>Pi Pose Preview</title>
<style>body{margin:0;background:#000;text-align:center;font-family:sans-serif}img{max-width:480px;width:90vw;height:auto;border:2px solid #0f0;border-radius:6px}</style>
<h2 style="color:#0f0">Pi Pose Preview</h2>
<img src="/video_feed" />
"""

@app.route("/")
def index():
    return render_template_string(PREVIEW_HTML)

@app.route("/video_feed")
def video_feed():
    def gen():
        while True:
            with jpeg_lock:
                frame = latest_jpeg
            if frame:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)
    return Response(stream_with_context(gen()), mimetype='multipart/x-mixed-replace; boundary=frame')

# Bresenham for matrix lines
def draw_line_matrix(buf, x0, y0, x1, y1, color):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1, -1)[x0 > x1], (1, -1)[y0 > y1]
    err = dx + dy
    h, w, _ = buf.shape
    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            buf[y0, x0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy

# Inference loop
def inference_loop(model_path, threads, rows, cols, chain, alpha, min_conf, use_matrix, use_preview):
    global latest_jpeg

    # Camera init RGB
    cam = Picamera2()
    cam.configure(cam.create_video_configuration(main={'size':(256,256),'format':'RGB888'}, controls={'FrameRate':30}))
    cam.start()

    # Interpreter
    interpreter = Interpreter(model_path=str(model_path), num_threads=threads)
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    in_idx, out_idx = inp['index'], out['index']
    dtype = inp['dtype']

    # Matrix init
    if use_matrix:
        width = cols * chain
        geo = piomatter.Geometry(width=width, height=rows, n_addr_lines=4, rotation=piomatter.Orientation.Normal)
        fb = np.zeros((rows, width, 3), dtype=np.uint8)
        panel = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed, pinout=piomatter.Pinout.AdafruitMatrixBonnet, framebuffer=fb, geometry=geo)
    else:
        fb = None

    prev_pts = None
    t0 = time.time(); count = 0
    while True:
        # Capture + mirror
        rgb = cam.capture_array('main')[:, ::-1]

        # Prepare tensor
        if dtype == np.float32:
            inp_img = rgb.astype(np.float32)/255.0
        else:
            inp_img = rgb.astype(dtype)
        tensor = np.expand_dims(inp_img, 0)

        # Inference
        interpreter.set_tensor(in_idx, tensor)
        interpreter.invoke()
        kps = interpreter.get_tensor(out_idx)[0,0]

        # Decode
        pts = [None if s<min_conf else (int(x*256),int(y*256)) for y,x,s in kps]
        # Smooth
        if prev_pts is None:
            sm = pts
        else:
            sm=[]
            for c,p in zip(pts,prev_pts):
                if c and p:
                    sm.append((int(alpha*c[0]+(1-alpha)*p[0]), int(alpha*c[1]+(1-alpha)*p[1])))
                else:
                    sm.append(c or p)
        prev_pts = sm

        # Preview
        if use_preview:
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            vis = bgr.copy()
            for pt in sm:
                if pt: cv2.circle(vis, pt, 3, CV_DOT, -1)
            for a,b in EDGES:
                if sm[a] and sm[b]: cv2.line(vis, sm[a], sm[b], CV_SKEL, 1)
            ok,buf = cv2.imencode('.jpg', vis, [cv2.IMWRITE_JPEG_QUALITY,80])
            if ok:
                with jpeg_lock: latest_jpeg=buf.tobytes()

        # Matrix draw
        if fb is not None:
            fb.fill(0)
            hm,wm = fb.shape[0], fb.shape[1]
            mapped=[None if p is None else (int(p[0]*wm/256), int(p[1]*hm/256)) for p in sm]
            for a,b in EDGES:
                if mapped[a] and mapped[b]: draw_line_matrix(fb, *mapped[a], *mapped[b], MAT_COLOR)
            panel.show()

        # FPS
        count+=1
        if count%30==0:
            print(f"FPS: {count/(time.time()-t0):.1f}")

# Main
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--rows',type=int,default=32)
    p.add_argument('--cols',type=int,default=64)
    p.add_argument('--chain',type=int,default=1)
    p.add_argument('--alpha',type=float,default=0.99)
    p.add_argument('--min-conf',type=float,default=0.2)
    p.add_argument('--no-preview',action='store_true')
    p.add_argument('--no-matrix',action='store_true')
    p.add_argument('--host',default='0.0.0.0')
    p.add_argument('--port',type=int,default=5000)
    args=p.parse_args()

    t=threading.Thread(target=inference_loop,args=(
        args.model,args.threads,args.rows,args.cols,args.chain,
        args.alpha,args.min_conf,not args.no_matrix,not args.no_preview),daemon=True)
    t.start()

    if not args.no_preview:
        print(f"Stream at http://{args.host}:{args.port}/")
        app.run(host=args.host,port=args.port,threaded=True,use_reloader=False)
    else:
        print("Preview disabled, running inference+matrix only...")
        while True: time.sleep(1)
