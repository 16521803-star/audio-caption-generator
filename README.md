# 🎙️ Audio Caption Generator

Convert speech in **MP3, M4A, WAV, OGG, FLAC** audio files to perfectly-synced captions — **100% locally, no API key required**.

Key features:
- 🎚️ **Adjustable playback speed** (0.5× – 2.0×) with automatic caption timing sync
- 🤖 **AI transcription** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper)
- 📄 **Multiple output formats**: SRT · VTT · TXT
- 🌍 **Auto language detection** (+ 20 languages selectable)
- 🖥️ **Beautiful web UI** — runs in your browser, powered by Gradio

---

## 🚀 How to Setup and Run

The automated scripts will check your system for Python and ffmpeg, set up the virtual environment, install dependencies, and launch the web UI.

### 🪟 Windows (Simplest Option)
Double-click the **`audio_caption_setup.bat`** file. 

*(Or run `audio_caption_setup.bat` in CMD/PowerShell)*

---

### 🍎 macOS / 🐧 Linux (Simplest Option)
Open your Terminal, navigate to the folder, and run:
```bash
chmod +x audio_caption_setup.sh && ./audio_caption_setup.sh
```

---

### Relaunching the App (Subsequent Runs)
Once setup is complete, you can launch the app instantly:
* **Windows:** Double-click **`run.bat`**
* **macOS / Linux:** Run **`./run.sh`**

*The application will automatically open in your web browser at **[http://127.0.0.1:7860](http://127.0.0.1:7860)**.*

---

## Usage

1. **Upload** your audio file (drag & drop or click the upload area)
2. **Set speed** using the slider (1.0× = original, 1.5× = 50% faster)
3. **Choose Whisper model** — `base` is a good default; `large-v3` for best accuracy
4. **Select language** — leave as "Auto-detect" or pick your language
5. **Select output formats** — SRT, VTT, and/or TXT
6. Click **✨ Generate Captions**
7. Download your caption files and (optionally) the speed-adjusted audio

---

## How Speed + Caption Sync Works

The magic is in the pipeline order:

```
Original audio → Speed adjustment (ffmpeg atempo) → Transcription → Captions
```

By transcribing the **already-speed-adjusted audio**, the caption timestamps are automatically in sync with the modified audio. No post-processing math needed.

---

## Whisper Model Guide

| Model | Speed | Accuracy | RAM needed |
|-------|-------|----------|-----------|
| `tiny` | ⚡ Fastest | ★★☆☆☆ | ~1 GB |
| `base` | ⚡ Fast | ★★★☆☆ | ~1 GB |
| `small` | 🔄 Moderate | ★★★★☆ | ~2 GB |
| `medium` | 🐢 Slow | ★★★★☆ | ~5 GB |
| `large-v3` | 🐢 Slowest | ★★★★★ | ~10 GB |

> **GPU acceleration**: If you have an NVIDIA GPU, install CUDA 12 + cuDNN 9 for dramatically faster transcription. The app auto-detects CUDA.

---

## Output Files

All output files are saved in the `output/` directory.

| Format | Description | Use case |
|--------|-------------|----------|
| `.srt` | SubRip subtitles | VLC, Premiere Pro, most video players |
| `.vtt` | WebVTT subtitles | HTML5 video, YouTube, web players |
| `.txt` | Plain transcript | Copy-paste, LLMs, search |

---

## Project Structure

```
audio-caption-generator/
├── app.py                   # 🚀 Main Gradio application
├── core/
│   ├── audio_processor.py   # 🎚️ ffmpeg speed adjustment
│   ├── transcriber.py       # 🤖 faster-whisper transcription
│   └── caption_writer.py    # 📄 SRT / VTT / TXT export
├── utils/
│   └── helpers.py           # 🔧 Timestamp formatters, file utils
├── output/                  # 📁 Generated caption files
├── requirements.txt
├── audio_caption_setup.bat  # 🖱️ Windows one-click setup
├── run.bat                  # 🖱️ Windows quick-launch (auto-created)
├── audio_caption_setup.sh   # 🍎 macOS / Linux automated setup
└── run.sh                   # 🍎 macOS / Linux quick-launch (auto-created)
```

---

## Troubleshooting

**"ffmpeg not found"**
→ Install ffmpeg and ensure it's in your system PATH. Run `ffmpeg -version` in a terminal to verify.

**Transcription is slow**
→ Use a smaller model (`tiny` or `base`), or use a machine with an NVIDIA GPU.

**Poor accuracy**
→ Try a larger model (`medium` or `large-v3`), or specify the exact language instead of "Auto-detect".

**App won't start**
→ Re-run `audio_caption_setup.bat` (Windows) or `./audio_caption_setup.sh` (macOS / Linux) to make sure all packages installed correctly.

---

## License

MIT — Free for personal and commercial use.
