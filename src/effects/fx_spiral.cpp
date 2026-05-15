#include "fx_spiral.h"

void fx_spiral_run(float phase) {
    if (!coords_loaded) {
        fill_rainbow(leds, NUM_LEDS, (uint8_t)(phase * 255), 7);
        return;
    }
    for (int i = 0; i < coord_count; i++) {
        float angle      = atan2f(coords[i].x, coords[i].y);
        float norm_angle = (angle / (2 * PI)) + 0.5f;
        float norm_z     = (coords[i].z + 1.0f) / 2.0f;
        uint8_t hue      = (uint8_t)((norm_angle + phase) * 255) % 255;
        uint8_t val      = (uint8_t)(128 + norm_z * 127);
        leds[i]          = CHSV(hue, 255, val);
    }
}