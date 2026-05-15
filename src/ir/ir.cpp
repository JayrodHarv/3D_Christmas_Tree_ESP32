#include <IRremote.hpp>
#include "ir.h"
#include "../effects/effects.h"
#include "../effects/fx_scheduler.h"

static void handle_command(uint8_t command) {
    // If scheduler is running, stop it on any effect/color button press
    // so manual control immediately takes over
    bool manual_trigger = false;

    switch (command) {
        // ── Scheduler ─────────────────────────────────────────────────────────
        case 0x0D:                                                          // #
            if (scheduler_is_running()) {
                scheduler_stop();
            } else {
                scheduler_start();
            }
            return;   // don't fall through to manual handling
        
        case 0x16:                                                          // STAR
            scheduler_stop();
            effects_set(current_effect == FX_OFF ? FX_SPIRAL : FX_OFF);
            break;
        
        case 0x18: effects_brightness_up();   break; // UP
        case 0x52: effects_brightness_down(); break; // DOWN

        case 0x08: manual_trigger = true; effects_prev(); break;  // LEFT
        case 0x1C: manual_trigger = true; break;  // OK
        case 0x5A: manual_trigger = true; effects_next(); break;  // RIGHT

        case 0x45:  // 1
            manual_trigger = true;
            solid_color = CHSV(random8(), 255, 255);
            effects_set(FX_SOLID);
            break;
        case 0x46: manual_trigger = true; effects_set(FX_SPIRAL);  break; // 2
        case 0x47: manual_trigger = true; effects_set(FX_RAINBOW); break; // 3
        case 0x44: manual_trigger = true; effects_set(FX_TWINKLE); break; // 4
        case 0x40: manual_trigger = true; effects_set(FX_WAVE);    break; // 5
        case 0x43: manual_trigger = true; solid_color = CRGB::Purple;   effects_set(FX_SOLID); break; // 6
        case 0x07: manual_trigger = true; solid_color = CRGB(255,100,0); effects_set(FX_SOLID); break; // 7
        case 0x15: manual_trigger = true; solid_color = CRGB(220,20,60); effects_set(FX_SOLID); break; // 8
        case 0x09: manual_trigger = true; solid_color = CRGB::Cyan;     effects_set(FX_SOLID); break; // 9
        default:
            Serial.printf("IR: Unknown 0x%02X\n", command);
    }

    // Any manual effect/color button stops the scheduler
    if (manual_trigger) scheduler_stop();
}

void ir_init() {
    IrReceiver.begin(IR_RX_PIN, ENABLE_LED_FEEDBACK);
    Serial.println("IR receiver ready");
}

void ir_tick() {
    if (!IrReceiver.decode()) return;
    if (!(IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT)) {
        Serial.printf("IR: 0x%02X\n", IrReceiver.decodedIRData.command);
        handle_command(IrReceiver.decodedIRData.command);
    }
    IrReceiver.resume();
}