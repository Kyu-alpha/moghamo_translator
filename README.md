# Moghamo Translator - Hardware Build

## What this is
A pocket device: press a button, speak English (or Moghamo), and it translates
and speaks/displays the result, using your own trained model.

## Architecture
```
[Mic (INMP441)] --I2S--> [ESP32] --WiFi/HTTP--> [Server: Whisper STT -> your model -> TTS]
                             |                                |
                        [ST7789 LCD]  <---------- text/audio result ----------
                             |
                  [MAX98357A amp] --I2S--> [Speaker]
```

The ESP32 can't run your trained NLP model on-device — it just captures audio,
ships it to a small server (your laptop, a Pi, or a cloud box), and renders
whatever comes back. This is the standard pattern for "AI hardware" projects
at this scale, and it's a perfectly legitimate maker-portfolio architecture —
you're not obligated to run inference on the microcontroller itself.

## Two things missing from your cart
1. **An ESP32 dev board.** The mic module lists ESP32 compatibility, so I
   assumed that as the target MCU — you'll need to add e.g. an
   ESP32-WROOM-32 DevKit.
2. **An I2S audio amplifier**, e.g. a **MAX98357A** breakout (~$5-8). The
   3W speaker you ordered can't be driven directly from ESP32 GPIO pins.

## Wiring (as coded in firmware.ino)
| Component        | ESP32 Pin |
|-------------------|-----------|
| INMP441 SCK        | 26 |
| INMP441 WS         | 25 |
| INMP441 SD         | 32 |
| INMP441 L/R        | GND (selects left channel) |
| MAX98357A BCLK     | 27 |
| MAX98357A LRC      | 14 |
| MAX98357A DIN      | 12 |
| ST7789 CS          | 15 |
| ST7789 DC          | 2  |
| ST7789 RST         | 33 |
| Record button      | 4 (to GND, uses internal pull-up) |
| Mode button        | 5 (to GND, uses internal pull-up) |

Double check against your specific board's pinout before wiring — some GPIOs
(6-11) are reserved for flash and shouldn't be used.

## Setup steps
1. **Server first** (do this on your laptop to develop/test before touching hardware):
   ```
   cd server
   pip install -r requirements.txt
   ```
   Open `app.py` and wire `translate_en_to_moghamo()` / `translate_moghamo_to_en()`
   to however you're currently running your trained model (Hugging Face model,
   a pickled sklearn/PyTorch model, whatever you built). Then:
   ```
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   Test it with curl before involving the ESP32 at all:
   ```
   curl -X POST http://localhost:8000/translate \
        -H "Content-Type: audio/wav" -H "X-Direction: en2mgo" \
        --data-binary @some_test_clip.wav
   ```

2. **Firmware**: open `firmware/firmware.ino` in Arduino IDE, install the
   Adafruit GFX and Adafruit ST7789 libraries, set your WiFi credentials and
   `SERVER_URL` (your laptop's LAN IP + port 8000), then flash to the ESP32.

3. **Moghamo TTS is the open problem.** No commercial TTS engine speaks
   Moghamo. For your MIT application this is actually a great "future work"
   talking point: phase 1 ships text-only output for the Moghamo direction,
   phase 2 fine-tunes a TTS model (e.g. Coqui/VITS) on audio you record
   yourself reading your Bible-derived training text aloud.

## Suggested demo script for your application video
1. Press record, speak an English sentence.
2. Screen shows "Translating...", then the Moghamo text appears.
3. If you've built TTS: speaker plays it back in Moghamo.
4. Flip mode, speak Moghamo, show the reverse direction.
