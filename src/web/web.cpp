#include "web.h"
#include "../leds/leds.h"
#include "../effects/effects.h"

static AsyncWebServer server(80);

static void setup_routes() {
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *req) {
        req->send(LittleFS, "/index.html", "text/html");
    });

    server.on("/upload", HTTP_POST,
        [](AsyncWebServerRequest *req) {
            req->send(200, "text/plain", "Coordinates saved! Reloading...");
        },
        [](AsyncWebServerRequest *req, String filename,
           size_t index, uint8_t *data, size_t len, bool final) {
            static File upload_file;
            if (index == 0)   upload_file = LittleFS.open(COORDS_PATH, "w");
            if (upload_file)  upload_file.write(data, len);
            if (final) {
                upload_file.close();
                coords_loaded = leds_load_coords();
            }
        }
    );

    server.on("/status", HTTP_GET, [](AsyncWebServerRequest *req) {
        JsonDocument doc;
        doc["coords_loaded"]  = coords_loaded;
        doc["coord_count"]    = coord_count;
        doc["current_effect"] = (int)current_effect;
        doc["brightness"]     = brightness;
        doc["ip"]             = WiFi.softAPIP().toString();
        String out;
        serializeJson(doc, out);
        req->send(200, "application/json", out);
    });

    server.begin();
}

void web_init() {
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("AP started — connect to '%s' (password: %s)\n", AP_SSID, AP_PASS);
    Serial.printf("Then open http://%s\n", WiFi.softAPIP().toString().c_str());
    setup_routes();
}