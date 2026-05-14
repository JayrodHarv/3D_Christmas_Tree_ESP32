#include <Arduino.h>
#include <FastLED.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <IRremote.hpp>

// ── Config ────────────────────────────────────────────────────────────────────
#define LED_PIN      13
#define IR_RX_PIN    15
#define NUM_LEDS     50
#define COORDS_PATH  "/coords.json"

// ── LED + coordinate state ────────────────────────────────────────────────────
CRGB leds[NUM_LEDS];

struct LedCoord { float x, y, z; };
LedCoord coords[NUM_LEDS];
int  coord_count  = 0;
bool coords_loaded = false;

// ── Animation state ───────────────────────────────────────────────────────────
enum Effect { FX_SPIRAL, FX_RAINBOW, FX_SOLID, FX_TWINKLE, FX_OFF };
Effect  current_effect = FX_SPIRAL;
CRGB    solid_color    = CRGB::White;
uint8_t brightness     = 40;
float   phase          = 0.0f;

AsyncWebServer server(80);

// ── Coordinate loader ─────────────────────────────────────────────────────────
bool load_coords() {
    if (!LittleFS.exists(COORDS_PATH)) {
        Serial.println("No coords.json — upload via web page");
        return false;
    }
    File f = LittleFS.open(COORDS_PATH, "r");
    if (!f) return false;

    JsonDocument doc;
    if (deserializeJson(doc, f)) { f.close(); return false; }
    f.close();

    JsonArray arr = doc["leds"];
    coord_count = min((int)arr.size(), NUM_LEDS);
    for (int i = 0; i < coord_count; i++) {
        coords[i].x = arr[i]["x"] | 0.0f;
        coords[i].y = arr[i]["y"] | 0.0f;
        coords[i].z = arr[i]["z"] | 0.0f;
    }
    Serial.printf("Loaded %d coordinates\n", coord_count);
    return true;
}

// ── Effects ───────────────────────────────────────────────────────────────────
void fx_spiral() {
    if (!coords_loaded) { fill_rainbow(leds, NUM_LEDS, (uint8_t)(phase * 255), 7); return; }
    for (int i = 0; i < coord_count; i++) {
        float angle    = atan2f(coords[i].x, coords[i].y);
        float norm_angle = (angle / (2 * PI)) + 0.5f;
        float norm_z   = (coords[i].z + 1.0f) / 2.0f;
        uint8_t hue    = (uint8_t)((norm_angle + phase) * 255) % 255;
        uint8_t val    = (uint8_t)(128 + norm_z * 127);
        leds[i]        = CHSV(hue, 255, val);
    }
}

void fx_rainbow() {
    fill_rainbow(leds, NUM_LEDS, (uint8_t)(phase * 255), 7);
}

void fx_solid() {
    fill_solid(leds, NUM_LEDS, solid_color);
}

void fx_twinkle() {
    // Randomly sparkle LEDs — fade everything slowly then pop random ones
    fadeToBlackBy(leds, NUM_LEDS, 20);
    int pos = random16(NUM_LEDS);
    leds[pos] = ColorFromPalette(RainbowColors_p, random8());
}

// ── IR handler ────────────────────────────────────────────────────────────────
void handle_ir(uint8_t command) {
    switch (command) {
        // Power
        case 0x45:
            current_effect = (current_effect == FX_OFF) ? FX_SPIRAL : FX_OFF;
            Serial.println("IR: Toggle power");
            break;

        // Brightness
        case 0x46:
            brightness = min(255, brightness + 20);
            FastLED.setBrightness(brightness);
            Serial.printf("IR: Brightness up -> %d\n", brightness);
            break;
        case 0x15:
            brightness = max(10, brightness - 20);
            FastLED.setBrightness(brightness);
            Serial.printf("IR: Brightness down -> %d\n", brightness);
            break;

        // Effects
        case 0x44: current_effect = FX_SPIRAL;  Serial.println("IR: Spiral");  break;
        case 0x40: current_effect = FX_RAINBOW; Serial.println("IR: Rainbow"); break;
        case 0x43: current_effect = FX_TWINKLE; Serial.println("IR: Twinkle"); break;

        // Solid colors via number buttons
        case 0x07: solid_color = CRGB::Red;                  current_effect = FX_SOLID; break; // 1
        case 0x19: solid_color = CRGB::Green;                current_effect = FX_SOLID; break; // 2
        case 0x0D: solid_color = CRGB::Blue;                 current_effect = FX_SOLID; break; // 3
        case 0x16: solid_color = CRGB(255, 180, 80);         current_effect = FX_SOLID; break; // 4 warm white
        case 0x0C: solid_color = CRGB::White;                current_effect = FX_SOLID; break; // 5
        case 0x18: solid_color = CRGB::Purple;               current_effect = FX_SOLID; break; // 6
        case 0x5E: solid_color = CRGB(255, 100, 0);          current_effect = FX_SOLID; break; // 7 orange
        case 0x08: solid_color = CRGB(220, 20, 60);          current_effect = FX_SOLID; break; // 8 crimson
        case 0x1C: solid_color = CRGB::Cyan;                 current_effect = FX_SOLID; break; // 9

        default:
            Serial.printf("IR: Unknown command 0x%02X\n", command);
    }
}

// ── Web server ────────────────────────────────────────────────────────────────
void setup_server() {
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
            if (index == 0) upload_file = LittleFS.open(COORDS_PATH, "w");
            if (upload_file)  upload_file.write(data, len);
            if (final) {
                upload_file.close();
                coords_loaded = load_coords();
            }
        }
    );

    server.on("/status", HTTP_GET, [](AsyncWebServerRequest *req) {
        JsonDocument doc;
        doc["coords_loaded"]  = coords_loaded;
        doc["coord_count"]    = coord_count;
        doc["current_effect"] = (int)current_effect;
        doc["brightness"]     = brightness;
        doc["ip"]             = WiFi.localIP().toString();
        String out;
        serializeJson(doc, out);
        req->send(200, "application/json", out);
    });

    server.begin();
    Serial.println("Web server started");
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    if (!LittleFS.begin(true)) { Serial.println("LittleFS failed"); return; }
    coords_loaded = load_coords();

    FastLED.addLeds<WS2811, LED_PIN, RGB>(leds, NUM_LEDS);
    FastLED.setBrightness(brightness);
    FastLED.clear(true);

    IrReceiver.begin(IR_RX_PIN, ENABLE_LED_FEEDBACK);
    Serial.println("IR receiver ready");

    // Access point mode — no router needed
    WiFi.softAP("ChristmasTree", "12345678");
    Serial.printf("AP ready! Connect to 'ChristmasTree' (password: 12345678)\n");
    Serial.printf("Then open http://%s\n", WiFi.softAPIP().toString().c_str());
    // IP will always be 192.168.4.1

    setup_server();
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    // IR — check every loop, non-blocking
    if (IrReceiver.decode()) {
        if (!(IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT)) {
            handle_ir(IrReceiver.decodedIRData.command);
        }
        IrReceiver.resume();
    }

    // Animation
    switch (current_effect) {
        case FX_SPIRAL:  fx_spiral();  break;
        case FX_RAINBOW: fx_rainbow(); break;
        case FX_SOLID:   fx_solid();   break;
        case FX_TWINKLE: fx_twinkle(); break;
        case FX_OFF:     FastLED.clear(); break;
    }

    phase += 0.005f;
    if (phase > 1.0f) phase -= 1.0f;

    FastLED.show();
    delay(16);
}