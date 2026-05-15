#pragma once
#include <FastLED.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "config.h"

// ── LED coordinate ────────────────────────────────────────────────────────────
struct LedCoord {
    float x, y, z;
};

// ── Globals shared across modules ─────────────────────────────────────────────
extern CRGB      leds[NUM_LEDS];
extern LedCoord  coords[NUM_LEDS];
extern int       coord_count;
extern bool      coords_loaded;

// ── API ───────────────────────────────────────────────────────────────────────
void leds_init();
bool leds_load_coords();