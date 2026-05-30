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
from core.transcriber import transcribe, AVAILABLE_MODELS, LANGUAGE_MAP, TRANSLATION_TARGETS
from core.caption_writer import write_captions
from utils.helpers import stem, get_temp_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LANGUAGES = list(LANGUAGE_MAP.keys())
TRANSLATION_OPTIONS = list(TRANSLATION_TARGETS.keys())

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
    translate_label: str,
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
    translate_to = TRANSLATION_TARGETS.get(translate_label)
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
            translate_to=translate_to,
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
    if translate_to:
        base_name += f"_{translate_to}"

    out_paths = write_captions(
        segments=segments,
        base_name=base_name,
        output_dir=str(OUTPUT_DIR),
        formats=selected_formats,
    )
    log(f"📝 Written: {', '.join(out_paths.keys()).upper()}")

    # ── Step 4: Build outputs ─────────────────────────────────────────────────
    preview_lines = []
    for i, (start, end, text) in enumerate(segments[:30], start=1):
        preview_lines.append(f"[{_fmt_ts(start)}]  {text.strip()}")
    if len(segments) > 30:
        preview_lines.append(f"\n… and {len(segments) - 30} more segments")
    caption_preview = "\n".join(preview_lines)

    duration_display = f"{info['duration']:.1f}s" if info["duration"] > 0 else "—"
    translation_label = translate_label if translate_to else "None"
    stats = (
        f"**🌍 Language detected:** {info['language'].upper() if info['language'] else '?'} "
        f"({info['language_probability']}% confidence)\n\n"
        f"**⏱️ Audio duration:** {duration_display}\n\n"
        f"**📝 Segments:** {len(segments)}\n\n"
        f"**⚡ Speed applied:** {speed:.2f}×\n\n"
        f"**🤖 Model used:** `{model_size}`\n\n"
        f"**🌐 Translation:** {translation_label}"
    )

    progress(1.0, desc="Done!")

    return caption_preview, stats, "\n".join(log_lines), list(out_paths.values()), segments



# ---------------------------------------------------------------------------
# Caption editor — re-export from edited preview text
# ---------------------------------------------------------------------------

def export_edited(
    edited_text: str,
    raw_segments: list | None,
    audio_file: str | None,
) -> tuple[list, str]:
    """
    Re-export caption files as SRT using the user-edited preview text.

    The edited_text format is:  [MM:SS]  caption text\n...
    Timestamps are taken from raw_segments (original); only the text is replaced.
    """
    import time
    t_start = time.time()

    if not edited_text or not edited_text.strip():
        raise gr.Error("Caption editor is empty. Generate captions first.")
    if not raw_segments:
        raise gr.Error("No transcription data found. Please run Generate Captions first.")

    # Parse edited text lines: [MM:SS]  some text
    import re
    lines = [line for line in edited_text.strip().splitlines() if line.strip()]
    # Filter out the "... and N more segments" trailer
    lines = [l for l in lines if not l.startswith("\u2026") and not l.startswith("...")]

    edited_texts: list[str] = []
    for line in lines:
        m = re.match(r"^\[\d{2}:\d{2}\]\s*(.*)$", line)
        if m:
            edited_texts.append(m.group(1).strip())
        else:
            # Line without timestamp prefix — append to last entry
            if edited_texts:
                edited_texts[-1] += " " + line.strip()

    # Match edited texts back to original segments (by index)
    # If user added/removed lines we fall back gracefully
    edited_segments: list[tuple[float, float, str]] = []
    for i, (start, end, _orig_text) in enumerate(raw_segments):
        text = edited_texts[i] if i < len(edited_texts) else _orig_text
        edited_segments.append((start, end, text))

    # Name the file based on the audio name if available
    if audio_file:
        base_name = f"{stem(audio_file)}_edited"
    else:
        base_name = "edited_captions"

    # Sanitize base_name to avoid any path/character issues
    base_name = "".join(c for c in base_name if c.isalnum() or c in ("-", "_", ".")).strip()
    if not base_name:
        base_name = "edited_captions"

    t_parse = time.time()
    print(f"[Profiling] Parsing and segment matching took {t_parse - t_start:.4f} seconds")

    out_paths = write_captions(
        segments=edited_segments,
        base_name=base_name,
        output_dir=str(OUTPUT_DIR),
        formats=["srt"],
    )
    
    out_path = out_paths.get("srt")
    t_write = time.time()
    print(f"[Profiling] Writing captions to disk took {t_write - t_parse:.4f} seconds")

    status_msg = f"\u2705 Exported SRT with your edits!"

    # Attempt to copy directly to user's system Downloads folder for instant access
    if out_path and os.path.exists(out_path):
        try:
            downloads_dir = Path.home() / "Downloads"
            if downloads_dir.exists():
                dest_path = downloads_dir / f"{base_name}.srt"
                shutil.copy2(out_path, dest_path)
                status_msg = (
                    f"\u2705 Exported SRT with your edits!\n\n"
                    f"📂 **Saved directly to your Downloads folder:**\n"
                    f"`{dest_path}`"
                )
                print(f"[Profiling] Copied file to Downloads folder at {dest_path}")
        except Exception as e:
            print(f"[Warning] Failed to copy to Downloads: {e}")

    t_total = time.time() - t_start
    print(f"[Profiling] Total export_edited execution took {t_total:.4f} seconds")

    return list(out_paths.values()), status_msg


# ---------------------------------------------------------------------------
# ChatGPT prompt preparation
# ---------------------------------------------------------------------------

CHATGPT_PROMPT_TEMPLATE = """Bạn là chuyên gia hiệu đính phụ đề tiếng Việt. Hãy sửa các lỗi nhận dạng giọng nói trong phụ đề dưới đây.

Quy tắc bắt buộc:
- GIỮ NGUYÊN toàn bộ cấu trúc dòng và timestamp [MM:SS]
- GIỮ NGUYÊN số lượng dòng, không thêm, không xóa dòng nào
- Chỉ sửa các từ bị nhận dạng sai ý nghĩa (ví dụ: "đang trái" → "đang cháy")
- Giữ nguyên những từ đã chính xác, không viết lại tùy tiện
- Không tóm tắt, không thêm giải thích, chỉ trả về toàn bộ phụ đề đã sửa

Phụ đề cần sửa:
{captions}"""


def prepare_chatgpt_prompt(raw_segments: list | None) -> str:
    """
    Build a ChatGPT correction prompt from ALL raw segments.
    Formats every segment as [MM:SS]  text so ChatGPT sees the full caption.
    """
    if not raw_segments:
        raise gr.Error("No transcription data found. Generate captions first.")

    lines = []
    for start, end, text in raw_segments:
        m = int(start // 60)
        s = int(start % 60)
        lines.append(f"[{m:02d}:{s:02d}]  {text.strip()}")

    all_captions = "\n".join(lines)
    return CHATGPT_PROMPT_TEMPLATE.format(captions=all_captions)


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
                            label="Audio Language",
                            info="Language spoken in the audio",
                        )

                    translation_dropdown = gr.Dropdown(
                        choices=TRANSLATION_OPTIONS,
                        value="None (Keep Original)",
                        label="🌐 Translate Captions To",
                        info="Translate the output captions to a different language (uses Google Translate)",
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
                    with gr.Tab("📋 Caption Preview & Editor"):
                        caption_output = gr.Textbox(
                            label="Edit captions directly here, then click \u2018Export Edited\u2019 below",
                            placeholder="Captions will appear here after processing. You can edit any line directly!",
                            lines=18,
                            max_lines=28,
                            interactive=True,
                        )
                        gr.Markdown(
                            "_✏️ **Tip:** Edit any text in the box above to fix transcription errors, "
                            "then click **Export Edited Captions** to re-download with your corrections._",
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
                    label="Caption files (SRT / VTT / TXT)",
                    file_count="multiple",
                )

                export_edit_btn = gr.Button(
                    "✏️  Export Edited Captions (SRT)",
                    variant="secondary",
                )
                export_edit_status = gr.Markdown("")

                gr.HTML('<div style="margin-top:1rem;border-top:1px solid rgba(124,58,237,.25);padding-top:1rem">')
                gr.Markdown("### 🤖 Fix with ChatGPT")
                gr.Markdown(
                    "_Click **Prepare Prompt** to generate a ready-to-paste ChatGPT prompt "
                    "that will correct Vietnamese transcription errors while keeping all timestamps intact. "
                    "After ChatGPT replies, paste the corrected text back into the Caption Editor above and click **Export Edited Captions**._"
                )
                chatgpt_btn = gr.Button(
                    "🤖  Prepare ChatGPT Prompt",
                    variant="secondary",
                    elem_id="chatgpt-btn",
                )
                chatgpt_prompt_box = gr.Textbox(
                    label="📋 ChatGPT Prompt (copy everything below and paste into ChatGPT)",
                    placeholder="Click 'Prepare ChatGPT Prompt' to generate...",
                    lines=12,
                    max_lines=20,
                    interactive=False,
                    elem_id="chatgpt-prompt-box",
                )
                gr.HTML(
                    '<button id="copy-chatgpt-btn"'
                    ' onclick="'
                    'const ta=document.querySelector(\'#chatgpt-prompt-box textarea\');'
                    'if(!ta||!ta.value){alert(\'Click Prepare ChatGPT Prompt first!\');return;}'
                    'const btn=this;'
                    'function doOpen(){'
                    'btn.textContent=\'Opening ChatGPT...\';'
                    'btn.style.background=\'linear-gradient(135deg,#059669,#10b981)\';'
                    'window.open(\'https://chatgpt.com/\',\'_blank\');'
                    'setTimeout(()=>{'
                    'btn.textContent=\'Open ChatGPT with Prompt\';'
                    'btn.style.background=\'\';'
                    '},3000);}'
                    'navigator.clipboard.writeText(ta.value).then(()=>doOpen()).catch(()=>{'
                    'ta.select();document.execCommand(\'copy\');doOpen();'
                    '});'
                    '"'
                    ' style="margin-top:0.5rem;padding:0.75rem 1.2rem;'
                    'background:linear-gradient(135deg,#7C3AED,#06B6D4);'
                    'color:#fff;border:none;border-radius:8px;'
                    'font-weight:700;font-size:1rem;cursor:pointer;'
                    'transition:opacity .2s;width:100%;letter-spacing:0.01em;"'
                    ' onmouseover="this.style.opacity=\'.85\'"'
                    ' onmouseout="this.style.opacity=\'1\'"'
                    ">Open ChatGPT with Prompt</button>"
                    '<p style="margin:0.4rem 0 0;color:#94A3B8;font-size:0.8rem;text-align:center;">'
                    'Prompt is copied to clipboard &mdash; just press <strong>Ctrl+V</strong> (or Cmd+V) in ChatGPT to paste.</p>'
                )
                gr.HTML('</div>')

        # ── Footer ─────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="app-footer">
            Powered by <strong>faster-whisper</strong> &nbsp;·&nbsp;
            <strong>ffmpeg</strong> &nbsp;·&nbsp;
            <strong>Gradio</strong> &nbsp;·&nbsp;
            <strong>Python 3.12</strong>
        </div>
        """)

        # ── State for raw segments (needed by editor) ────────────────────────
        raw_segments_state = gr.State(value=None)

        # ── Event wiring ────────────────────────────────────────────────────
        run_btn.click(
            fn=process_audio,
            inputs=[
                audio_input, speed_slider, model_dropdown, language_dropdown,
                translation_dropdown,
                srt_cb, vtt_cb, txt_cb,
            ],
            outputs=[
                caption_output, stats_output, log_output,
                download_files, raw_segments_state,
            ],
            api_name="generate_captions",
        )

        export_edit_btn.click(
            fn=export_edited,
            inputs=[caption_output, raw_segments_state, audio_input],
            outputs=[download_files, export_edit_status],
        )

        chatgpt_btn.click(
            fn=prepare_chatgpt_prompt,
            inputs=[raw_segments_state],
            outputs=[chatgpt_prompt_box],
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
