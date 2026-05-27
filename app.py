"""
Audio Caption Generator — Main Gradio Application
==================================================
Run:  python app.py
Then open http://127.0.0.1:7860 in your browser.
"""

import os
import sys
import shutil
from pathlib import Path

import gradio as gr

# ---------------------------------------------------------------------------
# Ensure project root is on the Python path when run from any directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from core.audio_processor import adjust_speed, get_audio_duration
from core.transcriber import transcribe, AVAILABLE_MODELS, LANGUAGE_MAP
from core.caption_writer import write_captions
from utils.helpers import stem, get_temp_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LANGUAGES = list(LANGUAGE_MAP.keys())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_ts(seconds: float) -> str:
    """Short timestamp for preview: MM:SS."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def process_audio(
    audio_file,
    speed: float,
    model_size: str,
    language_label: str,
    export_srt: bool,
    export_vtt: bool,
    export_txt: bool,
    progress=gr.Progress(track_tqdm=True),
):
    """
    Full pipeline:
      1. Validate inputs
      2. Adjust audio speed  (ffmpeg atempo — pitch preserved)
      3. Transcribe with faster-whisper
      4. Write SRT / VTT / TXT caption files
      5. Return results to the UI
    """
    log_lines: list[str] = []

    def log(msg: str):
        log_lines.append(msg)

    # ── Validate ──────────────────────────────────────────────────────────────
    if audio_file is None:
        raise gr.Error("Please upload an audio file first.")

    selected_formats = [
        fmt for fmt, enabled in [("srt", export_srt), ("vtt", export_vtt), ("txt", export_txt)]
        if enabled
    ]
    if not selected_formats:
        raise gr.Error("Please select at least one output format (SRT / VTT / TXT).")

    language_code = LANGUAGE_MAP.get(language_label)
    input_path: str = audio_file

    # ── Step 1: Speed adjustment ──────────────────────────────────────────────
    progress(0.05, desc="Adjusting audio speed…")
    tmp_audio_path = None

    if abs(speed - 1.0) < 0.01:
        audio_for_transcription = input_path
        log("⏩ Speed: 1.0× — using original audio (no processing needed)")
    else:
        log(f"⏩ Adjusting speed to {speed:.2f}× (ffmpeg atempo)…")
        try:
            tmp_audio_path = adjust_speed(input_path, speed, output_dir=get_temp_dir())
            audio_for_transcription = tmp_audio_path
            log("✅ Speed-adjusted audio ready")
        except RuntimeError as e:
            # ffmpeg not found or processing failure — surface clearly
            raise gr.Error(str(e))
        except Exception as e:
            raise gr.Error(f"Speed adjustment failed: {e}")

    # ── Step 2: Transcription ─────────────────────────────────────────────────
    progress(0.20, desc=f"Loading Whisper '{model_size}' model…")

    try:
        segments, info = transcribe(
            audio_path=audio_for_transcription,
            model_size=model_size,
            language=language_code,
            beam_size=5,
            vad_filter=True,
            progress_callback=log,
        )
    except Exception as e:
        raise gr.Error(f"Transcription failed: {e}")

    if not segments:
        raise gr.Error(
            "No speech detected in the audio. "
            "Try a different model or check that the file contains speech."
        )

    progress(0.85, desc="Writing caption files…")

    # ── Step 3: Write captions ────────────────────────────────────────────────
    base_name = stem(input_path)
    if abs(speed - 1.0) >= 0.01:
        base_name += f"_{speed:.2f}x"

    out_paths = write_captions(
        segments=segments,
        base_name=base_name,
        output_dir=str(OUTPUT_DIR),
        formats=selected_formats,
    )
    log(f"📝 Written: {', '.join(out_paths.keys()).upper()}")

    # ── Step 4: Save speed-adjusted audio ────────────────────────────────────
    modified_audio_out = None
    if tmp_audio_path and os.path.exists(tmp_audio_path):
        dest = str(OUTPUT_DIR / Path(tmp_audio_path).name)
        shutil.copy2(tmp_audio_path, dest)
        modified_audio_out = dest
        log("🎵 Speed-adjusted audio saved to output/")

    # ── Step 5: Build outputs ─────────────────────────────────────────────────
    preview_lines = []
    for i, (start, end, text) in enumerate(segments[:30], start=1):
        preview_lines.append(f"[{_fmt_ts(start)}]  {text.strip()}")
    if len(segments) > 30:
        preview_lines.append(f"\n… and {len(segments) - 30} more segments")
    caption_preview = "\n".join(preview_lines)

    duration_display = f"{info['duration']:.1f}s" if info["duration"] > 0 else "—"
    stats = (
        f"**🌍 Language detected:** {info['language'].upper() if info['language'] else '?'} "
        f"({info['language_probability']}% confidence)\n\n"
        f"**⏱️ Audio duration:** {duration_display}\n\n"
        f"**📝 Segments:** {len(segments)}\n\n"
        f"**⚡ Speed applied:** {speed:.2f}×\n\n"
        f"**🤖 Model used:** `{model_size}`"
    )

    download_files = list(out_paths.values())
    if modified_audio_out:
        download_files.append(modified_audio_out)

    progress(1.0, desc="Done!")

    return caption_preview, stats, "\n".join(log_lines), download_files, modified_audio_out


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --primary: #7C3AED;
    --primary-light: #A78BFA;
    --accent: #06B6D4;
    --accent-light: #67E8F9;
    --bg: #0F0F1A;
    --bg-card: #1A1A2E;
    --bg-input: #16213E;
    --border: rgba(124, 58, 237, 0.35);
    --text: #E2E8F0;
    --text-muted: #94A3B8;
    --radius: 14px;
}

body, .gradio-container {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', system-ui, sans-serif !important;
}

/* ── Header ── */
.app-header {
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
    background: linear-gradient(135deg, rgba(124,58,237,0.15), rgba(6,182,212,0.10));
    border-radius: 20px;
    border: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.app-title {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(90deg, #A78BFA, #67E8F9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.5px;
}
.app-subtitle {
    color: var(--text-muted);
    font-size: 1rem;
    margin: 0;
    line-height: 1.6;
}

/* ── Cards ── */
.gr-group {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 1rem !important;
}

/* ── Generate button ── */
#generate-btn {
    background: linear-gradient(135deg, #7C3AED, #06B6D4) !important;
    border: none !important;
    color: #fff !important;
    font-weight: 700 !important;
    font-size: 1.1rem !important;
    border-radius: 12px !important;
    padding: 0.85rem !important;
    transition: transform .2s, box-shadow .2s !important;
    box-shadow: 0 4px 24px rgba(124,58,237,.35) !important;
    width: 100% !important;
}
#generate-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(124,58,237,.5) !important;
}

/* ── Inputs ── */
input[type=range] { accent-color: #A78BFA !important; }
textarea, input[type=text], select {
    background: var(--bg-input) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    color: var(--text-muted);
    font-size: .82rem;
    padding: 1.2rem;
    margin-top: 0.5rem;
    border-top: 1px solid var(--border);
}
"""


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="🎙️ Audio Caption Generator",
    ) as demo:

        # ── Header ─────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="app-header">
            <h1 class="app-title">🎙️ Audio Caption Generator</h1>
            <p class="app-subtitle">
                Convert MP3 · M4A · WAV audio to perfectly-synced SRT, VTT &amp; TXT captions<br>
                Supports speed adjustment — captions automatically follow the audio timing<br>
                <strong style="color:#A78BFA">100% local · no API key · no data leaves your machine 🔒</strong>
            </p>
        </div>
        """)

        # ── Main layout ─────────────────────────────────────────────────────
        with gr.Row(equal_height=False):

            # Left column — controls
            with gr.Column(scale=4, min_width=320):

                with gr.Group():
                    gr.Markdown("### 📂 Input Audio")
                    audio_input = gr.Audio(
                        label="Drag & drop or click to upload (MP3, M4A, WAV, OGG, FLAC)",
                        type="filepath",
                    )

                with gr.Group():
                    gr.Markdown("### ⚙️ Processing Options")

                    speed_slider = gr.Slider(
                        minimum=0.5,
                        maximum=2.0,
                        step=0.05,
                        value=1.0,
                        label="Playback Speed",
                        info="1.0 = original  ·  < 1.0 = slower  ·  > 1.0 = faster",
                    )

                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            choices=AVAILABLE_MODELS,
                            value="base",
                            label="Whisper Model",
                            info="Larger = more accurate, slower",
                        )
                        language_dropdown = gr.Dropdown(
                            choices=LANGUAGES,
                            value="Auto-detect",
                            label="Language",
                            info="Auto-detect or pick manually",
                        )

                with gr.Group():
                    gr.Markdown("### 📄 Output Formats")
                    with gr.Row():
                        srt_cb = gr.Checkbox(value=True,  label="⬜ SRT")
                        vtt_cb = gr.Checkbox(value=True,  label="⬜ VTT")
                        txt_cb = gr.Checkbox(value=False, label="⬜ TXT")

                run_btn = gr.Button(
                    "✨  Generate Captions",
                    variant="primary",
                    elem_id="generate-btn",
                )

                with gr.Accordion("💡 Model size guide", open=False):
                    gr.Markdown("""
| Model | Speed | Accuracy | RAM needed |
|-------|-------|----------|-----------|
| `tiny` | ⚡⚡ Fastest | ★★☆☆☆ | ~1 GB |
| `base` | ⚡ Fast | ★★★☆☆ | ~1 GB |
| `small` | 🔄 Moderate | ★★★★☆ | ~2 GB |
| `medium` | 🐢 Slow | ★★★★☆ | ~5 GB |
| `large-v3` | 🐢🐢 Slowest | ★★★★★ | ~10 GB |

> **Tip:** `base` or `small` is ideal for most use-cases.
> Have an NVIDIA GPU? `medium` or `large-v3` gives best accuracy.
                    """)

            # Right column — results
            with gr.Column(scale=6, min_width=400):

                with gr.Tabs():
                    with gr.Tab("📋 Caption Preview"):
                        caption_output = gr.Textbox(
                            label="First 30 segments",
                            placeholder="Captions will appear here after processing…",
                            lines=18,
                            max_lines=28,
                        )

                    with gr.Tab("📊 Stats"):
                        stats_output = gr.Markdown(
                            "*Run the tool to see transcription statistics.*"
                        )

                    with gr.Tab("🔍 Processing Log"):
                        log_output = gr.Textbox(
                            label="Step-by-step log",
                            placeholder="Processing log will appear here…",
                            lines=18,
                            max_lines=28,
                        )

                gr.Markdown("### 📥 Downloads")
                download_files = gr.Files(
                    label="Caption files + speed-adjusted audio (if applicable)",
                    file_count="multiple",
                )

                audio_preview = gr.Audio(
                    label="🎵 Speed-adjusted audio preview",
                    type="filepath",
                )

        # ── Footer ─────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="app-footer">
            Powered by <strong>faster-whisper</strong> &nbsp;·&nbsp;
            <strong>ffmpeg</strong> &nbsp;·&nbsp;
            <strong>Gradio</strong> &nbsp;·&nbsp;
            <strong>Python 3.12</strong>
        </div>
        """)

        # ── Event wiring ────────────────────────────────────────────────────
        run_btn.click(
            fn=process_audio,
            inputs=[
                audio_input, speed_slider, model_dropdown, language_dropdown,
                srt_cb, vtt_cb, txt_cb,
            ],
            outputs=[
                caption_output, stats_output, log_output,
                download_files, audio_preview,
            ],
            api_name="generate_captions",
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        inbrowser=True,
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue="violet",
            secondary_hue="cyan",
            neutral_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
        ),
    )
