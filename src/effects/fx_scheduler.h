#pragma once
#include "effects.h"
#include "../config.h"

void     scheduler_start();           // shuffle and begin playing
void     scheduler_stop();            // return to manual control
void     scheduler_tick();            // call every loop
bool     scheduler_is_running();
Effect   scheduler_current();
uint32_t scheduler_time_remaining();  // ms left on current effect