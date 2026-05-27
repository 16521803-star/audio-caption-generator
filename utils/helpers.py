"""
Utility helpers: timestamp formatting and file management.
"""
import os
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Timestamp formatters
# ---------------------------------------------------------------------------

def seconds_to_srt_time(seconds: float) -> str:
    """Convert a float number of seconds to SRT timestamp format HH:MM:SS,ms."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    # Guard against rounding millis to 1000
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def seconds_to_vtt_time(seconds: float) -> str:
    """Convert a float number of seconds to WebVTT timestamp format HH:MM:SS.ms."""
    srt = seconds_to_srt_time(seconds)
    # VTT uses '.' instead of ',' as the millisecond separator
    return srt.replace(",", ".")


# ---------------------------------------------------------------------------
# File utilities
# ---------------------------------------------------------------------------

def get_temp_dir() -> str:
    """Return a persistent temp directory inside the working directory."""
    tmp = Path(tempfile.gettempdir()) / "audio_caption_gen"
    tmp.mkdir(parents=True, exist_ok=True)
    return str(tmp)


def stem(filepath: str) -> str:
    """Return the file stem (name without extension)."""
    return Path(filepath).stem


def ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist and return the path."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def cleanup_files(*paths: str) -> None:
    """Silently delete files from disk (used to clean up temp files)."""
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
