#include "web.h"
#include "../leds/leds.h"
#include "../effects/effects.h"
#include "../effects/fx_scheduler.h"
#include "../scan/scan.h"

static AsyncWebServer server(80);

static void setup_routes() {

    // ── Static files ──────────────────────────────────────────────────────────
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *req) {
        req->send(LittleFS, "/index.html", "text/html");
    });
    server.on("/style.css", HTTP_GET, [](AsyncWebServerRequest *req) {
        req->send(LittleFS, "/style.css", "text/css");
    });
    server.on("/app.js", HTTP_GET, [](AsyncWebServerRequest *req) {
        req->send(LittleFS, "/app.js", "application/javascript");
    });

    // ── Status ────────────────────────────────────────────────────────────────
    server.on("/status", HTTP_GET, [](AsyncWebServerRequest *req) {
        JsonDocument doc;
        doc["num_leds"]           = NUM_LEDS;
        doc["current_effect"]     = (int)current_effect;
        doc["brightness"]         = brightness;
        doc["scheduler_running"]  = scheduler_is_running();
        doc["time_remaining_ms"]  = scheduler_time_remaining();
        doc["coords_loaded"]      = coords_loaded;
        doc["coord_count"]        = coord_count;
        String out;
        serializeJson(doc, out);
        req->send(200, "application/json", out);
    });

    // ── Commands ──────────────────────────────────────────────────────────────
    server.on("/cmd", HTTP_GET, [](AsyncWebServerRequest *req) {
        if (!req->hasParam("action")) {
            req->send(400, "text/plain", "missing action");
            return;
        }

        String action = req->getParam("action")->value();

        if (action == "power") {
            effects_set(current_effect == FX_OFF ? FX_SPIRAL : FX_OFF);

        } else if (action == "next") {
            scheduler_stop();
            effects_next();

        } else if (action == "prev") {
            scheduler_stop();
            effects_prev();

        } else if (action == "scheduler") {
            if (scheduler_is_running()) scheduler_stop();
            else                        scheduler_start();

        } else if (action == "solid") {
            scheduler_stop();
            solid_color = CHSV(random8(), 255, 255);
            effects_set(FX_SOLID);

        } else if (action == "effect" && req->hasParam("id")) {
            int id = req->getParam("id")->value().toInt();
            if (id >= 0 && id < (int)FX_OFF) {
                scheduler_stop();
                effects_set((Effect)id);
            }

        } else if (action == "brightness" && req->hasParam("value")) {
            int val = req->getParam("value")->value().toInt();
            val = max(10, min(255, val));
            brightness = val;
            FastLED.setBrightness(brightness);

        } else {
            req->send(400, "text/plain", "unknown action");
            return;
        }

        req->send(200, "text/plain", "ok");
    });

    // ── Scan status ───────────────────────────────────────────────────────────────
    server.on("/scan/status", HTTP_GET, [](AsyncWebServerRequest *req) {
        JsonDocument doc;
        doc["state"]   = (int)scan_state();
        doc["current"] = scan_current();
        doc["total"]   = scan_total();
        String out;
        serializeJson(doc, out);
        req->send(200, "application/json", out);
    });

    // ── Scan commands ─────────────────────────────────────────────────────────────
    server.on("/scan/cmd", HTTP_GET, [](AsyncWebServerRequest *req) {
        if (!req->hasParam("action")) { req->send(400); return; }
        String action = req->getParam("action")->value();

        if      (action == "start")  scan_start();
        else if (action == "stop")   scan_stop();
        else if (action == "pause")  scan_pause();
        else if (action == "resume") scan_resume();
        else if (action == "next")   scan_next();
        else if (action == "prev")   scan_prev();
        else if (action == "goto" && req->hasParam("index")) {
            scan_goto(req->getParam("index")->value().toInt());
        }

        req->send(200, "text/plain", "ok");
    });

    // ── Coordinate upload ─────────────────────────────────────────────────────
    server.on("/upload", HTTP_POST,
        [](AsyncWebServerRequest *req) {
            req->send(200, "text/plain", "Coordinates saved!");
        },
        [](AsyncWebServerRequest *req, String filename,
           size_t index, uint8_t *data, size_t len, bool final) {
            static File upload_file;
            if (index == 0)  upload_file = LittleFS.open(COORDS_PATH, "w");
            if (upload_file) upload_file.write(data, len);
            if (final) {
                upload_file.close();
                coords_loaded = leds_load_coords();
            }
        }
    );

    server.begin();
}

void web_init() {
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("AP started — connect to '%s' (password: %s)\n", AP_SSID, AP_PASS);
    Serial.printf("Open http://%s\n", WiFi.softAPIP().toString().c_str());
    setup_routes();
}