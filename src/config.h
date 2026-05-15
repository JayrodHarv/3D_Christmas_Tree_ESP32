#pragma once

// ── Pins ──────────────────────────────────────────────────────────────────────
#define LED_PIN         13
#define IR_RX_PIN       15
#define NUM_LEDS        50

// ── LED config ────────────────────────────────────────────────────────────────
#define DEFAULT_BRIGHTNESS  40
#define BRIGHTNESS_STEP     20
#define BRIGHTNESS_MIN      10
#define BRIGHTNESS_MAX      255

// ── Wi-Fi AP config ───────────────────────────────────────────────────────────
#define AP_SSID         "ChristmasTree"
#define AP_PASS         "12345678"

// ── Filesystem ────────────────────────────────────────────────────────────────
#define COORDS_PATH     "/coords.json"

// ── Animation ─────────────────────────────────────────────────────────────────
#define ANIMATION_FPS   60
#define PHASE_STEP      0.005f