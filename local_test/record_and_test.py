"""
Full pipeline smoke test - runs entirely on your laptop.
------------------------------------------------------------
Records a few seconds from your LAPTOP's built-in mic, sends it to your
translation server, prints the translated text, and plays back any
returned audio through your laptop speakers.

No Pico W, external mic, amp, or LCD required - this is how you validate
your STT -> translation model -> TTS pipeline works before any hardware
shows up.

Install:
    pip install sounddevice soundfile requests simpleaudio

Run the server in another terminal first:
    cd server && uvicorn app:app --host 0.0.0.0 --port 8000

Then run this:
    python record_and_test.py
"""

import io

import requests
import sounddevice as sd
import soundfile as sf

try:
    import winsound  # built into Python on Windows - no install needed
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False  # not on Windows - falls back to simpleaudio below

SERVER_URL = "http://localhost:8000/translate"
SAMPLE_RATE = 16000
DURATION_SECONDS = 5
DIRECTION = "en2mgo"  # switch to "mgo2en" to test the reverse direction


def record_clip(path="test_clip.wav"):
    print(f"Recording {DURATION_SECONDS}s - speak now...")
    audio = sd.rec(
        int(DURATION_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    sf.write(path, audio, SAMPLE_RATE)
    print(f"Saved recording to {path}")
    return path


def send_to_server(path):
    with open(path, "rb") as f:
        wav_bytes = f.read()

    resp = requests.post(
        SERVER_URL,
        data=wav_bytes,
        headers={"Content-Type": "audio/wav", "X-Direction": DIRECTION},
    )
    print("Status:", resp.status_code)

    if resp.status_code != 200:
        print("Server response:", resp.text)
        return None

    data = resp.json()
    print("Heard (source text):", data.get("source_text"))
    print("Translated:", data.get("text"))
    return data


def play_result(data):
    if not data:
        return
    audio_url = data.get("audio_url")
    if not audio_url:
        print("(No audio returned - expected if TTS isn't wired up for this direction yet)")
        return

    r = requests.get(audio_url)

    if HAS_WINSOUND:
        # winsound needs an actual file on disk, not bytes in memory
        temp_path = "temp_playback.wav"
        with open(temp_path, "wb") as f:
            f.write(r.content)
        winsound.PlaySound(temp_path, winsound.SND_FILENAME)
    else:
        import simpleaudio as sa  # only imported here if actually needed
        wave_obj = sa.WaveObject.from_wave_file(io.BytesIO(r.content))
        play_obj = wave_obj.play()
        play_obj.wait_done()


if __name__ == "__main__":
    clip_path = record_clip()
    result = send_to_server(clip_path)
    play_result(result)
