"""
Pico W - WiFi + server connectivity test
------------------------------------------
Runs on the Pico W ALONE - no mic, amp, or display needed yet.
Confirms your WiFi credentials work and your server is reachable,
by sending a 1-second silent WAV and printing whatever comes back.

Setup:
  1. Flash MicroPython onto the Pico W (from micropython.org) using Thonny.
  2. In Thonny, with the Pico connected: Tools > Manage Packages > install
     "micropython-urequests" (or run `import mip; mip.install("urequests")`
     from the Pico's REPL while it has WiFi - chicken/egg, so easiest is
     via Thonny's package manager over USB).
  3. Fill in SSID / PASSWORD / SERVER_URL below.
  4. Run this file on the Pico (green play button in Thonny).

Note: the Pico W uses the RP2040 chip, which is a different architecture
from the ESP32 in a lot of "Arduino tutorials" you'll find online - this
script is MicroPython, not Arduino C++. Your eventual mic/speaker/display
code will use `machine.I2S` and `machine.SPI` on this board instead of the
`driver/i2s.h` calls from the ESP32 version.
"""

import network
import time
import urequests

SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"
SERVER_URL = "http://YOUR_SERVER_IP:8000/translate"  # your laptop's LAN IP + port 8000


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    print("Connecting to WiFi", end="")
    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        print(".", end="")
        time.sleep(1)
        timeout -= 1

    if wlan.isconnected():
        print("\nConnected:", wlan.ifconfig())
        return True
    print("\nFailed to connect - check SSID/password and signal strength.")
    return False


def build_silent_wav(seconds=1, sample_rate=16000):
    """Builds a valid, silent mono 16-bit WAV in memory - a stand-in for a
    real mic recording so you can test the network path today."""
    num_samples = sample_rate * seconds
    data_size = num_samples * 2

    header = bytearray(44)
    header[0:4] = b"RIFF"
    header[4:8] = (data_size + 36).to_bytes(4, "little")
    header[8:12] = b"WAVE"
    header[12:16] = b"fmt "
    header[16:20] = (16).to_bytes(4, "little")
    header[20:22] = (1).to_bytes(2, "little")
    header[22:24] = (1).to_bytes(2, "little")
    header[24:28] = sample_rate.to_bytes(4, "little")
    header[28:32] = (sample_rate * 2).to_bytes(4, "little")
    header[32:34] = (2).to_bytes(2, "little")
    header[34:36] = (16).to_bytes(2, "little")
    header[36:40] = b"data"
    header[40:44] = data_size.to_bytes(4, "little")

    silence = bytearray(data_size)  # zeroed out = silence
    return bytes(header) + bytes(silence)


def send_test_request():
    dummy_wav = build_silent_wav(seconds=1)
    try:
        r = urequests.post(
            SERVER_URL,
            data=dummy_wav,
            headers={"Content-Type": "audio/wav", "X-Direction": "en2mgo"},
        )
        print("Status:", r.status_code)
        print("Body:", r.text)
        r.close()
    except Exception as e:
        print("Request failed:", e)
        print("Check that your server is running and SERVER_URL matches its LAN IP.")


if __name__ == "__main__":
    if connect_wifi():
        send_test_request()
