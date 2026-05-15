#pragma once
#include <Arduino.h>
#include "../config.h"

enum ScanState {
    SCAN_IDLE,
    SCAN_RUNNING,
    SCAN_PAUSED
};

void     scan_init();
void     scan_tick();             // call every loop

void     scan_start();
void     scan_stop();
void     scan_pause();
void     scan_resume();
void     scan_next();             // advance to next LED manually
void     scan_prev();             // go back one LED
void     scan_goto(int index);    // jump to specific LED

int      scan_current();          // current LED index
ScanState scan_state();
bool     scan_is_running();
int      scan_total();