#include "fx_scheduler.h"
#include <Arduino.h>

// ── Internal state ────────────────────────────────────────────────────────────
static bool     s_running    = false;
static int      s_queue[FX_OFF];   // FX_OFF is the last non-off effect index
static int      s_queue_len  = 0;
static int      s_queue_pos  = 0;
static uint32_t s_started_at = 0;

// ── Fisher-Yates shuffle ──────────────────────────────────────────────────────
static void shuffle(int *arr, int len) {
    for (int i = len - 1; i > 0; i--) {
        int j   = random(0, i + 1);
        int tmp = arr[i];
        arr[i]  = arr[j];
        arr[j]  = tmp;
    }
}

// ── Build a shuffled queue, ensuring first effect != last effect of prev queue─
static void build_queue(int avoid_first) {
    s_queue_len = 0;

    // Fill with all schedulable effects (everything before FX_OFF)
    for (int i = 0; i < (int)FX_OFF; i++) {
        s_queue[s_queue_len++] = i;
    }

    shuffle(s_queue, s_queue_len);

    // If the first item matches the one we want to avoid (end of last queue),
    // swap it with the second item to prevent back-to-back repeats
    if (s_queue_len > 1 && s_queue[0] == avoid_first) {
        int tmp      = s_queue[0];
        s_queue[0]   = s_queue[1];
        s_queue[1]   = tmp;
    }
}

// ── Public API ────────────────────────────────────────────────────────────────
void scheduler_start() {
    s_running  = true;
    s_queue_pos = 0;
    build_queue(-1);   // -1 = no effect to avoid at start
    effects_set((Effect)s_queue[0]);
    s_started_at = millis();
    Serial.printf("Scheduler started — %d effects, %ds each\n",
                  s_queue_len, SCHEDULE_DURATION_MS / 1000);
    Serial.printf("Queue: ");
    for (int i = 0; i < s_queue_len; i++) {
        Serial.printf("%s ", effects_name((Effect)s_queue[i]));
    }
    Serial.println();
}

void scheduler_stop() {
    s_running = false;
    Serial.println("Scheduler stopped");
}

bool scheduler_is_running() {
    return s_running;
}

Effect scheduler_current() {
    return (Effect)s_queue[s_queue_pos];
}

uint32_t scheduler_time_remaining() {
    if (!s_running) return 0;
    uint32_t elapsed = millis() - s_started_at;
    if (elapsed >= SCHEDULE_DURATION_MS) return 0;
    return SCHEDULE_DURATION_MS - elapsed;
}

void scheduler_tick() {
    if (!s_running) return;

    if (millis() - s_started_at < SCHEDULE_DURATION_MS) return;

    // Time's up — advance to next effect
    int last_effect = s_queue[s_queue_pos];
    s_queue_pos++;

    // End of queue — build a new shuffled one
    if (s_queue_pos >= s_queue_len) {
        s_queue_pos = 0;
        build_queue(last_effect);   // avoid repeating the last effect
        Serial.println("Scheduler: new queue built");
        Serial.printf("Queue: ");
        for (int i = 0; i < s_queue_len; i++) {
            Serial.printf("%s ", effects_name((Effect)s_queue[i]));
        }
        Serial.println();
    }

    effects_set((Effect)s_queue[s_queue_pos]);
    s_started_at = millis();

    Serial.printf("Scheduler: next effect -> %s (%ds remaining in cycle)\n",
                  effects_name((Effect)s_queue[s_queue_pos]),
                  ((s_queue_len - s_queue_pos) * SCHEDULE_DURATION_MS) / 1000);
}