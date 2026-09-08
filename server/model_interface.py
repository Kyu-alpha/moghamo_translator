"""
Standalone test harness for your trained Moghamo translation model.
------------------------------------------------------------------------
Run this file directly to sanity-check translations before wiring the
model into the server. No server, no network, no hardware needed - just
your model files sitting in the local ./model folder.

    python model_interface.py

Expected folder layout (server/model/):
    config.json
    generation_config.json
    tokenizer.json
    tokenizer_config.json
    model.safetensors      <- renamed from model-002.safetensors
"""

from pathlib import Path

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODEL_DIR = Path(__file__).parent / "model"

# Loaded lazily so importing this file doesn't immediately load a 2GB+ model.
_tokenizer = None
_model = None


def _load_model():
    global _tokenizer, _model
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
        _model.eval()


def translate_en_to_moghamo(text: str) -> str:
    _load_model()
    inputs = _tokenizer(text, return_tensors="pt")
    output_ids = _model.generate(**inputs, max_new_tokens=128)
    return _tokenizer.decode(output_ids[0], skip_special_tokens=True)


def translate_moghamo_to_en(text: str) -> str:
    # You mentioned training English -> Moghamo specifically. If you only
    # have one direction trained, leave this raising until you train (or
    # find) a reverse-direction model - the server already handles that
    # gracefully by returning a clear error instead of crashing.
    raise NotImplementedError("No Moghamo -> English model trained yet.")


if __name__ == "__main__":
    test_sentences = [
        "God created the heavens and the earth.",
        "I love my family.",
        "Where is the market?",
    ]
    for sentence in test_sentences:
        print(f"EN:  {sentence}")
        try:
            print(f"MGO: {translate_en_to_moghamo(sentence)}\n")
        except NotImplementedError as e:
            print(f"({e})")
            break
