import os
import io
import numpy as np
from PIL import Image, ImageOps
from utils.ocr_tools import read_price_from_image
from datetime import datetime, timezone

TARGET_COLORS = [
    ((255, 25, 255), 'magenta'),
    ((0, 0, 255), 'blue'),
    ((0, 255, 0), 'green'),
    ((255, 0, 0), 'red'),
    ((206, 206, 99), 'olive')
]

def find_pixel(img, tolerance=5):
    img_rgb = img.convert('RGB')
    pixels = img_rgb.load()
    w, h = img_rgb.size
    for target_color, name in TARGET_COLORS:
        for y in range(h):
            for x in range(w):
                r, g, b = pixels[x, y]
                if (abs(r - target_color[0]) <= tolerance and
                    abs(g - target_color[1]) <= tolerance and
                    abs(b - target_color[2]) <= tolerance):
                    return True, x, y, name
    return False, None, None, None

def process_special_color_image(cropped_img, color_name, tolerance=3):
    color_map = {'green': (0,255,0), 'olive': (206,206,99)}
    img_rgb = cropped_img.convert('RGB')
    pixels = img_rgb.load()
    w, h = img_rgb.size
    cleaned = Image.new('RGB', (w, h))
    cpx = cleaned.load()
    target = color_map[color_name]
    tol = 1 if color_name == 'olive' else tolerance
    for y in range(h):
        for x in range(w):
            r,g,b = pixels[x,y]
            if abs(r-target[0])<=tol and abs(g-target[1])<=tol and abs(b-target[2])<=tol:
                cpx[x,y]=(255,255,255)
            else:
                cpx[x,y]=(r,g,b)
    return cleaned

def process_colored_image(cropped_img, color_name, tolerance=15):
    color_map = {'magenta': (255,25,255), 'blue': (0,0,255), 'red': (255,0,0)}
    target = color_map[color_name]
    img_rgb = cropped_img.convert('RGB')
    pixels = img_rgb.load()
    w,h = img_rgb.size
    iso = Image.new('RGB', (w,h))
    ipx = iso.load()
    for y in range(h):
        for x in range(w):
            r,g,b = pixels[x,y]
            if (abs(r-target[0])<=tolerance and abs(g-target[1])<=tolerance and abs(b-target[2])<=tolerance):
                ipx[x,y]=(255,255,255)
            else:
                ipx[x,y]=(0,0,0)
    gray = iso.convert("L")
    final = ImageOps.invert(gray.point(lambda p: 255 if p>50 else 0))

    # Save the processed image for debugging
    #debug_dir = "debug_ocr_images"
    #os.makedirs(debug_dir, exist_ok=True)
    #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Save both original and processed for comparison
    #original_filename = f"{debug_dir}/original_{color_name}_{timestamp}.png"
    #processed_filename = f"{debug_dir}/processed_{color_name}_{timestamp}.png"

    #cropped_img.save(original_filename)
    #final.save(processed_filename)
    #print(f"Saved debug images: {original_filename}, {processed_filename}")

    return final


async def process_image_for_price(attachment, ocr_reader):
    """
    Downloads an image, detects the color indicator, processes the price area,
    and uses EasyOCR to extract the price.

    Returns:
        tuple: (price, cleaned) on success, or (None, []) on failure
    """
    if ocr_reader is None:
        print("OCR Reader is not available in the Prices cog.")
        return None, []

    if not attachment:
        print("No attachment provided.")
        return None, []

    try:
        # 1. Download the image
        image_bytes = await attachment.read()
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"Error downloading/opening image: {e}")
        return None, []

    # 2. Find the indicator pixel
    found, x, y, color_name = find_pixel(img)
    if not found:
        print("Indicator pixel not found in image.")
        return None, []

    # 3. Define and Crop the Price Area
    crop_width = 90
    crop_height = 118
    start_x = x - 7
    start_y = y - 5
    end_x = start_x + crop_width
    end_y = start_y + crop_height

    try:
        cropped_img = img.crop((start_x, start_y, end_x, end_y))
    except Exception as e:
        print(f"Error cropping image: {e}")
        return None, []

    # 4. Process the cropped image for optimal OCR
    try:
        if color_name in ['green', 'olive']:
            processed_img = process_special_color_image(cropped_img, color_name)
        elif color_name in ['magenta', 'blue', 'red']:
            processed_img = process_colored_image(cropped_img, color_name)
        else:
            print(f"Unsupported color name: {color_name}")
            return None, []
    except Exception as e:
        print(f"Error processing image for color {color_name}: {e}")
        return None, []

    # 5. Read price from processed image
    try:
        price, cleaned = await read_price_from_image(ocr_reader, processed_img)

        # Ensure we always return a tuple, even if read_price_from_image returns None
        if price is None:
            return None, []

        return price, cleaned
    except Exception as e:
        print(f"Error reading price from image: {e}")
        return None, []
