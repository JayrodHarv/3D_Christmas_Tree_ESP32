#pragma once
#include <FastLED.h>
#include "config.h"

// ── Add new effects here — order determines IR cycling ────────────────────────
enum Effect {
    FX_SPIRAL,
    FX_RAINBOW,
    FX_SPECTRUM,      // new
    FX_TWINKLE,
    FX_WAVE,
    FX_SOLID,
    FX_OFF,
    FX_COUNT          // always last — used for cycling
};

// ── Shared state ──────────────────────────────────────────────────────────────
extern Effect  current_effect;
extern CRGB    solid_color;
extern uint8_t brightness;
extern float   phase;

// ── API ───────────────────────────────────────────────────────────────────────
void effects_init();
void effects_run();
void effects_set(Effect fx);
void effects_next();           // cycle to next effect
void effects_prev();           // cycle to previous effect
void effects_brightness_up();
void effects_brightness_down();
const char* effects_name(Effect fx);   // for serial debug