/*
  Moghamo Translator - ESP32 Firmware
  ------------------------------------
  Flow:
    1. Hold record button -> capture ~5s of audio via I2S mic (INMP441)
    2. POST the audio as WAV to your translation server
    3. Server replies with JSON: {"source_text","text","audio_url"}
    4. Display translated text on the ST7789 LCD
    5. Stream the returned audio and play it via I2S (through MAX98357A amp -> speaker)

  Required libraries (Arduino Library Manager):
    - Adafruit GFX Library
    - Adafruit ST7789
  Board: ESP32 Dev Module (any ESP32-WROOM32 board)

  HARDWARE NOTE: You need an I2S amplifier (e.g. MAX98357A) between the ESP32
  and the speaker. The speaker in your cart cannot be driven directly by GPIO.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

// ---------------- WiFi / server ----------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL    = "http://YOUR_SERVER_IP:8000/translate";

// ---------------- Pins ----------------
#define BTN_RECORD   4     // hold to record
#define BTN_MODE     5     // tap to flip translation direction

#define TFT_CS       15
#define TFT_DC       2
#define TFT_RST      33    // pick a free GPIO, must differ from mic pins below

#define I2S_MIC_SCK  26    // INMP441 SCK
#define I2S_MIC_WS   25    // INMP441 WS/LRCL
#define I2S_MIC_SD   32    // INMP441 SD  (tie L/R pin on the mic to GND)

#define I2S_SPK_BCLK 27    // MAX98357A BCLK
#define I2S_SPK_LRC  14    // MAX98357A LRC
#define I2S_SPK_DIN  12    // MAX98357A DIN

Adafruit_ST7789 tft = Adafruit_ST7789(&SPI, TFT_CS, TFT_DC, TFT_RST);

bool englishToMoghamo = true;   // false = Moghamo -> English

#define SAMPLE_RATE     16000
#define RECORD_SECONDS  5
#define I2S_MIC_PORT    I2S_NUM_0
#define I2S_SPK_PORT    I2S_NUM_1

static int16_t audioBuffer[SAMPLE_RATE * RECORD_SECONDS];

// ---------------- Display helper ----------------
void showMessage(const String &msg, uint16_t color = ST77XX_WHITE) {
  tft.fillScreen(ST77XX_BLACK);
  tft.setCursor(0, 0);
  tft.setTextColor(color);
  tft.setTextWrap(true);
  tft.setTextSize(2);
  tft.println(msg);
}

// ---------------- I2S setup ----------------
void setupMicI2S() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,  // INMP441 sends 24-bit in a 32-bit frame
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };
  i2s_driver_install(I2S_MIC_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &pins);
}

void setupSpeakerI2S() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SPK_BCLK,
    .ws_io_num = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  i2s_driver_install(I2S_SPK_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_SPK_PORT, &pins);
}

// ---------------- Recording ----------------
void recordAudio() {
  showMessage("Listening...", ST77XX_YELLOW);
  size_t bytesRead = 0;
  int32_t rawSample;
  int totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  for (int i = 0; i < totalSamples; i++) {
    i2s_read(I2S_MIC_PORT, &rawSample, sizeof(rawSample), &bytesRead, portMAX_DELAY);
    // Data is left-justified in the 32-bit word; shift down to a 16-bit PCM sample.
    audioBuffer[i] = (int16_t)(rawSample >> 14);
  }
}

// Minimal 44-byte WAV header for mono 16-bit PCM
void writeWavHeader(uint8_t *header, uint32_t dataSize) {
  uint32_t fileSize   = dataSize + 36;
  uint32_t sr         = SAMPLE_RATE;
  uint32_t byteRate   = sr * 2;
  uint16_t blockAlign = 2, bps = 16, audioFmt = 1, numCh = 1;
  uint32_t fmtSize    = 16;

  memcpy(header,      "RIFF", 4);
  memcpy(header + 4,  &fileSize, 4);
  memcpy(header + 8,  "WAVEfmt ", 8);
  memcpy(header + 16, &fmtSize, 4);
  memcpy(header + 20, &audioFmt, 2);
  memcpy(header + 22, &numCh, 2);
  memcpy(header + 24, &sr, 4);
  memcpy(header + 28, &byteRate, 4);
  memcpy(header + 32, &blockAlign, 2);
  memcpy(header + 34, &bps, 2);
  memcpy(header + 36, "data", 4);
  memcpy(header + 40, &dataSize, 4);
}

// Very small, dependency-free JSON string field grabber.
// Good enough for a flat {"key":"value",...} response; swap for ArduinoJson if it grows.
String extractJsonField(const String &json, const String &key) {
  String needle = "\"" + key + "\":\"";
  int start = json.indexOf(needle);
  if (start == -1) return "";
  start += needle.length();
  int end = json.indexOf("\"", start);
  if (end == -1) return "";
  return json.substring(start, end);
}

void playAudioFromUrl(const String &url) {
  HTTPClient http;
  http.begin(url);
  int code = http.GET();
  if (code == 200) {
    WiFiClient *stream = http.getStreamPtr();
    uint8_t buf[512];
    stream->readBytes(buf, 44);  // skip WAV header
    size_t bytesWritten;
    while (http.connected() && stream->available()) {
      int len = stream->readBytes(buf, sizeof(buf));
      i2s_write(I2S_SPK_PORT, buf, len, &bytesWritten, portMAX_DELAY);
    }
  }
  http.end();
}

void sendAudioAndPlayResult() {
  showMessage("Translating...", ST77XX_CYAN);

  uint32_t dataSize = SAMPLE_RATE * RECORD_SECONDS * 2;
  uint8_t wavHeader[44];
  writeWavHeader(wavHeader, dataSize);

  uint8_t *payload = (uint8_t *)malloc(44 + dataSize);
  memcpy(payload, wavHeader, 44);
  memcpy(payload + 44, audioBuffer, dataSize);

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "audio/wav");
  http.addHeader("X-Direction", englishToMoghamo ? "en2mgo" : "mgo2en");

  int httpCode = http.POST(payload, 44 + dataSize);
  free(payload);

  if (httpCode == 200) {
    String response = http.getString();
    String translatedText = extractJsonField(response, "text");
    String audioUrl       = extractJsonField(response, "audio_url");

    showMessage(translatedText.length() ? translatedText : "(no text returned)", ST77XX_GREEN);
    if (audioUrl.length() > 5) playAudioFromUrl(audioUrl);
  } else {
    showMessage("Server error: " + String(httpCode), ST77XX_RED);
  }
  http.end();
}

// ---------------- Setup / loop ----------------
void setup() {
  Serial.begin(115200);
  pinMode(BTN_RECORD, INPUT_PULLUP);
  pinMode(BTN_MODE, INPUT_PULLUP);

  tft.init(240, 320);
  tft.setRotation(1);
  showMessage("Connecting WiFi...");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
  }

  setupMicI2S();
  setupSpeakerI2S();
  showMessage("Ready.\nHold button to speak.\nTap MODE to flip direction.", ST77XX_WHITE);
}

void loop() {
  if (digitalRead(BTN_MODE) == LOW) {
    englishToMoghamo = !englishToMoghamo;
    showMessage(englishToMoghamo ? "Mode: EN -> Moghamo" : "Mode: Moghamo -> EN");
    delay(400);  // simple debounce
  }

  if (digitalRead(BTN_RECORD) == LOW) {
    recordAudio();
    sendAudioAndPlayResult();
    delay(500);
  }
}
