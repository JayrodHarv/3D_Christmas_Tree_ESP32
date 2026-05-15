#include "fx_spectrum.h"

void fx_spectrum_run(float phase) {
    // phase 0.0 -> 1.0 maps to hue 0 -> 255
    uint8_t hue = (uint8_t)(phase * 255);

    // Full saturation and brightness — pure spectrum colors
    CRGB color = CHSV(hue, 255, 255);

    fill_solid(leds, NUM_LEDS, color);
}