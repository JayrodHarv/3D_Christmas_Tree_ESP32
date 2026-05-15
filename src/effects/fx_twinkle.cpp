#include "fx_twinkle.h"

void fx_twinkle_run(float phase) {
    fadeToBlackBy(leds, NUM_LEDS, 20);
    leds[random16(NUM_LEDS)] = ColorFromPalette(RainbowColors_p, random8());
}