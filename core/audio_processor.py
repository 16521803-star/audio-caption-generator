"""
Audio speed adjustment using ffmpeg's atempo filter.
Pitch is preserved (time-stretching, not resampling).
"""
import os
import subprocess
import shutil
from pathlib import Path

from utils.helpers import get_temp_dir, stem


# atempo only accepts values in [0.5, 2.0]; chain filters for values outside.
_ATEMPO_MIN = 0.5
_ATEMPO_MAX = 2.0


def _build_atempo_chain(speed: float) -> str:
    """
    Build a comma-separated chain of atempo filters for arbitrary speed values.
    e.g. speed=4.0 → 'atempo=2.0,atempo=2.0'
         speed=0.25 → 'atempo=0.5,atempo=0.5'
    """
    filters = []
    remaining = speed
    if remaining > 1.0:
        while remaining > _ATEMPO_MAX:
            filters.append(f"atempo={_ATEMPO_MAX}")
            remaining /= _ATEMPO_MAX
        filters.append(f"atempo={remaining:.4f}")
    else:
        while remaining < _ATEMPO_MIN:
            filters.append(f"atempo={_ATEMPO_MIN}")
            remaining /= _ATEMPO_MIN
        filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def adjust_speed(
    input_path: str,
    speed: float,
    output_dir: str | None = None,
) -> str:
    """
    Apply speed adjustment to an audio file using ffmpeg atempo filter.

    Parameters
    ----------
    input_path : str
        Path to the source audio file (mp3, m4a, wav, ogg, flac …).
    speed : float
        Playback speed multiplier. 1.0 = original, 1.5 = 50% faster, 0.75 = 25% slower.
    output_dir : str | None
        Directory to write the output file. Defaults to system temp dir.

    Returns
    -------
    str
        Path to the speed-adjusted audio file (always .mp3).

    Raises
    ------
    RuntimeError
        If ffmpeg is not found or processing fails.
    FileNotFoundError
        If the input file does not exist.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    if speed == 1.0:
        return input_path

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is not installed or not found in PATH.\n"
            "Please install ffmpeg: https://ffmpeg.org/download.html\n"
            "  Windows: winget install ffmpeg"
        )

    out_dir = output_dir or get_temp_dir()
    out_filename = f"{stem(input_path)}_speed{speed:.2f}x.mp3"
    output_path = os.path.join(out_dir, out_filename)

    atempo_chain = _build_atempo_chain(speed)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-filter:a", atempo_chain,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        output_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    return output_path


def get_audio_duration(input_path: str) -> float:
    """
    Return the duration of an audio file in seconds using ffprobe.
    Returns -1.0 if unable to determine.
    """
    if not shutil.which("ffprobe"):
        return -1.0

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return -1.0
