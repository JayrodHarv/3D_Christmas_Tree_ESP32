#pragma once

// ── Pins ──────────────────────────────────────────────────────────────────────
#define LED_PIN             13
#define IR_RX_PIN           15

// ── LED ───────────────────────────────────────────────────────────────────────
#define NUM_LEDS            550
#define DEFAULT_BRIGHTNESS  40
#define BRIGHTNESS_STEP     20
#define BRIGHTNESS_MIN      10
#define BRIGHTNESS_MAX      255

// ── Wi-Fi AP ──────────────────────────────────────────────────────────────────
#define AP_SSID             "ChristmasTree"
#define AP_PASS             "12345678"

// ── Filesystem ────────────────────────────────────────────────────────────────
#define COORDS_PATH         "/coords.json"

// ── Animation ─────────────────────────────────────────────────────────────────
#define ANIMATION_FPS       60
#define PHASE_STEP          0.005f

// ── Scheduler ─────────────────────────────────────────────────────────────────
#define SCHEDULE_DURATION_MS  30000

// ── Wave effect ───────────────────────────────────────────────────────────────
#define WAVE_SPEED            40
#define WAVE_COLORS_COUNT     6

// ── Scan ──────────────────────────────────────────────────────────────────────
#define SCAN_AUTO_MS          500
#define SCAN_LED_COLOR        CRGB::White

// ── Plane effect ──────────────────────────────────────────────────────────────
#define PLANE_SPEED       0.4f   // increase for faster sweep
#define PLANE_THICKNESS   0.15f  // increase for wider band
#define PLANE_FADE_SPEED  15     // 1=slow fade, 40=fast fade, 0=no fade
#define PLANE_TRAIL       true   // false = LEDs snap off behind the plane