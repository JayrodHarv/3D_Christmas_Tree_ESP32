#pragma once
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include "config.h"

void web_init();   // starts AP + web server