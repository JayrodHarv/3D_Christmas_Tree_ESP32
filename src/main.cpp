#include <Arduino.h>
#include <LittleFS.h>
#include "config.h"
#include "leds/leds.h"
#include "effects/effects.h"
#include "effects/fx_scheduler.h"
#include "ir/ir.h"
#include "web/web.h"

void setup() {
    Serial.begin(115200);
    if (!LittleFS.begin(true)) { Serial.println("LittleFS failed"); return; }

    leds_init();
    effects_init();
    ir_init();
    web_init();

    coords_loaded = leds_load_coords();
}

void loop() {
    ir_tick();
    scheduler_tick();   // advances effect when 30s elapses
    effects_run();
    delay(1000 / ANIMATION_FPS);
}