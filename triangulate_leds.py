"""
triangulate_leds.py
--------------------
Triangulates 3D coordinates of LEDs on a Christmas tree from images taken
from 4 cardinal directions (front, right, back, left) by rotating the tree
in front of a fixed camera.

Directory structure expected:
    <root>/
        front/   led_0000.jpg, led_0001.jpg, led_0002.jpg ...
        right/   led_0000.jpg, led_0001.jpg, led_0002.jpg ...
        back/    led_0000.jpg, led_0001.jpg, led_0002.jpg ...
        left/    led_0000.jpg, led_0001.jpg, led_0002.jpg ...

Each image contains exactly one lit LED (the brightest point).

Usage:
    python triangulate_leds.py --input_dir ./images --output coords.json

Optional flags:
    --fov_deg        Horizontal camera FOV in degrees (default: 60)
    --camera_dist    Distance from camera to tree centre in metres (default: 1.0)
                     Used only to scale the output; ratios are always correct.
    --blur_radius    Gaussian blur radius before finding brightest point (default: 5)
    --debug          Save annotated images to ./debug/
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIRECTIONS = ["front", "right", "back", "left"]
LED_FILE_PATTERN = re.compile(r"^led_(\d{4})$", re.IGNORECASE)
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Rotation of the tree (in degrees, counter-clockwise when viewed from above)
# when a photo is taken from that nominal direction.
#   front  → tree at   0° rotation  → camera sees +Z face
#   right  → tree at  90° CCW       → camera sees +X face (tree rotated so right side faces cam)
#   back   → tree at 180°           → camera sees -Z face
#   left   → tree at 270°           → camera sees -X face
DIRECTION_ANGLES = {
    "front": 0,
    "right": 90,
    "back": 180,
    "left": 270,
}


# ---------------------------------------------------------------------------
# Camera model helpers
# ---------------------------------------------------------------------------

def build_intrinsics(image_width: int, image_height: int, fov_deg: float) -> np.ndarray:
    """Return a 3×3 camera intrinsic matrix K for a pinhole camera."""
    fx = (image_width / 2.0) / math.tan(math.radians(fov_deg / 2.0))
    fy = fx  # square pixels assumed
    cx = image_width / 2.0
    cy = image_height / 2.0
    K = np.array([
        [fx,  0, cx],
        [ 0, fy, cy],
        [ 0,  0,  1],
    ], dtype=np.float64)
    return K


def rotation_y(angle_deg: float) -> np.ndarray:
    """Rotation matrix around the Y axis (vertical) by angle_deg degrees."""
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    return np.array([
        [ c, 0, s],
        [ 0, 1, 0],
        [-s, 0, c],
    ], dtype=np.float64)


def build_extrinsics(angle_deg: float, camera_dist: float):
    """
    Return (R, t) for the camera viewing the tree after it has been rotated
    by angle_deg degrees counter-clockwise.

    Convention:
      - World origin = centre of tree base
      - Y axis = up
      - Camera is always at (0, 0, camera_dist) in world space looking at origin.

    Rotating the *tree* by angle_deg CCW is equivalent to rotating the
    *camera* by angle_deg CW around Y, i.e. R_world_from_cam = Ry(-angle_deg).
    """
    # Camera position in world coordinates (always same physical spot)
    cam_pos_world = np.array([0.0, 0.0, camera_dist], dtype=np.float64)

    # Rotation of tree ≡ inverse rotation of camera
    R_tree = rotation_y(angle_deg)          # tree rotation matrix
    R_cam  = rotation_y(-angle_deg)         # camera's rotation in world frame

    # Standard OpenCV convention: X_cam = R * X_world + t
    # where R rotates world→camera and t = -R @ cam_pos_world
    # The camera always points at the origin; we build R so that the camera
    # coordinate frame has:
    #   Z_cam pointing toward the tree centre (from the camera position)
    #   Y_cam pointing up (same as world Y)
    #   X_cam = Y_cam × Z_cam

    # Z_cam (into scene from camera)
    z_cam = -cam_pos_world / np.linalg.norm(cam_pos_world)   # (0,0,-1) before rotation
    # Apply tree rotation to camera direction vector
    z_cam = R_tree @ z_cam        # after rotating tree, camera effectively moved
    # Undo: camera is fixed, tree rotated → reproject
    # Simpler: just use the angle directly.

    # Rebuild properly:
    # Camera is at world position p_c = (0, 0, d).
    # After tree rotation by θ, a world point P_tree becomes R_tree @ P_tree in the
    # un-rotated frame.  So we treat the camera as being at p_c but looking at a
    # rotated world.  The extrinsic is:
    #   R_cv  = R_lookat @ R_tree
    #   t_cv  = -R_cv @ p_c   ... but p_c is fixed
    #
    # R_lookat: rotation that takes world axes to camera axes when tree is at 0°.
    # Camera at (0,0,d) looking at origin → z_cam = (0,0,-1), x_cam=(1,0,0), y_cam=(0,1,0)
    # That is just the identity (no flip needed if we define world Z toward camera).
    # Actually standard: cam looks along +Z_cam; world Z_cam = world -Z. So:
    R_lookat = np.array([
        [1,  0,  0],
        [0,  1,  0],
        [0,  0, -1],   # flip Z so camera looks toward +Z_cam = world -Z
    ], dtype=np.float64)
    # Hmm – let's keep it simple and consistent:
    # Place camera at (0, 0, +d), looking toward –Z world direction.
    # R_extrinsic = R_lookat @ R_tree  (tree rotation applied first in world)
    # No—tree rotation rotates the LED positions, not the camera frame.
    # The correct formulation:

    # World coords WITH tree rotation θ: P' = Ry(θ) @ P_original
    # Camera extrinsic (fixed camera at (0,0,d) looking at origin):
    #   R_cv  = R_lookat   (constant, camera never moves)
    #   t_cv  = -R_cv @ [0, 0, d]^T
    # But we want to recover P_original from pixel coords.
    # ray in camera frame → ray in world frame → intersect with geometry.
    # Equivalently we can absorb tree rotation into R:
    #   R_eff = R_lookat @ Ry(θ)
    #   t_eff = -R_lookat @ [0, 0, d]^T   (t doesn't change with tree rotation)

    R_lookat2 = np.diag([1.0, -1.0, -1.0])   # standard OpenCV: Y down, Z forward
    # Camera at (0,0,d): in camera frame it is at origin, world origin is at (0,0,-d) camera frame
    # without tree rotation. With tree rotation θ:
    R_eff = R_lookat2 @ rotation_y(angle_deg)
    t_eff = R_lookat2 @ np.array([0.0, 0.0, -camera_dist])

    return R_eff, t_eff


# ---------------------------------------------------------------------------
# LED detection
# ---------------------------------------------------------------------------

def find_brightest_point(image_path: Path, blur_radius: int = 5) -> tuple[float, float] | None:
    """
    Load a grayscale image and return the (x, y) pixel coords of the
    brightest point, using Gaussian blur to reduce noise.
    Returns None if the image cannot be loaded.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Blur to smooth noise
    k = blur_radius | 1  # ensure odd
    blurred = cv2.GaussianBlur(gray, (k * 4 + 1, k * 4 + 1), k)

    _, _, _, max_loc = cv2.minMaxLoc(blurred)
    return float(max_loc[0]), float(max_loc[1])


def find_brightest_point_subpixel(image_path: Path, blur_radius: int = 5,
                                   window: int = 15) -> tuple[float, float] | None:
    """
    Like find_brightest_point but refines to sub-pixel accuracy using a
    weighted centroid around the peak.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    k = blur_radius | 1
    blurred = cv2.GaussianBlur(gray, (k * 4 + 1, k * 4 + 1), float(k))

    _, _, _, max_loc = cv2.minMaxLoc(blurred)
    px, py = max_loc

    # Weighted centroid in a local window
    h, w = blurred.shape
    x0 = max(0, px - window)
    x1 = min(w, px + window + 1)
    y0 = max(0, py - window)
    y1 = min(h, py + window + 1)

    patch = blurred[y0:y1, x0:x1].astype(np.float64)
    patch = np.clip(patch - patch.min(), 0, None)  # shift so min = 0
    total = patch.sum()
    if total == 0:
        return float(px), float(py)

    ys, xs = np.mgrid[y0:y1, x0:x1]
    cx = float((xs * patch).sum() / total)
    cy = float((ys * patch).sum() / total)
    return cx, cy


# ---------------------------------------------------------------------------
# Triangulation
# ---------------------------------------------------------------------------

def pixel_to_ray(px: float, py: float, K: np.ndarray, R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Given a pixel (px, py), intrinsics K, and extrinsic rotation R (world→cam),
    return (origin, direction) of the ray in world coordinates.
    The origin is the camera centre in world coordinates.
    """
    # Camera centre in world coords: C = -R^T @ t  (we pass t separately below)
    # This function only needs R to get direction.
    # Normalised image coords
    p_img = np.array([px, py, 1.0], dtype=np.float64)
    p_cam = np.linalg.inv(K) @ p_img          # direction in camera frame
    p_cam /= np.linalg.norm(p_cam)
    # Direction in world frame
    direction = R.T @ p_cam
    direction /= np.linalg.norm(direction)
    return direction


def triangulate_rays(rays: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    """
    Least-squares triangulation from N rays.
    Each ray is (origin, direction) in world coordinates.
    Uses the DLT / linear least squares method:
      minimise sum of squared distances from point P to each ray.

    Returns estimated 3D point.
    """
    # For each ray i: origin o_i, unit direction d_i
    # Distance² from point P to ray = ||(P - o_i) - ((P - o_i)·d_i) d_i||²
    # Minimising leads to a linear system A @ P = b
    # A = sum_i (I - d_i d_i^T)
    # b = sum_i (I - d_i d_i^T) @ o_i

    A = np.zeros((3, 3), dtype=np.float64)
    b = np.zeros(3, dtype=np.float64)

    for origin, direction in rays:
        d = direction.reshape(3, 1)
        proj = np.eye(3) - d @ d.T
        A += proj
        b += proj @ origin

    P, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    return P


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------

def save_debug_image(image_path: Path, point: tuple[float, float], debug_dir: Path) -> None:
    img = cv2.imread(str(image_path))
    if img is None:
        return
    x, y = int(round(point[0])), int(round(point[1]))
    cv2.drawMarker(img, (x, y), (0, 255, 0), cv2.MARKER_CROSS, 30, 2)
    cv2.circle(img, (x, y), 15, (0, 0, 255), 2)
    out_path = debug_dir / image_path.parent.name / image_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def collect_led_ids(input_dir: Path) -> set[str]:
    ids: set[str] = set()
    for direction in DIRECTIONS:
        d = input_dir / direction
        if not d.is_dir():
            print(f"  [warn] Directory not found: {d}")
            continue
        for f in d.iterdir():
            if f.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
                continue
            match = LED_FILE_PATTERN.match(f.stem)
            if match:
                ids.add(match.group(1))
    return ids


def run(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    debug = args.debug
    debug_dir = Path("debug") if debug else None

    if debug and debug_dir:
        debug_dir.mkdir(exist_ok=True)

    # Collect all LED IDs
    print("Scanning directories...")
    led_ids = collect_led_ids(input_dir)
    if not led_ids:
        print("No images found. Check --input_dir.")
        sys.exit(1)
    print(f"  Found {len(led_ids)} unique LED IDs across all directions.")

    # Probe image size from first available image
    sample_img = None
    for direction in DIRECTIONS:
        d = input_dir / direction
        if d.is_dir():
            for f in d.iterdir():
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                    sample_img = cv2.imread(str(f))
                    break
        if sample_img is not None:
            break

    if sample_img is None:
        print("Could not read any images.")
        sys.exit(1)

    img_h, img_w = sample_img.shape[:2]
    print(f"  Image size: {img_w}×{img_h}  |  FOV: {args.fov_deg}°  |  Camera dist: {args.camera_dist} m")

    K = build_intrinsics(img_w, img_h, args.fov_deg)

    # Build extrinsics per direction
    extrinsics: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    camera_centres: dict[str, np.ndarray] = {}
    for direction, angle in DIRECTION_ANGLES.items():
        R, t = build_extrinsics(angle, args.camera_dist)
        extrinsics[direction] = (R, t)
        # Camera centre in world: C = -R^T @ t
        camera_centres[direction] = -R.T @ t

    # Process each LED
    results: dict[str, dict] = {}
    missing: list[str] = []

    led_ids_sorted = sorted(led_ids, key=lambda x: int(x) if x.isdigit() else x)

    print(f"\nProcessing {len(led_ids_sorted)} LEDs...")
    for led_id in led_ids_sorted:
        rays: list[tuple[np.ndarray, np.ndarray]] = []
        detections: dict[str, list[float]] = {}
        found_dirs: list[str] = []

        for direction in DIRECTIONS:
            img_path = None
            for ext in VALID_IMAGE_EXTENSIONS:
                candidate = input_dir / direction / f"led_{led_id}{ext}"
                if candidate.exists():
                    img_path = candidate
                    break

            if img_path is None:
                continue  # this direction has no image for this LED

            point = find_brightest_point_subpixel(img_path, blur_radius=args.blur_radius)
            if point is None:
                print(f"  [warn] Could not read {img_path}")
                continue

            detections[direction] = list(point)
            found_dirs.append(direction)

            R, t = extrinsics[direction]
            direction_vec = pixel_to_ray(point[0], point[1], K, R)
            origin = camera_centres[direction]
            rays.append((origin, direction_vec))

            if debug and debug_dir:
                save_debug_image(img_path, point, debug_dir)

        if len(rays) < 2:
            print(f"  [skip] LED {led_id}: only {len(rays)} view(s) found, need ≥2.")
            missing.append(led_id)
            continue

        P = triangulate_rays(rays)

        # Convert metres → whole-number millimetres
        results[led_id] = {
            "id": int(led_id) if led_id.isdigit() else led_id,
            "x": int(round(float(P[0]) * 1000)),
            "y": int(round(float(P[1]) * 1000)),
            "z": int(round(float(P[2]) * 1000)),
        }

    # --- Normalize coordinates ---
    # x/z: centre on the average of all LEDs (trunk assumed at centroid)
    # y:   shift so the lowest LED is y=0
    raw = [results[k] for k in led_ids_sorted if k in results]
    if raw:
        cx = sum(r["x"] for r in raw) / len(raw)
        cz = sum(r["z"] for r in raw) / len(raw)
        min_y = min(r["y"] for r in raw)
        for r in raw:
            r["x"] = int(round(r["x"] - cx))
            r["z"] = int(round(r["z"] - cz))
            r["y"] = int(round(r["y"] - min_y))
        print(f"  Normalized: x/z centred (offset {cx:.1f}, {cz:.1f} mm), y shifted by {min_y:.1f} mm")

    # Write JSON in the required format: {"leds": [{"id":0,"x":0,"y":0,"z":0}, ...]}
    output_data = {"leds": raw}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Wrote {len(raw)} LED coordinates to {output_path}")
    if missing:
        print(f"  Skipped {len(missing)} LEDs (insufficient views): {missing}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Triangulate 3D LED positions from 4-direction Christmas tree images."
    )
    parser.add_argument(
        "--input_dir", required=True,
        help="Root directory containing front/, right/, back/, left/ subdirectories."
    )
    parser.add_argument(
        "--output", default="led_coordinates.json",
        help="Output JSON file path (default: led_coordinates.json)."
    )
    parser.add_argument(
        "--fov_deg", type=float, default=60.0,
        help="Horizontal camera field of view in degrees (default: 60). "
             "If you know your camera's focal length f and sensor width w, "
             "use: fov = 2 * atan(w / (2*f)) in degrees."
    )
    parser.add_argument(
        "--camera_dist", type=float, default=1.0,
        help="Distance from camera to centre of tree in metres (default: 1.0). "
             "Output coordinates will be in the same unit."
    )
    parser.add_argument(
        "--blur_radius", type=int, default=5,
        help="Gaussian blur radius for LED detection (default: 5). "
             "Increase if the background has bright noise."
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Save annotated images to ./debug/ showing detected LED positions."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args)