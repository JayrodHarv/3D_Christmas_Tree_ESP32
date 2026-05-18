#!/usr/bin/env python3
"""
tree_scan_triangulate.py

Complete pipeline:
  1. For each of 4 sides, find the lit LED in every photo
  2. Triangulate 3D coordinates using least-squares ray intersection
  3. Auto-correct obvious outliers
  4. Normalize to -1..1 range
  5. Export coords.json for the ESP32

Usage:
  python tree_scan_triangulate.py \
      --num_leds 184 \
      --camera_distance_mm 1905 \
      --front  scan_photos/side_1/ \
      --right  scan_photos/side_2/ \
      --back   scan_photos/side_3/ \
      --left   scan_photos/side_4/ \
      --output coords.json \
      --display

Dependencies:
  pip install opencv-python numpy scipy matplotlib
"""

import os
import sys
import json
import argparse
import math
import numpy as np
import cv2
import matplotlib.pyplot as plt
from scipy.ndimage import label
from mpl_toolkits.mplot3d import Axes3D

# ── Config ─────────────────────────────────────────────────────────────────────
IMAGE_WIDTH  = 1920
IMAGE_HEIGHT = 1080
FOCAL_LENGTH = 1200.0       # pixels — tune this to match your camera
CX           = IMAGE_WIDTH  / 2.0
CY           = IMAGE_HEIGHT / 2.0

# LED detection tuning
BRIGHTNESS_PERCENTILE  = 99.0   # how bright a pixel must be to be a candidate
MIN_BLOB_AREA          = 2      # minimum pixel area of a valid LED blob
MAX_BLOB_AREA          = 2000   # ignore blobs larger than this (background leak)
BACKGROUND_SAMPLE_IMGS = 5      # how many images to average for background subtraction

# Outlier correction
MAX_NEIGHBOR_DIST_MM   = 200    # mm — neighbours further than this are flagged

# ── Rotation matrices ──────────────────────────────────────────────────────────
def rotation_x(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])

def rotation_z(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])

# Z = up, camera looks down +Z, rotated 90deg around X to align axes
ROTATIONS = [
    rotation_z(0)              @ rotation_x(np.pi / 2),   # front
    rotation_z(np.pi / 2)     @ rotation_x(np.pi / 2),   # right
    rotation_z(np.pi)          @ rotation_x(np.pi / 2),   # back
    rotation_z(3 * np.pi / 2) @ rotation_x(np.pi / 2),   # left
]

# ── Image loading ──────────────────────────────────────────────────────────────
def load_images_from_dir(directory, num_leds):
    """Load images sorted by filename, return list of BGR arrays."""
    extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
    files = sorted([
        f for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in extensions
    ])

    if len(files) == 0:
        print(f"ERROR: No images found in {directory}")
        sys.exit(1)

    if len(files) != num_leds:
        print(f"WARNING: Expected {num_leds} images in {directory}, "
              f"found {len(files)}")

    images = []
    for fname in files:
        path = os.path.join(directory, fname)
        img  = cv2.imread(path)
        if img is None:
            print(f"ERROR: Could not read {path}")
            sys.exit(1)
        images.append(img)

    print(f"  Loaded {len(images)} images from {directory}")
    return images

# ── Background subtraction ─────────────────────────────────────────────────────
def build_background(images, n_samples=BACKGROUND_SAMPLE_IMGS):
    """
    Average a sample of images to estimate the background (unlit tree + ambient).
    Using the median is more robust than the mean against bright outliers.
    """
    step   = max(1, len(images) // n_samples)
    sample = [images[i].astype(np.float32) for i in range(0, len(images), step)]
    bg     = np.median(np.stack(sample), axis=0).astype(np.uint8)
    return bg

# ── LED detection ──────────────────────────────────────────────────────────────
def find_led_centroid(image, background, debug_name=None):
    """
    Find the sub-pixel centroid of the lit LED in an image.

    Strategy:
      1. Subtract background to isolate the LED
      2. Convert to grayscale
      3. Threshold at a high percentile to keep only the brightest region
      4. Find connected components, pick the one most likely to be a single LED
      5. Return intensity-weighted centroid (more accurate than bounding box center)

    Returns (u, v) in pixel coordinates, or None if no LED found.
    """
    # Background subtraction — removes ambient light and tree structure
    diff = cv2.subtract(image, background)

    # Grayscale
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    # Threshold — keep only the top N% of pixels
    threshold = np.percentile(gray, BRIGHTNESS_PERCENTILE)
    threshold = max(threshold, 15)   # floor to avoid thresholding pure noise
    _, mask   = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

    # Morphological close to fill small gaps in the blob
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8)

    # Filter blobs by area and pick the best candidate
    best_centroid = None
    best_score    = -1

    for lbl in range(1, num_labels):   # skip label 0 = background
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area < MIN_BLOB_AREA or area > MAX_BLOB_AREA:
            continue

        # Score = total brightness of blob (intensity-weighted is more accurate
        # than just picking the largest blob — a small very bright LED beats a
        # large dim reflection)
        blob_mask     = (labels == lbl).astype(np.uint8)
        total_bright  = float(cv2.sumElems(cv2.bitwise_and(gray, gray,
                                           mask=blob_mask))[0])
        if total_bright > best_score:
            best_score = total_bright
            # Intensity-weighted centroid within this blob
            ys, xs = np.where(blob_mask > 0)
            weights = gray[ys, xs].astype(np.float64)
            if weights.sum() > 0:
                u = float(np.average(xs, weights=weights))
                v = float(np.average(ys, weights=weights))
                best_centroid = (u, v)

    if debug_name and best_centroid is None:
        print(f"    WARNING: no LED found in {debug_name}")

    return best_centroid

def detect_all_leds(images, label, display=False):
    """
    Run find_led_centroid on every image in a side's image list.
    Returns list of (u, v) pairs. Missing detections are interpolated.
    """
    print(f"  Detecting LEDs — {label} ({len(images)} images)...")

    background = build_background(images)
    coords     = []
    missing    = []

    for i, img in enumerate(images):
        uv = find_led_centroid(img, background, debug_name=f"{label}/led_{i:04d}")
        coords.append(uv)
        if uv is None:
            missing.append(i)

        # Progress
        pct = (i + 1) / len(images) * 100
        bar = '#' * int(pct / 2) + '-' * (50 - int(pct / 2))
        sys.stdout.write(f'\r    [{bar}] {pct:.0f}%')
        sys.stdout.flush()

    print(f'\n    {len(missing)} missing detections')

    # Interpolate missing detections from neighbours
    coords = interpolate_missing(coords, missing)

    if display:
        _show_detections(images, background, coords, label)

    return coords

def interpolate_missing(coords, missing):
    """
    Replace None entries with linear interpolation from nearest valid neighbours.
    Falls back to nearest valid point if no bracket exists.
    """
    n      = len(coords)
    result = list(coords)

    for i in missing:
        # Find nearest valid points before and after
        prev_i = next((j for j in range(i-1, -1, -1) if result[j] is not None), None)
        next_i = next((j for j in range(i+1, n)      if result[j] is not None), None)

        if prev_i is not None and next_i is not None:
            t        = (i - prev_i) / (next_i - prev_i)
            pu, pv   = result[prev_i]
            nu, nv   = result[next_i]
            result[i] = (pu + t * (nu - pu), pv + t * (nv - pv))
        elif prev_i is not None:
            result[i] = result[prev_i]
        elif next_i is not None:
            result[i] = result[next_i]
        else:
            result[i] = (CX, CY)   # dead fallback

    return result

def _show_detections(images, background, coords, label):
    """Show a grid of detection results for manual inspection."""
    n_show = min(16, len(images))
    step   = max(1, len(images) // n_show)
    fig, axes = plt.subplots(4, 4, figsize=(14, 10))
    fig.suptitle(f'LED detections — {label}', fontsize=12)
    for idx, ax in enumerate(axes.flat):
        i = idx * step
        if i >= len(images):
            ax.axis('off')
            continue
        diff = cv2.subtract(images[i], background)
        rgb  = cv2.cvtColor(diff, cv2.COLOR_BGR2RGB)
        ax.imshow(rgb)
        ax.axis('off')
        ax.set_title(f'LED {i}', fontsize=8)
        if coords[i] is not None:
            u, v = coords[i]
            ax.plot(u, v, 'r+', markersize=10, markeredgewidth=2)
    plt.tight_layout()
    plt.show()

# ── Triangulation (your proven approach) ──────────────────────────────────────
def pixel_to_ray(u, v):
    x   = (u - CX) / FOCAL_LENGTH
    y   = -(v - CY) / FOCAL_LENGTH
    ray = np.array([x, y, 1.0])
    return ray / np.linalg.norm(ray)

def triangulate_point(pixel_sets, camera_distance_mm):
    """
    Least-squares intersection of 4 camera rays.
    pixel_sets: [(u0,v0), (u90,v90), (u180,v180), (u270,v270)]
    """
    A = np.zeros((3, 3))
    b = np.zeros(3)

    for (u, v), R in zip(pixel_sets, ROTATIONS):
        ray    = R @ pixel_to_ray(u, v)
        ray   /= np.linalg.norm(ray)
        origin = R @ np.array([0, 0, -camera_distance_mm])
        I      = np.eye(3)
        M      = I - np.outer(ray, ray)
        A     += M
        b     += M @ origin

    return np.linalg.solve(A, b).tolist()

def triangulate_all(c0, c90, c180, c270, camera_distance_mm):
    assert len(c0) == len(c90) == len(c180) == len(c270), \
        "All four sides must have the same number of detections"

    points = []
    n      = len(c0)

    print(f"\nTriangulating {n} points...")
    for i in range(n):
        pixels = [c0[i], c90[i], c180[i], c270[i]]
        points.append(triangulate_point(pixels, camera_distance_mm))
        pct = (i + 1) / n * 100
        bar = '#' * int(pct / 2) + '-' * (50 - int(pct / 2))
        sys.stdout.write(f'\r  [{bar}] {pct:.0f}%')
        sys.stdout.flush()

    print(' Done!')
    return points

# ── Outlier correction ─────────────────────────────────────────────────────────
def correct_outliers(coords, max_dist_mm=MAX_NEIGHBOR_DIST_MM):
    """
    Flag points that are too far from both neighbours and replace with
    linear interpolation. Iterates until no more outliers are found.
    """
    pts      = [np.array(p) for p in coords]
    n        = len(pts)
    total    = 0
    iteration = 0

    while True:
        iteration += 1
        bad = set()

        for i in range(1, n - 1):
            d_prev = np.linalg.norm(pts[i] - pts[i-1])
            d_next = np.linalg.norm(pts[i] - pts[i+1])
            if d_prev > max_dist_mm and d_next > max_dist_mm:
                bad.add(i)

        if not bad:
            break

        for i in sorted(bad):
            pts[i] = (pts[i-1] + pts[i+1]) / 2.0

        total += len(bad)
        print(f"  Outlier pass {iteration}: corrected {len(bad)} points")

    if total == 0:
        print("  No outliers detected")
    else:
        print(f"  Total corrected: {total} points")

    return [p.tolist() for p in pts]

# ── Normalization ──────────────────────────────────────────────────────────────
def normalize_coords(coords):
    """
    Normalize coordinates to -1..1 range, preserving aspect ratio.
    Centers on the tree trunk axis (XY center) and normalizes by max extent.
    """
    pts = np.array(coords)

    # Center X and Y on the tree axis
    pts[:, 0] -= np.mean(pts[:, 0])
    pts[:, 1] -= np.mean(pts[:, 1])

    # Z: shift so bottom of tree = -1
    pts[:, 2] -= pts[:, 2].min()
    pts[:, 2]  = pts[:, 2] / pts[:, 2].max() * 2.0 - 1.0

    # Scale X and Y by the same factor used for Z so aspect ratio is preserved
    max_xy = np.max(np.abs(pts[:, :2]))
    if max_xy > 0:
        pts[:, 0] /= max_xy
        pts[:, 1] /= max_xy

    return pts.tolist()

# ── Export ─────────────────────────────────────────────────────────────────────
def save_coords_json(coords, filename):
    """Save in the format expected by the ESP32 firmware."""
    data = {
        'leds': [
            {'id': i, 'x': round(p[0], 4),
                       'y': round(p[1], 4),
                       'z': round(p[2], 4)}
            for i, p in enumerate(coords)
        ]
    }
    if not filename.endswith('.json'):
        filename += '.json'
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved {len(coords)} coordinates to {filename}")

# ── Visualization ──────────────────────────────────────────────────────────────
def plot_3d(coords, title='3D Coordinates', bad_indices=None):
    pts     = np.array(coords)
    bad_set = set(bad_indices or [])
    colors  = ['red' if i in bad_set else 'limegreen' for i in range(len(coords))]

    fig = plt.figure(figsize=(10, 8))
    ax  = fig.add_subplot(111, projection='3d')
    ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
               s=8, c=colors, marker='o', depthshade=True)

    # Annotate a few LED indices for reference
    for i in range(0, len(coords), max(1, len(coords) // 20)):
        ax.text(pts[i, 0], pts[i, 1], pts[i, 2], str(i), fontsize=6, color='white')

    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_title(title, color='white')
    ax.tick_params(colors='white')

    # Equal aspect ratio
    max_range = np.ptp(pts, axis=0).max() / 2
    mid       = pts.mean(axis=0)
    ax.set_xlim(mid[0]-max_range, mid[0]+max_range)
    ax.set_ylim(mid[1]-max_range, mid[1]+max_range)
    ax.set_zlim(mid[2]-max_range, mid[2]+max_range)
    ax.view_init(elev=20, azim=45)
    plt.tight_layout()
    plt.show()

def plot_detection_quality(all_coords, side_labels):
    """
    Plot the 2D (u,v) detections for each side — useful for spotting
    systematic detection errors before triangulation.
    """
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, coords, label in zip(axes, all_coords, side_labels):
        us = [p[0] for p in coords]
        vs = [p[1] for p in coords]
        ax.scatter(us, vs, s=4, c=range(len(us)), cmap='viridis')
        ax.set_xlim(0, IMAGE_WIDTH)
        ax.set_ylim(IMAGE_HEIGHT, 0)
        ax.set_title(label)
        ax.set_aspect('equal')
        ax.set_xlabel('u (px)')
        ax.set_ylabel('v (px)')
    fig.suptitle('2D detections per side (color = LED index)')
    plt.tight_layout()
    plt.show()

# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description='Christmas tree LED coordinate triangulation')
    p.add_argument('--num_leds',            type=int,   required=True)
    p.add_argument('--camera_distance_mm',  type=float, required=True)
    p.add_argument('--focal_length',        type=float, default=FOCAL_LENGTH,
                   help=f'Camera focal length in pixels (default {FOCAL_LENGTH})')
    p.add_argument('--scan_dir', required=True,
               help='Root scan folder containing side_1/ side_2/ side_3/ side_4/')
    p.add_argument('--output', default='coords.json')
    p.add_argument('--display', action='store_true',
                   help='Show detection and result plots')
    p.add_argument('--max_outlier_dist_mm', type=float,
                   default=MAX_NEIGHBOR_DIST_MM)
    return p.parse_args()

def resolve_side_dirs(scan_dir):
    sides = {
        'front': os.path.join(scan_dir, 'front'),
        'right': os.path.join(scan_dir, 'right'),
        'back':  os.path.join(scan_dir, 'back'),
        'left':  os.path.join(scan_dir, 'left'),
    }
    missing = [name for name, path in sides.items() if not os.path.isdir(path)]
    if missing:
        print(f"ERROR: Could not find side folders in {scan_dir}:")
        for name in missing:
            print(f"  {sides[name]}")
        print("\nExpected structure:")
        print(f"  {scan_dir}/")
        print(f"  ├── front/   (front)")
        print(f"  ├── right/   (right)")
        print(f"  ├── back/   (back)")
        print(f"  └── left/   (left)")
        sys.exit(1)
    return sides['front'], sides['right'], sides['back'], sides['left']

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # Override globals from CLI args
    global FOCAL_LENGTH
    FOCAL_LENGTH = args.focal_length

    # Validate paths
    front, right, back, left = resolve_side_dirs(args.scan_dir)

    print("=" * 60)
    print("  Christmas Tree LED Coordinate Triangulation")
    print("=" * 60)
    print(f"  LEDs:             {args.num_leds}")
    print(f"  Camera distance:  {args.camera_distance_mm} mm")
    print(f"  Focal length:     {FOCAL_LENGTH} px")
    print(f"  Output:           {args.output}")
    print()

    # ── Step 1: Load images ────────────────────────────────────────────────────
    print("Loading images...")
    imgs_front = load_images_from_dir(front, args.num_leds)
    imgs_right = load_images_from_dir(right, args.num_leds)
    imgs_back  = load_images_from_dir(back,  args.num_leds)
    imgs_left  = load_images_from_dir(left,  args.num_leds)

    # ── Step 2: Detect LED pixel coordinates ──────────────────────────────────
    print("\nDetecting LEDs...")
    uv_front = detect_all_leds(imgs_front, 'front', display=args.display)
    uv_right = detect_all_leds(imgs_right, 'right', display=args.display)
    uv_back  = detect_all_leds(imgs_back,  'back',  display=args.display)
    uv_left  = detect_all_leds(imgs_left,  'left',  display=args.display)

    if args.display:
        plot_detection_quality(
            [uv_front, uv_right, uv_back, uv_left],
            ['Front', 'Right', 'Back', 'Left'])

    # ── Step 3: Triangulate ────────────────────────────────────────────────────
    coords = triangulate_all(
        uv_front, uv_right, uv_back, uv_left,
        args.camera_distance_mm)

    if args.display:
        plot_3d(coords, 'Raw triangulated coordinates')

    # ── Step 4: Correct outliers ───────────────────────────────────────────────
    print("\nCorrecting outliers...")
    coords = correct_outliers(coords, max_dist_mm=args.max_outlier_dist_mm)

    if args.display:
        plot_3d(coords, 'After outlier correction')

    # ── Step 5: Normalize ──────────────────────────────────────────────────────
    print("\nNormalizing to -1..1 range...")
    coords = normalize_coords(coords)

    if args.display:
        plot_3d(coords, 'Final normalized coordinates')

    # ── Step 6: Save ───────────────────────────────────────────────────────────
    save_coords_json(coords, args.output)

    print("\nDone! Upload coords.json via http://192.168.4.1")
    print("=" * 60)

if __name__ == '__main__':
    main()