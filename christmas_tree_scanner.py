#!/usr/bin/env python3
"""
christmas_tree_scan.py

Workflow:
  1. Run script, camera in fixed position (side 1)
  2. Script scans all LEDs automatically, camera shoots each one
  3. Script tells you to rotate tree 90 degrees
  4. Repeat for sides 2, 3, 4
  5. Photos saved to organized folders for coordinate extraction
"""

import requests
import time
import os
import sys

# ── Config ────────────────────────────────────────────────────────────────────
ESP32_IP      = "192.168.4.1"
NUM_LEDS      = 50
OUTPUT_DIR    = "scan_photos"
NUM_SIDES     = 4
LED_SETTLE_MS = 150    # ms to wait after lighting LED before shooting
BETWEEN_MS    = 50     # ms between photo taken and next LED

# Camera backend: "gphoto2", "opencv", or "manual"
CAMERA_BACKEND = "opencv"

# ── Camera backends ───────────────────────────────────────────────────────────
def setup_camera():
    if CAMERA_BACKEND == "gphoto2":
        import subprocess
        result = subprocess.run(["gphoto2", "--auto-detect"],
                                capture_output=True, text=True)
        print(result.stdout)
        if "usb:" not in result.stdout:
            print("ERROR: No camera detected. Check USB connection.")
            sys.exit(1)
        print("Camera detected via gPhoto2")

    elif CAMERA_BACKEND == "opencv":
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("ERROR: Could not open webcam")
            sys.exit(1)
        # Warm up the camera — first few frames are often dark
        for _ in range(10):
            cap.read()
        print("Webcam ready")
        return cap

    elif CAMERA_BACKEND == "manual":
        print("Manual mode — you will be prompted for each photo")

    return None

def capture_photo(filepath, camera=None):
    """Take a photo and save it to filepath."""

    if CAMERA_BACKEND == "gphoto2":
        import subprocess
        subprocess.run([
            "gphoto2",
            "--capture-image-and-download",
            f"--filename={filepath}",
            "--force-overwrite"
        ], capture_output=True)   # suppress gphoto2 output noise

    elif CAMERA_BACKEND == "opencv":
        import cv2
        # Grab a few frames to flush the buffer — webcams buffer frames
        for _ in range(3):
            camera.read()
        ret, frame = camera.read()
        if ret:
            cv2.imwrite(filepath, frame)
        else:
            print(f"  WARNING: Failed to capture frame for {filepath}")

    elif CAMERA_BACKEND == "manual":
        input(f"  Take photo, save as {filepath}, then press Enter...")

# ── ESP32 control ─────────────────────────────────────────────────────────────
def esp_request(path, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(f"http://{ESP32_IP}{path}",
                             params=params, timeout=5)
            return r
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                print(f"  ERROR: ESP32 request failed: {e}")
                return None
            time.sleep(0.5)

def light_led(index):
    esp_request("/scan/cmd", {"action": "goto", "index": index})

def scan_stop():
    esp_request("/scan/cmd", {"action": "stop"})

def scan_start():
    esp_request("/scan/cmd", {"action": "start"})

# ── Main scan ─────────────────────────────────────────────────────────────────
def scan_side(side_num, camera=None):
    """Scan all LEDs for one side of the tree."""

    side_dir = os.path.join(OUTPUT_DIR, f"side_{side_num}")
    os.makedirs(side_dir, exist_ok=True)

    print(f"\n  Scanning side {side_num} — {NUM_LEDS} LEDs")
    print(f"  Photos saving to: {side_dir}/")
    print(f"  Estimated time: ~{(NUM_LEDS * (LED_SETTLE_MS + BETWEEN_MS)) // 1000}s\n")

    scan_start()
    time.sleep(0.3)

    for i in range(NUM_LEDS):
        # Light the LED
        light_led(i)
        time.sleep(LED_SETTLE_MS / 1000.0)

        # Take the photo
        filepath = os.path.join(side_dir, f"led_{i:04d}.jpg")
        capture_photo(filepath, camera)
        time.sleep(BETWEEN_MS / 1000.0)

        # Progress indicator
        pct = (i + 1) / NUM_LEDS * 100
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f"\r  [{bar}] {i+1}/{NUM_LEDS} ({pct:.0f}%)", end='', flush=True)

    print()  # newline after progress bar
    scan_stop()
    print(f"  Side {side_num} complete — {NUM_LEDS} photos saved")

def main():
    print("=" * 50)
    print("  Christmas Tree LED Scanner")
    print("=" * 50)

    # Check ESP32 is reachable
    print("\nConnecting to ESP32...")
    r = esp_request("/status")
    if r is None:
        print("ERROR: Could not reach ESP32.")
        print("Make sure you are connected to the 'ChristmasTree' Wi-Fi network.")
        sys.exit(1)
    print("ESP32 connected")

    # Setup camera
    print("Setting up camera...")
    camera = setup_camera()

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"""
Scan plan:
  LEDs:      {NUM_LEDS}
  Sides:     {NUM_SIDES}
  Photos:    {NUM_LEDS * NUM_SIDES} total
  Output:    {OUTPUT_DIR}/
  Camera:    {CAMERA_BACKEND}

Output folder structure:
  {OUTPUT_DIR}/
  ├── side_1/  led_0000.jpg ... led_{NUM_LEDS-1:04d}.jpg
  ├── side_2/  led_0000.jpg ... led_{NUM_LEDS-1:04d}.jpg
  ├── side_3/  led_0000.jpg ... led_{NUM_LEDS-1:04d}.jpg
  └── side_4/  led_0000.jpg ... led_{NUM_LEDS-1:04d}.jpg
    """)

    input("Position camera at side 1, then press Enter to begin...")

    for side in range(1, NUM_SIDES + 1):
        scan_side(side, camera)

        if side < NUM_SIDES:
            print(f"\n{'=' * 50}")
            print(f"  Rotate tree 90 degrees for side {side + 1}")
            print(f"{'=' * 50}")
            input(f"  Press Enter when ready for side {side + 1}...")

    # Cleanup
    if CAMERA_BACKEND == "opencv" and camera:
        import cv2
        camera.release()

    print(f"""
{'=' * 50}
  Scan complete!
  {NUM_LEDS * NUM_SIDES} photos saved to {OUTPUT_DIR}/

  Next steps:
  1. Use xmas-tree-mapper or similar tool to extract
     3D coordinates from the photos
  2. Export as coords.json
  3. Upload via http://192.168.4.1
{'=' * 50}
    """)

if __name__ == "__main__":
    main()