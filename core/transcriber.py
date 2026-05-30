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

# Translation target options — maps display label to Google Translate language code
TRANSLATION_TARGETS = {
    "None (Keep Original)": None,
    "→ Vietnamese": "vi",
    "→ English": "en",
    "→ Spanish": "es",
    "→ French": "fr",
    "→ German": "de",
    "→ Japanese": "ja",
    "→ Korean": "ko",
    "→ Chinese (Simplified)": "zh-CN",
    "→ Portuguese": "pt",
    "→ Italian": "it",
    "→ Russian": "ru",
    "→ Arabic": "ar",
    "→ Hindi": "hi",
    "→ Indonesian": "id",
    "→ Thai": "th",
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
# Translation
# ---------------------------------------------------------------------------

def translate_segments(
    segments: list[tuple[float, float, str]],
    target_lang: str,
    progress_callback: Callable | None = None,
) -> list[tuple[float, float, str]]:
    """
    Translate the text of each segment to target_lang using GoogleTranslator.

    Segments are batched into chunks to minimise API calls while staying
    under the per-request character limit (~4500 chars).

    Parameters
    ----------
    segments : list of (start_sec, end_sec, text)
    target_lang : str
        Google Translate language code, e.g. 'vi', 'en', 'zh-CN'.
    progress_callback : callable | None

    Returns
    -------
    list of (start_sec, end_sec, translated_text)
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        if progress_callback:
            progress_callback("⚠️ deep-translator not installed — skipping translation.")
        return segments

    if progress_callback:
        progress_callback(f"🌐 Translating {len(segments)} segments to '{target_lang}'…")

    translator = GoogleTranslator(source="auto", target=target_lang)
    translated: list[tuple[float, float, str]] = []

    # -- Chunk segments so each batch stays under 4500 chars ----------------
    CHUNK_LIMIT = 4000
    chunks: list[list[int]] = []   # list of lists of segment indices
    current_chunk: list[int] = []
    current_len = 0

    for i, (_, _, text) in enumerate(segments):
        t = text.strip()
        if current_len + len(t) > CHUNK_LIMIT and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [i]
            current_len = len(t)
        else:
            current_chunk.append(i)
            current_len += len(t)
    if current_chunk:
        chunks.append(current_chunk)

    # -- Translate each chunk -----------------------------------------------
    result_texts: dict[int, str] = {}
    for chunk_indices in chunks:
        texts = [segments[i][2].strip() for i in chunk_indices]
        try:
            translated_batch = translator.translate_batch(texts)
            if len(translated_batch) == len(texts):
                for idx, trans_text in zip(chunk_indices, translated_batch):
                    result_texts[idx] = trans_text or segments[idx][2]
            else:
                # Length mismatch — fall back to one-by-one
                for idx, orig_text in zip(chunk_indices, texts):
                    try:
                        result_texts[idx] = translator.translate(orig_text) or orig_text
                    except Exception:
                        result_texts[idx] = segments[idx][2]
        except Exception as e:
            if progress_callback:
                progress_callback(f"⚠️ Translation chunk failed ({e}) — keeping original for this batch.")
            for idx in chunk_indices:
                result_texts[idx] = segments[idx][2]

    # -- Reconstruct segment list -------------------------------------------
    translated = [
        (start, end, result_texts.get(i, text))
        for i, (start, end, text) in enumerate(segments)
    ]

    if progress_callback:
        progress_callback(f"✅ Translation complete ({len(translated)} segments → '{target_lang}')")

    return translated


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(
    audio_path: str,
    model_size: str = "base",
    language: str | None = None,
    beam_size: int = 5,
    vad_filter: bool = True,
    translate_to: str | None = None,
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
        ISO 639-1 language code for the *input* audio, or None for auto-detect.
    beam_size : int
        Beam search width. Higher = more accurate but slower.
    vad_filter : bool
        Use Voice Activity Detection to skip silent sections.
    translate_to : str | None
        If set, translate output captions to this language code (e.g. 'vi').
        Uses deep-translator (Google Translate). None = no translation.
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

    # -- Optional translation -----------------------------------------------
    if translate_to:
        segments = translate_segments(segments, translate_to, progress_callback)

    return segments, info_dict
