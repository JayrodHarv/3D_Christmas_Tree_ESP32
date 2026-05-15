#include "fx_wave.h"

static const CRGB WAVE_COLORS[] = {
    CRGB::Red,
    CRGB::Orange,
    CRGB::Yellow,
    CRGB::Green,
    CRGB::Blue,
    CRGB::Purple,
};

void fx_wave_run(float phase) {
    // How far the wave front has advanced along the strand (in LED indices)
    float time_s   = millis() / 1000.0f;
    float wave_pos = fmodf(time_s * WAVE_SPEED, NUM_LEDS);

    // Band size — how many LEDs each color occupies
    float band_size = (float)NUM_LEDS / WAVE_COLORS_COUNT;

    for (int i = 0; i < NUM_LEDS; i++) {
        // How far behind the wave front is this LED, wrapping around
        float behind = fmodf((float)i - wave_pos + NUM_LEDS, NUM_LEDS);

        // Which color band does that put us in
        int color_idx = (int)(behind / band_size) % WAVE_COLORS_COUNT;

        leds[i] = WAVE_COLORS[color_idx];
    }
}