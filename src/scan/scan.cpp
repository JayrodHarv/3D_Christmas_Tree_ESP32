#include "scan.h"
#include "../leds/leds.h"
#include <FastLED.h>

// ── State ─────────────────────────────────────────────────────────────────────
static ScanState s_state      = SCAN_IDLE;
static int       s_current    = 0;
static uint32_t  s_last_step  = 0;

// ── Internal ──────────────────────────────────────────────────────────────────
static void light_current() {
    FastLED.clear();
    if (s_current >= 0 && s_current < NUM_LEDS) {
        leds[s_current] = SCAN_LED_COLOR;
    }
    FastLED.show();
    Serial.printf("Scan: LED %d / %d\n", s_current, NUM_LEDS - 1);
}

// ── Public API ────────────────────────────────────────────────────────────────
void scan_init() {
    s_state   = SCAN_IDLE;
    s_current = 0;
}

void scan_start() {
    s_state   = SCAN_RUNNING;
    s_current = 0;
    s_last_step = millis();
    light_current();
    Serial.printf("Scan started: %d LEDs\n", NUM_LEDS);
}

void scan_stop() {
    s_state = SCAN_IDLE;
    FastLED.clear();
    FastLED.show();
    Serial.println("Scan stopped");
}

void scan_pause() {
    if (s_state == SCAN_RUNNING) s_state = SCAN_PAUSED;
}

void scan_resume() {
    if (s_state == SCAN_PAUSED) {
        s_state = SCAN_RUNNING;
        s_last_step = millis();
    }
}

void scan_next() {
    s_current = (s_current + 1) % NUM_LEDS;
    s_last_step = millis();
    light_current();
}

void scan_prev() {
    s_current = (s_current - 1 + NUM_LEDS) % NUM_LEDS;
    s_last_step = millis();
    light_current();
}

void scan_goto(int index) {
    if (index < 0 || index >= NUM_LEDS) return;
    s_current = index;
    s_last_step = millis();
    light_current();
}

int scan_current()    { return s_current; }
ScanState scan_state() { return s_state; }
bool scan_is_running() { return s_state != SCAN_IDLE; }
int scan_total()       { return NUM_LEDS; }

void scan_tick() {
    if (s_state != SCAN_RUNNING) return;
    if (SCAN_AUTO_MS == 0) return;   // manual only mode

    if (millis() - s_last_step >= SCAN_AUTO_MS) {
        if (s_current >= NUM_LEDS - 1) {
            scan_stop();             // finished all LEDs
            Serial.println("Scan complete!");
            return;
        }
        scan_next();
    }
}