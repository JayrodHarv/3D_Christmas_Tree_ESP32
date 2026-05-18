#include "fx_plane.h"
#include <math.h>

// ── Config ────────────────────────────────────────────────────────────────────
#define PLANE_SPEED         0.4f    // units per second (coord space is -1 to 1)
#define PLANE_THICKNESS     0.15f   // how thick the lit band is
#define PLANE_FADE_SPEED    15      // how fast LEDs behind the plane fade out
#define PLANE_TRAIL         true    // if true, LEDs fade after plane passes
                                    // if false, they turn off instantly

// ── Axes the plane can sweep along ───────────────────────────────────────────
enum PlaneAxis { AXIS_X, AXIS_Y, AXIS_Z, AXIS_COUNT };

// ── A single sweeping plane ───────────────────────────────────────────────────
struct Plane {
    float    position;    // current position along axis (-1.0 to 1.0)
    float    target;      // destination (+1.0 or -1.0)
    float    direction;   // +1 or -1
    PlaneAxis axis;       // which axis it sweeps along
    CRGB     color;       // color of this plane
    bool     active;      // is this plane currently sweeping
};

static Plane   s_plane;
static bool    s_ready = false;
static uint32_t s_last_update = 0;

// ── Get the coordinate value for a given axis ─────────────────────────────────
static float get_axis(int led_index, PlaneAxis axis) {
    switch (axis) {
        case AXIS_X: return coords[led_index].x;
        case AXIS_Y: return coords[led_index].y;
        case AXIS_Z: return coords[led_index].z;
        default:     return 0.0f;
    }
}

// ── Spawn a new plane at a random end of a random axis ────────────────────────
static void spawn_plane() {
    s_plane.axis      = (PlaneAxis)random(AXIS_COUNT);
    s_plane.direction = random(2) ? 1.0f : -1.0f;
    s_plane.position  = -s_plane.direction;   // start at the opposite end
    s_plane.target    =  s_plane.direction;   // sweep to this end
    s_plane.color     = CHSV(random8(), 200 + random8(55), 255);
    s_plane.active    = true;

    const char* axis_name[] = {"X", "Y", "Z"};
    Serial.printf("fx_plane: spawning on axis %s direction %+.0f\n",
                  axis_name[s_plane.axis], s_plane.direction);
}

// ── Init ──────────────────────────────────────────────────────────────────────
void fx_plane_init() {
    if (!coords_loaded) { s_ready = false; return; }
    s_ready      = true;
    s_last_update = millis();
    FastLED.clear();
    spawn_plane();
}

// ── Run ───────────────────────────────────────────────────────────────────────
void fx_plane_run(float phase) {
    if (!s_ready) {
        // Fallback — no coordinates loaded
        fill_rainbow(leds, NUM_LEDS, (uint8_t)(phase * 255), 7);
        return;
    }

    // ── Delta time so speed is frame-rate independent ─────────────────────────
    uint32_t now     = millis();
    float    delta   = (now - s_last_update) / 1000.0f;
    s_last_update    = now;

    // ── Advance plane position ────────────────────────────────────────────────
    s_plane.position += s_plane.direction * PLANE_SPEED * delta;

    // ── Check if plane has reached the other end ──────────────────────────────
    bool finished = s_plane.direction > 0
                    ? s_plane.position >= s_plane.target
                    : s_plane.position <= s_plane.target;

    if (finished) {
        // Let the trail fully fade before spawning next plane
        bool all_dark = true;
        for (int i = 0; i < coord_count; i++) {
            if (leds[i].getLuma() > 10) { all_dark = false; break; }
        }
        if (all_dark) {
            FastLED.clear();
            spawn_plane();
        }
        // While waiting for fade, just fall through and keep fading
    }

    // ── Update LEDs ───────────────────────────────────────────────────────────
    if (PLANE_TRAIL) {
        // Fade all LEDs slightly each frame
        fadeToBlackBy(leds, NUM_LEDS, PLANE_FADE_SPEED);
    }

    for (int i = 0; i < coord_count; i++) {
        float val  = get_axis(i, s_plane.axis);
        float dist = fabsf(val - s_plane.position);

        if (dist < PLANE_THICKNESS) {
            // Inside the plane band — brightness based on distance from center
            float brightness = 1.0f - (dist / PLANE_THICKNESS);
            leds[i] = blend(CRGB::Black, s_plane.color,
                            (uint8_t)(brightness * 255));
        } else if (!PLANE_TRAIL) {
            // No trail — LEDs behind the plane turn off
            bool behind = s_plane.direction > 0
                          ? val < s_plane.position - PLANE_THICKNESS
                          : val > s_plane.position + PLANE_THICKNESS;
            if (behind) leds[i] = CRGB::Black;
        }
    }
}