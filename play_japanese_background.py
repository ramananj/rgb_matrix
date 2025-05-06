#!/usr/bin/python3
"""
Display an animated gif

Run like this:

$ python play_gif.py

The animated gif is played repeatedly until interrupted with ctrl-c.
"""

import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from PIL import ImageEnhance
import requests
import adafruit_blinka_raspberry_pi5_piomatter as piomatter


API_KEY = "188b74ed419d910f9b947708e31ab32d"
LATITUDE = "43.879099337335475"
LONGITUDE = "-79.05372454124822"


def get_current_weather_by_coord():
    """
    Fetch the current weather for a given latitude and longitude using OpenWeatherMap API.
    
    :param latitude: float, latitude of location
    :param longitude: float, longitude of location
    :param api_key: str, your OpenWeatherMap API key
    :return: tuple (weather_status, temperature) or (None, None) if an error occurred
    """
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": LATITUDE,
        "lon": LONGITUDE,
        "appid": API_KEY,
        "units": "metric"  # "imperial" if you want °F
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raises an HTTPError if the status code is 4xx or 5xx
        data = response.json()

        # Weather status can be taken from "weather"[0]["main"] or "weather"[0]["description"]
        weather_status = data["weather"][0]["main"]
        temperature = data["main"]["temp"]

        return weather_status, temperature
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None, None
    except (KeyError, IndexError) as e:
        print(f"Response format error: {e}")
        return None, None
    

def get_weather_image(status, weather_img_map):
    """
    Return the best matching weather image path for the given status.
    If none is found, return a default image path.
    """
    # Convert the status to lowercase for case-insensitive comparison
    status_lower = status.lower()
    
    for key, image_path in weather_img_map.items():
        # Split the dict key on whitespace, e.g. "drizzle rain thunderstorm" -> ["drizzle","rain","thunderstorm"]
        key_words = key.split()
        
        # Check if our status is in that list of words
        if status_lower in key_words:
            return image_path
    
    # Fallback if there's no match
    return "weather_images/clear.png"


def main_display():
    last_weather_call_time = 0
    weather_status, weather_temp, weather_img_path = None, None, None
    weather_img_dict = {
        "drizzle rain": "weather_images/rainy.png",
        "thunder": "weather_images/thunder,png",
        "clear": "weather_images/clear.png",
        "snow": "weather_images/snowy.png",
        "fog clouds mist": "weather_images/cloudy.png",
    }
    

    width = 64
    height = 32

    background_images = ["japanese_wave_pixel.png", "japanese_temple_2_pixel.png", "cherry_blossom_pixel.png"]

    canvas = Image.new('RGB', (width, height), (0, 0, 0))
    geometry = piomatter.Geometry(width=width, height=height,
                                n_addr_lines=4, rotation=piomatter.Orientation.Normal)
    framebuffer = np.asarray(canvas) + 0  # Make a mutable copy
    matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                                pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                                framebuffer=framebuffer,
                                geometry=geometry)

    top_height = 25
    full_width = 64
    full_height = 32

    while True:
        current_time = time.time()
        # Check if 30 minutes have passed since last weather update
        if current_time - last_weather_call_time >= 1800:
            status, temp = get_current_weather_by_coord()
            if status is not None:
                weather_status, weather_temp = status, temp
                print(weather_status, weather_temp)
                weather_img_path = get_weather_image(weather_status, weather_img_dict)
            else:
                weather_img_path = None
            last_weather_call_time = time.time()


        for background_image in background_images:
            canvas = Image.new('RGB', (width, height), (0, 0, 0))
            if weather_img_path is not None:
                with open(weather_img_path, "rb") as f:
                    weather_img = Image.open(f).convert("RGB").resize((12, 6), Image.LANCZOS)
            else:
                weather_img = None
            with open(background_image, "rb") as f:
                img = Image.open(f).convert("RGB")
                img = img.resize((full_width, top_height), Image.LANCZOS)

            draw = ImageDraw.Draw(canvas)

            # Use your font
            font = ImageFont.truetype("fonts/font_2_5x7.ttf", size=8)
            # font = ImageFont.load_bdf("fonts/font_5x7.bdf")
            # font = ImageFont.truetype("fonts/PixelOperatorMono.ttf", size=9)

            # Get timestamp
            now = datetime.now()
            timestamp = now.strftime("%H:%M %b%d")
            draw.text((0, 25), timestamp, font=font, fill=(255, 255, 255))

            # Fixed pixel width per character (experimentally chosen)
            # char_width = 4  # Try 5 or 6 depending on your font + size
            # char_spacing = 0  # Or try 1 if needed
            # step = char_width + char_spacing

            # # Total width for centering
            # total_width = len(timestamp) * step
            # x_start = 1#(full_width - total_width) // 2
            # y = top_height

            # # Draw each character with fixed step
            # x = x_start
            # for char in timestamp:
            #     draw.text((x, y), char, font=font, fill=(255, 255, 255))
            #     x += step

            # Then crop out the region holding the text
            text_region_box = (0, top_height, 47, height)
            text_region = canvas.crop(text_region_box)

            # Apply brightness or contrast
            enhancer = ImageEnhance.Brightness(text_region)
            brighter_region = enhancer.enhance(0.75)  # e.g. double the brightness

            # Paste back
            canvas.paste(brighter_region, text_region_box)
        
            enhancer = ImageEnhance.Contrast(img)
            high_contrast = enhancer.enhance(1.5)
            # posterized = high_contrast.convert("P", palette=Image.ADAPTIVE, colors=8).convert("RGB") 
            canvas.paste(high_contrast, (0,0))
            if weather_img is not None:
                enhancer = ImageEnhance.Contrast(weather_img)
                high_contrast = enhancer.enhance(2.5)
                canvas.paste(high_contrast, (49, 26))
            framebuffer[:] = np.asarray(canvas)
            matrix.show()
            time.sleep(10)

           

if __name__ == "__main__":
    main_display()