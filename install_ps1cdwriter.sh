#!/bin/bash
set -e

echo "======================================"
echo " PS1 CUE Burner - Dependencies Setup "
echo "======================================"

# -------- Check Python 3 --------
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python3 is required but not installed. Aborting."
    exit 1
fi

echo "Python3 found: $(python3 --version)"

# -------- Install cdrdao (apt-based distros) --------
if command -v apt >/dev/null 2>&1; then
    echo "Detected apt-based system. Installing cdrdao..."
    sudo apt update -y
    sudo apt install -y cdrdao
else
    echo "apt package manager not found."
    echo "Please install 'cdrdao' manually with your distro's package manager."
fi

# -------- Ensure pip3 exists --------
if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 not found. Installing python3-pip (apt)..."
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y python3-pip
    else
        echo "Cannot install pip3 automatically (no apt)."
        echo "Please install pip3 manually, then re-run this script."
        exit 1
    fi
fi

echo "pip3 found: $(pip3 --version)"

# -------- Install PyQt6 for the current user --------
echo "Installing PyQt6 (user mode, no virtualenv)..."
pip3 install --user --upgrade PyQt6

echo "Verifying PyQt6 import..."
python3 - << 'EOF'
try:
    import PyQt6
    print("PyQt6 import OK.")
except Exception as e:
    print("PyQt6 import FAILED:", e)
    raise SystemExit(1)
EOF

echo ""
echo "======================================"
echo " All dependencies installed successfully."
echo "======================================"
echo ""
echo "To run the application, use:"
echo ""
echo "  python3 ps1_cdrdao_gui.py"
echo ""
echo "Make sure ps1_cdrdao_gui.py is in the current directory when you run it."
