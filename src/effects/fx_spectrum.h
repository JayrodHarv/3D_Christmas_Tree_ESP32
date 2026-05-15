#pragma once
#include <FastLED.h>
#include "../leds/leds.h"
#include "../config.h"

// Slowly cycles all LEDs through the full RGB spectrum together.
// All LEDs show the same color, smoothly transitioning HSV hue 0->255->0.
// Speed is controlled by SPECTRUM_SPEED in config.h

void fx_spectrum_run(float phase);