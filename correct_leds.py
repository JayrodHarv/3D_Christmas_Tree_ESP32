"""
correct_leds.py
---------------
Detects and corrects outlier LED coordinates in a JSON file produced by
triangulate_leds.py.

Outlier detection: for each LED, computes the mean distance to its K nearest
neighbours. If that distance exceeds (global_median + threshold * global_MAD)
it is flagged as an outlier.

Correction: outlier coordinates are replaced by a weighted average of their
K nearest *non-outlier* neighbours, with weights = 1 / distance.  The process
runs iteratively (up to --max_passes) until no new outliers are found.

Usage:
    python correct_leds.py --input coords.json --output corrected.json

Optional flags:
    --k               Number of neighbours to consider (default: 6)
    --threshold       Outlier sensitivity in MAD units (default: 3.5)
                      Lower = more aggressive, higher = more lenient.
    --max_passes      Maximum correction iterations (default: 5)
    --dry_run         Report outliers but do not write corrected output
    --debug           Print per-LED distance statistics
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Neighbour distance helpers
# ---------------------------------------------------------------------------

def coords_array(leds: list[dict]) -> np.ndarray:
    """Return an (N, 3) float array of [x, y, z] for each LED."""
    return np.array([[led["x"], led["y"], led["z"]] for led in leds], dtype=np.float64)


def mean_knn_distances(pts: np.ndarray, k: int) -> np.ndarray:
    """
    For each point compute the mean Euclidean distance to its K nearest
    neighbours (excluding itself).  Returns a 1-D array of length N.
    """
    n = len(pts)
    k = min(k, n - 1)
    dists = np.zeros(n, dtype=np.float64)
    for i in range(n):
        diff = pts - pts[i]                          # (N, 3)
        d = np.sqrt((diff ** 2).sum(axis=1))         # (N,)
        d[i] = np.inf                                # exclude self
        nearest = np.sort(d)[:k]
        dists[i] = nearest.mean()
    return dists


def mad(x: np.ndarray) -> float:
    """Median Absolute Deviation."""
    return float(np.median(np.abs(x - np.median(x))))


# ---------------------------------------------------------------------------
# Outlier detection
# ---------------------------------------------------------------------------

def detect_outliers(pts: np.ndarray, k: int, threshold: float,
                    debug: bool = False) -> np.ndarray:
    """
    Return a boolean mask (length N) — True where the LED is an outlier.

    An LED is an outlier when its mean-KNN-distance exceeds:
        median(distances) + threshold * MAD(distances)
    """
    dists = mean_knn_distances(pts, k)
    med = float(np.median(dists))
    m = mad(dists)
    cutoff = med + threshold * m

    if debug:
        print(f"  KNN distances — median: {med:.1f}  MAD: {m:.1f}  cutoff: {cutoff:.1f}")
        for i, d in enumerate(dists):
            flag = " ← OUTLIER" if d > cutoff else ""
            print(f"    LED index {i:4d}: mean-KNN-dist = {d:8.2f}{flag}")

    return dists > cutoff


# ---------------------------------------------------------------------------
# Interpolation / correction
# ---------------------------------------------------------------------------

def interpolate_outliers(leds: list[dict], outlier_mask: np.ndarray,
                         pts: np.ndarray, k: int) -> list[dict]:
    """
    Replace each outlier's coordinates with a distance-weighted average of
    its K nearest *non-outlier* neighbours.

    Returns a new list of LED dicts (originals are not mutated).
    """
    good_idx = np.where(~outlier_mask)[0]
    if len(good_idx) == 0:
        print("  [warn] No good LEDs to interpolate from — skipping correction.")
        return leds

    corrected = [dict(led) for led in leds]  # shallow copies

    for i in np.where(outlier_mask)[0]:
        good_pts = pts[good_idx]                         # (M, 3)
        diff = good_pts - pts[i]
        d = np.sqrt((diff ** 2).sum(axis=1))             # (M,)

        # Pick K nearest good neighbours
        kk = min(k, len(good_idx))
        nn_order = np.argsort(d)[:kk]
        nn_dists = d[nn_order]
        nn_idx = good_idx[nn_order]

        # Avoid division by zero if an outlier sits exactly on a good point
        if nn_dists[0] == 0:
            weights = np.zeros(kk)
            weights[0] = 1.0
        else:
            weights = 1.0 / np.maximum(nn_dists, 1e-9)
        weights /= weights.sum()

        interp = (pts[nn_idx] * weights[:, None]).sum(axis=0)
        corrected[i]["x"] = int(round(float(interp[0])))
        corrected[i]["y"] = int(round(float(interp[1])))
        corrected[i]["z"] = int(round(float(interp[2])))

    return corrected


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)

    # --- Load ---
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    leds: list[dict] = data.get("leds", [])
    if len(leds) < 4:
        print(f"Error: need at least 4 LEDs, found {len(leds)}.")
        sys.exit(1)

    print(f"Loaded {len(leds)} LEDs from {input_path}")
    print(f"Settings: k={args.k}  threshold={args.threshold}  max_passes={args.max_passes}\n")

    total_corrected: set[int] = set()

    for pass_num in range(1, args.max_passes + 1):
        pts = coords_array(leds)
        outlier_mask = detect_outliers(pts, k=args.k, threshold=args.threshold,
                                       debug=args.debug)
        outlier_indices = np.where(outlier_mask)[0]

        if len(outlier_indices) == 0:
            print(f"Pass {pass_num}: no outliers detected — done.")
            break

        led_ids = [leds[i].get("id", i) for i in outlier_indices]
        print(f"Pass {pass_num}: {len(outlier_indices)} outlier(s) detected — "
              f"IDs: {led_ids}")

        if args.dry_run:
            print("  (dry-run: no changes made)")
            break

        leds = interpolate_outliers(leds, outlier_mask, pts, k=args.k)
        total_corrected.update(int(i) for i in outlier_indices)
    else:
        pts = coords_array(leds)
        remaining = detect_outliers(pts, k=args.k, threshold=args.threshold)
        if remaining.any():
            rem_ids = [leds[i].get("id", i) for i in np.where(remaining)[0]]
            print(f"\n[warn] {remaining.sum()} LED(s) still flagged after "
                  f"{args.max_passes} passes: {rem_ids}")
            print("  Consider lowering --threshold or raising --max_passes.")

    print(f"\nTotal LEDs corrected: {len(total_corrected)}")

    if args.dry_run:
        print("Dry-run mode — no output written.")
        return

    # Preserve any extra top-level keys (e.g. metadata) from the original file
    output_data = {**data, "leds": leds}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Wrote corrected coordinates to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect and correct outlier LED coordinates via KNN interpolation."
    )
    parser.add_argument(
        "--input", required=True,
        help="Input JSON file (output of triangulate_leds.py)."
    )
    parser.add_argument(
        "--output", default="corrected.json",
        help="Output JSON file path (default: corrected.json)."
    )
    parser.add_argument(
        "--k", type=int, default=6,
        help="Number of nearest neighbours used for outlier detection and "
             "interpolation (default: 6)."
    )
    parser.add_argument(
        "--threshold", type=float, default=3.5,
        help="Outlier cutoff in MAD units above the median KNN distance "
             "(default: 3.5). Lower = stricter, higher = more lenient."
    )
    parser.add_argument(
        "--max_passes", type=int, default=5,
        help="Maximum correction iterations (default: 5). Each pass re-evaluates "
             "distances after correcting the previous round of outliers."
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Detect and report outliers without writing a corrected file."
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print per-LED KNN distance statistics."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args)