"""
tree_visualizer.py
------------
Interactive 3D viewer for LED coordinate JSON files produced by triangulate_leds.py.

Usage:
    python tree_visualizer.py coords.json

Controls:
    - Click + drag     : rotate
    - Scroll / right-drag : zoom
    - Middle-drag      : pan
    - Hover over point : shows LED id and coordinates in status bar
    - Colormap dropdown: change how LEDs are coloured
    - Point size slider: adjust dot size
    - Elevation/Azimuth sliders: set exact camera angle
    - Reset View button: return to default perspective
"""

import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, Slider
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

matplotlib.use("TkAgg")   # works on most desktops; fall back to Qt5Agg if needed


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_coords(path: str) -> tuple[list[int], np.ndarray]:
    with open(path) as f:
        data = json.load(f)
    leds = data["leds"]
    ids = [entry["id"] for entry in leds]
    coords = np.array([[entry["x"], entry["y"], entry["z"]] for entry in leds], dtype=float)
    return ids, coords


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

COLORMAPS = ["height (Y)", "warm glow", "id index", "depth (Z)", "cool blue"]

def get_colors(coords: np.ndarray, ids: list, mode: str) -> np.ndarray:
    n = len(coords)
    if mode == "height (Y)":
        values = coords[:, 1]
    elif mode == "id index":
        values = np.arange(n, dtype=float)
    elif mode == "depth (Z)":
        values = coords[:, 2]
    elif mode == "warm glow":
        values = coords[:, 1]  # height, but warm palette
    elif mode == "cool blue":
        values = coords[:, 1]
    else:
        values = coords[:, 1]

    # Normalise to [0,1]
    vmin, vmax = values.min(), values.max()
    if vmax == vmin:
        normed = np.zeros(n)
    else:
        normed = (values - vmin) / (vmax - vmin)

    cmap_lut = {
        "height (Y)":  plt.cm.plasma,
        "id index":    plt.cm.viridis,
        "depth (Z)":   plt.cm.coolwarm,
        "warm glow":   plt.cm.YlOrRd,
        "cool blue":   plt.cm.Blues,
    }
    cmap = cmap_lut.get(mode, plt.cm.plasma)
    return cmap(normed)


# ---------------------------------------------------------------------------
# Main viewer
# ---------------------------------------------------------------------------

DEFAULT_ELEV = 20
DEFAULT_AZIM = -60
DEFAULT_SIZE = 18


def launch_viewer(json_path: str) -> None:
    ids, coords = load_coords(json_path)
    n = len(coords)
    filename = Path(json_path).name

    # ── Figure layout ────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(13, 8), facecolor="#0d0d0d")
    fig.canvas.manager.set_window_title(f"LED Viewer — {filename}")

    # 3-D axes (left, bottom, width, height)
    ax3d = fig.add_axes([0.0, 0.08, 0.72, 0.88], projection="3d")
    ax3d.set_facecolor("#0d0d0d")
    ax3d.set_proj_type("persp")

    # ── Styling ──────────────────────────────────────────────────────────────
    for pane in (ax3d.xaxis.pane, ax3d.yaxis.pane, ax3d.zaxis.pane):
        pane.fill = False
        pane.set_edgecolor("#2a2a2a")

    for axis in (ax3d.xaxis, ax3d.yaxis, ax3d.zaxis):
        axis.label.set_color("#888888")
        axis._axinfo["tick"]["color"] = "#444444"
        axis._axinfo["grid"]["color"] = "#1e1e1e"
        axis._axinfo["grid"]["linewidth"] = 0.5

    ax3d.tick_params(colors="#555555", labelsize=7)
    ax3d.set_xlabel("X (mm)", color="#666666", labelpad=8)
    ax3d.set_ylabel("Y (mm)", color="#666666", labelpad=8)
    ax3d.set_zlabel("Z (mm)", color="#666666", labelpad=8)

    title = ax3d.set_title(
        f"{filename}  ·  {n} LEDs",
        color="#cccccc", fontsize=11, pad=12, fontfamily="monospace"
    )

    # ── Initial scatter ──────────────────────────────────────────────────────
    state = {"cmap": COLORMAPS[0], "size": DEFAULT_SIZE}
    colors = get_colors(coords, ids, state["cmap"])

    sc = ax3d.scatter(
        coords[:, 0], coords[:, 1], coords[:, 2],
        c=colors, s=state["size"], depthshade=True, alpha=0.88,
        linewidths=0,
    )

    ax3d.view_init(elev=DEFAULT_ELEV, azim=DEFAULT_AZIM)

    # ── Right-side panel widgets ──────────────────────────────────────────────
    panel_x = 0.74
    widget_bg = "#181818"
    label_kw = dict(color="#aaaaaa", fontsize=8, fontfamily="monospace")

    # Section: Colour map
    fig.text(panel_x, 0.90, "COLOUR MAP", **label_kw)
    cmap_buttons: list[Button] = []
    cmap_axes: list[plt.Axes] = []
    for i, name in enumerate(COLORMAPS):
        bax = fig.add_axes([panel_x, 0.80 - i * 0.062, 0.24, 0.050])
        btn = Button(bax, name, color="#222222", hovercolor="#333333")
        btn.label.set_fontsize(8)
        btn.label.set_fontfamily("monospace")
        btn.label.set_color("#dddddd")
        cmap_buttons.append(btn)
        cmap_axes.append(bax)

    # Section: Point size
    fig.text(panel_x, 0.475, "POINT SIZE", **label_kw)
    ax_size = fig.add_axes([panel_x, 0.435, 0.24, 0.028], facecolor=widget_bg)
    sl_size = Slider(ax_size, "", 2, 80, valinit=DEFAULT_SIZE, color="#444466",
                     track_color="#222222")
    sl_size.valtext.set_color("#aaaaaa")
    sl_size.valtext.set_fontsize(8)
    sl_size.label.set_color("#aaaaaa")

    # Section: Elevation
    fig.text(panel_x, 0.395, "ELEVATION", **label_kw)
    ax_elev = fig.add_axes([panel_x, 0.355, 0.24, 0.028], facecolor=widget_bg)
    sl_elev = Slider(ax_elev, "", -90, 90, valinit=DEFAULT_ELEV, color="#446644",
                     track_color="#222222")
    sl_elev.valtext.set_color("#aaaaaa")
    sl_elev.valtext.set_fontsize(8)
    sl_elev.label.set_color("#aaaaaa")

    # Section: Azimuth
    fig.text(panel_x, 0.315, "AZIMUTH", **label_kw)
    ax_azim = fig.add_axes([panel_x, 0.275, 0.24, 0.028], facecolor=widget_bg)
    sl_azim = Slider(ax_azim, "", -180, 180, valinit=DEFAULT_AZIM, color="#664444",
                     track_color="#222222")
    sl_azim.valtext.set_color("#aaaaaa")
    sl_azim.valtext.set_fontsize(8)
    sl_azim.label.set_color("#aaaaaa")

    # Reset button
    ax_reset = fig.add_axes([panel_x, 0.195, 0.24, 0.055])
    btn_reset = Button(ax_reset, "⟳  Reset View", color="#1e2a1e", hovercolor="#2a3d2a")
    btn_reset.label.set_color("#88cc88")
    btn_reset.label.set_fontsize(9)
    btn_reset.label.set_fontfamily("monospace")

    # Stats panel
    fig.text(panel_x, 0.155, "STATS", **label_kw)
    x_range = coords[:, 0].max() - coords[:, 0].min()
    y_range = coords[:, 1].max() - coords[:, 1].min()
    z_range = coords[:, 2].max() - coords[:, 2].min()
    stats_lines = [
        f"  LEDs : {n}",
        f"  X    : {coords[:,0].min():.0f} → {coords[:,0].max():.0f} mm",
        f"  Y    : {coords[:,1].min():.0f} → {coords[:,1].max():.0f} mm",
        f"  Z    : {coords[:,2].min():.0f} → {coords[:,2].max():.0f} mm",
        f"  span : {x_range:.0f} × {y_range:.0f} × {z_range:.0f}",
    ]
    for i, line in enumerate(stats_lines):
        fig.text(panel_x, 0.118 - i * 0.026, line,
                 color="#666666", fontsize=7, fontfamily="monospace")

    # Status bar at bottom
    status = fig.text(0.01, 0.01, "Hover over a point to inspect it",
                      color="#555555", fontsize=8, fontfamily="monospace",
                      transform=fig.transFigure)

    # ── Callbacks ────────────────────────────────────────────────────────────

    def redraw_scatter():
        nonlocal sc
        sc.remove()
        colors = get_colors(coords, ids, state["cmap"])
        sc = ax3d.scatter(
            coords[:, 0], coords[:, 1], coords[:, 2],
            c=colors, s=state["size"], depthshade=True, alpha=0.88,
            linewidths=0,
        )
        fig.canvas.draw_idle()

    def make_cmap_callback(name):
        def cb(event):
            state["cmap"] = name
            # Highlight active button
            for i, n2 in enumerate(COLORMAPS):
                cmap_axes[i].set_facecolor("#333355" if n2 == name else "#222222")
            redraw_scatter()
        return cb

    for btn, name in zip(cmap_buttons, COLORMAPS):
        btn.on_clicked(make_cmap_callback(name))

    def on_size(val):
        state["size"] = val
        sc._sizes = np.full(n, val)
        fig.canvas.draw_idle()

    def on_elev(val):
        ax3d.view_init(elev=val, azim=sl_azim.val)
        fig.canvas.draw_idle()

    def on_azim(val):
        ax3d.view_init(elev=sl_elev.val, azim=val)
        fig.canvas.draw_idle()

    def on_reset(event):
        ax3d.view_init(elev=DEFAULT_ELEV, azim=DEFAULT_AZIM)
        sl_elev.set_val(DEFAULT_ELEV)
        sl_azim.set_val(DEFAULT_AZIM)
        sl_size.set_val(DEFAULT_SIZE)
        fig.canvas.draw_idle()

    sl_size.on_changed(on_size)
    sl_elev.on_changed(on_elev)
    sl_azim.on_changed(on_azim)
    btn_reset.on_clicked(on_reset)

    # ── Hover tooltip ────────────────────────────────────────────────────────
    annot = ax3d.text2D(0, 0, "", transform=ax3d.transAxes,
                         color="#ffdd88", fontsize=8, fontfamily="monospace",
                         bbox=dict(boxstyle="round,pad=0.3", fc="#222222",
                                   ec="#555555", alpha=0.85))
    annot.set_visible(False)

    def on_mouse_move(event):
        if event.inaxes != ax3d:
            annot.set_visible(False)
            status.set_text("Hover over a point to inspect it")
            fig.canvas.draw_idle()
            return

        # Project all 3-D points to display coords and find nearest
        xs, ys, _ = proj3d_transform(coords, ax3d)
        if xs is None:
            return

        dist2 = (xs - event.x) ** 2 + (ys - event.y) ** 2
        idx = int(np.argmin(dist2))
        if dist2[idx] > 600:   # pixels²; ~25 px radius
            annot.set_visible(False)
            status.set_text("")
            fig.canvas.draw_idle()
            return

        led_id = ids[idx]
        x, y, z = coords[idx]
        tip = f" id:{led_id}  x:{x:.0f}  y:{y:.0f}  z:{z:.0f} "
        annot.set_text(tip)
        # Place annotation near cursor in axes-fraction coords
        ax_frac_x = (event.x - ax3d.get_position().x0 * fig.get_figwidth() * fig.dpi) / \
                    (ax3d.get_position().width * fig.get_figwidth() * fig.dpi)
        ax_frac_y = (event.y - ax3d.get_position().y0 * fig.get_figheight() * fig.dpi) / \
                    (ax3d.get_position().height * fig.get_figheight() * fig.dpi)
        ax_frac_x = min(max(ax_frac_x + 0.02, 0.01), 0.75)
        ax_frac_y = min(max(ax_frac_y + 0.02, 0.01), 0.92)
        annot.set_position((ax_frac_x, ax_frac_y))
        annot.set_visible(True)
        status.set_text(f"  LED {led_id}  →  x={x:.0f} mm   y={y:.0f} mm   z={z:.0f} mm")
        fig.canvas.draw_idle()

    def proj3d_transform(pts, ax):
        """Project world coords to display (pixel) coords."""
        try:
            from mpl_toolkits.mplot3d import proj3d
            xs2d, ys2d, _ = proj3d.proj_transform(
                pts[:, 0], pts[:, 1], pts[:, 2], ax.get_proj()
            )
            # Convert from axes coords to display pixels
            disp = ax.transData.transform(np.column_stack([xs2d, ys2d]))
            return disp[:, 0], disp[:, 1], None
        except Exception:
            return None, None, None

    fig.canvas.mpl_connect("motion_notify_event", on_mouse_move)

    # ── Highlight initial cmap button ────────────────────────────────────────
    cmap_axes[0].set_facecolor("#333355")

    plt.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tree_visualizer.py <coords.json>")
        sys.exit(1)
    launch_viewer(sys.argv[1])