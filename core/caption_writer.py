"""
Caption file writers: SRT, VTT, and plain TXT.
"""
import os
from pathlib import Path
from typing import List, Tuple

from utils.helpers import seconds_to_srt_time, seconds_to_vtt_time, stem


# Type alias: a transcription segment
Segment = Tuple[float, float, str]   # (start_sec, end_sec, text)


# ---------------------------------------------------------------------------
# SRT writer
# ---------------------------------------------------------------------------

def write_srt(segments: list[Segment], output_path: str) -> str:
    """Write segments to a SubRip (.srt) caption file."""
    lines = []
    for idx, (start, end, text) in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}")
        lines.append(text.strip())
        lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# ---------------------------------------------------------------------------
# VTT writer
# ---------------------------------------------------------------------------

def write_vtt(segments: list[Segment], output_path: str) -> str:
    """Write segments to a WebVTT (.vtt) caption file."""
    lines = ["WEBVTT", ""]

    for idx, (start, end, text) in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{seconds_to_vtt_time(start)} --> {seconds_to_vtt_time(end)}")
        lines.append(text.strip())
        lines.append("")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# ---------------------------------------------------------------------------
# TXT writer
# ---------------------------------------------------------------------------

def write_txt(segments: list[Segment], output_path: str) -> str:
    """Write a plain-text transcript (no timestamps)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for _, _, text in segments:
            f.write(text.strip() + "\n")

    return output_path


# ---------------------------------------------------------------------------
# Convenience: write all requested formats
# ---------------------------------------------------------------------------

def write_captions(
    segments: list[Segment],
    base_name: str,
    output_dir: str,
    formats: list[str],
) -> dict[str, str]:
    """
    Write caption files for all requested formats.

    Parameters
    ----------
    segments : list of (start, end, text)
    base_name : str
        Filename stem (no extension), e.g. 'interview_1.5x'
    output_dir : str
        Directory to write files into.
    formats : list of str
        Any combination of ['srt', 'vtt', 'txt'].

    Returns
    -------
    dict mapping format → absolute file path
    """
    results: dict[str, str] = {}
    writers = {
        "srt": write_srt,
        "vtt": write_vtt,
        "txt": write_txt,
    }

    for fmt in formats:
        fmt = fmt.lower()
        if fmt not in writers:
            continue
        out_path = os.path.join(output_dir, f"{base_name}.{fmt}")
        writers[fmt](segments, out_path)
        results[fmt] = out_path

    return results
