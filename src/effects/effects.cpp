#include "effects.h"
#include "fx_spiral.h"
#include "fx_rainbow.h"
#include "fx_spectrum.h"
#include "fx_twinkle.h"
#include "fx_wave.h"
#include "../leds/leds.h"

// ── State ─────────────────────────────────────────────────────────────────────
Effect  current_effect = FX_SPIRAL;
CRGB    solid_color    = CRGB::White;
uint8_t brightness     = DEFAULT_BRIGHTNESS;
float   phase          = 0.0f;

// ── Effect name table — keep in sync with enum order ─────────────────────────
static const char* EFFECT_NAMES[] = {
    "Spiral",
    "Rainbow",
    "Spectrum",
    "Twinkle",
    "Wave",
    "Solid",
    "Off"
};

// ── Public API ────────────────────────────────────────────────────────────────
void effects_init() {
    brightness = DEFAULT_BRIGHTNESS;
    FastLED.setBrightness(brightness);
}

void effects_set(Effect fx) {
    FastLED.clear();
    FastLED.show();
    current_effect = fx;
    Serial.printf("Effect: %s\n", effects_name(fx));
}

void effects_next() {
    // Cycle through all effects except FX_OFF and FX_COUNT
    int next = ((int)current_effect + 1) % ((int)FX_OFF);
    effects_set((Effect)next);
}

void effects_prev() {
    int prev = ((int)current_effect - 1 + (int)FX_OFF) % (int)FX_OFF;
    effects_set((Effect)prev);
}

void effects_brightness_up() {
    brightness = min(BRIGHTNESS_MAX, brightness + BRIGHTNESS_STEP);
    FastLED.setBrightness(brightness);
    Serial.printf("Brightness: %d\n", brightness);
}

void effects_brightness_down() {
    brightness = max(BRIGHTNESS_MIN, brightness - BRIGHTNESS_STEP);
    FastLED.setBrightness(brightness);
    Serial.printf("Brightness: %d\n", brightness);
}

const char* effects_name(Effect fx) {
    if (fx >= FX_COUNT) return "Unknown";
    return EFFECT_NAMES[(int)fx];
}

void effects_run() {
    switch (current_effect) {
        case FX_SPIRAL:   fx_spiral_run(phase);   break;
        case FX_RAINBOW:  fx_rainbow_run(phase);  break;
        case FX_SPECTRUM: fx_spectrum_run(phase);  break;
        case FX_TWINKLE:  fx_twinkle_run(phase);  break;
        case FX_WAVE:     fx_wave_run(phase);      break;
        case FX_SOLID:    fill_solid(leds, NUM_LEDS, solid_color); break;
        case FX_OFF:      FastLED.clear();         break;
        default: break;
    }

    phase += PHASE_STEP;
    if (phase > 1.0f) phase -= 1.0f;

    FastLED.show();
}