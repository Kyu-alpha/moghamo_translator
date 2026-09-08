"""
Moghamo Translator - Backend Server
------------------------------------
Receives a WAV recording from the ESP32, transcribes it (English side is
handled by Whisper), runs it through YOUR trained translation model, then
synthesizes speech for the result and hands back text + an audio URL.

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8000

Plug in your own model in translate_en_to_moghamo() / translate_moghamo_to_en().
"""

import io
import os
import uuid

import numpy as np
import soundfile as sf
import whisper
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from model_interface import translate_en_to_moghamo, translate_moghamo_to_en

app = FastAPI()

# Loaded once at startup. "base" is a good speed/accuracy tradeoff on CPU;
# bump to "small" or "medium" if you have a GPU.
whisper_model = whisper.load_model("base")

AUDIO_OUT_DIR = "generated_audio"
os.makedirs(AUDIO_OUT_DIR, exist_ok=True)


# Translation functions now live in model_interface.py - edit that file to
# wire in your trained model. Test it standalone with `python model_interface.py`.

# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------
def synthesize_speech(text: str, lang: str) -> str:
    """
    Returns a path to a generated WAV file.

    - English output: any off-the-shelf TTS works (pyttsx3 offline, or
      gTTS/edge-tts if you have internet access).
    - Moghamo output: no commercial TTS supports this language, so you'll
      likely need to fine-tune your own (e.g. Coqui TTS or VITS) using
      audio aligned to your Bible-text training data. Until that exists,
      you can return None here and the ESP32 will just show text with no
      audio playback for that direction — a reasonable phase-1 milestone.
    """
    filename = f"{uuid.uuid4()}.wav"
    out_path = os.path.join(AUDIO_OUT_DIR, filename)

    if lang == "en":
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        return out_path

    # lang == "mgo" (Moghamo) - no built-in engine available.
    raise NotImplementedError(
        "No Moghamo TTS yet. Train one, or return text-only for this direction."
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/translate")
async def translate(request: Request):
    direction = request.headers.get("X-Direction", "en2mgo")
    raw_bytes = await request.body()

    # Save the incoming WAV so Whisper can read it
    audio_np, sr = sf.read(io.BytesIO(raw_bytes))
    tmp_path = f"/tmp/{uuid.uuid4()}.wav"
    sf.write(tmp_path, audio_np, sr)

    stt_result = whisper_model.transcribe(tmp_path)
    source_text = stt_result["text"].strip()
    os.remove(tmp_path)

    try:
        if direction == "en2mgo":
            translated = translate_en_to_moghamo(source_text)
            out_lang = "mgo"
        else:
            translated = translate_moghamo_to_en(source_text)
            out_lang = "en"
    except NotImplementedError as e:
        return JSONResponse({"error": str(e), "source_text": source_text}, status_code=501)

    response = {"source_text": source_text, "text": translated, "audio_url": ""}

    try:
        audio_path = synthesize_speech(translated, out_lang)
        filename = os.path.basename(audio_path)
        host = request.url.hostname
        response["audio_url"] = f"http://{host}:8000/audio/{filename}"
    except NotImplementedError:
        pass  # text-only response is fine for now

    return JSONResponse(response)


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    return FileResponse(os.path.join(AUDIO_OUT_DIR, filename), media_type="audio/wav")
