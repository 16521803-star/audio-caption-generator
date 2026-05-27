"""
Speech-to-text transcription using faster-whisper.
Returns a list of (start_sec, end_sec, text) segments.
"""
from __future__ import annotations

import os
from typing import Callable

from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

LANGUAGE_MAP = {
    "Auto-detect": None,
    "English": "en",
    "Vietnamese": "vi",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese": "zh",
    "Portuguese": "pt",
    "Italian": "it",
    "Russian": "ru",
    "Arabic": "ar",
    "Hindi": "hi",
    "Dutch": "nl",
    "Turkish": "tr",
    "Polish": "pl",
    "Swedish": "sv",
    "Indonesian": "id",
    "Thai": "th",
}

# Cache the loaded model to avoid re-loading on every call
_model_cache: dict[str, WhisperModel] = {}


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def _detect_device() -> str:
    """Return 'cuda' if an NVIDIA GPU is available, else 'cpu'."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        pass
    try:
        import ctranslate2
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------

def load_model(model_size: str, device: str = "auto") -> WhisperModel:
    """
    Load (or return cached) a faster-whisper model.

    Parameters
    ----------
    model_size : str
        One of AVAILABLE_MODELS.
    device : str
        'auto' → use CUDA if available, else CPU.
        'cuda' → force GPU.
        'cpu'  → force CPU.
    """
    if device == "auto":
        device = _detect_device()

    compute_type = "float16" if device == "cuda" else "int8"

    cache_key = f"{model_size}_{device}"
    if cache_key not in _model_cache:
        _model_cache[cache_key] = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    return _model_cache[cache_key]


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(
    audio_path: str,
    model_size: str = "base",
    language: str | None = None,
    beam_size: int = 5,
    vad_filter: bool = True,
    progress_callback: Callable | None = None,
) -> tuple[list[tuple[float, float, str]], dict]:
    """
    Transcribe an audio file and return caption segments.

    Parameters
    ----------
    audio_path : str
        Path to the audio file.
    model_size : str
        Whisper model size (tiny / base / small / medium / large-v3).
    language : str | None
        ISO 639-1 language code, or None for auto-detect.
    beam_size : int
        Beam search width. Higher = more accurate but slower.
    vad_filter : bool
        Use Voice Activity Detection to skip silent sections.
    progress_callback : callable | None
        Optional function(message: str) for progress reporting.

    Returns
    -------
    segments : list of (start_sec, end_sec, text)
    info     : dict with 'language', 'language_probability', 'duration'
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if progress_callback:
        progress_callback(f"⚙️ Loading Whisper model '{model_size}'…")

    model = load_model(model_size)

    if progress_callback:
        progress_callback("🎙️ Transcribing audio… (this may take a moment)")

    raw_segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    # Materialise the generator
    segments: list[tuple[float, float, str]] = [
        (seg.start, seg.end, seg.text) for seg in raw_segments
    ]

    info_dict = {
        "language": info.language,
        "language_probability": round(info.language_probability * 100, 1),
        "duration": round(info.duration, 2),
    }

    if progress_callback:
        lang_label = info.language.upper() if info.language else "?"
        progress_callback(
            f"✅ Transcription complete — detected language: {lang_label} "
            f"({info_dict['language_probability']}% confidence), "
            f"{len(segments)} segments"
        )

    return segments, info_dict
