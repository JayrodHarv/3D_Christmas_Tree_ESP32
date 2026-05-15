#include "fx_rainbow.h"

void fx_rainbow_run(float phase) {
    fill_rainbow(leds, NUM_LEDS, (uint8_t)(phase * 255), 7);
}