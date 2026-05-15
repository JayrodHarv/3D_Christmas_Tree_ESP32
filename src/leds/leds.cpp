#include "leds.h"

// ── Definitions ───────────────────────────────────────────────────────────────
CRGB     leds[NUM_LEDS];
LedCoord coords[NUM_LEDS];
int      coord_count  = 0;
bool     coords_loaded = false;

void leds_init() {
    FastLED.addLeds<WS2811, LED_PIN, RGB>(leds, NUM_LEDS);
    FastLED.setBrightness(DEFAULT_BRIGHTNESS);
    FastLED.clear(true);
}

bool leds_load_coords() {
    if (!LittleFS.exists(COORDS_PATH)) {
        Serial.println("No coords.json found — upload via web page");
        return false;
    }

    File f = LittleFS.open(COORDS_PATH, "r");
    if (!f) return false;

    JsonDocument doc;
    if (deserializeJson(doc, f)) { f.close(); return false; }
    f.close();

    JsonArray arr = doc["leds"];
    coord_count = min((int)arr.size(), NUM_LEDS);
    for (int i = 0; i < coord_count; i++) {
        coords[i].x = arr[i]["x"] | 0.0f;
        coords[i].y = arr[i]["y"] | 0.0f;
        coords[i].z = arr[i]["z"] | 0.0f;
    }

    Serial.printf("Loaded %d LED coordinates\n", coord_count);
    return true;
}