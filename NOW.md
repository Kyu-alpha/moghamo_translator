# What You Can Build Right Now (Pico W + case only, nothing else)

You don't need the mic, amp, or LCD to make real progress. Do these in order:

## 1. Wire in your trained model (no hardware, no server, no network)
Open `server/model_interface.py` and replace the `raise NotImplementedError`
lines with your actual model's inference call. Run it directly:
```
python server/model_interface.py
```
This is the single most valuable thing you can do right now - it forces you
to confirm your model loads and runs outside of whatever notebook you
trained it in.

## 2. Bring up the full server pipeline (still no external hardware)
```
cd server
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```
Whisper (STT) and, once you wire it in, your model, are now running as a
real HTTP service.

## 3. Test the full loop with your laptop's own mic/speakers
```
pip install sounddevice soundfile requests simpleaudio
python local_test/record_and_test.py
```
This records you speaking, sends it through STT -> your model -> (optional)
TTS, prints the translation, and plays back any returned audio - the entire
pipeline your final device will run, minus the enclosure.

## 4. Confirm the Pico W can talk to your server
Flash MicroPython onto the Pico W, fill in your WiFi + server IP in
`pico/wifi_test.py`, and run it from Thonny. It sends a silent placeholder
WAV over WiFi to your server and prints the response - proving the network
leg of the architecture works before any mic is wired up.

## What's still blocked on hardware
- Real on-device recording (needs the I2S mic)
- On-device playback (needs the I2S amp + speaker)
- On-device display of translated text (needs the SPI LCD)
- Button-triggered recording (needs the tactile switches wired to a GPIO)

Everything above this line, though, is genuine, testable engineering work
you can screen-record for your application before a single extra part
arrives.

## Note on Pico W vs. ESP32
The original firmware sketch (`firmware/firmware.ino`) was written for an
ESP32 in Arduino C++. The Pico W (RP2040 chip) is a different architecture -
once your peripherals arrive, the on-device code will be MicroPython using
`machine.I2S` and `machine.SPI` instead, following the same pattern as
`pico/wifi_test.py`. Say the word when you have the parts and I'll write
the full mic/display/speaker version for the Pico W specifically.
