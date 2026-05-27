#!/bin/bash

# Exit on error
set -e

echo
echo "============================================================"
echo "  Audio Caption Generator — macOS/Linux Setup"
echo "============================================================"
echo

# ── Check Python Version ───────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH."
    echo "        Please install Python 3.10+ using Homebrew:"
    echo "            brew install python"
    echo "        Or download it from https://www.python.org/downloads/"
    exit 1
fi

# Verify Python version >= 3.10
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if [ $? -ne 0 ]; then
    PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "[ERROR] Python 3.10+ is required (found version $PYTHON_VER)."
    echo "        Please upgrade Python using Homebrew:"
    echo "            brew install python"
    echo "        Or download the latest installer from python.org."
    exit 1
fi

echo "[OK] Found $(python3 --version)"

# ── Check ffmpeg ───────────────────────────────────────────────────────────
if ! command -v ffmpeg &> /dev/null; then
    echo
    echo "[WARNING] ffmpeg is NOT installed or not in PATH."
    echo "          Speed adjustment will NOT work without ffmpeg."
    echo
    echo "          Please install it on macOS using Homebrew:"
    echo "              brew install ffmpeg"
    echo "          Or on Debian/Ubuntu:"
    echo "              sudo apt-get install ffmpeg"
    echo
    read -p "Press Enter to continue setup anyway, or Ctrl+C to abort... "
else
    echo "[OK] Found ffmpeg: $(ffmpeg -version | head -n 1)"
fi

# ── Create virtual environment ─────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo
    echo "[SETUP] Creating Python virtual environment in .venv..."
    python3 -m venv .venv
    echo "[OK] Virtual environment created."
else
    echo "[OK] Virtual environment already exists."
fi

# ── Upgrade pip & Install dependencies ─────────────────────────────────────
echo
echo "[SETUP] Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip -q

echo
echo "[SETUP] Installing Python dependencies (this may take a few minutes)..."
.venv/bin/python -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo
    echo "[ERROR] Dependency installation failed."
    exit 1
fi

echo
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo
echo "  To run the app:"
echo "    1. Activate the virtual environment:"
echo "          source .venv/bin/activate"
echo "    2. Start the app:"
echo "          python app.py"
echo "    3. Open your browser at:"
echo "          http://127.0.0.1:7860"
echo
echo "  Or just run:  ./run.sh"
echo

# ── Create run.sh ──────────────────────────────────────────────────────────
if [ ! -f "run.sh" ]; then
    cat << 'EOF' > run.sh
#!/bin/bash
source .venv/bin/activate
python app.py
EOF
    chmod +x run.sh
    echo "[OK] Created run.sh for easy startup."
fi

read -p "Would you like to launch the app now? (y/n): " launch_now
if [[ "$launch_now" =~ ^[Yy]$ ]]; then
    echo "[SETUP] Launching the app..."
    source .venv/bin/activate
    python app.py
fi
